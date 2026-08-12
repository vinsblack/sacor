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

def _schema_default() -> Path:
    # Schema impacchettato dentro src/sacor/schemas/ (parte del wheel:
    # packages=["src/sacor"] in pyproject.toml lo include senza bisogno
    # di force-include). Path relativo a questo file funziona sia in
    # editable install sia da wheel installato altrove.
    return Path(__file__).parent / "schemas" / "bolletta_luce_it.yaml"


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
