"""Rendering pagina->PNG per il tier 1 (ADR-048 punto 1): spostato da
eval/run.py (dev-only, non impacchettato nel wheel) qui, dentro il package,
perche' sacor.pipeline ne ha bisogno per chiamare tier1 da fuori il repo.
eval/run.py e scripts/bakeoff.py continuano a usarlo da qui, stessa firma."""

from __future__ import annotations

import io

import pdfplumber

from sacor.segmentation import Istanza

# T4.5, C1: stessa risoluzione usata da --dry-run per stimare e da
# scripts/bakeoff.py per chiamare davvero — la stima deve misurare quello
# che poi viene realmente inviato, non un'approssimazione indipendente.
RISOLUZIONE_RENDER_DPI = 150


def renderizza_pagine_istanza(istanza: Istanza) -> list[tuple[bytes, int, int]]:
    """PNG (bytes, larghezza_px, altezza_px) per ogni pagina dell'istanza,
    alla stessa risoluzione di scripts/bakeoff.py (T4.5, C1): le pagine del
    tier 1 sono SCANSIONE/IBRIDA, senza text layer — solo l'immagine
    renderizzata dice quanto costa davvero la chiamata."""
    with pdfplumber.open(istanza.file) as documento:
        pagine = documento.pages[istanza.pagina_da - 1 : istanza.pagina_a]
        risultato: list[tuple[bytes, int, int]] = []
        for pagina in pagine:
            immagine = pagina.to_image(resolution=RISOLUZIONE_RENDER_DPI).original
            buffer = io.BytesIO()
            immagine.save(buffer, format="PNG")
            larghezza, altezza = immagine.size
            risultato.append((buffer.getvalue(), larghezza, altezza))
        return risultato
