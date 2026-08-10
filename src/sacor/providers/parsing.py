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
from sacor.schema import Campo

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


def normalizza_risposta(testo: str, campi: Sequence[Campo]) -> dict[str, str | None]:
    dati = estrai_json(testo)
    if dati is None:
        return {campo.nome: None for campo in campi}

    valori: dict[str, str | None] = {}
    for campo in campi:
        grezzo = dati.get(campo.nome)
        stringa = grezzo if isinstance(grezzo, str) else None
        valori[campo.nome] = ripara(stringa, campo.tipo) if stringa is not None else None
    return valori
