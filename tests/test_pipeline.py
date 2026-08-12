"""TDD per sacor.pipeline (ADR-048): primo punto d'ingresso pubblico
single-file, prima esistevano solo script batch guidati da oracle
(eval/run.py, scripts/bakeoff.py). Usato dalla CLI."""

from __future__ import annotations

import random
from pathlib import Path

from sacor.invariants import Violazione
from sacor.pipeline import _calcola_esito, estrai_file
from sacor.schema import load
from scripts.genera_corpus import Flags, genera_documento

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"


def _scrivi(tmp_path: Path, nome: str, pdf_bytes: bytes) -> Path:
    p = tmp_path / nome
    p.write_bytes(pdf_bytes)
    return p


# --- _calcola_esito (puro) -------------------------------------------------


def test_esito_pass_senza_mancanti_ne_violazioni() -> None:
    schema = load(SCHEMA_PATH)
    valori = {c.nome: "x" for c in schema.campi}
    esito, motivo = _calcola_esito(schema, valori, ())
    assert esito == "pass"
    assert motivo is None


def test_esito_reject_su_campo_obbligatorio_mancante() -> None:
    schema = load(SCHEMA_PATH)
    valori = {c.nome: None for c in schema.campi}
    esito, motivo = _calcola_esito(schema, valori, ())
    assert esito == "reject"
    assert motivo is not None and "pod" in motivo


def test_esito_warning_su_violazione_non_reject() -> None:
    schema = load(SCHEMA_PATH)
    valori = {c.nome: "x" for c in schema.campi}
    violazione = Violazione(invariante_id="somma_fasce", severita="warning", messaggio="test")
    esito, motivo = _calcola_esito(schema, valori, (violazione,))
    assert esito == "warning"


def test_esito_reject_su_violazione_severita_reject_anche_con_obbligatori_presenti() -> None:
    schema = load(SCHEMA_PATH)
    valori = {c.nome: "x" for c in schema.campi}
    violazione = Violazione(invariante_id="somma_fasce", severita="reject", messaggio="grave")
    esito, motivo = _calcola_esito(schema, valori, (violazione,))
    assert esito == "reject"
    assert motivo is not None and "grave" in motivo


# --- estrai_file (integrazione, tier0 su documento sintetico) --------------


def test_estrai_file_documento_pulito_e_pass(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    pdf_bytes, _, _ = genera_documento(random.Random(50), "S030", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S030.pdf", pdf_bytes)

    risultati = estrai_file(path, schema)

    assert len(risultati) == 1
    assert risultati[0].esito == "pass"
    assert risultati[0].valori["pod"] is not None


def test_estrai_file_scansione_e_reject_per_obbligatori_mancanti(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    pdf_bytes, _, _ = genera_documento(
        random.Random(51), "S031", "Beta Luce", Flags(scansione=True)
    )
    path = _scrivi(tmp_path, "S031.pdf", pdf_bytes)

    risultati = estrai_file(path, schema)

    assert len(risultati) == 1
    assert risultati[0].esito == "reject"
    assert risultati[0].motivo is not None
