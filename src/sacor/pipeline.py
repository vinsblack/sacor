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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pdfplumber

from sacor.evidence import (
    Derivazione,
    EsitoInvariante,
    Evidenza,
    EvidenzaDocumento,
    PaginaEvidenza,
    RiepilogoInvarianti,
    Riparazione,
    RisultatoCampo,
    confidenza_da_evidenza,
)
from sacor.extractor import DiagnosticaCampo, TierZeroExtractor
from sacor.gate import gate
from sacor.invariants import (
    EsitoInvarianteValutazione,
    ProvenienzaDerivazione,
    Violazione,
    campi_coinvolti,
    deriva_mancanti_con_provenienza,
    valuta_tutte_con_esito,
)
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
    # ADR-056/058, Commit 2: la stessa storia gia' calcolata sopra
    # (origine/repair/derivazione/invarianti), non piu' buttata via.
    # 'confidenza' resta calcolata come prima (Commit 3 la sostituira'
    # con confidenza_da_evidenza) — questi due campi sono additivi,
    # nessun consumatore esistente li legge ancora.
    evidenze: dict[str, Evidenza] = field(default_factory=dict)
    evidenza_documento: EvidenzaDocumento | None = None


def _confidenza_da_evidenze(
    evidenze: Mapping[str, Evidenza], valori: Mapping[str, str | None]
) -> dict[str, Confidenza | None]:
    """ADR-059: la pipeline non 'calcola' piu' la confidenza, la LEGGE da
    Evidenza gia' assemblata — confidenza_da_evidenza (sacor.evidence,
    Commit 1) e' l'unica regola, dichiarata una sola volta. Sostituisce
    _calcola_confidenza (rimossa, Commit 3): stesso comportamento,
    dimostrato bit-identico da test_confidenza_e_funzione_di_evidenza_su_
    un_ventaglio_di_documenti prima di questo switch."""
    return {nome: confidenza_da_evidenza(valori.get(nome), ev) for nome, ev in evidenze.items()}


def _provider_tier1_default() -> ModelProvider:
    # Import pigro (stesso pattern di scripts/bakeoff.py::_provider_per_
    # modello): l'SDK Anthropic e la chiave API non servono a chi usa solo
    # tier0 (default), che e' la maggioranza dei casi.
    from sacor.providers.anthropic import AnthropicProvider

    return AnthropicProvider(MODELLO_TIER1)


def _deriva_e_traccia_origine(
    schema: Schema,
    valori: dict[str, str | None],
    origine: dict[str, str],
    provenienza_derivazione: list[ProvenienzaDerivazione],
) -> dict[str, str | None]:
    # ADR-051: un campo mancante puo' essere aritmeticamente derivabile
    # dagli altri due di una stessa invariante (es. periodo_a da
    # periodo_da+giorni) — non e' un indovinare, e' la stessa formula
    # gia' usata per validare, applicata al contrario quando l'incognita
    # e' una sola. Chiamata PRIMA di tier1 (risparmia la chiamata se
    # basta l'aritmetica) e di nuovo dopo (tier1 puo' sbloccare una
    # derivazione prima non possibile). `origine` mutato in place, non
    # e' un closure sul loop in estrai_file (B023).
    #
    # ADR-058: provenienza_derivazione accumula anche COME (quale
    # invariante, quali campi in input) — Evidence.derivazione ne ha
    # bisogno, deriva_mancanti() da solo non lo esponeva.
    derivati, provenienza = deriva_mancanti_con_provenienza(schema, valori)
    for nome, valore in derivati.items():
        if valore is not None and valori.get(nome) is None:
            origine[nome] = "derivato"
    provenienza_derivazione.extend(provenienza)
    return derivati


