"""Evidence Model (ADR-056/057). Commit 1: solo strutture dati, zero
logica agganciata alla pipeline — importabile e testabile in isolamento,
nessun chiamante esistente lo usa ancora, quindi introdurlo non cambia il
comportamento di nulla (nessun test esistente puo' rompersi).

confidenza_da_evidenza() e' la stessa regola gia' in produzione in
pipeline._calcola_confidenza() (vedi ADR-056): qui dichiarata come
funzione pura sopra una struttura Evidenza esplicita, invece che calcolata
internamente e scartata subito dopo."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Confidenza = Literal["alta", "media", "bassa"]


@dataclass(frozen=True)
class Riparazione:
    """Una trasformazione applicata al valore grezzo prima dell'uso
    (es. normalizzazione di un decimale o di una data italiana)."""

    tipo: str
    da: str | None = None
    a: str | None = None


@dataclass(frozen=True)
class Derivazione:
    """Un valore ottenuto aritmeticamente da altri campi noti (ADR-051),
    non letto direttamente dal documento."""

    tipo: str
    invariante_id: str
    da_campi: tuple[str, ...] = ()


@dataclass(frozen=True)
class EsitoInvariante:
    id: str
    esito: Literal["pass", "fail"]
    severita: str


@dataclass(frozen=True)
class RiepilogoInvarianti:
    """Non solo le invarianti fallite (come 'violazioni' oggi) — anche
    quelle valutate con successo, per rispondere a 'invarianti: 3/3'."""

    passate: int = 0
    fallite: int = 0
    dettaglio: tuple[EsitoInvariante, ...] = ()


@dataclass(frozen=True)
class Evidenza:
    """ADR-057: 'origine' e 'stato' rispondono a domande diverse — 'da
    dove viene questo valore' contro 'perche' l'origine e' assente o
    inutilizzabile'. Mai comprimerle in un solo campo (stessa lezione di
    "confidenza calcolata e buttata via" che ha motivato ADR-056).

    origine/stato sono stringhe aperte, non enum chiusi: un nuovo tier o
    un nuovo motivo di assenza si aggiungono senza rompere il contratto
    (ADR-056)."""

    origine: str | None = None
    stato: str | None = None
    repair: tuple[Riparazione, ...] = ()
    derivazione: tuple[Derivazione, ...] = ()
    invarianti: RiepilogoInvarianti = field(default_factory=RiepilogoInvarianti)


@dataclass(frozen=True)
class PaginaEvidenza:
    indice: int
    tipo: str  # "digitale" | "ibrida" | "scansione" (sacor.triage)


@dataclass(frozen=True)
class EvidenzaDocumento:
    """Evidenza a livello di documento, non di campo — distingue un
    problema del DOCUMENTO (scansione illeggibile) da un problema del
    CAMPO (regex non ha trovato nulla su un documento leggibile), oggi
    indistinguibile nell'output (ADR-056)."""

    schema: str
    schema_versione: int
    classificazione: str | None = None
    pagine: tuple[PaginaEvidenza, ...] = ()


@dataclass(frozen=True)
class RisultatoCampo:
    valore: str | None
    evidenza: Evidenza
    confidenza: Confidenza | None


def confidenza_da_evidenza(valore: str | None, evidenza: Evidenza) -> Confidenza | None:
    """Regola dichiarata in ADR-056 (identica a quella gia' in
    produzione, vedi pipeline._calcola_confidenza):

    null   se il valore e' assente
    bassa  se una qualunque invariante coinvolgente il campo e' fallita
    media  se l'origine e' tier1 o derivato (eredita l'incertezza a monte)
    alta   altrimenti (origine tier0, deterministica)
    """
    if valore is None:
        return None
    if evidenza.invarianti.fallite > 0:
        return "bassa"
    if evidenza.origine in ("tier1", "derivato"):
        return "media"
    return "alta"
