"""Eval harness: esegue un extractor sul corpus e stampa il report per campo
e per documento (ADR-011). Extractor di default: TierZeroExtractor (ADR-032,
nessuna AI). Itera sulle istanze rilevate dalla segmentazione, non su quelle
dichiarate nell'oracle (ADR-033): misura la pipeline vera."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from sacor.compare import uguali
from sacor.extractor import (
    DiagnosticaCampo,
    EsitoCampo,
    Extractor,
    TierZeroExtractor,
)
from sacor.oracle import Oracle, OracleError, load_oracle
from sacor.schema import Schema, SchemaError, load
from sacor.segmentation import Istanza, segmenta
from sacor.triage import analizza, normalizza_testo

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"
ORACLE_PATH = REPO_ROOT / "corpus" / "attesi.json"
METADATA_PATH = REPO_ROOT / "corpus" / "metadata.json"
CORPUS_RAW = REPO_ROOT / "corpus" / "synth"


@dataclass(frozen=True)
class RisultatoCampo:
    nome: str
    non_estratto: int
    non_normalizzabile: int
    normalizzato: int
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
    valori_errati: int = 0  # T3.3: non-None ma sbagliato — l'estrattore "inventa"
    segmentazione_disallineata: int = 0  # T3.4: n. istanze rilevate != n. istanze oracle

    @property
    def accuratezza_documento(self) -> float:
        return self.documenti_corretti / self.n_documenti if self.n_documenti else 0.0


def _carica_metadata(path: Path) -> dict[str, Mapping[str, object]]:
    if not path.is_file():
        return {}
    dati = json.loads(path.read_text())
    if not isinstance(dati, dict):
        return {}
    # ADR-025: corpus/metadata.json porta un blocco "composizione" in testa;
    # le voci per istanza vivono sotto "documenti". Formato piatto (senza
    # wrapper) tollerato per compatibilita' con generazioni non composite.
    documenti = dati.get("documenti", dati)
    return documenti if isinstance(documenti, dict) else {}


def _raggruppa_per_file(
    oracle: Oracle, metadata: Mapping[str, Mapping[str, object]]
) -> dict[str, list[str]]:
    """file -> chiavi oracle che vi appartengono, nell'ordine di apparizione.

    Si parte dalle chiavi dell'ORACLE (cio' che serve valutare), non da
    quelle di metadata: un oracle scritto a mano (senza metadata.json) deve
    restare valutabile. Il file si risolve da metadata quando c'e'; altrimenti
    si assume che la chiave coincida col nome del file (ADR-014-bis: stesso
    fallback gia' usato altrove per un'istanza senza metadata)."""
    per_file: dict[str, list[str]] = {}
    for chiave in oracle.documenti:
        voce = metadata.get(chiave, {})
        nome_file = str(voce.get("file", f"{chiave}.pdf"))
        per_file.setdefault(nome_file, []).append(chiave)
    return per_file


def _diagnostica_per(
    extractor: Extractor, istanza: Istanza, schema: Schema
) -> dict[str, DiagnosticaCampo]:
    """T3.3: solo TierZeroExtractor sa distinguere non_estratto da
    non_normalizzabile (passa dentro Repair). Per un Extractor generico si
    puo' solo dedurre normalizzato/non_estratto dal valore finale."""
    if isinstance(extractor, TierZeroExtractor):
        return extractor.estrai_diagnostica(istanza, schema)

    estratti = extractor.extract(istanza, schema)
    return {
        nome: DiagnosticaCampo(
            EsitoCampo.NORMALIZZATO if valore is not None else EsitoCampo.NON_ESTRATTO,
            valore,
        )
        for nome, valore in estratti.items()
    }


