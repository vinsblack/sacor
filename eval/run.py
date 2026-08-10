"""Eval harness: esegue un extractor sul corpus e stampa il report per campo
e per documento (ADR-011). In questo blocco l'extractor e' il DummyExtractor."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from sacor.compare import uguali
from sacor.extractor import DummyExtractor, Extractor
from sacor.oracle import Oracle, OracleError, load_oracle
from sacor.schema import Schema, SchemaError, load

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"
ORACLE_PATH = REPO_ROOT / "corpus" / "attesi.json"
CORPUS_RAW = REPO_ROOT / "corpus" / "raw"


@dataclass(frozen=True)
class RisultatoCampo:
    nome: str
    corretti: int
    totale: int

    @property
    def accuratezza(self) -> float:
        return self.corretti / self.totale if self.totale else 0.0


@dataclass(frozen=True)
class Report:
    documento: str
    n_documenti: int
    documenti_corretti: int
    campi: tuple[RisultatoCampo, ...]
    gate_pass: int
    gate_warning: int
    gate_reject: int

    @property
    def accuratezza_documento(self) -> float:
        return self.documenti_corretti / self.n_documenti if self.n_documenti else 0.0


def esegui_eval(schema: Schema, oracle: Oracle, extractor: Extractor, corpus_raw: Path) -> Report:
    contatori = {c.nome: 0 for c in schema.campi}
    documenti_corretti = 0
    gate_reject = 0

    for doc_id, attesi in oracle.documenti.items():
        pdf = corpus_raw / f"{doc_id}.pdf"
        estratti = extractor.extract(pdf, schema)

        tutti_corretti = True
        for campo in schema.campi:
            if uguali(attesi.get(campo.nome), estratti.get(campo.nome), campo.tipo):
                contatori[campo.nome] += 1
            else:
                tutti_corretti = False
        if tutti_corretti:
            documenti_corretti += 1

        # ponytail: gate minimo, solo su campo obbligatorio mancante. Il livello
        # "warning" richiede l'esecuzione delle invarianti, non ancora costruita:
        # qui il gate puo' solo confermare pass o reject.
        if any(c.obbligatorio and estratti.get(c.nome) is None for c in schema.campi):
            gate_reject += 1

    n_documenti = len(oracle.documenti)
    campi_report = tuple(
        RisultatoCampo(nome=c.nome, corretti=contatori[c.nome], totale=n_documenti)
        for c in schema.campi
    )

    return Report(
        documento=schema.documento,
        n_documenti=n_documenti,
        documenti_corretti=documenti_corretti,
        campi=campi_report,
        gate_pass=n_documenti - gate_reject,
        gate_warning=0,
        gate_reject=gate_reject,
    )


def carica_report(
    schema_path: Path = SCHEMA_PATH,
    oracle_path: Path = ORACLE_PATH,
    corpus_raw: Path = CORPUS_RAW,
    extractor: Extractor | None = None,
) -> Report | None:
    """Ritorna il report, o None se il corpus (oracle) non e' ancora presente."""
    schema = load(schema_path)
    if not oracle_path.is_file():
        return None
    oracle = load_oracle(oracle_path, schema)
    return esegui_eval(schema, oracle, extractor or DummyExtractor(), corpus_raw)


def formatta_report(report: Report) -> str:
    righe = [
        f"sacor eval — {report.documento} — {report.n_documenti} documenti",
        "",
        f"ACCURATEZZA PER DOCUMENTO: {report.accuratezza_documento * 100:.1f}%  "
        f"({report.documenti_corretti}/{report.n_documenti})",
        "",
        f"{'Campo':<18}{'Corretti':>10}   {'Accuratezza':>11}",
    ]

    totale_corretti = 0
    totale_slot = 0
    for c in report.campi:
        frazione = f"{c.corretti}/{c.totale}"
        righe.append(f"{c.nome:<18}{frazione:>10}   {c.accuratezza * 100:>10.1f}%")
        totale_corretti += c.corretti
        totale_slot += c.totale

    accuratezza_totale = totale_corretti / totale_slot if totale_slot else 0.0
    righe.append("---")
    frazione_totale = f"{totale_corretti}/{totale_slot}"
    righe.append(f"{'TOTALE CAMPI':<18}{frazione_totale:>10}   {accuratezza_totale * 100:>10.1f}%")
    righe.append("")
    righe.append(
        f"Gate: pass {report.gate_pass} | warning {report.gate_warning} | "
        f"reject {report.gate_reject}"
    )
    righe.append("Escalation: n/d (nessun extractor a due tier)")
    return "\n".join(righe)


def main() -> int:
    try:
        report = carica_report()
    except SchemaError as exc:
        print(f"errore schema: {exc}", file=sys.stderr)
        return 1
    except OracleError as exc:
        print(f"errore oracle: {exc}", file=sys.stderr)
        return 1

    if report is None:
        print("corpus non ancora presente: manca corpus/attesi.json")
        return 0

    print(formatta_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
