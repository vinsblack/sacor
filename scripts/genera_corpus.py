"""Generatore di bollette luce sintetiche (Blocco 1-bis, ADR-012/013).

Principio: l'oracle e' l'INPUT del generatore, non una lettura del PDF. I
valori si generano prima, il PDF li rappresenta dopo: e' esatto per
costruzione. Nessun dato reale: anagrafiche, fornitori e POD sono inventati.

ADR-038: una pagina "scansione" e' il rendering ad alta risoluzione dello
STESSO layout digitale, degradato — non un documento disegnato a parte con
altri strumenti. ADR-039: struttura a tre pagine osservata su bollette luce
reali (nessun valore reale riportato, solo la forma)."""

from __future__ import annotations

import argparse
import io
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pdfplumber
from PIL import Image, ImageDraw, ImageFilter
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

REPO_ROOT = Path(__file__).parent.parent

LAYOUTS: tuple[str, ...] = ("Alfa Energia", "Beta Luce", "Gamma Power")

NOME_ESTESO: dict[str, str] = {
    "Alfa Energia": "Alfa Energia S.p.A. - Vendita al Dettaglio",
    "Beta Luce": "Beta Luce S.r.l. Unipersonale",
    "Gamma Power": "Gamma Power Societa' Benefit S.p.A.",
}

MESI_IT = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)

FLAG_NOMI: tuple[str, ...] = (
    "multi_fattura",
    "periodo_mensile",
    "fornitore_esteso",
    "consumo_stimato",
    "monoraria",
    "ruotata",
    "scansione",
    "scansione_sporca",
    "scansione_aggressiva",
    "scansione_illeggibile",
    "pagina_ibrida",
    "data_con_punti",
    "canone_extra",
    "pagine_allegate",
)


@dataclass(frozen=True)
class Flags:
    multi_fattura: bool = False
    periodo_mensile: bool = False
    fornitore_esteso: bool = False
    consumo_stimato: bool = False
    monoraria: bool = False
    ruotata: bool = False
    scansione: bool = False
    scansione_sporca: bool = False
    # T4.14 (ADR-040): gg.mm.aaaa invece di gg/mm/aaaa — secondo formato
    # data osservato su bollette reali (Hera/EstEnergy), oltre a slash e
    # mese-esteso. Solo sul periodo "Dal...al...": periodo_mensile non lo usa.
    data_con_punti: bool = False
    # T4.14 (ADR-040): canone RAI + "Totale da pagare" diverso dal "Totale
    # scontrino" — rumore puro, mai un campo tracciato (vedi _CANONE_RAI_*).
    canone_extra: bool = False
    # T4.14 (ADR-041): una pagina di modulo di pagamento allegata dopo le
    # PAGINE_PER_FATTURA pagine vere — assorbita nell'istanza dalla
    # segmentazione per costruzione (nessun marcatore "Fattura n." sopra),
    # gap noto e misurato, non un difetto da correggere qui (vedi ADR-041).
    pagine_allegate: bool = False
    # T4.10, C1: casi dichiarati distinti dal degrado di produzione (MEDIO).
    # scansione_aggressiva -> caso difficile ma leggibile (97% misurato).
    # scansione_illeggibile -> atteso reject, non "estrarre bene" (ADR-036).
    scansione_aggressiva: bool = False
    scansione_illeggibile: bool = False
    pagina_ibrida: bool = False

    def attivi(self) -> list[str]:
        return [nome for nome in FLAG_NOMI if getattr(self, nome)]


# T4.9, C2 (ADR-039): stile di contenuto di default per fornitore — non e'
# un flag esplicito del caso, e' cio' che quel fornitore fa sempre ("Alfa
# bimestrale monoraria, Beta mensile a fasce, Gamma mensile stimato"). Si
# somma ai flag del caso (struttura: scansione/rotazione/multi-fattura),
# non li sostituisce — sono due assi indipendenti.
_STILE_LAYOUT: dict[str, Flags] = {
    "Alfa Energia": Flags(monoraria=True, data_con_punti=True),
    "Beta Luce": Flags(periodo_mensile=True),
    "Gamma Power": Flags(periodo_mensile=True, consumo_stimato=True, canone_extra=True),
}


def _flags_effettivi(layout: str, flags: Flags) -> Flags:
    stile = _STILE_LAYOUT.get(layout, Flags())
    valori = {nome: getattr(flags, nome) or getattr(stile, nome) for nome in FLAG_NOMI}
    return Flags(**valori)


@dataclass(frozen=True)
class CasoComposizione:
    etichetta: str
    layout: str
    flags: Flags


# Corpus di default (ADR-025): una miscela dichiarata di casi difficili, non
# un campione uniforme. Il corpus base esiste apposta per misurare cio' che
# il triage dovrebbe misurare — un campione di soli digitali puliti avrebbe
# una risposta di default ovvia per ogni attributo, e il numero sarebbe vuoto.
COMPOSIZIONE_DEFAULT: tuple[CasoComposizione, ...] = (
    CasoComposizione("digitale_pulito", "Alfa Energia", Flags()),
    CasoComposizione("digitale_pulito", "Beta Luce", Flags()),
    CasoComposizione("digitale_pulito", "Gamma Power", Flags()),
    CasoComposizione("digitale_pulito", "Alfa Energia", Flags()),
    CasoComposizione("scansione_pulita", "Beta Luce", Flags(scansione=True)),
    CasoComposizione("scansione_pulita", "Gamma Power", Flags(scansione=True)),
    CasoComposizione("scansione_sporca", "Alfa Energia", Flags(scansione_sporca=True)),
    CasoComposizione("scansione_sporca", "Beta Luce", Flags(scansione_sporca=True)),
    CasoComposizione("pagina_ibrida", "Gamma Power", Flags(pagina_ibrida=True)),
    CasoComposizione("multi_fattura_digitale", "Alfa Energia", Flags(multi_fattura=True)),
    CasoComposizione(
        "multi_fattura_scansionato",
        "Beta Luce",
        Flags(multi_fattura=True, scansione=True),
    ),
    CasoComposizione("ruotato", "Gamma Power", Flags(ruotata=True)),
    CasoComposizione("documento_con_allegato", "Beta Luce", Flags(pagine_allegate=True)),
)


