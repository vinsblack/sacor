"""Triage: ricostruisce dal solo PDF ciò che, per il corpus sintetico,
`corpus/metadata.json` dichiara (ADR-016). In produzione quel file non
esiste — il triage e' l'unica fonte. Costo di inferenza zero: nessuna AI."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pdfplumber
from PIL import Image


class TipoPagina(StrEnum):
    """Tre stati, non due (ADR-022): una pagina ibrida non e' ne' digitale
    ne' scansione, e' entrambe. Un binario forzato commette un errore
    silenzioso in una delle due direzioni — vedi ADR-022 per l'analisi."""

    DIGITALE = "digitale"
    IBRIDA = "ibrida"
    SCANSIONE = "scansione"


# Confine banda digitale/ibrida (ADR-022). Sotto -> solo parser testuale.
# Margine osservato: 5,6x (0,15 / 0,0266 copertura digitale con logo+QR).
SOGLIA_COPERTURA_DIGITALE = 0.15

# Confine banda ibrida/scansione (ADR-022). Sopra -> solo percorso immagine.
# Margine osservato: 1,18x (1,00 / 0,85) — sottile. La scansione sintetica e'
# a piena pagina per costruzione (--scansione disegna un'immagine 0-100%): va
# rimisurato su documenti reali prima di fidarsi di questo margine.
SOGLIA_COPERTURA_SCANSIONE = 0.85

# Segnale secondario: non decide da solo (ADR-020), resta esposto per
# ispezione/futuro uso combinato con la copertura. Media geometrica tra gli
# estremi misurati (6,78e-5 scansione sporca, 4,17e-4 digitale peggiore):
# margine registrato ~2,5x per lato.
SOGLIA_DENSITA_TESTO = 1.7e-4

# Risoluzione della griglia usata da _copertura_immagine. Vedi il docstring
# della funzione per il motivo dell'approccio a griglia invece che unione
# esatta di rettangoli.
_GRID = 64


@dataclass(frozen=True)
class PaginaInfo:
    numero: int
    ha_text_layer: bool
    densita_testo: float
    copertura_immagine: float
    tipo: TipoPagina
    rotazione: int | None


@dataclass(frozen=True)
class Istanza:
    id: str
    pagina_da: int
    pagina_a: int


@dataclass(frozen=True)
class TriageResult:
    file: str
    pagine: tuple[PaginaInfo, ...]
    istanze: tuple[Istanza, ...]
    # ADR-018: il tipo (ADR-022) e' proprieta' di pagina (PaginaInfo.tipo),
    # non di documento. Un campo qui instraderebbe un intero file misto su
    # un solo percorso. Il chiamante scrive all(...)/any(...) esplicito, o
    # smista per pagina (ADR-022 — instradamento della banda ibrida:
    # progettazione Blocco 3, non qui).


def _copertura_immagine(pagina: pdfplumber.page.Page) -> float:
    """Stima la frazione di pagina coperta da immagini.

    Approccio: rasterizza la pagina su una griglia _GRID x _GRID e marca ogni
    cella il cui centro cade dentro il bounding box di almeno un'immagine.
    La frazione di celle marcate e' la stima di copertura. Una cella coperta
    da piu' immagini sovrapposte conta una sola volta, quindi le sovrapposizioni
    non gonfiano il risultato oltre 1.0 — senza dover implementare l'unione
    esatta di rettangoli (non necessaria per una metrica di per se' euristica).
    """
    immagini = pagina.images
    if not immagini or not pagina.width or not pagina.height:
        return 0.0

    larghezza, altezza = pagina.width, pagina.height
    celle_coperte = 0
    for riga in range(_GRID):
        cy = (riga + 0.5) / _GRID * altezza
        for colonna in range(_GRID):
            cx = (colonna + 0.5) / _GRID * larghezza
            dentro_qualche_immagine = any(
                img["x0"] <= cx <= img["x1"] and img["top"] <= cy <= img["bottom"]
                for img in immagini
            )
            if dentro_qualche_immagine:
                celle_coperte += 1

    return celle_coperte / (_GRID * _GRID)


