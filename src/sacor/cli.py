"""CLI (ADR-048): `sacor extract file.pdf` — il punto d'ingresso per chi
integra sacor senza scrivere Python. Solo tier0 per ora (YAGNI: tier1
richiede una chiave API a pagamento, non lo fa partire di default finché
qualcuno non lo chiede esplicitamente — vedi sacor.pipeline)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sacor.pipeline import estrai_file
from sacor.schema import SchemaError, load

REPO_ROOT = Path(__file__).parent.parent.parent


def _schema_default() -> Path:
    # ponytail: schema letto dal repo, non ancora impacchettato nel wheel
    # (un primo tentativo con force-include ha rotto l'editable install —
    # namespace package fantasma in site-packages/sacor/). Da risolvere
    # quando si pubblica davvero su PyPI, non prima: fino ad allora `sacor
    # extract` funziona solo dentro il repo o con --schema esplicito.
    return REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"


def _comando_extract(args: argparse.Namespace) -> int:
    schema_path = Path(args.schema) if args.schema else _schema_default()
    try:
        schema = load(schema_path)
    except SchemaError as exc:
        print(f"errore schema: {exc}", file=sys.stderr)
        return 2

    file = Path(args.file)
    if not file.is_file():
        print(f"errore: file non trovato: {file}", file=sys.stderr)
        return 2

    risultati = estrai_file(file, schema)
    output = [
        {
            "istanza_id": r.istanza_id,
            "valori": r.valori,
            "esito": r.esito,
            "motivo": r.motivo,
            "violazioni": [
                {"id": v.invariante_id, "severita": v.severita, "messaggio": v.messaggio}
                for v in r.violazioni
            ],
        }
        for r in risultati
    ]
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 1 if any(r.esito == "reject" for r in risultati) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sacor", description=__doc__)
    sotto = parser.add_subparsers(dest="comando", required=True)

    estrai = sotto.add_parser(
        "extract", help="Estrae dati da un documento (tier0, solo regex, zero costo)."
    )
    estrai.add_argument("file", help="Percorso del PDF da estrarre.")
    estrai.add_argument("--schema", help="Schema YAML da usare (default: bolletta_luce_it).")
    estrai.set_defaults(func=_comando_extract)

    args = parser.parse_args(argv)
    return args.func(args)  # type: ignore[no-any-return]


if __name__ == "__main__":
    sys.exit(main())