def esegui_eval(
    schema: Schema,
    oracle: Oracle,
    extractor: Extractor,
    corpus_raw: Path,
    metadata: Mapping[str, Mapping[str, object]] | None = None,
) -> Report:
    metadata = metadata or {}
    per_file = _raggruppa_per_file(oracle, metadata)

    non_estratto = {c.nome: 0 for c in schema.campi}
    non_normalizzabile = {c.nome: 0 for c in schema.campi}
    normalizzato = {c.nome: 0 for c in schema.campi}
    corretti = {c.nome: 0 for c in schema.campi}
    documenti_corretti = 0
    gate_reject = 0
    valori_errati = 0
    segmentazione_disallineata = 0

    for nome_file, chiavi_oracle in per_file.items():
        pdf = corpus_raw / nome_file
        triage_result = analizza(pdf)
        with pdfplumber.open(pdf) as documento:
            testi = [normalizza_testo(p) for p in documento.pages]
        esito_segmentazione = segmenta(pdf, triage_result.pagine, testi, schema.segmentazione)
        istanze_rilevate = esito_segmentazione.istanze

        if len(istanze_rilevate) != len(chiavi_oracle):
            # ADR-033: non si forza l'allineamento con l'oracle. Se la
            # segmentazione rilevata non ha lo stesso numero di istanze
            # dichiarate, non c'e' un modo onesto di attribuire i campi
            # estratti a una specifica istanza oracle: ogni istanza oracle
            # di questo file conta come non estratta e non corretta.
            segmentazione_disallineata += 1
            for _ in chiavi_oracle:
                for campo in schema.campi:
                    non_estratto[campo.nome] += 1
                if any(c.obbligatorio for c in schema.campi):
                    gate_reject += 1
            continue

        # Il conteggio combacia: si accoppiano per ordine di pagina, MAI per
        # id (ADR-014-bis: gli id oracle sono opachi, non si interpretano).
        for istanza, chiave_oracle in zip(istanze_rilevate, chiavi_oracle, strict=True):
            attesi = oracle.documenti[chiave_oracle]
            diagnostica = _diagnostica_per(extractor, istanza, schema)
            estratti = {nome: d.valore for nome, d in diagnostica.items()}

            tutti_corretti = True
            for campo in schema.campi:
                esito = diagnostica[campo.nome].esito
                if esito is EsitoCampo.NON_ESTRATTO:
                    non_estratto[campo.nome] += 1
                elif esito is EsitoCampo.NON_NORMALIZZABILE:
                    non_normalizzabile[campo.nome] += 1
                else:
                    normalizzato[campo.nome] += 1

                valore_estratto = estratti.get(campo.nome)
                if uguali(attesi.get(campo.nome), valore_estratto, campo.tipo):
                    corretti[campo.nome] += 1
                else:
                    tutti_corretti = False
                    if valore_estratto is not None:
                        valori_errati += 1

            if tutti_corretti:
                documenti_corretti += 1

            # ponytail: gate minimo, solo su campo obbligatorio mancante. Il
            # livello "warning" richiede l'esecuzione delle invarianti, non
            # ancora costruita: qui il gate puo' solo confermare pass o reject.
            if any(c.obbligatorio and estratti.get(c.nome) is None for c in schema.campi):
                gate_reject += 1

    n_documenti = len(oracle.documenti)
    campi_report = tuple(
        RisultatoCampo(
            nome=c.nome,
            non_estratto=non_estratto[c.nome],
            non_normalizzabile=non_normalizzabile[c.nome],
            normalizzato=normalizzato[c.nome],
            corretti=corretti[c.nome],
            totale=n_documenti,
        )
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
        valori_errati=valori_errati,
        segmentazione_disallineata=segmentazione_disallineata,
    )


def carica_report(
    schema_path: Path = SCHEMA_PATH,
    oracle_path: Path = ORACLE_PATH,
    corpus_raw: Path = CORPUS_RAW,
    metadata_path: Path = METADATA_PATH,
    extractor: Extractor | None = None,
) -> Report | None:
    """Ritorna il report, o None se il corpus (oracle) non e' ancora presente."""
    schema = load(schema_path)
    if not oracle_path.is_file():
        return None
    oracle = load_oracle(oracle_path, schema)
    metadata = _carica_metadata(metadata_path)
    return esegui_eval(schema, oracle, extractor or TierZeroExtractor(), corpus_raw, metadata)


def _cella(n: int, totale: int) -> str:
    return f"{n}/{totale}"


def formatta_report(report: Report) -> str:
    righe = [
        f"sacor eval — {report.documento} — {report.n_documenti} documenti",
        "",
        f"ACCURATEZZA PER DOCUMENTO: {report.accuratezza_documento * 100:.1f}%  "
        f"({report.documenti_corretti}/{report.n_documenti})",
        "",
        f"{'Campo':<16}{'non estratto':>14}{'non normaliz.':>15}"
        f"{'normalizzato':>14}{'corretto':>10}",
    ]

    tot_non_estratto = tot_non_normalizzabile = tot_normalizzato = tot_corretti = 0
    for c in report.campi:
        righe.append(
            f"{c.nome:<16}"
            f"{_cella(c.non_estratto, c.totale):>14}"
            f"{_cella(c.non_normalizzabile, c.totale):>15}"
            f"{_cella(c.normalizzato, c.totale):>14}"
            f"{_cella(c.corretti, c.totale):>10}"
        )
        tot_non_estratto += c.non_estratto
        tot_non_normalizzabile += c.non_normalizzabile
        tot_normalizzato += c.normalizzato
        tot_corretti += c.corretti

    totale_slot = report.n_documenti * len(report.campi)
    righe.append("---")
    righe.append(
        f"{'TOTALE CAMPI':<16}"
        f"{_cella(tot_non_estratto, totale_slot):>14}"
        f"{_cella(tot_non_normalizzabile, totale_slot):>15}"
        f"{_cella(tot_normalizzato, totale_slot):>14}"
        f"{_cella(tot_corretti, totale_slot):>10}"
    )
    righe.append("")
    righe.append(
        f"Gate: pass {report.gate_pass} | warning {report.gate_warning} | "
        f"reject {report.gate_reject}"
    )
    righe.append("Escalation: n/d (nessun extractor a due tier)")
    righe.append(f"Campi con valore NON-None ma errato: {report.valori_errati}")
    righe.append(
        f"File con segmentazione disallineata dall'oracle: {report.segmentazione_disallineata}"
    )
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