def _costruisci_evidenze(
    schema: Schema,
    valori: Mapping[str, str | None],
    origine: Mapping[str, str],
    diagnostica: Mapping[str, DiagnosticaCampo],
    provenienza_derivazione: Sequence[ProvenienzaDerivazione],
    valutazioni: Sequence[EsitoInvarianteValutazione],
    usa_tier1: bool,
    tier1_errore: str | None,
) -> dict[str, Evidenza]:
    """ADR-056/058: assembla l'Evidenza per campo dai segnali gia'
    calcolati dai layer sopra — non decide nulla di nuovo, descrive
    soltanto (ADR-058: Evidenza e' un contenitore, non un decisore)."""
    by_id: dict[str, Invariante] = {inv.id: inv for inv in schema.invarianti}
    dettaglio_per_campo: dict[str, list[EsitoInvariante]] = {c.nome: [] for c in schema.campi}
    for v in valutazioni:
        if not v.valutata:
            continue
        esito_txt: Literal["pass", "fail"] = "fail" if v.violazione is not None else "pass"
        messaggio = v.violazione.messaggio if v.violazione is not None else None
        voce = EsitoInvariante(
            id=v.invariante_id, esito=esito_txt, severita=v.severita, messaggio=messaggio
        )
        for nome_campo in campi_coinvolti(by_id[v.invariante_id]):
            dettaglio_per_campo.setdefault(nome_campo, []).append(voce)

    evidenze: dict[str, Evidenza] = {}
    for campo in schema.campi:
        nome = campo.nome
        valore = valori.get(nome)
        origine_campo = origine.get(nome)

        # ADR-057: stato risponde a "perche'" solo quando non c'e' un
        # valore da giustificare — la stessa domanda non ha senso se il
        # valore c'e'.
        stato: str | None = None
        if valore is None:
            if not usa_tier1:
                stato = "tier1_non_tentato"
            elif tier1_errore is not None:
                stato = "tier1_fallito"
            else:
                stato = "non_trovato"

        repair: tuple[Riparazione, ...] = ()
        if origine_campo == "tier0":
            diag = diagnostica.get(nome)
            if diag is not None and diag.grezzo is not None and diag.grezzo != diag.valore:
                repair = (Riparazione(tipo="ripara", da=diag.grezzo, a=diag.valore),)

        derivazione = tuple(
            Derivazione(tipo=p.tipo, invariante_id=p.invariante_id, da_campi=p.da_campi)
            for p in provenienza_derivazione
            if p.campo == nome
        )

        dettaglio = tuple(dettaglio_per_campo.get(nome, ()))
        invarianti_riepilogo = RiepilogoInvarianti(
            passate=sum(1 for d in dettaglio if d.esito == "pass"),
            fallite=sum(1 for d in dettaglio if d.esito == "fail"),
            dettaglio=dettaglio,
        )

        evidenze[nome] = Evidenza(
            origine=origine_campo,
            stato=stato,
            repair=repair,
            derivazione=derivazione,
            invarianti=invarianti_riepilogo,
        )
    return evidenze


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
        diagnostica = tier0.estrai_diagnostica(istanza, schema)
        valori: dict[str, str | None] = {nome: d.valore for nome, d in diagnostica.items()}
        origine = {nome: "tier0" for nome, v in valori.items() if v is not None}
        costo_tier1 = 0.0
        tier1_errore: str | None = None
        provenienza_derivazione: list[ProvenienzaDerivazione] = []

        valori = _deriva_e_traccia_origine(schema, valori, origine, provenienza_derivazione)

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

            valori = _deriva_e_traccia_origine(schema, valori, origine, provenienza_derivazione)

        valutazioni = valuta_tutte_con_esito(schema, valori)
        violazioni = tuple(v.violazione for v in valutazioni if v.violazione is not None)
        evidenze = _costruisci_evidenze(
            schema,
            valori,
            origine,
            diagnostica,
            provenienza_derivazione,
            valutazioni,
            usa_tier1,
            tier1_errore,
        )
        # ADR-059: confidenza non e' piu' calcolata dai segnali grezzi
        # (violazioni/origine) — e' LETTA dall'Evidenza gia' assemblata
        # sopra. La pipeline non sa piu' cosa sia la confidenza, sa solo
        # costruire Evidenza.
        confidenza = _confidenza_da_evidenze(evidenze, valori)
        # ADR-060: il Gate legge solo RisultatoCampo (valore + evidenza +
        # confidenza + obbligatorio) — 'obbligatorio' e' l'unico fatto
        # che la pipeline deve ancora prendere dallo schema, il Gate
        # stesso non lo tocca mai.
        campi_gate = {
            c.nome: RisultatoCampo(
                valore=valori.get(c.nome),
                evidenza=evidenze[c.nome],
                confidenza=confidenza.get(c.nome),
                obbligatorio=c.obbligatorio,
            )
            for c in schema.campi
        }
        risultato_gate = gate(campi_gate)
        esito, motivo = risultato_gate.esito, risultato_gate.motivo
        evidenza_documento = EvidenzaDocumento(
            schema=schema.documento,
            schema_versione=schema.schema_version,
            classificazione=None,
            pagine=tuple(
                PaginaEvidenza(indice=p.numero, tipo=p.tipo.value)
                for p in triage_result.pagine[istanza.pagina_da - 1 : istanza.pagina_a]
            ),
        )
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
                evidenze=evidenze,
                evidenza_documento=evidenza_documento,
            )
        )
    return tuple(risultati)
