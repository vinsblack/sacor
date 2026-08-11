"""Bake-off tier 1 contro il corpus reale (T4.14, ADR-042) — stessa logica
di scripts/bakeoff.py (chiamate reali, cache disattivata, tetto di spesa),
puntata a corpus/reale invece che al sintetico.

I PDF (`corpus/reale/raw/`) non sono nel repo — questo script gira solo in
locale, su chi ha gia' i file."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.run import MODELLI_BAKEOFF, SCHEMA_PATH, istanze_da_completare  # noqa: E402
from scripts.bakeoff import (  # noqa: E402
    LIMITE_SPESA_USD,
    TracciatoreSpesa,
    _valuta_modello,
    formatta_tabella,
)

ORACLE_PATH = REPO_ROOT / "corpus" / "reale" / "attesi.json"
CORPUS_RAW = REPO_ROOT / "corpus" / "reale" / "raw"
METADATA_PATH = REPO_ROOT / "corpus" / "reale" / "metadata.json"


def main() -> int:
    if not CORPUS_RAW.is_dir():
        print(
            "PDF reali non presenti in locale (corpus/reale/raw/, mai nel repo, "
            "vedi corpus/reale/README.md)"
        )
        return 0

    esito = istanze_da_completare(SCHEMA_PATH, ORACLE_PATH, CORPUS_RAW, METADATA_PATH)
    if esito is None:
        print("corpus reale non presente: manca corpus/reale/attesi.json")
        return 0
    schema, oracle, chiamate, file_disallineati = esito

    print(
        "sacor bake-off SU CORPUS REALE (T4.14) — cache disattivata, chiamate reali.\n"
        f"Chiamate necessarie: {len(chiamate)}, file disallineati: {file_disallineati}\n"
        f"Tetto di spesa per il giro completo: ${LIMITE_SPESA_USD:.2f}.\n"
    )

    tracciatore = TracciatoreSpesa(LIMITE_SPESA_USD)
    righe = [
        _valuta_modello(m, chiamate, oracle.documenti, tracciatore, schema)
        for m in MODELLI_BAKEOFF
    ]

    print(formatta_tabella(righe))
    print(f"\nSpeso reale totale: ${tracciatore.speso:.4f}")
    if tracciatore.fermato:
        print(
            f"TETTO DI SPESA (${LIMITE_SPESA_USD:.2f}) RAGGIUNTO — giro interrotto in anticipo.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