@dataclass(frozen=True)
class DatiFattura:
    pod: str
    fornitore_stampato: str
    numero_fattura: str
    periodo_da: date
    periodo_a: date
    giorni: int
    scadenza: date
    kwh_f1: Decimal
    kwh_f2: Decimal
    kwh_f3: Decimal
    kwh_totale: Decimal
    consumo_annuo_kwh: Decimal
    prezzo_kwh: Decimal
    quota_energia: Decimal
    quota_fissa: Decimal
    quota_potenza: Decimal
    accisa: Decimal
    iva: Decimal
    importo_totale: Decimal
    potenza_impegnata_kw: Decimal
    potenza_disponibile_kw: Decimal
    lettura_precedente_f1: Decimal
    lettura_attuale_f1: Decimal
    lettura_precedente_f2: Decimal
    lettura_attuale_f2: Decimal
    lettura_precedente_f3: Decimal
    lettura_attuale_f3: Decimal
    codice_offerta: str
    nome_offerta: str
    tipologia_offerta: str  # "fisso" | "variabile"
    indice_pun: Decimal


def _due_decimali(valore: Decimal) -> Decimal:
    return valore.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


_PREZZO_KWH = Decimal("0.28")
_ALIQUOTA_ACCISA = Decimal("0.05")
_ALIQUOTA_IVA = Decimal("0.10")

# T4.14 (ADR-040): canone RAI + secondo "Totale da pagare" diverso dal
# "Totale scontrino" — pattern osservato su piu' bollette reali, mai
# tracciato dallo schema (rumore puro, non un campo). Aliquota IVA 22% sul
# canone: coerente col fatto che i reali mostrano aliquote miste nello
# stesso documento (canone tassato diversamente dall'energia, IVA 10%).
_CANONE_RAI_MENSILE = Decimal("9.00")
_ALIQUOTA_IVA_CANONE = Decimal("0.22")


def _genera_dati_fattura(
    rng: random.Random, fornitore_stampato: str, monoraria: bool, bimestrale: bool = False
) -> DatiFattura:
    giorni_min, giorni_max = (55, 62) if bimestrale else (28, 62)
    periodo_da = date(2025, rng.randint(1, 10), rng.randint(1, 28))
    periodo_a = periodo_da + timedelta(days=rng.randint(giorni_min, giorni_max) - 1)
    giorni = (periodo_a - periodo_da).days + 1
    scadenza = periodo_a + timedelta(days=rng.randint(15, 30))

    pod = f"IT{rng.randint(1, 999):03d}E{rng.randint(0, 99_999_999):08d}"
    numero_fattura = str(rng.randint(1_000_000, 9_999_999))

    if monoraria:
        kwh_f1 = _due_decimali(Decimal(rng.randint(2000, 20000)) / 100)
        kwh_f2 = Decimal("0.00")
        kwh_f3 = Decimal("0.00")
    else:
        kwh_f1 = _due_decimali(Decimal(rng.randint(500, 8000)) / 100)
        kwh_f2 = _due_decimali(Decimal(rng.randint(500, 8000)) / 100)
        kwh_f3 = _due_decimali(Decimal(rng.randint(500, 8000)) / 100)
    kwh_totale = _due_decimali(kwh_f1 + kwh_f2 + kwh_f3)
    consumo_annuo_kwh = _due_decimali(kwh_totale * Decimal(365) / Decimal(giorni))

    quota_energia = _due_decimali(kwh_totale * _PREZZO_KWH)
    quota_fissa = _due_decimali(Decimal(rng.randint(500, 2000)) / 100)
    quota_potenza = _due_decimali(Decimal(rng.randint(200, 600)) / 100)
    subtotale = quota_energia + quota_fissa + quota_potenza
    accisa = _due_decimali(subtotale * _ALIQUOTA_ACCISA)
    imponibile = subtotale + accisa
    iva = _due_decimali(imponibile * _ALIQUOTA_IVA)
    importo_totale = _due_decimali(imponibile + iva)

    potenza_impegnata_kw = _due_decimali(Decimal(rng.randint(300, 600)) / 100)
    potenza_disponibile_kw = _due_decimali(potenza_impegnata_kw * Decimal("1.1"))

    lettura_precedente_f1 = _due_decimali(Decimal(rng.randint(10_000, 80_000)) / 10)
    lettura_precedente_f2 = _due_decimali(Decimal(rng.randint(10_000, 80_000)) / 10)
    lettura_precedente_f3 = _due_decimali(Decimal(rng.randint(10_000, 80_000)) / 10)

    tipologia_offerta = "fisso" if rng.random() < 0.5 else "variabile"
    codice_offerta = (
        f"{fornitore_stampato[:3].upper()}{periodo_da.year % 100}"
        f"{'F' if tipologia_offerta == 'fisso' else 'V'}"
    )
    nome_offerta = f"{fornitore_stampato} {'Fissa' if tipologia_offerta == 'fisso' else 'Flex'}"
    indice_pun = _due_decimali(Decimal(rng.randint(8, 18)) / 100)

    return DatiFattura(
        pod=pod,
        fornitore_stampato=fornitore_stampato,
        numero_fattura=numero_fattura,
        periodo_da=periodo_da,
        periodo_a=periodo_a,
        giorni=giorni,
        scadenza=scadenza,
        kwh_f1=kwh_f1,
        kwh_f2=kwh_f2,
        kwh_f3=kwh_f3,
        kwh_totale=kwh_totale,
        consumo_annuo_kwh=consumo_annuo_kwh,
        prezzo_kwh=_PREZZO_KWH,
        quota_energia=quota_energia,
        quota_fissa=quota_fissa,
        quota_potenza=quota_potenza,
        accisa=accisa,
        iva=iva,
        importo_totale=importo_totale,
        potenza_impegnata_kw=potenza_impegnata_kw,
        potenza_disponibile_kw=potenza_disponibile_kw,
        lettura_precedente_f1=lettura_precedente_f1,
        lettura_attuale_f1=_due_decimali(lettura_precedente_f1 + kwh_f1),
        lettura_precedente_f2=lettura_precedente_f2,
        lettura_attuale_f2=_due_decimali(lettura_precedente_f2 + kwh_f2),
        lettura_precedente_f3=lettura_precedente_f3,
        lettura_attuale_f3=_due_decimali(lettura_precedente_f3 + kwh_f3),
        codice_offerta=codice_offerta,
        nome_offerta=nome_offerta,
        tipologia_offerta=tipologia_offerta,
        indice_pun=indice_pun,
    )


