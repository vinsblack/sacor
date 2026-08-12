"""Orchestrazione end-to-end su un singolo file (ADR-048): triage ->
segmentazione -> tier0 -> tier1 (opt-in) -> invarianti -> confidenza ->
gate. Primo punto d'ingresso pubblico single-file — prima esistevano solo
script batch guidati da oracle (eval/run.py, scripts/bakeoff.py),
inutilizzabili da chi non ha un corpus con risposte già note. Usato dalla
CLI (`sacor extract`).

Tier1 e' opt-in esplicito (usa_tier1=False di default, mai automatico —
chiamata reale a pagamento): quando attivo completa SOLO i campi che il
tier0 ha lasciato None, mai quelli gia' risolti (ADR-045/049: opt-in
esplicito e' la regola per ogni chiamata che costa soldi veri). Modello
fisso claude-opus-5 (ADR-049: l'arbitrato misurato sul reale non migliora
l'accuratezza rispetto a opus da solo, non vale il doppio costo)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pdfplumber

from sacor.extractor import TierZeroExtractor
from sacor.invariants import Violazione, campi_coinvolti, valuta_tutte
from sacor.providers.base import ModelProvider
from sacor.providers.errors import ErroreProvider
from sacor.providers.prompt import costruisci_prompt
from sacor.render import renderizza_pagine_istanza
from sacor.schema import Invariante, Schema
from sacor.segmentation import segmenta
from sacor.triage import analizza, normalizza_testo

EsitoGate = Literal["pass", "warning", "reject"]
Confidenza = Literal["alta", "media", "bassa"]

# ADR-049: unico modello usato per tier1, l'arbitrato haiku/opus misurato
# sul reale non ha migliorato l'accuratezza rispetto a opus da solo.
MODELLO_TIER1 = "claude-opus-5"


@dataclass(frozen=True)
class RisultatoEstrazione:
    istanza_id: str
    valori: dict[str, str | None]
    violazioni: tuple[Violazione, ...]
    esito: EsitoGate
    motivo: str | None  # perche' reject — None se pass/warning
    # ADR-048 punto 2 — "ogni campo esce con un livello di confidenza"
    # (north star, mai stato vero finora: solo la segmentazione ne aveva
    # una). None se il campo non ha valore (nulla da giudicare).
    confidenza: dict[str, Confidenza | None]
    costo_tier1_usd: float = 0.0
    tier1_errore: str | None = None  # chiamata tier1 fallita — non esplode


def _calcola_esito(
    schema: Schema, valori: dict[str, str | None], violazioni: tuple[Violazione, ...]
) -> tuple[EsitoGate, str | None]:
    mancanti = [c.nome for c in schema.campi if c.obbligatorio and valori.get(c.nome) is None]
    if mancanti:
        return "reject", f"campi obbligatori mancanti: {', '.join(mancanti)}"

    violazioni_gravi = [v for v in violazioni if v.severita == "reject"]
    if violazioni_gravi:
        return "reject", f"invariante violata: {violazioni_gravi[0].messaggio}"

    if violazioni:
        return "warning", None
    return "pass", None


def _calcola_confidenza(
    schema: Schema,
    valori: Mapping[str, str | None],
    violazioni: tuple[Violazione, ...],
    origine: Mapping[str, str],  # nome campo -> "tier0" | "tier1"
) -> dict[str, Confidenza | None]:
    """Un campo senza violazioni e' 'alta' se deterministico (tier0, regex
    dichiarata nello schema — T3.2 non indovina mai), 'media' se da tier1
    (AI, 60.9%/campo misurato su reale, ADR-044). Coinvolto in un'invariante
    VIOLATA -> 'bassa' a prescindere dall'origine: il disaccordo tra campi
    e' il segnale (stesso principio di ADR-045), non solo l'origine del
    singolo valore."""
    by_id: dict[str, Invariante] = {inv.id: inv for inv in schema.invarianti}
    campi_sospetti: set[str] = set()
    for v in violazioni:
        campi_sospetti.update(campi_coinvolti(by_id[v.invariante_id]))

    confidenza: dict[str, Confidenza | None] = {}
    for nome, valore in valori.items():
        if valore is None:
            confidenza[nome] = None
        elif nome in campi_sospetti:
            confidenza[nome] = "bassa"
        elif origine.get(nome) == "tier1":
            confidenza[nome] = "media"
        else:
            confidenza[nome] = "alta"
    return confidenza


def _provider_tier1_default() -> ModelProvider:
    # Import pigro (stesso pattern di scripts/bakeoff.py::_provider_per_
    # modello): l'SDK Anthropic e la chiave API non servono a chi usa solo
    # tier0 (default), che e' la maggioranza dei casi.
    from sacor.providers.anthropic import AnthropicProvider

    return AnthropicProvider(MODELLO_TIER1)


def estrai_file(
    file: Path,
    schema: Schema,
    *,
    usa_tier1: bool = False,
    provider: ModelProvider | None = None,
) -> tuple[RisultatoEstrazione, ...]:
    """Un risultato per istanza documentale rilevata nel file (ADR-014-bis:
    un PDF può contenere più documenti). `provider` e' iniettabile (test);
    se None e usa_tier1=True, usa AnthropicProvider(claude-opus-5)."""
    triage_result = analizza(file)
    with pdfplumber.open(file) as documento:
        testi = [normalizza_testo(p) for p in documento.pages]
    esito_segmentazione = segmenta(file, triage_result.pagine, testi, schema.segmentazione)

    provider_tier1: ModelProvider | None = None
    errore_provider_tier1: str | None = None
    if usa_tier1:
        try:
            provider_tier1 = provider or _provider_tier1_default()
        except ErroreProvider as exc:
            errore_provider_tier1 = str(exc)

    tier0 = TierZeroExtractor()
    risultati = []
    for istanza in esito_segmentazione.istanze:
        valori = tier0.extract(istanza, schema)
        origine = {nome: "tier0" for nome, v in valori.items() if v is not None}
        costo_tier1 = 0.0
        tier1_errore: str | None = None

        campi_mancanti = tuple(c for c in schema.campi if valori.get(c.nome) is None)
        if usa_tier1 and campi_mancanti:
            if provider_tier1 is None:
                tier1_errore = errore_provider_tier1
            else:
                try:
                    pagine = [png for png, _l, _a in renderizza_pagine_istanza(istanza)]
                    prompt = costruisci_prompt(campi_mancanti)
                    risposta = provider_tier1.estrai(pagine, prompt, campi_mancanti)
                    costo_tier1 = risposta.costo_stimato
                    for campo in campi_mancanti:
                        valore = risposta.valori.get(campo.nome)
                        if valore is not None:
                            valori[campo.nome] = valore
                            origine[campo.nome] = "tier1"
                except ErroreProvider as exc:
                    tier1_errore = str(exc)

        violazioni = valuta_tutte(schema, valori)
        esito, motivo = _calcola_esito(schema, valori, violazioni)
        confidenza = _calcola_confidenza(schema, valori, violazioni, origine)
        risultati.append(
            RisultatoEstrazione(
                istanza_id=istanza.id,
                valori=valori,
                violazioni=violazioni,
                esito=esito,
                motivo=motivo,
                confidenza=confidenza,
                costo_tier1_usd=costo_tier1,
                tier1_errore=tier1_errore,
            )
        )
    return tuple(risultati)
