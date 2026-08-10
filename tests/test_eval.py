from pathlib import Path

from eval.run import carica_report
from sacor.extractor import DummyExtractor
from scripts.genera_corpus import genera_corpus

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"


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


def test_carica_report_e_none_se_oracle_assente(tmp_path: Path) -> None:
    report = carica_report(
        schema_path=SCHEMA_PATH,
        oracle_path=tmp_path / "non_esiste.json",
        corpus_raw=tmp_path,
    )
    assert report is None
