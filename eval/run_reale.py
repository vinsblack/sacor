"""Eval del tier 0 contro il corpus reale (T4.14, ADR-042): stessa logica di
eval/run.py ma senza triage/segmentazione — ogni PDF reale e' un'unica
istanza nota (un documento = una bolletta, nessun multi-fattura in questo
corpus), quindi l'istanza copre semplicemente tutte le pagine del file.

I PDF (`corpus/reale/raw/`) non sono nel repo (`.gitignore`, ADR-042) —
questo script gira solo in locale, su chi ha gia' i file."""

from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber

from sacor.compare import uguali
from sacor.extractor import TierZeroExtractor
from sacor.oracle import OracleError, load_oracle
from sacor.schema import SchemaError, load
from sacor.segmentation import Istanza

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"
ORACLE_PATH = REPO_ROOT / "corpus" / "reale" / "attesi.json"
CORPUS_RAW = REPO_ROOT / "corpus" / "reale" / "raw"


def main() -> int:
    try:
        schema = load(SCHEMA_PATH)
    except SchemaError as exc:
        print(f"errore schema: {exc}", file=sys.stderr)
        return 1

    if not ORACLE_PATH.is_file():
        print("corpus reale non presente: manca corpus/reale/attesi.json")
        return 0
    try:
        oracle = load_oracle(ORACLE_PATH, schema)
    except OracleError as exc:
        print(f"errore oracle: {exc}", file=sys.stderr)
        return 1

    if not CORPUS_RAW.is_dir():
        print(
            "PDF reali non presenti in locale (corpus/reale/raw/, mai nel repo, "
            "vedi corpus/reale/README.md)"
        )
        return 0

    extractor = TierZeroExtractor()
    corretti = {c.nome: 0 for c in schema.campi}
    non_estratto = {c.nome: 0 for c in schema.campi}
    totale = {c.nome: 0 for c in schema.campi}
    mancanti: list[str] = []

    for doc_id, attesi in oracle.documenti.items():
        pdf_path = CORPUS_RAW / f"{doc_id}.pdf"
        if not pdf_path.is_file():
            mancanti.append(doc_id)
            continue
        with pdfplumber.open(pdf_path) as documento:
            n_pagine = len(documento.pages)
        istanza = Istanza(id=doc_id, file=pdf_path, pagina_da=1, pagina_a=n_pagine)
        estratti = extractor.extract(istanza, schema)

        for campo in schema.campi:
            totale[campo.nome] += 1
            valore = estratti.get(campo.nome)
            if valore is None:
                non_estratto[campo.nome] += 1
            if uguali(attesi.get(campo.nome), valore, campo.tipo):
                corretti[campo.nome] += 1

    print(f"sacor eval — {schema.documento} — corpus REALE, {len(oracle.documenti)} documenti\n")
    print(f"{'Campo':<16}{'corretto':>10}{'non estratto':>14}{'totale':>8}")
    tot_c = tot_t = 0
    for c in schema.campi:
        print(f"{c.nome:<16}{corretti[c.nome]:>10}{non_estratto[c.nome]:>14}{totale[c.nome]:>8}")
        tot_c += corretti[c.nome]
        tot_t += totale[c.nome]
    print("---")
    pct = tot_c / tot_t * 100 if tot_t else 0.0
    print(f"{'TOTALE':<16}{tot_c:>10}{'':>14}{tot_t:>8}   {pct:.1f}%")
    if mancanti:
        print(f"\nPDF mancanti in locale (esclusi dalla misura): {', '.join(mancanti)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
