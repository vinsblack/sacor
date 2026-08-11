"""Registro dei tipi di invariante noti, e il motore che le valuta
(ADR-045, Fase 1) — lo strato "Arbitrate" del disegno a 7 strati, mai
costruito fino a questa sessione: solo dichiarato e validato al load,
mai eseguito contro un set di valori estratti veri."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sacor.schema import Invariante, Schema, Severita

TIPI_NOTI: dict[str, tuple[str, ...]] = {
    "somma_approssimata": ("addendi", "totale"),
    "differenza_giorni": ("da", "a", "risultato"),
    "valore_minimo": ("campo",),
    "ordine_date": ("precedente", "successiva"),
    "formato": ("campo",),
}


@dataclass(frozen=True)
class Violazione:
    invariante_id: str
    severita: Severita
    messaggio: str


def _decimal_o_none(valore: str | None) -> Decimal | None:
    if valore is None:
        return None
    try:
        return Decimal(valore)
    except InvalidOperation:
        return None


def _valuta_somma_approssimata(
    invariante: Invariante, valori: Mapping[str, str | None]
) -> Violazione | None:
    """Regola dura, come ovunque nel progetto: un addendo o il totale non
    determinabile (None o non un decimale valido) rende l'invariante non
    valutabile, non violata — un None non e' un errore."""
    addendi_nomi = invariante.params["addendi"]
    totale_nome = invariante.params["totale"]
    tolleranza = Decimal(str(invariante.params["tolleranza_relativa"]))

    addendi_valori = [_decimal_o_none(valori.get(nome)) for nome in addendi_nomi]
    totale_valore = _decimal_o_none(valori.get(totale_nome))
    if totale_valore is None or any(v is None for v in addendi_valori):
        return None

    somma = sum((v for v in addendi_valori if v is not None), start=Decimal(0))
    scarto_ammesso = abs(totale_valore) * tolleranza
    if abs(somma - totale_valore) <= scarto_ammesso:
        return None

    return Violazione(
        invariante_id=invariante.id,
        severita=invariante.severita,
        messaggio=(
            f"somma di {', '.join(addendi_nomi)} = {somma}, "
            f"atteso {totale_nome} = {totale_valore} (tolleranza relativa {tolleranza})"
        ),
    )


def _valuta_differenza_giorni(
    invariante: Invariante, valori: Mapping[str, str | None]
) -> Violazione | None:
    da_nome = invariante.params["da"]
    a_nome = invariante.params["a"]
    risultato_nome = invariante.params["risultato"]
    offset = invariante.params["offset"]

    da_str = valori.get(da_nome)
    a_str = valori.get(a_nome)
    risultato_str = valori.get(risultato_nome)
    if da_str is None or a_str is None or risultato_str is None:
        return None

    try:
        da_data = date.fromisoformat(da_str)
        a_data = date.fromisoformat(a_str)
        risultato_atteso = int(risultato_str)
    except ValueError:
        return None

    calcolato = (a_data - da_data).days + offset
    if calcolato == risultato_atteso:
        return None

    return Violazione(
        invariante_id=invariante.id,
        severita=invariante.severita,
        messaggio=(
            f"{a_nome} - {da_nome} + {offset} = {calcolato}, "
            f"{risultato_nome} dichiarato = {risultato_atteso}"
        ),
    )


def _valuta_valore_minimo(
    invariante: Invariante, valori: Mapping[str, str | None]
) -> Violazione | None:
    """Un valore negativo (kwh, importo) e' quasi sempre un OCR/parsing
    andato storto, non un dato reale — soglia INCLUSIVA (0 e' ammesso,
    non e' una violazione)."""
    campo_nome = invariante.params["campo"]
    minimo = Decimal(str(invariante.params["minimo"]))

    valore = _decimal_o_none(valori.get(campo_nome))
    if valore is None:
        return None
    if valore >= minimo:
        return None

    return Violazione(
        invariante_id=invariante.id,
        severita=invariante.severita,
        messaggio=f"{campo_nome} = {valore}, atteso >= {minimo}",
    )


def _valuta_ordine_date(
    invariante: Invariante, valori: Mapping[str, str | None]
) -> Violazione | None:
    precedente_nome = invariante.params["precedente"]
    successiva_nome = invariante.params["successiva"]

    precedente_str = valori.get(precedente_nome)
    successiva_str = valori.get(successiva_nome)
    if precedente_str is None or successiva_str is None:
        return None

    try:
        precedente_data = date.fromisoformat(precedente_str)
        successiva_data = date.fromisoformat(successiva_str)
    except ValueError:
        return None

    if successiva_data >= precedente_data:
        return None

    return Violazione(
        invariante_id=invariante.id,
        severita=invariante.severita,
        messaggio=f"{successiva_nome} = {successiva_data} precede {precedente_nome} = {precedente_data}",
    )


def _valuta_formato(invariante: Invariante, valori: Mapping[str, str | None]) -> Violazione | None:
    campo_nome = invariante.params["campo"]
    pattern = invariante.params["pattern"]

    valore = valori.get(campo_nome)
    if valore is None:
        return None
    if re.fullmatch(pattern, valore) is not None:
        return None

    return Violazione(
        invariante_id=invariante.id,
        severita=invariante.severita,
        messaggio=f"{campo_nome} = {valore!r} non rispetta il formato '{pattern}'",
    )


_VALUTATORI = {
    "somma_approssimata": _valuta_somma_approssimata,
    "differenza_giorni": _valuta_differenza_giorni,
    "valore_minimo": _valuta_valore_minimo,
    "ordine_date": _valuta_ordine_date,
    "formato": _valuta_formato,
}


def valuta(invariante: Invariante, valori: Mapping[str, str | None]) -> Violazione | None:
    valutatore = _VALUTATORI.get(invariante.tipo)
    if valutatore is None:
        # Tipo gia' validato al load dello schema (sacor.schema): irraggiungibile
        # a runtime con uno schema caricato correttamente.
        raise AssertionError(f"tipo invariante non gestito: {invariante.tipo}")
    return valutatore(invariante, valori)


def valuta_tutte(schema: Schema, valori: Mapping[str, str | None]) -> tuple[Violazione, ...]:
    return tuple(v for inv in schema.invarianti if (v := valuta(inv, valori)) is not None)