def _fmt_it(valore: Decimal) -> str:
    """Formato italiano (virgola decimale, punto per le migliaia) — mai
    quello di str(Decimal) (punto decimale), formato osservato in ZERO delle
    22 bollette reali ispezionate (ADR-040, T4.14). Solo per il testo
    renderizzato nel PDF: l'oracle (_a_oracle) resta nella forma canonica
    di str(Decimal), invariata (ADR-010)."""
    testo_us = f"{valore:,.2f}"  # es. "1,234.56"
    return testo_us.translate(str.maketrans(",.", ".,"))


def _a_oracle(dati: DatiFattura) -> dict[str, str | None]:
    return {
        "pod": dati.pod,
        "fornitore": dati.fornitore_stampato,
        "periodo_da": dati.periodo_da.isoformat(),
        "periodo_a": dati.periodo_a.isoformat(),
        "giorni": str(dati.giorni),
        "kwh_totale": str(dati.kwh_totale),
        "kwh_f1": str(dati.kwh_f1),
        "kwh_f2": str(dati.kwh_f2),
        "kwh_f3": str(dati.kwh_f3),
        "importo_totale": str(dati.importo_totale),
    }


def _testo_periodo(dati: DatiFattura, periodo_mensile: bool, data_con_punti: bool = False) -> str:
    if periodo_mensile:
        mese = MESI_IT[dati.periodo_da.month - 1]
        return f"Periodo di fatturazione: {mese} {dati.periodo_da.year}"
    formato = "%d.%m.%Y" if data_con_punti else "%d/%m/%Y"
    da = dati.periodo_da.strftime(formato)
    a = dati.periodo_a.strftime(formato)
    return f"Dal {da} al {a} ({dati.giorni} giorni)"


# --- contenuto a tre pagine (ADR-039) ---
# Pagina 1: totale da pagare, scadenza, periodo, consumo del periodo,
# consumo annuo su finestra 12 mesi.
# Pagina 2: POD + potenza impegnata/disponibile, scontrino energia, offerta.
# Pagina 3: letture e consumi, imposte.
#
# I campi tracciati dallo schema (schemas/bolletta_luce_it.yaml) restano
# etichettati esattamente come le regex del tier 0 li cercano (T4.9 non
# tocca schema o estrazione): "POD: ...", "Fornitore: ...", "Dal ... al
# ... (N giorni)" / "Periodo di fatturazione: ...", "Energia FN: ... kWh",
# "Importo totale: EUR ...". Il resto e' realismo strutturale, non tracciato.

PagineFattura = tuple[list[str], ...]


def _righe_modulo_pagamento() -> list[str]:
    """T4.14 (ADR-041): pagina di modulo di pagamento allegata — nessuna
    delle etichette che le regex del tier 0 cercano, struttura estranea al
    contenuto della bolletta (bollettino postale/SEPA osservato su piu'
    bollette reali)."""
    return [
        "MODULO DI PAGAMENTO",
        "Bollettino postale allegato",
        "Conto corrente: da compilare a cura del pagatore",
        "Causale: pagamento utenza",
        "ATTENZIONE: piegare e staccare lungo le perforazioni",
    ]


def _canone_extra(dati: DatiFattura) -> tuple[Decimal, Decimal, Decimal]:
    """canone_rai, iva_canone, totale_da_pagare (T4.14) — proporzionale ai
    giorni fatturati, mai un campo tracciato: solo rumore vicino al campo
    che lo e' davvero (importo_totale, "Totale scontrino")."""
    canone_rai = _due_decimali(_CANONE_RAI_MENSILE * Decimal(dati.giorni) / Decimal(30))
    iva_canone = _due_decimali(canone_rai * _ALIQUOTA_IVA_CANONE)
    totale_da_pagare = _due_decimali(dati.importo_totale + canone_rai + iva_canone)
    return canone_rai, iva_canone, totale_da_pagare


