"""CLI (ADR-048): `sacor extract file.pdf` — il punto d'ingresso per chi
integra sacor senza scrivere Python. Tier0 sempre (regex, gratis). Tier1
(ADR-048 punto 1) opt-in via --tier1: claude-opus-5 (ADR-049), chiamata
reale a pagamento, mai automatica — richiede ANTHROPIC_API_KEY.

Senza --schema, classifica il documento (ADR-053) prima di scegliere lo
schema — bug osservato in sessione: una bolletta gas letta con lo schema
luce senza nessun avviso. Solo bolletta_luce ha uno schema oggi; gas/CTE
si fermano con un errore chiaro invece di essere letti col posto
sbagliato."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sacor.classifica import TipoDocumento, classifica_file
from sacor.pipeline import estrai_file
from sacor.schema import SchemaError, load


def _schema_default() -> Path:
    # Schema impacchettato dentro src/sacor/schemas/ (parte del wheel:
    # packages=["src/sacor"] in pyproject.toml lo include senza bisogno
    # di force-include). Path relativo a questo file funziona sia in
    # editable install sia da wheel installato altrove.
    return Path(__file__).parent / "schemas" / "bolletta_luce_it.yaml"


def _schema_da_classificazione(file: Path) -> Path | None:
    """None = nessuno schema utilizzabile, l'estrazione deve fermarsi con
    un errore chiaro (mai forzare bolletta_luce su un documento che non lo
    e', ADR-053). SCONOSCIUTO (documenti scansionati, nessun text layer)
    resta bolletta_luce per compatibilita' — con avviso, non in silenzio:
    e' l'unico schema che esiste oggi, e resta il default corretto per il
    corpus reale attuale (tutto luce)."""
    tipo = classifica_file(file)
    if tipo == TipoDocumento.BOLLETTA_LUCE:
        return _schema_default()
    if tipo == TipoDocumento.SCONOSCIUTO:
        print(
            "avviso: tipo documento non determinato con certezza, uso lo "
            "schema bolletta_luce per default — verifica il risultato.",
            file=sys.stderr,
        )
        return _schema_default()
    print(
        f"errore: documento classificato come '{tipo.value}', nessuno "
        "schema disponibile per questo tipo ancora — usa --schema per "
        "forzarne uno esplicito.",
        file=sys.stderr,
    )
    return None


def _comando_extract(args: argparse.Namespace) -> int:
    file = Path(args.file)
    if not file.is_file():
        print(f"errore: file non trovato: {file}", file=sys.stderr)
        return 2

    if args.schema:
        schema_path: Path | None = Path(args.schema)
    else:
        schema_path = _schema_da_classificazione(file)
    if schema_path is None:
        return 2

    try:
        schema = load(schema_path)
    except SchemaError as exc:
        print(f"errore schema: {exc}", file=sys.stderr)
        return 2

    risultati = estrai_file(file, schema, usa_tier1=args.tier1)
    output = [
        {
            "istanza_id": r.istanza_id,
            "valori": r.valori,
            # ADR-048 punto 2: "alta"/"media"/"bassa" per campo, None se il
            # campo non ha valore — vedi sacor.pipeline._calcola_confidenza.
            "confidenza": r.confidenza,
            "esito": r.esito,
            "motivo": r.motivo,
            "violazioni": [
                {"id": v.invariante_id, "severita": v.severita, "messaggio": v.messaggio}
                for v in r.violazioni
            ],
            "costo_tier1_usd": round(r.costo_tier1_usd, 6),
            "tier1_errore": r.tier1_errore,
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
    estrai.add_argument(
        "--tier1",
        action="store_true",
        help=(
            "Completa i campi non trovati dal tier0 con claude-opus-5 "
            "(ADR-049). Chiamata reale a pagamento, richiede "
            "ANTHROPIC_API_KEY — opt-in esplicito, mai automatico."
        ),
    )
    estrai.set_defaults(func=_comando_extract)

    args = parser.parse_args(argv)
    return args.func(args)  # type: ignore[no-any-return]


if __name__ == "__main__":
    sys.exit(main())
