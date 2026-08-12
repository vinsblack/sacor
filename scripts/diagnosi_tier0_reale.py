"""Diagnosi tier0 SUL CORPUS REALE (T4.17) — ZERO chiamate API, zero costo:
tier0 e' solo regex, gira in locale sempre. Serve a misurare l'effetto di
una modifica a `schemas/*.yaml` o a `sacor.extractor` PRIMA di spendere
soldi veri su un bake-off tier1 — stessa disciplina di misura di ADR-044,
applicata al layer che non costa nulla da rimisurare.

I PDF (`corpus/reale/raw/`) non sono nel repo — questo script gira solo in
locale, su chi ha gia' i file."""

from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.run import SCHEMA_PATH, _carica_metadata, _raggruppa_per_file  # noqa: E402
from sacor.compare import uguali  # noqa: E402
from sacor.extractor import TierZeroExtractor  # noqa: E402
from sacor.oracle import load_oracle  # noqa: E402
from sacor.schema import load  # noqa: E402
from sacor.segmentation import segmenta  # noqa: E402
from sacor.triage import analizza, normalizza_testo  # noqa: E402

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

    schema = load(SCHEMA_PATH)
    oracle = load_oracle(ORACLE_PATH, schema)
    metadata = _carica_metadata(METADATA_PATH)
    per_file = _raggruppa_per_file(oracle, metadata)
    tier0 = TierZeroExtractor()

    giusti = sbagliati = mancanti = 0
    per_campo: dict[str, dict[str, int]] = {}
    file_disallineati = 0

    for nome_file, chiavi_oracle in per_file.items():
        pdf = CORPUS_RAW / nome_file
        triage_result = analizza(pdf)
        with pdfplumber.open(pdf) as documento:
            testi_pagine = [normalizza_testo(p) for p in documento.pages]
        esito_segmentazione = segmenta(
            pdf, triage_result.pagine, testi_pagine, schema.segmentazione
        )

        if len(esito_segmentazione.istanze) != len(chiavi_oracle):
            file_disallineati += 1
            continue

        for istanza, chiave in zip(esito_segmentazione.istanze, chiavi_oracle, strict=True):
            estratti = tier0.extract(istanza, schema)
            attesi = oracle.documenti[chiave]
            for campo in schema.campi:
                valore = estratti.get(campo.nome)
                atteso = attesi.get(campo.nome)
                stat = per_campo.setdefault(
                    campo.nome, {"giusti": 0, "sbagliati": 0, "mancanti": 0}
                )
                if valore is None:
                    mancanti += 1
                    stat["mancanti"] += 1
                elif uguali(atteso, valore, campo.tipo):
                    giusti += 1
                    stat["giusti"] += 1
                else:
                    sbagliati += 1
                    stat["sbagliati"] += 1
                    print(
                        f"  [sbagliato] {chiave} {campo.nome}: "
                        f"tier0={valore!r} oracle={atteso!r}",
                        file=sys.stderr,
                    )

    totale = giusti + sbagliati + mancanti
    print("diagnosi tier0 su corpus reale (T4.17) — zero chiamate API, zero costo.\n")
    print(f"file disallineati: {file_disallineati}")
    if totale:
        print(
            f"totale: giusti={giusti} sbagliati={sbagliati} mancanti={mancanti} "
            f"({giusti / totale * 100:.1f}%)"
        )
    else:
        print("nessun campo valutato")
    print()
    intestazione = f"{'campo':<16}{'giusti':>8}{'sbagliati':>11}{'mancanti':>10}"
    print(intestazione)
    print("-" * len(intestazione))
    for nome, s in per_campo.items():
        print(f"{nome:<16}{s['giusti']:>8}{s['sbagliati']:>11}{s['mancanti']:>10}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
