import json
from pathlib import Path

from eval.run import carica_report
from sacor.extractor import DummyExtractor
from sacor.schema import Schema
from sacor.segmentation import Istanza
from scripts.genera_corpus import genera_corpus

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"


class _ExtractorConTotaleCorrotto:
    """T4.16 (ADR-045): restituisce i valori giusti dall'oracle per ogni
    campo tranne kwh_totale, corrotto apposta — forza deterministicamente
    una violazione dell'invariante somma_fasce, senza dipendere da cosa
    genera il corpus casuale in questo giro."""

    def __init__(self, oracle_path: Path) -> None:
        self._documenti = json.loads(oracle_path.read_text())["documenti"]

    def extract(self, istanza: Istanza, schema: Schema) -> dict[str, str | None]:
        valori = dict(self._documenti[istanza.id])
        valori["kwh_totale"] = "999999.99"
        return valori


def test_run_completo_con_dummy_extractor(tmp_path: Path) -> None:
    # ADR-033: l'eval esegue triage+segmentazione sul file reale prima di
    # chiamare l'extractor, quindi servono PDF veri anche con DummyExtractor.
    genera_corpus(
        seed=1,
        n=2,
        out_dir=tmp_path / "synth",
        oracle_path=tmp_path / "attesi.json",
        metadata_path=tmp_path / "metadata.json",
    )

    report = carica_report(
        schema_path=SCHEMA_PATH,
        oracle_path=tmp_path / "attesi.json",
        corpus_raw=tmp_path / "synth",
        metadata_path=tmp_path / "metadata.json",
        extractor=DummyExtractor(),
    )

    assert report is not None
    assert report.n_documenti == 2
    assert report.accuratezza_documento == 0.0
    assert len(report.campi) == 10


def test_violazione_invariante_finisce_in_gate_warning(tmp_path: Path) -> None:
    """T4.16 (ADR-045): lo strato Arbitrate, appena costruito, deve
    riflettersi nel gate — un'incongruenza aritmetica (somma_fasce, severita'
    'warning' nello schema reale) sposta il documento da pass a warning,
    anche se tutti i campi obbligatori sono presenti."""
    oracle_path = tmp_path / "attesi.json"
    genera_corpus(
        seed=1,
        n=1,
        out_dir=tmp_path / "synth",
        oracle_path=oracle_path,
        metadata_path=tmp_path / "metadata.json",
    )

    report = carica_report(
        schema_path=SCHEMA_PATH,
        oracle_path=oracle_path,
        corpus_raw=tmp_path / "synth",
        metadata_path=tmp_path / "metadata.json",
        extractor=_ExtractorConTotaleCorrotto(oracle_path),
    )

    assert report is not None
    assert report.violazioni_invarianti >= 1
    assert report.gate_warning >= 1
    assert report.gate_reject == 0


def test_carica_report_e_none_se_oracle_assente(tmp_path: Path) -> None:
    report = carica_report(
        schema_path=SCHEMA_PATH,
        oracle_path=tmp_path / "non_esiste.json",
        corpus_raw=tmp_path,
    )
    assert report is None