def _rasterizza_pagina(pagina: pdfplumber.page.Page) -> Image.Image:
    """Rasterizza l'intera pagina, non solo l'immagine incorporata piu'
    grande: cosi' l'OSD vede anche eventuale testo digitale reale sopra
    l'immagine (--scansione-sporca, --pagina-ibrida), non solo lo sfondo.

    Via pypdfium2 (dipendenza di pdfplumber stesso, gia' presente): nessuna
    dipendenza aggiuntiva, nessun binario di sistema.
    """
    return pagina.to_image(resolution=150).original


def _rotazione_via_osd(pagina: pdfplumber.page.Page) -> int | None:
    """OSD Tesseract (binario esterno, opzionale) per l'orientamento.

    None in ogni caso di incertezza — Tesseract assente, output inatteso,
    timeout: MAI un'eccezione (T2.3). Tesseract non e' una dipendenza
    obbligatoria del pacchetto.
    """
    if shutil.which("tesseract") is None:
        return None

    immagine = _rasterizza_pagina(pagina)

    try:
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            immagine.save(tmp.name)
            esito = subprocess.run(
                ["tesseract", tmp.name, "-", "--psm", "0"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
    except (OSError, subprocess.SubprocessError):
        return None

    for riga in esito.stdout.splitlines():
        if riga.startswith("Rotate:"):
            try:
                return int(riga.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def _rotazione(pagina: pdfplumber.page.Page, tipo: TipoPagina) -> int | None:
    """/Rotate dai metadati se presente (autoritativo, letto da pdfplumber
    che lo espone gia' come page.rotation). Se assente (0, che pdfplumber non
    distingue da "esplicitamente zero") e la pagina e' SCANSIONE o IBRIDA,
    OSD Tesseract. Su DIGITALE l'OSD e' solo rumore (T2.3): /Rotate assente
    vale 0, senza escalation."""
    if pagina.rotation != 0:
        return int(pagina.rotation)
    if tipo in (TipoPagina.SCANSIONE, TipoPagina.IBRIDA):
        return _rotazione_via_osd(pagina)
    return 0


def _classifica(
    copertura: float, soglia_digitale: float, soglia_scansione: float
) -> TipoPagina:
    if copertura < soglia_digitale:
        return TipoPagina.DIGITALE
    if copertura > soglia_scansione:
        return TipoPagina.SCANSIONE
    return TipoPagina.IBRIDA


def _pagina_info(
    pagina: pdfplumber.page.Page, soglia_digitale: float, soglia_scansione: float
) -> PaginaInfo:
    n_caratteri = len(pagina.chars)
    area = pagina.width * pagina.height
    densita = n_caratteri / area if area else 0.0
    copertura = _copertura_immagine(pagina)
    tipo = _classifica(copertura, soglia_digitale, soglia_scansione)
    return PaginaInfo(
        numero=pagina.page_number,
        ha_text_layer=n_caratteri > 0,
        densita_testo=densita,
        copertura_immagine=copertura,
        tipo=tipo,
        rotazione=_rotazione(pagina, tipo),
    )


def analizza(
    path: Path,
    soglia_digitale: float = SOGLIA_COPERTURA_DIGITALE,
    soglia_scansione: float = SOGLIA_COPERTURA_SCANSIONE,
) -> TriageResult:
    with pdfplumber.open(path) as documento:
        pagine = tuple(
            _pagina_info(p, soglia_digitale, soglia_scansione) for p in documento.pages
        )

    # T2.4 (segmentazione guidata dallo schema) non ancora implementato:
    # default ADR-017, una sola istanza che copre l'intero file.
    istanza_unica = Istanza(id=path.stem, pagina_da=1, pagina_a=len(pagine))

    return TriageResult(file=path.name, pagine=pagine, istanze=(istanza_unica,))
