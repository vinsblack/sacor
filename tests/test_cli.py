"""TDD per sacor.cli (ADR-048): `sacor extract file.pdf`, il primo punto
d'ingresso pensato per chi integra sacor da fuori, non per chi lavora
dentro il repo."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from sacor.cli import main
from scripts.genera_corpus import Flags, genera_documento

REPO_ROOT = Path(__file__).parent.parent


def _scrivi(tmp_path: Path, nome: str, pdf_bytes: bytes) -> Path:
    p = tmp_path / nome
    p.write_bytes(pdf_bytes)
    return p


def test_extract_documento_pulito_esce_0_e_stampa_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(60), "S040", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S040.pdf", pdf_bytes)

    codice = main(["extract", str(path)])

    assert codice == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["esito"] == "pass"
    assert output[0]["valori"]["pod"] is not None


def test_extract_scansione_esce_1_reject(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(61), "S041", "Beta Luce", Flags(scansione=True))
    path = _scrivi(tmp_path, "S041.pdf", pdf_bytes)

    codice = main(["extract", str(path)])

    assert codice == 1
    output = json.loads(capsys.readouterr().out)
    assert output[0]["esito"] == "reject"
    assert output[0]["motivo"] is not None


def test_extract_file_inesistente_esce_2(capsys: pytest.CaptureFixture[str]) -> None:
    codice = main(["extract", "/non/esiste/davvero.pdf"])

    assert codice == 2
    assert "non trovato" in capsys.readouterr().err


def test_extract_schema_esplicito_sovrascrive_default(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(62), "S042", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S042.pdf", pdf_bytes)
    schema_path = REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"

    codice = main(["extract", str(path), "--schema", str(schema_path)])

    assert codice == 0


def test_main_senza_comando_esce_con_errore_argparse() -> None:
    with pytest.raises(SystemExit):
        main([])
