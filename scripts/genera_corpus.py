"""Generatore di bollette luce sintetiche (Blocco 1-bis, ADR-012/013).

Principio: l'oracle e' l'INPUT del generatore, non una lettura del PDF. I
valori si generano prima, il PDF li rappresenta dopo: e' esatto per
costruzione. Nessun dato reale: anagrafiche, fornitori e POD sono inventati.
"""

from __future__ import annotations

import argparse
import io
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
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
    "pagina_ibrida",
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
    pagina_ibrida: bool = False

    def attivi(self) -> list[str]:
        return [nome for nome in FLAG_NOMI if getattr(self, nome)]


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
)


@dataclass(frozen=True)
class DatiFattura:
    pod: str
    fornitore_stampato: str
    numero_fattura: str
    periodo_da: date
    periodo_a: date
    giorni: int
    kwh_f1: Decimal
    kwh_f2: Decimal
    kwh_f3: Decimal
    kwh_totale: Decimal
    importo_totale: Decimal


def _due_decimali(valore: Decimal) -> Decimal:
    return valore.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _genera_dati_fattura(
    rng: random.Random, fornitore_stampato: str, monoraria: bool
) -> DatiFattura:
    periodo_da = date(2025, rng.randint(1, 10), rng.randint(1, 28))
    periodo_a = periodo_da + timedelta(days=rng.randint(28, 62) - 1)
    giorni = (periodo_a - periodo_da).days + 1

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

    prezzo_kwh = Decimal("0.28")
    quota_fissa = _due_decimali(Decimal(rng.randint(500, 2000)) / 100)
    importo_totale = _due_decimali(kwh_totale * prezzo_kwh + quota_fissa)

    return DatiFattura(
        pod=pod,
        fornitore_stampato=fornitore_stampato,
        numero_fattura=numero_fattura,
        periodo_da=periodo_da,
        periodo_a=periodo_a,
        giorni=giorni,
        kwh_f1=kwh_f1,
        kwh_f2=kwh_f2,
        kwh_f3=kwh_f3,
        kwh_totale=kwh_totale,
        importo_totale=importo_totale,
    )


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


def _testo_periodo(dati: DatiFattura, periodo_mensile: bool) -> str:
    if periodo_mensile:
        mese = MESI_IT[dati.periodo_da.month - 1]
        return f"Periodo di fatturazione: {mese} {dati.periodo_da.year}"
    da = dati.periodo_da.strftime("%d/%m/%Y")
    a = dati.periodo_a.strftime("%d/%m/%Y")
    return f"Dal {da} al {a} ({dati.giorni} giorni)"


def _righe_fattura(dati: DatiFattura, flags: Flags) -> list[str]:
    righe = [
        f"Fattura n. {dati.numero_fattura}",
        f"POD: {dati.pod}",
        f"Fornitore: {dati.fornitore_stampato}",
        _testo_periodo(dati, flags.periodo_mensile),
        f"Energia F1: {dati.kwh_f1} kWh",
        f"Energia F2: {dati.kwh_f2} kWh",
        f"Energia F3: {dati.kwh_f3} kWh",
        f"Energia totale: {dati.kwh_totale} kWh",
        f"Importo totale: EUR {dati.importo_totale}",
    ]
    if flags.consumo_stimato:
        righe.append("Nota: consumo stimato, soggetto a conguaglio nella prossima fattura")
    return righe


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


def _disegna_layout_alfa(c: Canvas, rng: random.Random, blocchi: list[list[str]]) -> None:
    _, altezza = A4
    for indice, blocco in enumerate(blocchi):
        if indice > 0:
            c.showPage()  # --multi-fattura: una pagina per fattura (T2.4)
        _disegna_logo_e_qr(c, rng, "Alfa Energia")
        y = altezza - 100
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, "ALFA ENERGIA — Bolletta luce")
        y -= 30
        c.setFont("Helvetica", 11)
        for riga in blocco:
            c.drawString(50, y, riga)
            y -= 16


def _disegna_layout_beta(c: Canvas, rng: random.Random, blocchi: list[list[str]]) -> None:
    larghezza, altezza = A4
    for indice, blocco in enumerate(blocchi):
        if indice > 0:
            c.showPage()
        _disegna_logo_e_qr(c, rng, "Beta Luce")
        y = altezza - 100
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(larghezza / 2, y, "Beta Luce S.r.l.")
        c.line(50, y - 8, larghezza - 50, y - 8)
        y -= 40
        c.setFont("Helvetica-Oblique", 11)
        for riga in blocco:
            c.drawString(70, y, riga)
            y -= 16


