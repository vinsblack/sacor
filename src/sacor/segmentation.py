"""Segmentazione guidata dallo schema (ADR-017): il core non sa cosa sia una
fattura, esegue solo il criterio dichiarato in YAML. Registro dei tipi noti,
come per le invarianti (sacor.invariants) — nuovo tipo di documento, nuovo
pattern nello YAML, non nuovo codice.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sacor.triage import PaginaInfo, TipoPagina

TIPI_NOTI: tuple[str, ...] = ("cambio_valore",)

_LETTERE_ISTANZA = "abcdefghijklmnopqrstuvwxyz"


@dataclass(frozen=True)
class SegmentazioneConfig:
    tipo: str
    pattern: str
    minimo_pagine: int


class ConfidenzaSegmentazione(StrEnum):
    """ADR-024: non_determinabile deve propagarsi come warning, mai come
    pass silenzioso — mai trattata come un esito normale a valle."""

    CERTA = "certa"  # text layer ovunque, pattern trovato
    PRESUNTA = "presunta"  # text layer ovunque, pattern mai trovato
    NON_DETERMINABILE = "non_determinabile"  # almeno una pagina SCANSIONE/IBRIDA


@dataclass(frozen=True)
class Istanza:
    """ADR-033: porta file e intervallo di pagine — e' cio' che un
    Extractor riceve per leggere SOLO le proprie pagine, mai il file intero."""

    id: str
    file: Path
    pagina_da: int
    pagina_a: int


@dataclass(frozen=True)
class SegmentazioneResult:
    istanze: tuple[Istanza, ...]
    confidenza: ConfidenzaSegmentazione


def _istanza_unica(file: Path, n_pagine: int) -> Istanza:
    return Istanza(id=file.stem, file=file, pagina_da=1, pagina_a=max(n_pagine, 1))


def _raggruppa(valori: Sequence[str | None]) -> list[tuple[int, int]]:
    """Confini di istanza dove il valore catturato cambia (ADR-017).
    Pagine consecutive con lo stesso valore appartengono alla stessa istanza.
    """
    spezzoni: list[tuple[int, int]] = []
    inizio = 1
    corrente = valori[0]
    for i in range(1, len(valori)):
        if valori[i] != corrente:
            spezzoni.append((inizio, i))
            inizio = i + 1
            corrente = valori[i]
    spezzoni.append((inizio, len(valori)))
    return spezzoni


def _assegna_id(file: Path, spezzoni: list[tuple[int, int]]) -> tuple[Istanza, ...]:
    doc_id = file.stem
    if len(spezzoni) == 1:
        pagina_da, pagina_a = spezzoni[0]
        return (Istanza(id=doc_id, file=file, pagina_da=pagina_da, pagina_a=pagina_a),)
    return tuple(
        Istanza(id=f"{doc_id}{_LETTERE_ISTANZA[i]}", file=file, pagina_da=da, pagina_a=a)
        for i, (da, a) in enumerate(spezzoni)
    )


def _cambio_valore(file: Path, testi: Sequence[str], pattern: str) -> SegmentazioneResult:
    regex = re.compile(pattern)
    valori: list[str | None] = [
        (m.group(1) if (m := regex.search(testo)) else None) for testo in testi
    ]

    if all(v is None for v in valori):
        return SegmentazioneResult(
            istanze=(_istanza_unica(file, len(testi)),),
            confidenza=ConfidenzaSegmentazione.PRESUNTA,
        )

    spezzoni = _raggruppa(valori)
    return SegmentazioneResult(
        istanze=_assegna_id(file, spezzoni),
        confidenza=ConfidenzaSegmentazione.CERTA,
    )


def segmenta(
    file: Path,
    pagine: Sequence[PaginaInfo],
    testi: Sequence[str],
    config: SegmentazioneConfig | None,
) -> SegmentazioneResult:
    """Applica il criterio di segmentazione dichiarato nello schema.

    Assente -> default una istanza per file, confidenza certa (ADR-017): il
    comportamento semplice resta il default, non un caso speciale.

    Scorciatoia aritmetica (ADR-031, corregge ADR-029, revocata): CERTA senza
    leggere il testo SOLO se pagine_totali < 2 * minimo_pagine E tutte le
    pagine sono DIGITALE. La premessa di ADR-029 — "un'istanza occupa almeno
    minimo_pagine pagine quindi una pagina ne contiene al piu' una" — era
    falsa: due fatture possono stare sulla stessa pagina fisica (S011, corpus
    di default), e la vecchia scorciatoia le dichiarava CERTA/1 istanza
    mentre la verita' era 2. Un errore silenzioso e sicuro di se', il
    fallimento esatto che il progetto esiste per prevenire.

    Su una pagina SCANSIONE/IBRIDA la scorciatoia non si applica mai: li'
    l'incertezza e' reale (ADR-024), non un falso allarme da sopprimere. Si
    riduce rendendo leggibile la pagina (OCR, Blocco 3), non assumendo.
    Si produce comunque un risultato — mai un'eccezione.
    """
    if config is None:
        return SegmentazioneResult(
            istanze=(_istanza_unica(file, len(pagine)),),
            confidenza=ConfidenzaSegmentazione.CERTA,
        )

    tutte_digitale = all(p.tipo is TipoPagina.DIGITALE for p in pagine)
    if len(pagine) < 2 * config.minimo_pagine and tutte_digitale:
        return SegmentazioneResult(
            istanze=(_istanza_unica(file, len(pagine)),),
            confidenza=ConfidenzaSegmentazione.CERTA,
        )

    if any(p.tipo in (TipoPagina.SCANSIONE, TipoPagina.IBRIDA) for p in pagine):
        return SegmentazioneResult(
            istanze=(_istanza_unica(file, len(pagine)),),
            confidenza=ConfidenzaSegmentazione.NON_DETERMINABILE,
        )

    if config.tipo == "cambio_valore":
        return _cambio_valore(file, testi, config.pattern)

    # Tipo gia' validato al load dello schema (sacor.schema): irraggiungibile
    # a runtime, ma nessuna eccezione per un tipo comunque sconosciuto qui.
    return SegmentazioneResult(
        istanze=(_istanza_unica(file, len(pagine)),),
        confidenza=ConfidenzaSegmentazione.NON_DETERMINABILE,
    )
