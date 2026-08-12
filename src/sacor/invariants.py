"""Registro dei tipi di invariante noti, e il motore che le valuta
(ADR-045, Fase 1) — lo strato "Arbitrate" del disegno a 7 strati, mai
costruito fino a questa sessione: solo dichiarato e validato al load,
mai eseguito contro un set di valori estratti veri."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
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
        messaggio=(
            f"{successiva_nome} = {successiva_data} precede "
            f"{precedente_nome} = {precedente_data}"
        ),
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


@dataclass(frozen=True)
class EsitoInvarianteValutazione:
    """ADR-056/058: 'valuta_tutte' tiene solo le fallite (None copre sia
    'passata' che 'non valutabile per campi mancanti' — la stessa
    ambiguita' che _valuta_somma_approssimata commenta al suo interno).
    Evidence.invarianti (per campo) ha bisogno anche delle passate, e di
    sapere se l'invariante e' stata valutata affatto: un'invariante non
    valutabile (campi mancanti) non conta ne' come passata ne' come
    fallita."""

    invariante_id: str
    severita: Severita
    valutata: bool
    violazione: Violazione | None  # sempre None se valutata e' False


def valuta_tutte_con_esito(
    schema: Schema, valori: Mapping[str, str | None]
) -> tuple[EsitoInvarianteValutazione, ...]:
    """Come valuta_tutte, ma per OGNI invariante dello schema, non solo le
    fallite. 'valutabile' == tutti i campi che l'invariante referenzia
    (campi_coinvolti) sono presenti in valori — la stessa condizione che
    ciascun _valuta_* verifica internamente per restituire None invece di
    giudicare, resa esplicita qui invece che nascosta nel None."""
    risultati = []
    for inv in schema.invarianti:
        valutabile = all(valori.get(nome) is not None for nome in campi_coinvolti(inv))
        violazione = valuta(inv, valori) if valutabile else None
        risultati.append(
            EsitoInvarianteValutazione(
                invariante_id=inv.id,
                severita=inv.severita,
                valutata=valutabile,
                violazione=violazione,
            )
        )
    return tuple(risultati)


def valuta_tutte(schema: Schema, valori: Mapping[str, str | None]) -> tuple[Violazione, ...]:
    return tuple(
        r.violazione for r in valuta_tutte_con_esito(schema, valori) if r.violazione is not None
    )


def _deriva_differenza_giorni(invariante: Invariante, valori: dict[str, str | None]) -> None:
    da_nome = invariante.params["da"]
    a_nome = invariante.params["a"]
    risultato_nome = invariante.params["risultato"]
    offset = invariante.params["offset"]

    da_str = valori.get(da_nome)
    a_str = valori.get(a_nome)
    risultato_str = valori.get(risultato_nome)
    mancanti = sum(v is None for v in (da_str, a_str, risultato_str))
    if mancanti != 1:
        return  # 0: niente da fare. 2+: sottodeterminato, non e' matematica.

    try:
        if da_str is None:
            a_data = date.fromisoformat(a_str)  # type: ignore[arg-type]
            risultato = int(risultato_str)  # type: ignore[arg-type]
            valori[da_nome] = (a_data - timedelta(days=risultato - offset)).isoformat()
        elif a_str is None:
            da_data = date.fromisoformat(da_str)
            risultato = int(risultato_str)  # type: ignore[arg-type]
            valori[a_nome] = (da_data + timedelta(days=risultato - offset)).isoformat()
        else:
            da_data = date.fromisoformat(da_str)
            a_data = date.fromisoformat(a_str)
            valori[risultato_nome] = str((a_data - da_data).days + offset)
    except ValueError:
        return  # presente ma non parsabile: non derivabile, non un errore qui


def _deriva_somma_approssimata(invariante: Invariante, valori: dict[str, str | None]) -> None:
    # SOLO il totale si deriva, mai un addendo mancante (bug trovato in
    # audit, 12-08): un addendo None puo' significare "non ancora letto"
    # (derivabile) O "non applicabile per questo documento" (es. kwh_f3 su
    # bolletta bioraria — kwh_f2 e' GIA' l'aggregato F2+F3 per costruzione
    # dello schema, kwh_f3 resta null per design, bolletta_luce_it.yaml
    # descrizione kwh_f3). La funzione non puo' distinguere i due casi
    # guardando solo 'None' — derivare comunque avrebbe inventato un
    # valore plausibile ma falso, con confidenza 'media' invece di un
    # allarme: esattamente cio' che "mai sbagliare in silenzio" vieta.
    # Derivare il totale da TUTTI gli addendi noti non ha questa
    # ambiguita' (nessun addendo viene inventato) e resta sicuro.
    addendi_nomi = invariante.params["addendi"]
    totale_nome = invariante.params["totale"]

    addendi_valori = [valori.get(nome) for nome in addendi_nomi]
    totale_valore = valori.get(totale_nome)
    if totale_valore is not None or any(v is None for v in addendi_valori):
        return

    try:
        somma = sum((Decimal(v) for v in addendi_valori if v is not None), start=Decimal(0))
    except InvalidOperation:
        return
    valori[totale_nome] = str(somma)


@dataclass(frozen=True)
class ProvenienzaDerivazione:
    """ADR-056: Evidence.derivazione ha bisogno di COME un valore
    derivato e' stato ottenuto, non solo del risultato — quale
    invariante, quale formula, da quali altri campi."""

    campo: str
    tipo: str  # "differenza_giorni" | "somma_approssimata"
    invariante_id: str
    da_campi: tuple[str, ...]


def deriva_mancanti_con_provenienza(
    schema: Schema, valori: Mapping[str, str | None]
) -> tuple[dict[str, str | None], tuple[ProvenienzaDerivazione, ...]]:
    """Come deriva_mancanti, ma registra anche la provenienza di ogni
    campo effettivamente derivato (ADR-058: la pipeline deve poter
    raccontare la storia di un campo leggendo solo la sua Evidenza, non
    reindovinando quale invariante l'ha prodotto)."""
    derivati = dict(valori)
    provenienza: list[ProvenienzaDerivazione] = []
    for invariante in schema.invarianti:
        prima = dict(derivati)
        if invariante.tipo == "differenza_giorni":
            _deriva_differenza_giorni(invariante, derivati)
            campi_derivazione = (
                invariante.params["da"],
                invariante.params["a"],
                invariante.params["risultato"],
            )
        elif invariante.tipo == "somma_approssimata":
            _deriva_somma_approssimata(invariante, derivati)
            campi_derivazione = (*invariante.params["addendi"], invariante.params["totale"])
        else:
            continue

        for nome in campi_derivazione:
            if prima.get(nome) is None and derivati.get(nome) is not None:
                altri = tuple(c for c in campi_derivazione if c != nome)
                provenienza.append(
                    ProvenienzaDerivazione(
                        campo=nome,
                        tipo=invariante.tipo,
                        invariante_id=invariante.id,
                        da_campi=altri,
                    )
                )
    return derivati, tuple(provenienza)


def deriva_mancanti(schema: Schema, valori: Mapping[str, str | None]) -> dict[str, str | None]:
    """Riempie i campi mancanti derivabili aritmeticamente da un
    'differenza_giorni' o 'somma_approssimata' dichiarato nello schema, se
    esattamente un termine e' mancante e gli altri sono noti e validi
    (ADR-051): non e' un'invenzione, e' la stessa formula gia' usata per
    VALIDARE l'invariante — qui la si usa per risolvere l'incognita quando
    ce n'e' una sola. Nuovo dict, l'input non viene mutato."""
    derivati, _ = deriva_mancanti_con_provenienza(schema, valori)
    return derivati


def campi_coinvolti(invariante: Invariante) -> tuple[str, ...]:
    """Nomi dei campi che questa invariante referenzia (ADR-048 punto 2):
    usato per marcare come 'bassa confidenza' i campi coinvolti in
    un'invariante violata, non solo il documento nel suo complesso. Stessa
    tabella TIPI_NOTI che valida le referenze al load dello schema — un
    parametro qui e' o il nome di un campo (str) o una lista di nomi
    (es. 'addendi' in somma_approssimata)."""
    nomi: list[str] = []
    for chiave in TIPI_NOTI[invariante.tipo]:
        valore = invariante.params[chiave]
        nomi.extend(valore if isinstance(valore, list) else [valore])
    return tuple(nomi)
