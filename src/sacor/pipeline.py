"""Orchestrazione end-to-end su un singolo file (ADR-048): triage ->
segmentazione -> tier0 -> invarianti -> gate. Primo punto d'ingresso
pubblico single-file — prima esistevano solo script batch guidati da
oracle (eval/run.py, scripts/bakeoff.py), inutilizzabili da chi non ha
un corpus con risposte già note. Usato dalla CLI (`sacor extract`).

Solo tier0 qui (deterministico, gratis, sempre disponibile senza chiave
API) — tier1 resta negli script che già lo orchestrano, non duplicato
qui per YAGNI finché la CLI non lo richiede esplicitamente."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pdfplumber

from sacor.extractor import TierZeroExtractor
from sacor.invariants import Violazione, valuta_tutte
from sacor.schema import Schema
from sacor.segmentation import segmenta
from sacor.triage import analizza, normalizza_testo

EsitoGate = Literal["pass", "warning", "reject"]


@dataclass(frozen=True)
class RisultatoEstrazione:
    istanza_id: str
    valori: dict[str, str | None]
    violazioni: tuple[Violazione, ...]
    esito: EsitoGate
    motivo: str | None  # perche' reject — None se pass/warning


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


def estrai_file(file: Path, schema: Schema) -> tuple[RisultatoEstrazione, ...]:
    """Un risultato per istanza documentale rilevata nel file (ADR-014-bis:
    un PDF può contenere più documenti)."""
    triage_result = analizza(file)
    with pdfplumber.open(file) as documento:
        testi = [normalizza_testo(p) for p in documento.pages]
    esito_segmentazione = segmenta(file, triage_result.pagine, testi, schema.segmentazione)

    tier0 = TierZeroExtractor()
    risultati = []
    for istanza in esito_segmentazione.istanze:
        valori = tier0.extract(istanza, schema)
        violazioni = valuta_tutte(schema, valori)
        esito, motivo = _calcola_esito(schema, valori, violazioni)
        risultati.append(
            RisultatoEstrazione(
                istanza_id=istanza.id,
                valori=valori,
                violazioni=violazioni,
                esito=esito,
                motivo=motivo,
            )
        )
    return tuple(risultati)
