import json
from pathlib import Path

import pytest

from sacor.oracle import OracleError, load_oracle
from sacor.schema import load

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"
ORACLE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "attesi.json"


def test_oracle_valido_carica() -> None:
    schema = load(SCHEMA_PATH)
    oracle = load_oracle(ORACLE_FIXTURE, schema)
    assert oracle.documento == "bolletta_luce_it"
    assert set(oracle.documenti) == {"F001", "F002"}


def test_documento_con_campo_in_piu_alza_oracle_error(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    dati = json.loads(ORACLE_FIXTURE.read_text())
    dati["documenti"]["F001"]["campo_extra"] = "sorpresa"
    p = tmp_path / "attesi.json"
    p.write_text(json.dumps(dati))

    with pytest.raises(OracleError):
        load_oracle(p, schema)


def test_documento_diverso_dallo_schema_alza_oracle_error(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    dati = json.loads(ORACLE_FIXTURE.read_text())
    dati["documento"] = "bolletta_gas_it"
    p = tmp_path / "attesi.json"
    p.write_text(json.dumps(dati))

    with pytest.raises(OracleError):
        load_oracle(p, schema)
