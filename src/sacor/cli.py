"""CLI (ADR-048): `sacor extract file.pdf` — il punto d'ingresso per chi
integra sacor senza scrivere Python. Tier0 sempre (regex, gratis). Tier1
(ADR-048 punto 1) opt-in via --tier1: claude-opus-5 (ADR-049), chiamata
reale a pagamento, mai automatica — richiede ANTHROPIC_API_KEY.

Senza --schema, classifica il documento (ADR-053) prima di scegliere lo
schema — bug osservato in sessione: una bolletta gas letta con lo schema
luce senza nessun avviso. bolletta_luce, bolletta_gas e CTE hanno uno
schema; un tipo futuro senza schema si ferma con un errore chiaro
invece di essere letto col posto sbagliato."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sacor.classifica import TipoDocumento, classifica_file
from sacor.pipeline import RisultatoEstrazione, estrai_file
from sacor.schema import SchemaError, load


def _schema_default() -> Path:
    # Schema impacchettato dentro src/sacor/schemas/ (parte del wheel:
    # packages=["src/sacor"] in pyproject.toml lo include senza bisogno
    # di force-include). Path relativo a questo file funziona sia in
    # editable install sia da wheel installato altrove.
    return Path(__file__).parent / "schemas" / "bolletta_luce_it.yaml"


def _schema_gas() -> Path:
    return Path(__file__).parent / "schemas" / "bolletta_gas_it.yaml"


def _schema_cte() -> Path:
    return Path(__file__).parent / "schemas" / "cte_it.yaml"


# ADR-053: solo i tipi con uno schema pronto. Un tipo futuro senza
# schema resta assente qui apposta — vedi il ramo else sotto, si ferma
# con un errore chiaro invece di forzare un tipo sbagliato.
_SCHEMA_PER_TIPO = {
    TipoDocumento.BOLLETTA_LUCE: _schema_default,
    TipoDocumento.BOLLETTA_GAS: _schema_gas,
    TipoDocumento.CTE: _schema_cte,
}


def _schema_da_classificazione(file: Path) -> Path | None:
    """None = nessuno schema utilizzabile, l'estrazione deve fermarsi con
    un errore chiaro (mai forzare bolletta_luce su un documento che non lo
    e', ADR-053). SCONOSCIUTO (documenti scansionati, nessun text layer)
    resta bolletta_luce per compatibilita' — con avviso, non in silenzio:
    e' il default piu' probabile sul corpus reale attuale (tutto luce)."""
    tipo = classifica_file(file)
    costruttore = _SCHEMA_PER_TIPO.get(tipo)
    if costruttore is not None:
        return costruttore()
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
    output = [_serializza_risultato(r) for r in risultati]
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 1 if any(r.esito == "reject" for r in risultati) else 0


def _serializza_risultato(r: RisultatoEstrazione) -> dict[str, object]:
    """Result Contract v1 (ADR-056, corretto da ADR-057/058/059/060) —
    il JSON pubblico riflette la stessa struttura di Evidenza costruita
    internamente, non una proiezione ridotta. Rompe la forma precedente
    (valori/confidenza piatti) di proposito: e' il momento giusto per
    farlo, prima del primo tag pubblico (ADR-056, 'romperlo dopo sarebbe
    la stessa violazione di contratto che l'ADR esiste per evitare')."""
    documento = None
    if r.evidenza_documento is not None:
        documento = {
            "schema": r.evidenza_documento.schema,
            "schema_versione": r.evidenza_documento.schema_versione,
            "classificazione": r.evidenza_documento.classificazione,
            "pagine": [
                {"indice": p.indice, "tipo": p.tipo} for p in r.evidenza_documento.pagine
            ],
        }
    return {
        "istanza_id": r.istanza_id,
        "documento": documento,
        "campi": {nome: _serializza_campo(r, nome) for nome in r.valori},
        "esito": r.esito,
        "motivo": r.motivo,
        "costo_tier1_usd": round(r.costo_tier1_usd, 6),
        "tier1_errore": r.tier1_errore,
    }


def _serializza_campo(r: RisultatoEstrazione, nome: str) -> dict[str, object]:
    ev = r.evidenze[nome]
    return {
        "value": r.valori[nome],
        "evidence": {
            "origin": ev.origine,
            "status": ev.stato,
            "repair": [{"tipo": rp.tipo, "da": rp.da, "a": rp.a} for rp in ev.repair],
            "derivation": [
                {"tipo": d.tipo, "invariante_id": d.invariante_id, "da_campi": list(d.da_campi)}
                for d in ev.derivazione
            ],
            "invariants": {
                "passed": ev.invarianti.passate,
                "failed": ev.invarianti.fallite,
                "dettaglio": [
                    {
                        "id": e.id,
                        "esito": e.esito,
                        "severita": e.severita,
                        "messaggio": e.messaggio,
                    }
                    for e in ev.invarianti.dettaglio
                ],
            },
        },
        "confidence": r.confidenza.get(nome),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sacor", description=__doc__)
    sotto = parser.add_subparsers(dest="comando", required=True)

    estrai = sotto.add_parser(
        "extract",
        help=(
            "Estrae dati da un documento (tier0 gratis sempre; --tier1 "
            "opzionale, chiamata reale a pagamento)."
        ),
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
