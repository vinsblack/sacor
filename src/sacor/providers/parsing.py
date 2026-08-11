"""Interpretazione della risposta di un provider reale (T4.3): JSON non
parsabile -> tutti i campi None, mai un valore parziale o indovinato —
'vale la stessa regola del tier 0' (istruzione utente verbatim). Il valore
grezzo estratto passa comunque per Repair (sacor.repair), lo stesso strato
che canonicalizza le catture regex del tier 0: stessa forma, stesso rigore
sull'ambiguo, un solo posto che decide 'e' normalizzabile o no'."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from sacor.repair import ripara
from sacor.schema import Campo, TipoCampo

_BLOCCO_MARKDOWN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def estrai_json(testo: str) -> dict[str, Any] | None:
    """Se il modello ignora l'istruzione 'solo JSON' e lo avvolge in un
    blocco markdown, lo si toglie — e' normalizzazione di formato, non
    un'interpretazione del contenuto. Qualunque altro fallimento di parsing
    (o un JSON che non e' un oggetto) -> None: nessun tentativo ulteriore di
    recuperare frammenti, sarebbe indovinare."""
    ripulito = _BLOCCO_MARKDOWN.sub("", testo.strip()).strip()
    try:
        dati = json.loads(ripulito)
    except json.JSONDecodeError:
        return None
    return dati if isinstance(dati, dict) else None


def _a_stringa(grezzo: Any, tipo: TipoCampo) -> str | None:
    """Il modello risponde spesso con un numero JSON nativo (48.5) invece di
    una stringa ("48.5") per i campi numerici — JSON valido, comportamento
    naturale del modello, non un errore suo (T4.16, trovato analizzando il
    dump grezzo di haiku-4-5 su bollette reali: scartato a None prima di
    questo fix, indipendentemente dal valore). Tollerato solo per
    decimal/integer — un numero al posto di un fornitore o una data non e'
    normalizzabile, resta None. bool e' sottoclasse di int in Python,
    escluso esplicitamente."""
    if isinstance(grezzo, str):
        return grezzo
    if isinstance(grezzo, bool):
        return None
    if tipo == "decimal" and isinstance(grezzo, int | float):
        return str(grezzo)
    if tipo == "integer" and isinstance(grezzo, int):
        return str(grezzo)
    if tipo == "integer" and isinstance(grezzo, float) and grezzo.is_integer():
        return str(int(grezzo))
    return None


def normalizza_risposta(testo: str, campi: Sequence[Campo]) -> dict[str, str | None]:
    dati = estrai_json(testo)
    if dati is None:
        return {campo.nome: None for campo in campi}

    valori: dict[str, str | None] = {}
    for campo in campi:
        stringa = _a_stringa(dati.get(campo.nome), campo.tipo)
        valori[campo.nome] = ripara(stringa, campo.tipo) if stringa is not None else None
    return valori
