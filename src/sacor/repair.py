"""Repair (01-architecture.md, strato 4): normalizza un valore grezzo
estratto nella forma canonica dell'oracle, guidato dal `tipo` dichiarato nel
campo. Mai AI: solo parsing e riformattazione deterministici.

Regola dura: se il valore non e' normalizzabile con certezza, None. Mai
un'interpretazione plausibile — un valore inventato e' peggio di uno assente
(stesso principio di ADR-011/ADR-024/ADR-031 applicato qui).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from sacor.schema import TipoCampo

_PATTERN_DATA = re.compile(r"^(\d{2})[/.-](\d{2})[/.-](\d{4})$")


def _ripara_data(valore: str) -> str | None:
    m = _PATTERN_DATA.match(valore.strip())
    if not m:
        return None
    giorno, mese, anno = (int(x) for x in m.groups())
    try:
        return date(anno, mese, giorno).isoformat()
    except ValueError:
        return None


def _ripara_decimale(valore: str) -> str | None:
    """Separatore migliaia/decimale italiano: '.' migliaia, ',' decimale.

    Regola per il caso ambiguo (nessuna virgola, un solo punto): un gruppo
    delle migliaia italiano e' sempre di ESATTAMENTE 3 cifre. Se dopo l'unico
    punto ci sono cifre in numero diverso da 3, il punto non puo' essere un
    separatore delle migliaia valido -> e' un punto decimale genuino
    ("56.25", "119.19", 2 cifre). Se le cifre dopo il punto sono
    esattamente 3 ("1.234"), la stringa e' STRUTTURALMENTE ambigua: puo'
    essere 1234 (migliaia) o un decimale a tre cifre, e non c'e' modo di
    distinguerli senza altro contesto. In quel caso si rifiuta (None)
    piuttosto che indovinare.

    Con la virgola presente non c'e' ambiguita': la virgola e' sempre il
    separatore decimale, ogni punto prima di essa e' migliaia, qualunque sia
    il raggruppamento delle cifre.
    """
    grezzo = valore.strip()
    if not grezzo:
        return None

    if "," in grezzo:
        parte_intera, _, parte_decimale = grezzo.rpartition(",")
        candidato = parte_intera.replace(".", "") + "." + parte_decimale
    else:
        punti = grezzo.count(".")
        if punti == 0:
            candidato = grezzo
        elif punti == 1:
            cifre_dopo_punto = len(grezzo.split(".")[1])
            if cifre_dopo_punto == 3:
                return None  # ambiguo per costruzione, vedi docstring
            candidato = grezzo
        else:
            candidato = grezzo.replace(".", "")

    try:
        return str(Decimal(candidato))
    except InvalidOperation:
        return None


def _ripara_intero(valore: str) -> str | None:
    """Un intero non ha parte decimale per definizione: un punto e' sempre
    separatore delle migliaia, mai ambiguo (a differenza del decimale)."""
    ripulito = valore.strip().replace(".", "")
    corpo = ripulito[1:] if ripulito.startswith("-") else ripulito
    if not corpo.isdigit():
        return None
    return str(int(ripulito))


def _ripara_stringa(valore: str) -> str | None:
    ripulito = re.sub(r"\s+", " ", valore.strip())
    return ripulito or None


def ripara(valore: str | None, tipo: TipoCampo) -> str | None:
    """Punto d'ingresso: None passa attraverso invariato (nessun dato da
    riparare), altrimenti normalizza secondo il tipo dichiarato."""
    if valore is None:
        return None
    if tipo == "string":
        return _ripara_stringa(valore)
    if tipo == "date":
        return _ripara_data(valore)
    if tipo == "integer":
        return _ripara_intero(valore)
    if tipo == "decimal":
        return _ripara_decimale(valore)
    raise AssertionError(f"tipo campo non gestito: {tipo}")