def _righe_pagina1(dati: DatiFattura, flags: Flags) -> list[str]:
    righe = [
        f"Fattura n. {dati.numero_fattura}",
        f"Fornitore: {dati.fornitore_stampato}",
        "TOTALE DA PAGARE",
        f"Importo totale: EUR {_fmt_it(dati.importo_totale)}",
        f"Scadenza: {dati.scadenza.strftime('%d/%m/%Y')}",
        _testo_periodo(dati, flags.periodo_mensile, flags.data_con_punti),
        f"Consumo del periodo: {_fmt_it(dati.kwh_totale)} kWh",
        f"Consumo annuo (ultimi 12 mesi): {_fmt_it(dati.consumo_annuo_kwh)} kWh",
    ]
    if flags.consumo_stimato:
        righe.append(
            "Nota: consumo stimato, soggetto a conguaglio/ricalcolo nella prossima fattura"
        )
    return righe


def _righe_pagina2(dati: DatiFattura, flags: Flags) -> list[str]:
    return [
        f"POD: {dati.pod}",
        f"Potenza impegnata: {_fmt_it(dati.potenza_impegnata_kw)} kW",
        f"Potenza disponibile: {_fmt_it(dati.potenza_disponibile_kw)} kW",
        "SCONTRINO DELL'ENERGIA",
        "Voce                 Quantita'        Prezzo medio        Importo",
        f"Energia F1: {_fmt_it(dati.kwh_f1)} kWh    x {_fmt_it(dati.prezzo_kwh)} EUR/kWh",
        f"Energia F2: {_fmt_it(dati.kwh_f2)} kWh    x {_fmt_it(dati.prezzo_kwh)} EUR/kWh",
        f"Energia F3: {_fmt_it(dati.kwh_f3)} kWh    x {_fmt_it(dati.prezzo_kwh)} EUR/kWh",
        f"Energia totale: {_fmt_it(dati.kwh_totale)} kWh    "
        f"Importo: EUR {_fmt_it(dati.quota_energia)}",
        f"Quota fissa: EUR {_fmt_it(dati.quota_fissa)}",
        f"Quota potenza: EUR {_fmt_it(dati.quota_potenza)}",
        f"Accise e IVA: EUR {_fmt_it(dati.accisa + dati.iva)}",
        f"Totale scontrino: EUR {_fmt_it(dati.importo_totale)}",
        *(
            [
                f"Canone RAI: EUR {_fmt_it(_canone_extra(dati)[0])}",
                f"Totale da pagare: EUR {_fmt_it(_canone_extra(dati)[2])}",
            ]
            if flags.canone_extra
            else []
        ),
        "",
        "BOX DELL'OFFERTA",
        f"Nome offerta: {dati.nome_offerta}",
        f"Tipologia: {dati.tipologia_offerta}",
        f"Tipologia prezzo: {'monoraria' if flags.monoraria else 'fasce'}",
        f"Codice offerta: {dati.codice_offerta}",
        "Formula: prezzo indicizzato all'indice PUN",
        f"Indice PUN: {_fmt_it(dati.indice_pun)} EUR/kWh",
    ]


def _righe_pagina3(dati: DatiFattura, flags: Flags) -> list[str]:
    return [
        "LETTURE E CONSUMI",
        f"F1  precedente {_fmt_it(dati.lettura_precedente_f1)} kWh  ->  attuale "
        f"{_fmt_it(dati.lettura_attuale_f1)} kWh  ->  "
        f"consumo fatturato {_fmt_it(dati.kwh_f1)} kWh",
        f"F2  precedente {_fmt_it(dati.lettura_precedente_f2)} kWh  ->  attuale "
        f"{_fmt_it(dati.lettura_attuale_f2)} kWh  ->  "
        f"consumo fatturato {_fmt_it(dati.kwh_f2)} kWh",
        f"F3  precedente {_fmt_it(dati.lettura_precedente_f3)} kWh  ->  attuale "
        f"{_fmt_it(dati.lettura_attuale_f3)} kWh  ->  "
        f"consumo fatturato {_fmt_it(dati.kwh_f3)} kWh",
        "",
        "IMPOSTE",
        f"Accisa sui consumi: EUR {_fmt_it(dati.accisa)}",
        f"IVA (10% su imponibile): EUR {_fmt_it(dati.iva)}",
        *(
            [f"IVA (22% su canone RAI): EUR {_fmt_it(_canone_extra(dati)[1])}"]
            if flags.canone_extra
            else []
        ),
    ]


# --- rendering digitale (reportlab), tre layout distinti ---


_COLORE_LOGO: dict[str, tuple[int, int, int]] = {
    "Alfa Energia": (230, 126, 34),
    "Beta Luce": (41, 128, 185),
    "Gamma Power": (39, 174, 96),
}


