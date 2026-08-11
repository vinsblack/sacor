"""Calibrazione del degrado --scansione (T4.7/T4.9, C1/C4; ADR-036, ADR-038):
misura il recupero OCR dei campi OBBLIGATORI a piu' livelli di degrado,
PRIMA di scegliere un livello — stesso principio delle soglie di triage
(ADR-020): non si sceglie a occhio, si misura e si annota il margine.

Nessuna scelta qui. Solo la tabella.

Chiama la STESSA scripts.genera_corpus._pdf_scansione usata in produzione,
non una copia: la divergenza tra codice misurato e codice usato era
esattamente il difetto scoperto in ADR-038 (font PIL a parte, mai la stessa
funzione del generatore).

Se Tesseract non e' disponibile sul sistema, lo dichiara e salta (ADR-036) —
non fallisce silenziosamente, non stima un numero al posto della misura."""

from __future__ import annotations

import io
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pdfplumber  # noqa: E402

from scripts.genera_corpus import (  # noqa: E402
    DatiFattura,
    Flags,
    LivelloDegrado,
    PagineFattura,
    _genera_dati_fattura,
    _pdf_scansione,
    _righe_pagina1,
    _righe_pagina2,
    _righe_pagina3,
)

TESSERACT_BIN = shutil.which("tesseract")

# Dal degrado "vecchio" (font PIL, illeggibile — ADR-036) al quasi-lossless,
# ora con la rasterizzazione del layout reale (ADR-038): dove cade il
# recupero OCR lungo la scala, per scegliere DOPO aver visto i numeri.
LIVELLI: tuple[LivelloDegrado, ...] = (
    LivelloDegrado("aggressivo", 1.2, 2.0, 55),
    LivelloDegrado("medio", 0.6, 1.5, 70),
    LivelloDegrado("leggero", 0.3, 1.2, 80),
    LivelloDegrado("minimo", 0.0, 1.0, 90),
    LivelloDegrado("quasi-lossless", 0.0, 1.0, 95),
)


def _ocr_testo(png_bytes: bytes) -> str:
    assert TESSERACT_BIN is not None
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        tmp.write(png_bytes)
        tmp.flush()
        esito = subprocess.run(
            [TESSERACT_BIN, tmp.name, "-", "--psm", "6"],
            capture_output=True,
            text=True,
            check=True,
        )
        return esito.stdout


def _ocr_documento(pdf_bytes: bytes) -> str:
    """OCR di TUTTE le pagine, concatenato: col layout a tre pagine
    (ADR-039) il POD e' in pagina 2, non piu' nella stessa pagina del
    periodo — la misura deve guardare il documento intero, come farebbe
    il tier 1."""
    testi: list[str] = []
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        with pdfplumber.open(tmp.name) as documento:
            for pagina in documento.pages:
                immagine = pagina.to_image(resolution=150).original
                buf = io.BytesIO()
                immagine.save(buf, format="PNG")
                testi.append(_ocr_testo(buf.getvalue()))
    return "\n".join(testi)


def _pulisci(testo: str) -> str:
    """Solo alfanumerico maiuscolo: l'OCR introduce spazi/punteggiatura
    spuri intorno a codici e date, non conta come mancato recupero."""
    return "".join(ch for ch in testo.upper() if ch.isalnum())


def _campi_obbligatori_attesi(dati: DatiFattura) -> dict[str, str]:
    # Solo i campi con obbligatorio: true nello schema (schemas/bolletta_luce_it.yaml).
    return {
        "pod": dati.pod,
        "periodo_da": dati.periodo_da.strftime("%d/%m/%Y"),
        "periodo_a": dati.periodo_a.strftime("%d/%m/%Y"),
    }


def misura_livello(livello: LivelloDegrado, semi: tuple[int, ...]) -> dict[str, tuple[int, int]]:
    """{nome_campo: (recuperati, totali)} sui documenti generati coi semi dati."""
    per_campo: dict[str, tuple[int, int]] = {c: (0, 0) for c in ("pod", "periodo_da", "periodo_a")}
    for seme in semi:
        rng = random.Random(seme)
        flags = Flags()
        dati = _genera_dati_fattura(rng, "Fornitore Test", monoraria=False)
        blocchi: list[PagineFattura] = [
            (_righe_pagina1(dati, flags), _righe_pagina2(dati, flags), _righe_pagina3(dati, flags))
        ]
        pdf_bytes = _pdf_scansione(
            "Alfa Energia",
            blocchi,
            rng,
            sporca=False,
            fornitore_stampato="Fornitore Test",
            livello=livello,
        )
        testo_ocr = _pulisci(_ocr_documento(pdf_bytes))

        for campo, valore_atteso in _campi_obbligatori_attesi(dati).items():
            recuperati, totali = per_campo[campo]
            trovato = _pulisci(valore_atteso) in testo_ocr
            per_campo[campo] = (recuperati + (1 if trovato else 0), totali + 1)
    return per_campo


def main() -> int:
    if TESSERACT_BIN is None:
        print("tesseract non disponibile su questo sistema: calibrazione saltata (ADR-036).")
        return 0

    semi = tuple(range(1, 11))
    print(f"sacor — calibrazione degrado --scansione (T4.9, C4), tesseract: {TESSERACT_BIN}\n")
    intestazione = (
        f"{'livello':<20}{'blur':>6}{'downsc.':>9}{'jpeg q':>7}"
        f"{'pod':>9}{'periodo_da':>12}{'periodo_a':>12}{'totale':>14}"
    )
    print(intestazione)
    print("-" * len(intestazione))

    for livello in LIVELLI:
        per_campo = misura_livello(livello, semi)
        tot_rec = sum(r for r, _t in per_campo.values())
        tot_tot = sum(t for _r, t in per_campo.values())
        pct_totale = 100 * tot_rec / tot_tot if tot_tot else 0.0
        celle = {campo: f"{r}/{t}" for campo, (r, t) in per_campo.items()}

        print(
            f"{livello.nome:<20}{livello.blur_radius:>6}{livello.fattore_downscale:>9}"
            f"{livello.qualita_jpeg:>7}{celle['pod']:>9}{celle['periodo_da']:>12}"
            f"{celle['periodo_a']:>12}{f'{tot_rec}/{tot_tot} ({pct_totale:.0f}%)':>14}"
        )

    print(
        "\nOCR: solo modello linguistico inglese (eng) disponibile in questa "
        "sessione — nessun impatto atteso sui campi misurati (codici POD e "
        "date, non parole italiane)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
