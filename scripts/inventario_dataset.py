"""Inventario del dataset CTE (12-08): hash + metadati per ogni PDF in
corpus/cte/raw/, PRIMA di decidere quali (se non tutti) committare.
'pubblico' e' lasciato 'da_confermare' — nessuna assunzione su
diritti di redistribuzione, solo la provenienza che il codice puo'
verificare da solo (hash, pagine). Il resto lo decide l'utente.

Uso: uv run python scripts/inventario_dataset.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import pdfplumber  # noqa: E402

CORPUS_DIR = REPO_ROOT / "corpus" / "cte" / "raw"
OUTPUT_PATH = REPO_ROOT / "corpus" / "cte" / "inventario.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    voci = []
    for path in sorted(CORPUS_DIR.rglob("*.pdf")):
        fornitore = path.parent.name
        with pdfplumber.open(path) as pdf:
            n_pagine = len(pdf.pages)
        voci.append(
            {
                "file": str(path.relative_to(CORPUS_DIR)),
                "fornitore": fornitore,
                "sha256": _sha256(path),
                "pagine": n_pagine,
                "dimensione_byte": path.stat().st_size,
                "pubblico": "da_confermare",
                "redistribuibile": "da_confermare",
            }
        )

    OUTPUT_PATH.write_text(
        json.dumps(
            {"dataset": "cte-it-v1", "totale": len(voci), "documenti": voci},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(f"scritto {OUTPUT_PATH} — {len(voci)} documenti")


if __name__ == "__main__":
    main()