def _immagine_logo(colore: tuple[int, int, int]) -> ImageReader:
    img = Image.new("RGB", (200, 60), color=colore)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _immagine_qr_finta(rng: random.Random, celle_lato: int = 16, px_cella: int = 6) -> ImageReader:
    """QR finto: griglia bianco/nero pseudo-casuale, stessa forma e posizione
    di un QR reale ma non decodificabile. Basta ad occupare un blocco
    immagine plausibile in dimensione e posizione (ADR-021)."""
    lato_px = celle_lato * px_cella
    img = Image.new("L", (lato_px, lato_px), color=255)
    disegno = ImageDraw.Draw(img)
    for riga in range(celle_lato):
        for colonna in range(celle_lato):
            if rng.random() < 0.5:
                x0, y0 = colonna * px_cella, riga * px_cella
                disegno.rectangle([x0, y0, x0 + px_cella, y0 + px_cella], fill=0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _disegna_logo_e_qr(c: Canvas, rng: random.Random, layout: str) -> None:
    """Logo in alto a sinistra, QR finto in alto a destra: le tre bollette
    reali esaminate li avevano entrambi, il corpus sintetico prima no
    (ADR-021)."""
    larghezza, altezza = A4
    c.drawImage(
        _immagine_logo(_COLORE_LOGO[layout]), 50, altezza - 60, width=120, height=35, mask="auto"
    )
    lato_qr = 90.0
    c.drawImage(
        _immagine_qr_finta(rng),
        larghezza - lato_qr - 50,
        altezza - lato_qr - 45,
        width=lato_qr,
        height=lato_qr,
    )


def _disegna_layout_alfa(
    c: Canvas, rng: random.Random, blocchi: list[PagineFattura], fornitore_stampato: str
) -> None:
    _, altezza = A4
    prima_pagina = True
    for pagine in blocchi:
        for pagina_righe in pagine:
            if not prima_pagina:
                c.showPage()
            prima_pagina = False
            _disegna_logo_e_qr(c, rng, "Alfa Energia")
            y = altezza - 100
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, y, "ALFA ENERGIA — Bolletta luce")
            y -= 30
            c.setFont("Helvetica", 11)
            for riga in pagina_righe:
                c.drawString(50, y, riga)
                y -= 16


def _disegna_layout_beta(
    c: Canvas, rng: random.Random, blocchi: list[PagineFattura], fornitore_stampato: str
) -> None:
    # Testata allineata al campo "fornitore" dell'oracle: prima diceva
    # sempre "Beta Luce S.r.l." a prescindere da fornitore_esteso, un
    # fornitore diverso da quello nella riga "Fornitore: ..." che il tier 0
    # legge — il modello vedeva due nomi sulla stessa pagina e inventava
    # scegliendo quello sbagliato (T4.11, campo inventato su S008).
    larghezza, altezza = A4
    prima_pagina = True
    for pagine in blocchi:
        for pagina_righe in pagine:
            if not prima_pagina:
                c.showPage()
            prima_pagina = False
            _disegna_logo_e_qr(c, rng, "Beta Luce")
            y = altezza - 100
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(larghezza / 2, y, fornitore_stampato)
            c.line(50, y - 8, larghezza - 50, y - 8)
            y -= 40
            c.setFont("Helvetica-Oblique", 11)
            for riga in pagina_righe:
                c.drawString(70, y, riga)
                y -= 16


def _disegna_layout_gamma(
    c: Canvas, rng: random.Random, blocchi: list[PagineFattura], fornitore_stampato: str
) -> None:
    _, altezza = A4
    prima_pagina = True
    for pagine in blocchi:
        for pagina_righe in pagine:
            if not prima_pagina:
                c.showPage()
            prima_pagina = False
            _disegna_logo_e_qr(c, rng, "Gamma Power")
            y = altezza - 90
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y, "GAMMA POWER")
            y -= 20
            c.setFont("Helvetica", 9)
            c.drawString(50, y, "www.gammapower-esempio.it")
            y -= 30
            c.setFont("Courier", 10)
            for riga in pagina_righe:
                c.drawString(50, y, "> " + riga)
                y -= 15


_DISEGNATORI = {
    "Alfa Energia": _disegna_layout_alfa,
    "Beta Luce": _disegna_layout_beta,
    "Gamma Power": _disegna_layout_gamma,
}


def _pdf_digitale(
    layout: str, blocchi: list[PagineFattura], rng: random.Random, fornitore_stampato: str
) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=A4, invariant=1)
    _DISEGNATORI[layout](c, rng, blocchi, fornitore_stampato)
    c.showPage()
    c.save()
    return buf.getvalue()


# --- rendering "scansione": rasterizzazione del layout digitale (ADR-038) ---


_ALFABETO_RUMORE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _frammenti_rumorosi(rng: random.Random, n: int = 12) -> list[str]:
    """Poche decine di caratteri totali: frammenti corti, tipo intestazioni
    digitali o numeri isolati sopra un corpo immagine (ADR-019)."""
    return [
        "".join(rng.choice(_ALFABETO_RUMORE) for _ in range(rng.randint(2, 4))) for _ in range(n)
    ]


@dataclass(frozen=True)
class LivelloDegrado:
    nome: str
    blur_radius: float
    fattore_downscale: float  # 1.0 = nessun downscale/upscale
    qualita_jpeg: int


