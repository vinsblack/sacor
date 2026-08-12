"""Il Gate (ADR-056/058/059/060, Commit 4): legge SOLO Evidence, il
componente piu' stupido del progetto per costruzione — non importa
Schema, pipeline, extractor, provider. Se un domani serve un fatto che
Evidence non porta, e' un pezzo di Evidence mancante da aggiungere in
sacor.evidence, mai una scorciatoia che fa leggere altro da qui
(istruzione utente verbatim, sessione 12-08)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from sacor.evidence import RisultatoCampo

EsitoGate = Literal["pass", "warning", "reject"]


@dataclass(frozen=True)
class RisultatoGate:
    esito: EsitoGate
    motivo: str | None  # perche' reject — None se pass/warning


def gate(campi: Mapping[str, RisultatoCampo]) -> RisultatoGate:
    """Stessa regola di sempre (ex pipeline._calcola_esito, ADR-048),
    riletta da Evidenza invece che da (schema, valori, violazioni):

    1. un campo obbligatorio senza valore -> reject
    2. un'invariante fallita con severita' 'reject' -> reject
    3. qualunque altra invariante fallita -> warning
    4. altrimenti -> pass
    """
    mancanti = [nome for nome, c in campi.items() if c.obbligatorio and c.valore is None]
    if mancanti:
        return RisultatoGate("reject", f"campi obbligatori mancanti: {', '.join(mancanti)}")

    for c in campi.values():
        for d in c.evidenza.invarianti.dettaglio:
            if d.esito == "fail" and d.severita == "reject":
                return RisultatoGate("reject", f"invariante violata: {d.messaggio}")

    ha_violazioni = any(
        d.esito == "fail" for c in campi.values() for d in c.evidenza.invarianti.dettaglio
    )
    if ha_violazioni:
        return RisultatoGate("warning", None)
    return RisultatoGate("pass", None)
