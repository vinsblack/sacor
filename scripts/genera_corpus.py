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

    def attivi(self) -> list[str]:
        return [nome for nome in FLAG_NOMI if getattr(self, nome)]


@dataclass(frozen=True)
class DatiFattura:
    pod: str
    fornitore_stampato: str
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


def _disegna_layout_alfa(c: Canvas, blocchi: list[list[str]]) -> None:
    _, altezza = A4
    y = altezza - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "ALFA ENERGIA — Bolletta luce")
    y -= 30
    for blocco in blocchi:
        c.setFont("Helvetica", 11)
        for riga in blocco:
            c.drawString(50, y, riga)
            y -= 16
        y -= 20


def _disegna_layout_beta(c: Canvas, blocchi: list[list[str]]) -> None:
    larghezza, altezza = A4
    y = altezza - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(larghezza / 2, y, "Beta Luce S.r.l.")
    c.line(50, y - 8, larghezza - 50, y - 8)
    y -= 40
    for blocco in blocchi:
        c.setFont("Helvetica-Oblique", 11)
        for riga in blocco:
            c.drawString(70, y, riga)
            y -= 16
        y -= 20


def _disegna_layout_gamma(c: Canvas, blocchi: list[list[str]]) -> None:
    _, altezza = A4
    y = altezza - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "GAMMA POWER")
    y -= 20
    c.setFont("Helvetica", 9)
    c.drawString(50, y, "www.gammapower-esempio.it")
    y -= 30
    for blocco in blocchi:
        c.setFont("Courier", 10)
        for riga in blocco:
            c.drawString(50, y, "> " + riga)
            y -= 15
        y -= 20


_DISEGNATORI = {
    "Alfa Energia": _disegna_layout_alfa,
    "Beta Luce": _disegna_layout_beta,
    "Gamma Power": _disegna_layout_gamma,
}


def _pdf_digitale(layout: str, blocchi: list[list[str]]) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=A4, invariant=1)
    _DISEGNATORI[layout](c, blocchi)
    c.showPage()
    c.save()
    return buf.getvalue()


# --- rendering "scansione": immagine degradata, nessun text layer ---


def _pdf_scansione(blocchi: list[list[str]]) -> bytes:
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

    pdf_bytes = _pdf_scansione(blocchi) if flags.scansione else _pdf_digitale(layout, blocchi)
    if flags.ruotata:
        pdf_bytes = _ruota(pdf_bytes)

    nome_file = f"{doc_id}.pdf"
    if n_fatture == 1:
        istanze = [(doc_id, fatture[0])]
    else:
        istanze = [(f"{doc_id}{_LETTERE_ISTANZA[i]}", dati) for i, dati in enumerate(fatture)]

    oracle_entries = {instanza_id: _a_oracle(dati) for instanza_id, dati in istanze}

    # ponytail: il generatore produce un solo file a pagina singola per ogni
    # doc_id (anche con --multi-fattura, le fatture stanno sulla stessa
    # pagina). "pagine" e' quindi [1, 1] per ogni istanza finche' non serve
    # un rendering multi-pagina con sezioni davvero separate.
    metadata_entries = {
        instanza_id: {
            "file": nome_file,
            "pagine": [1, 1],
            "layout": layout,
            "tipo_lettura": "stimata" if flags.consumo_stimato else "effettiva",
            "monoraria": flags.monoraria,
            "qualita": "scansione_degradata" if flags.scansione else "digitale",
            "flag_attivi": flags.attivi(),
        }
        for instanza_id, _ in istanze
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un corpus sintetico di bollette luce.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "corpus" / "synth")
    parser.add_argument("--oracle-out", type=Path, default=REPO_ROOT / "corpus" / "attesi.json")
    parser.add_argument("--metadata-out", type=Path, default=REPO_ROOT / "corpus" / "metadata.json")
    for nome in FLAG_NOMI:
        parser.add_argument(f"--{nome.replace('_', '-')}", action="store_true")
    args = parser.parse_args()

    flags = Flags(**{nome: getattr(args, nome) for nome in FLAG_NOMI})
    genera_corpus(
        seed=args.seed,
        n=args.n,
        out_dir=args.out,
        oracle_path=args.oracle_out,
        metadata_path=args.metadata_out,
        flags=flags,
    )
    print(f"generati {args.n} documenti in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