# Livello di produzione (T4.10, C1; ADR-036). Misura, scripts/calibra_degrado.py,
# n=10 documenti/livello, 3 campi obbligatori (pod/periodo_da/periodo_a):
#
#   medio (0.6, 1.5, 70)            100%
#   aggressivo (1.2, 2.0, 55)        97%
#   quasi-lossless (0.0, 1.0, 95)    83%
#
# Scelto MEDIO, non il migliore in assoluto. Il migliore misurato era
# "leggero" a pari merito col 100%, ma scegliere il livello che massimizza
# il recupero significa ottimizzare il corpus per far bella figura —
# esattamente l'errore gia' corretto tre volte in questo progetto (copertura
# immagine tautologica ADR-021, scansioni a zero caratteri ADR-019, degrado
# illeggibile ADR-036 stesso). MEDIO e' il punto centrale della scala
# misurata: non il piu' comodo per il benchmark, non il piu' vicino al
# collasso — un compromesso motivato dal margine, non dal risultato.
#
# Risultato controintuitivo, annotato perche' e' vero e non ovvio: MENO
# degrado non implica PIU' leggibile. Quasi-lossless (zero blur, zero
# downscale, JPEG 95) recupera peggio (83%) di aggressivo (97%). Un filo di
# sfocatura/compressione ammorbidisce i bordi vettoriali netti del font
# reportlab in modi che aiutano il motore OCR a segmentare i caratteri;
# senza, i bordi duri del rendering ad alta risoluzione confondono Tesseract
# piu' spesso. Non e' rumore di campione (n=10, scarto consistente) — e' un
# effetto reale del rendering, il motivo per cui "degrado zero" non era mai
# stata l'ipotesi da testare per prima.
DEGRADO_DEFAULT = LivelloDegrado("medio", blur_radius=0.6, fattore_downscale=1.5, qualita_jpeg=70)

# Caso difficile dichiarato (--scansione-aggressiva): leggibile ma al limite
# (97% misurato), non il livello di produzione. Serve a misurare quanto il
# tier 1 degrada quando il documento e' peggiore del caso comune.
DEGRADO_AGGRESSIVO = LivelloDegrado(
    "aggressivo", blur_radius=1.2, fattore_downscale=2.0, qualita_jpeg=55
)

# --scansione-illeggibile: comportamento atteso e' reject, non estrazione
# (ADR-036) — un caso volutamente oltre il collasso, piu' severo di
# "aggressivo". Non misurato nello sweep di calibrazione (che cerca il
# livello di produzione, non il fondo della scala): il punto di questo
# livello e' proprio essere fuori dalla scala utile. Verificato a parte
# (non per intuito, la regola vale anche qui): un primo tentativo
# (blur 3.0, downscale 4.0, jpeg 15) recuperava ancora 14/15 campi — il
# font vettoriale reportlab e' piu' robusto del vecchio font PIL anche sotto
# degrado pesante. Questi parametri, misurati, danno 0/15.
DEGRADO_ILLEGGIBILE = LivelloDegrado(
    "illeggibile", blur_radius=4.0, fattore_downscale=8.0, qualita_jpeg=10
)

# ADR-038: rasterizzare "ad alta risoluzione" prima del degrado, non alla
# risoluzione a cui il documento verra' poi riletto (150dpi, eval.run.
# RISOLUZIONE_RENDER_DPI) — evita di sommare due arrotondamenti indipendenti.
_RISOLUZIONE_RASTER_DPI = 300


def _pdf_scansione(
    layout: str,
    blocchi: list[PagineFattura],
    rng: random.Random,
    sporca: bool,
    fornitore_stampato: str,
    livello: LivelloDegrado = DEGRADO_DEFAULT,
) -> bytes:
    """ADR-038: una scansione e' il rendering dello STESSO layout digitale,
    non un documento disegnato a parte. Percorso: layout reportlab identico
    al digitale -> raster ad alta risoluzione -> degrado -> pagina immagine,
    senza text layer (a meno di --scansione-sporca, che aggiunge rumore reale
    SOPRA l'immagine, non testo del documento)."""
    pdf_digitale = _pdf_digitale(layout, blocchi, rng, fornitore_stampato)

    buf_pdf = io.BytesIO()
    c = Canvas(buf_pdf, pagesize=A4, invariant=1)
    larghezza_pt, altezza_pt = A4

    with pdfplumber.open(io.BytesIO(pdf_digitale)) as documento:
        for indice, pagina in enumerate(documento.pages):
            if indice > 0:
                c.showPage()

            immagine = pagina.to_image(resolution=_RISOLUZIONE_RASTER_DPI).original.convert("L")
            if livello.blur_radius > 0:
                immagine = immagine.filter(ImageFilter.GaussianBlur(radius=livello.blur_radius))
            if livello.fattore_downscale > 1.0:
                larghezza_px, altezza_px = immagine.size
                piccola = immagine.resize(
                    (
                        int(larghezza_px / livello.fattore_downscale),
                        int(altezza_px / livello.fattore_downscale),
                    )
                )
                immagine = piccola.resize((larghezza_px, altezza_px))

            buf_img = io.BytesIO()
            immagine.save(buf_img, format="JPEG", quality=livello.qualita_jpeg)
            buf_img.seek(0)
            c.drawImage(ImageReader(buf_img), 0, 0, width=larghezza_pt, height=altezza_pt)

            if sporca:
                # text layer rado e rumoroso SOPRA l'immagine: caratteri reali
                # ed estraibili, a differenza del contenuto "cotto" nei pixel.
                c.setFont("Helvetica", 6)
                for frammento in _frammenti_rumorosi(rng):
                    x = rng.uniform(20, larghezza_pt - 20)
                    y_pt = rng.uniform(20, altezza_pt - 20)
                    c.drawString(x, y_pt, frammento)

    c.showPage()
    c.save()
    return buf_pdf.getvalue()


# --- rendering "ibrida": immagine grande + intestazione digitale reale ---

