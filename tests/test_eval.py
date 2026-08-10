from pathlib import Path

from eval.run import carica_report
from sacor.extractor import DummyExtractor

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"
ORACLE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "attesi.json"
CORPUS_RAW = REPO_ROOT / "corpus" / "raw"


def test_run_completo_su_fixture_con_dummy_extractor() -> None:
    report = carica_report(
        schema_path=SCHEMA_PATH,
        oracle_path=ORACLE_FIXTURE,
        corpus_raw=CORPUS_RAW,
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
        corpus_raw=CORPUS_RAW,
    )
    assert report is None
