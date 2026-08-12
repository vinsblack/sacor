import json
from pathlib import Path

from sacor.providers.fake import FakeProvider, chiave_pagine
from sacor.schema import load

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"


def test_fake_provider_legge_valori_da_fixture(tmp_path: Path) -> None:
    pagine = [b"contenuto sintetico di pagina per il test"]
    chiave = chiave_pagine(pagine)
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        json.dumps({chiave: {"pod": "IT001E12345678", "fornitore": "Fornitore Test"}})
    )

    schema = load(SCHEMA_PATH)
    provider = FakeProvider(fixture_path)

    risposta = provider.estrai(pagine, "estrai i campi", schema.campi)

    assert risposta.valori["pod"] == "IT001E12345678"
    assert risposta.valori["fornitore"] == "Fornitore Test"
    assert risposta.token_input > 0
    assert risposta.token_output > 0
    assert risposta.costo_stimato > 0
    assert risposta.modello == "fake-model-v1"


def test_fake_provider_pagina_non_in_fixture_da_valori_none(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text("{}")

    schema = load(SCHEMA_PATH)
    provider = FakeProvider(fixture_path)

    risposta = provider.estrai([b"pagina mai vista dalla fixture"], "prompt", schema.campi)

    assert all(valore is None for valore in risposta.valori.values())


def test_fake_provider_e_deterministico(tmp_path: Path) -> None:
    pagine = [b"pagina identica"]
    chiave = chiave_pagine(pagine)
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps({chiave: {"pod": "IT001E12345678"}}))

    schema = load(SCHEMA_PATH)
    provider = FakeProvider(fixture_path)

    risposta_1 = provider.estrai(pagine, "prompt", schema.campi)
    risposta_2 = provider.estrai(pagine, "prompt", schema.campi)

    assert risposta_1 == risposta_2