_PAROLE_INTESTAZIONE_IBRIDA = (
    "Comunicazione relativa alla fornitura di energia elettrica per il "
    "periodo di riferimento indicato in bolletta con dettaglio dei consumi "
    "rilevati dal contatore e della potenza impegnata per l'utenza"
).split()


def _immagine_grande_ibrida(rng: random.Random) -> ImageReader:
    """Immagine 'allegato' generica (non testo cotto): qualche rettangolo
    grigio a tonalita' variabile, solo per occupare un'area plausibile —
    il contenuto non e' rilevante, conta la geometria (ADR-021)."""
    larghezza_px, altezza_px = 800, 1000
    img = Image.new("L", (larghezza_px, altezza_px), color=200)
    disegno = ImageDraw.Draw(img)
    for _ in range(30):
        x0 = rng.randint(0, larghezza_px)
        y0 = rng.randint(0, altezza_px)
        x1 = min(larghezza_px, x0 + rng.randint(20, 120))
        y1 = min(altezza_px, y0 + rng.randint(20, 120))
        disegno.rectangle([x0, y0, x1, y1], fill=rng.randint(120, 230))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    buf.seek(0)
    return ImageReader(buf)


def _pdf_ibrida(rng: random.Random) -> bytes:
    """Pagina che rompe entrambe le feature del triage per costruzione
    (ADR-021): immagine grande (~85% dell'area) PIU' un'intestazione
    digitale reale in alto (~20-30 parole, densita' paragonabile al
    digitale — testo vero, non cotto nei pixel). Non e' legata al contenuto
    delle fatture: serve solo a misurare dove cade il triage, non a
    rappresentare un documento reale specifico.
    """
    buf_pdf = io.BytesIO()
    c = Canvas(buf_pdf, pagesize=A4, invariant=1)
    larghezza_pt, altezza_pt = A4

    c.setFont("Helvetica", 10)
    y = altezza_pt - 50
    parole = _PAROLE_INTESTAZIONE_IBRIDA
    for i in range(0, len(parole), 8):
        c.drawString(50, y, " ".join(parole[i : i + 8]))
        y -= 14

    larghezza_img = larghezza_pt * 0.95
    altezza_img = altezza_pt * 0.85
    x_img = (larghezza_pt - larghezza_img) / 2
    c.drawImage(_immagine_grande_ibrida(rng), x_img, 20, width=larghezza_img, height=altezza_img)

    c.showPage()
    c.save()
    return buf_pdf.getvalue()


def _ruota(pdf_bytes: bytes) -> bytes:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for pagina in reader.pages:
        pagina.rotate(180)
        writer.add_page(pagina)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


_LETTERE_ISTANZA = "abcdefghijklmnopqrstuvwxyz"

# ADR-039: una fattura e' sempre a tre pagine (totale/scadenza/periodo; POD e
# scontrino; letture e imposte) — tranne --pagina-ibrida, un caso a se' che
# non passa mai da DatiFattura/blocchi.
PAGINE_PER_FATTURA = 3


def genera_documento(
    rng: random.Random, doc_id: str, layout: str, flags: Flags
) -> tuple[bytes, dict[str, dict[str, str | None]], dict[str, dict[str, object]]]:
    """Genera un documento sintetico: pdf, voci oracle, voci metadata.

    Le chiavi di oracle_entries e metadata_entries sono id OPACHI di istanza
    documentale (ADR-014-bis): "S007" per un documento singolo, "S007a" /
    "S007b" per --multi-fattura. Mai interpretate: il legame con il file
    fisico vive solo in metadata_entries[...]["file"].
    """
    flags = _flags_effettivi(layout, flags)
    fornitore_stampato = NOME_ESTESO[layout] if flags.fornitore_esteso else layout

    n_fatture = 2 if flags.multi_fattura else 1
    bimestrale = layout == "Alfa Energia"
    fatture = [
        _genera_dati_fattura(rng, fornitore_stampato, flags.monoraria, bimestrale=bimestrale)
        for _ in range(n_fatture)
    ]
    blocchi: list[PagineFattura] = [
        (
            _righe_pagina1(dati, flags),
            _righe_pagina2(dati, flags),
            _righe_pagina3(dati, flags),
            *([_righe_modulo_pagamento()] if flags.pagine_allegate else []),
        )
        for dati in fatture
    ]

    e_scansione = (
        flags.scansione
        or flags.scansione_sporca
        or flags.scansione_aggressiva
        or flags.scansione_illeggibile
    )
    if flags.pagina_ibrida:
        pdf_bytes = _pdf_ibrida(rng)
    elif e_scansione:
        if flags.scansione_illeggibile:
            livello = DEGRADO_ILLEGGIBILE
        elif flags.scansione_aggressiva:
            livello = DEGRADO_AGGRESSIVO
        else:
            livello = DEGRADO_DEFAULT
        pdf_bytes = _pdf_scansione(
            layout,
            blocchi,
            rng,
            sporca=flags.scansione_sporca,
            fornitore_stampato=fornitore_stampato,
            livello=livello,
        )
    else:
        pdf_bytes = _pdf_digitale(layout, blocchi, rng, fornitore_stampato)
    if flags.ruotata:
        pdf_bytes = _ruota(pdf_bytes)

    nome_file = f"{doc_id}.pdf"
    if n_fatture == 1:
        istanze = [(doc_id, fatture[0])]
    else:
        istanze = [(f"{doc_id}{_LETTERE_ISTANZA[i]}", dati) for i, dati in enumerate(fatture)]

    oracle_entries = {instanza_id: _a_oracle(dati) for instanza_id, dati in istanze}

    if flags.pagina_ibrida:
        qualita = "ibrida"
    elif flags.scansione_illeggibile:
        qualita = "scansione_illeggibile"  # atteso: reject, non estrazione (ADR-036)
    elif flags.scansione_aggressiva:
        qualita = "scansione_aggressiva"  # caso difficile dichiarato, leggibile (97%)
    elif flags.scansione_sporca:
        qualita = "scansione_sporca"
    elif flags.scansione:
        qualita = "scansione_degradata"
    else:
        qualita = "digitale"

    pagine_per_fattura = 1 if flags.pagina_ibrida else PAGINE_PER_FATTURA

    metadata_entries = {}
    for indice, (instanza_id, _) in enumerate(istanze):
        pagina_da = indice * pagine_per_fattura + 1
        pagina_a = pagina_da + pagine_per_fattura - 1
        metadata_entries[instanza_id] = {
            "file": nome_file,
            "pagine": [pagina_da, pagina_a],
            "layout": layout,
            "tipo_lettura": "stimata" if flags.consumo_stimato else "effettiva",
            "monoraria": flags.monoraria,
            "qualita": qualita,
            "flag_attivi": flags.attivi(),
        }

    return pdf_bytes, oracle_entries, metadata_entries