def _disegna_layout_gamma(c: Canvas, rng: random.Random, blocchi: list[list[str]]) -> None:
    _, altezza = A4
    for indice, blocco in enumerate(blocchi):
        if indice > 0:
            c.showPage()
        _disegna_logo_e_qr(c, rng, "Gamma Power")
        y = altezza - 90
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "GAMMA POWER")
        y -= 20
        c.setFont("Helvetica", 9)
        c.drawString(50, y, "www.gammapower-esempio.it")
        y -= 30
        c.setFont("Courier", 10)
        for riga in blocco:
            c.drawString(50, y, "> " + riga)
            y -= 15


_DISEGNATORI = {
    "Alfa Energia": _disegna_layout_alfa,
    "Beta Luce": _disegna_layout_beta,
    "Gamma Power": _disegna_layout_gamma,
}


def _pdf_digitale(layout: str, blocchi: list[list[str]], rng: random.Random) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=A4, invariant=1)
    _DISEGNATORI[layout](c, rng, blocchi)
    c.showPage()
    c.save()
    return buf.getvalue()


# --- rendering "scansione": immagine degradata, nessun text layer ---


_ALFABETO_RUMORE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _frammenti_rumorosi(rng: random.Random, n: int = 12) -> list[str]:
    """Poche decine di caratteri totali: frammenti corti, tipo intestazioni
    digitali o numeri isolati sopra un corpo immagine (ADR-019)."""
    return [
        "".join(rng.choice(_ALFABETO_RUMORE) for _ in range(rng.randint(2, 4))) for _ in range(n)
    ]


def _pdf_scansione(blocchi: list[list[str]], rng: random.Random, sporca: bool) -> bytes:
    larghezza_px, altezza_px = 1240, 1754  # ~150dpi su A4
    img = Image.new("L", (larghezza_px, altezza_px), color=255)
    disegno = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    y = 60
    for blocco in blocchi:
        for riga in blocco:
            disegno.text((60, y), riga, fill=0, font=font)
            y += 22
        y += 25

    # degrado deterministico: sfocatura + downscale/upscale (artefatti di
    # ricampionamento), nessuna sorgente di casualita' non seedata.
    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    piccola = img.resize((larghezza_px // 2, altezza_px // 2))
    img = piccola.resize((larghezza_px, altezza_px))

    buf_img = io.BytesIO()
    img.save(buf_img, format="JPEG", quality=55)
    buf_img.seek(0)

    buf_pdf = io.BytesIO()
    c = Canvas(buf_pdf, pagesize=A4, invariant=1)
    larghezza_pt, altezza_pt = A4
    c.drawImage(ImageReader(buf_img), 0, 0, width=larghezza_pt, height=altezza_pt)

    if sporca:
        # text layer rado e rumoroso SOPRA l'immagine: caratteri reali ed
        # estraibili, a differenza del testo "cotto" nei pixel sopra.
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


def genera_documento(
    rng: random.Random, doc_id: str, layout: str, flags: Flags
) -> tuple[bytes, dict[str, dict[str, str | None]], dict[str, dict[str, object]]]:
    """Genera un documento sintetico: pdf, voci oracle, voci metadata.

    Le chiavi di oracle_entries e metadata_entries sono id OPACHI di istanza
    documentale (ADR-014-bis): "S007" per un documento singolo, "S007a" /
    "S007b" per --multi-fattura. Mai interpretate: il legame con il file
    fisico vive solo in metadata_entries[...]["file"].
    """
    fornitore_stampato = NOME_ESTESO[layout] if flags.fornitore_esteso else layout

    n_fatture = 2 if flags.multi_fattura else 1
    fatture = [
        _genera_dati_fattura(rng, fornitore_stampato, flags.monoraria) for _ in range(n_fatture)
    ]
    blocchi = [_righe_fattura(dati, flags) for dati in fatture]

    if flags.pagina_ibrida:
        pdf_bytes = _pdf_ibrida(rng)
    elif flags.scansione or flags.scansione_sporca:
        pdf_bytes = _pdf_scansione(blocchi, rng, sporca=flags.scansione_sporca)
    else:
        pdf_bytes = _pdf_digitale(layout, blocchi, rng)
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
    elif flags.scansione_sporca:
        qualita = "scansione_sporca"
    elif flags.scansione:
        qualita = "scansione_degradata"
    else:
        qualita = "digitale"

    # Solo il percorso digitale mette --multi-fattura su pagine separate
    # (T2.4: serve al pattern di segmentazione un confine di pagina reale).
    # scansione/ibrida restano a pagina singola: il rendering non le separa.
    e_multipagina = n_fatture > 1 and qualita == "digitale"

    metadata_entries = {}
    for indice, (instanza_id, _) in enumerate(istanze):
        pagina = indice + 1 if e_multipagina else 1
        metadata_entries[instanza_id] = {
            "file": nome_file,
            "pagine": [pagina, pagina],
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
