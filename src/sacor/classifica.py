"""Classificazione documento (ADR-053): quale schema usare, PRIMA di
estrarre — decisione mai delegata all'utente per errore. Bug osservato in
sessione (12-08): una bolletta gas passata con lo schema luce viene letta
comunque, senza nessun avviso, producendo un campo (kwh_totale) con
l'unità sbagliata (smc scambiati per kWh). Stesso principio del tier0:
deterministico, gratis, zero AI, sempre disponibile — nessuna chiamata
serve per sapere se un documento è gas o luce.

Segnali presi da documenti reali (bolletta luce, bolletta gas, CTE
Engie, poi verificati sui 15 documenti di corpus/reale) — non inventati:
'gas naturale'/'energia elettrica'/'condizioni economiche' compaiono
ovunque nel testo intero (boilerplate su pagine successive che nomina
entrambe le commodity), inaffidabili come segnale se cercati su tutto il
documento. 'periodo di fatturazione' si e' rivelato fragile (troppe
varianti per fornitore, T4.17-stile) — sostituito con 'totale da pagare',
l'unico segnale verificato universale sui fornitori controllati."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

import pdfplumber

_SMC = re.compile(r"\bsmc\b")
_KWH = re.compile(r"\bkwh\b")
# Alcuni fornitori (Eni Plenitude, Hera) anteponono una lettera di
# copertina (comunicazione, non dati) alla pagina con "Totale da pagare"
# — verificato su 3 fornitori reali del corpus (R007/R009/R015). 3 pagine
# copre 6/9 di quei casi senza dover renderizzare l'intero file.
N_PAGINE_CLASSIFICAZIONE = 3


class TipoDocumento(StrEnum):
    """CTE ('Condizioni Tecnico-Economiche', ADR-053): un documento di
    offerta/condizioni contrattuali, non una bolletta — non ha un importo
    da pagare né un periodo di fatturazione, per definizione."""

    BOLLETTA_LUCE = "bolletta_luce"
    BOLLETTA_GAS = "bolletta_gas"
    CTE = "cte"
    SCONOSCIUTO = "sconosciuto"  # nessun segnale chiaro — mai indovinare


def classifica_testo(testo: str) -> TipoDocumento:
    """`testo` tipicamente le prime pagine del documento (dove il tipo si
    annuncia — T3.2), non l'intero file: piu' veloce, ed evita il
    boilerplate sulle pagine successive che nomina entrambe le commodity.
    Su alcuni fornitori la pagina 1 e' una lettera di copertina
    (comunicazione, non dati) — chi chiama passa piu' di una pagina se sa
    che il fornitore lo fa (vedi sacor.classifica.classifica_file)."""
    testo_lower = testo.lower()

    # 'totale da pagare' verificato su 6+ fornitori reali diversi come
    # l'UNICO segnale davvero universale di "questo e' un consuntivo con
    # importo dovuto" — 'periodo di X' ha troppe varianti per fornitore
    # (fatturazione/competenza/riferimento/oggetto di fatturazione/bare
    # 'PERIODO:') per essere enumerate in modo affidabile, si e' rivelato
    # un segnale fragile durante la verifica su corpus/reale.
    ha_totale = "totale da pagare" in testo_lower
    if not ha_totale:
        # Nessun importo dovuto: non e' un consuntivo. Un segnale positivo
        # ('condizioni economiche', 'codice offerta') lo rende un CTE — la
        # sola ASSENZA del segnale da bolletta non basta, altrimenti
        # qualunque documento senza importo verrebbe chiamato CTE (mai
        # indovinare per esclusione).
        if "condizioni economiche" in testo_lower or "codice offerta" in testo_lower:
            return TipoDocumento.CTE
        return TipoDocumento.SCONOSCIUTO

    ha_smc = bool(_SMC.search(testo_lower))
    ha_kwh = bool(_KWH.search(testo_lower))
    if ha_smc and not ha_kwh:
        return TipoDocumento.BOLLETTA_GAS
    if ha_kwh and not ha_smc:
        return TipoDocumento.BOLLETTA_LUCE
    return TipoDocumento.SCONOSCIUTO  # entrambe o nessuna unità: ambiguo


def classifica_file(file: Path, n_pagine: int = N_PAGINE_CLASSIFICAZIONE) -> TipoDocumento:
    """Legge le prime `n_pagine` (mai l'intero file — inutile su un PDF
    scansionato lungo, e la classificazione si gioca sempre nelle prime
    pagine). Su pagine SCANSIONE (nessun text layer) resta SCONOSCIUTO,
    non un errore: coerente con T3.2, mai indovinare da un'immagine qui
    (la classificazione e' tier0-style, zero AI)."""
    with pdfplumber.open(file) as documento:
        pagine = documento.pages[:n_pagine]
        testo = " ".join(p.extract_text() or "" for p in pagine)
    return classifica_testo(testo)