def genera_corpus(
    seed: int,
    n: int = 10,
    out_dir: Path = REPO_ROOT / "corpus" / "synth",
    oracle_path: Path = REPO_ROOT / "corpus" / "attesi.json",
    metadata_path: Path = REPO_ROOT / "corpus" / "metadata.json",
    flags: Flags | None = None,
) -> None:
    flags = flags or Flags()
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    documenti_oracle: dict[str, dict[str, str | None]] = {}
    metadata: dict[str, dict[str, object]] = {}

    for i in range(n):
        doc_id = f"S{i + 1:03d}"
        layout = LAYOUTS[i % len(LAYOUTS)]
        pdf_bytes, oracle_entries, metadata_entries = genera_documento(rng, doc_id, layout, flags)
        (out_dir / f"{doc_id}.pdf").write_bytes(pdf_bytes)
        documenti_oracle.update(oracle_entries)
        metadata.update(metadata_entries)

    oracle = {"oracle_version": 1, "documento": "bolletta_luce_it", "documenti": documenti_oracle}
    oracle_path.write_text(json.dumps(oracle, ensure_ascii=False, indent=2) + "\n")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")


def genera_corpus_composito(
    seed: int,
    out_dir: Path = REPO_ROOT / "corpus" / "synth",
    oracle_path: Path = REPO_ROOT / "corpus" / "attesi.json",
    metadata_path: Path = REPO_ROOT / "corpus" / "metadata.json",
    composizione: tuple[CasoComposizione, ...] = COMPOSIZIONE_DEFAULT,
) -> None:
    """Corpus di default (ADR-025): miscela dichiarata, non n copie uniformi.
    metadata.json porta un blocco "composizione" in testa con i conteggi, cosi'
    chi apre il repo vede cosa contiene il benchmark senza aprire i PDF."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    documenti_oracle: dict[str, dict[str, str | None]] = {}
    documenti_metadata: dict[str, dict[str, object]] = {}
    conteggi: dict[str, int] = {}

    for i, caso in enumerate(composizione):
        doc_id = f"S{i + 1:03d}"
        pdf_bytes, oracle_entries, metadata_entries = genera_documento(
            rng, doc_id, caso.layout, caso.flags
        )
        (out_dir / f"{doc_id}.pdf").write_bytes(pdf_bytes)
        documenti_oracle.update(oracle_entries)
        documenti_metadata.update(metadata_entries)
        conteggi[caso.etichetta] = conteggi.get(caso.etichetta, 0) + 1

    oracle = {"oracle_version": 1, "documento": "bolletta_luce_it", "documenti": documenti_oracle}
    oracle_path.write_text(json.dumps(oracle, ensure_ascii=False, indent=2) + "\n")

    metadata = {"composizione": conteggi, "documenti": documenti_metadata}
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un corpus sintetico di bollette luce.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "corpus" / "synth")
    parser.add_argument("--oracle-out", type=Path, default=REPO_ROOT / "corpus" / "attesi.json")
    parser.add_argument("--metadata-out", type=Path, default=REPO_ROOT / "corpus" / "metadata.json")
    for nome in FLAG_NOMI:
        parser.add_argument(f"--{nome.replace('_', '-')}", action="store_true")
    args = parser.parse_args()

    flags = Flags(**{nome: getattr(args, nome) for nome in FLAG_NOMI})

    if flags == Flags() and args.n is None:
        # Nessun flag, nessun --n esplicito: corpus di default composito
        # (ADR-025), non n copie uniformi.
        genera_corpus_composito(
            seed=args.seed,
            out_dir=args.out,
            oracle_path=args.oracle_out,
            metadata_path=args.metadata_out,
        )
        print(f"generati {len(COMPOSIZIONE_DEFAULT)} documenti (corpus composito) in {args.out}")
        return 0

    n = args.n if args.n is not None else 10
    genera_corpus(
        seed=args.seed,
        n=n,
        out_dir=args.out,
        oracle_path=args.oracle_out,
        metadata_path=args.metadata_out,
        flags=flags,
    )
    print(f"generati {n} documenti in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
