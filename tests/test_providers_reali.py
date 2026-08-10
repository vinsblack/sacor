"""T4.3: prompt builder, parsing/normalizzazione risposta, tabella prezzi, e
i due adattatori reali con l'SDK sempre mockato — nessuna rete, mai (stessa
regola di FakeProvider)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sacor.providers.anthropic import AnthropicProvider
from sacor.providers.errors import ErroreProvider
from sacor.providers.openai import OpenAIProvider
from sacor.providers.parsing import estrai_json, normalizza_risposta
from sacor.providers.pricing import (
    PrezziError,
    PrezzoModello,
    TabellaPrezzi,
    TokenImmagineConfig,
    carica,
)
from sacor.providers.prompt import costruisci_prompt
from sacor.providers.token_stima import TipoFormulaSconosciuto, stima_token_immagine
from sacor.schema import Campo, load

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"
PREZZI_PATH = REPO_ROOT / "config" / "prezzi_modelli.yaml"


def _campi(*nomi_tipi: tuple[str, str]) -> list[Campo]:
    return [Campo(nome=n, tipo=t, obbligatorio=True, estrazione=None) for n, t in nomi_tipi]  # type: ignore[arg-type]


# --- prompt.costruisci_prompt --------------------------------------------


def test_prompt_chiede_esattamente_i_campi_passati() -> None:
    campi = _campi(("pod", "string"), ("importo_totale", "decimal"))
    prompt = costruisci_prompt(campi)

    assert "pod" in prompt
    assert "importo_totale" in prompt
    assert "numero decimale" in prompt
    assert "null" in prompt
    assert "JSON" in prompt


def test_prompt_generato_dallo_schema_reale_senza_hardcode() -> None:
    schema = load(SCHEMA_PATH)
    prompt = costruisci_prompt(schema.campi)
    for campo in schema.campi:
        assert campo.nome in prompt


# --- parsing.estrai_json / normalizza_risposta ----------------------------


def test_estrai_json_puro() -> None:
    assert estrai_json('{"pod": "IT001E12345678"}') == {"pod": "IT001E12345678"}


def test_estrai_json_toglie_blocco_markdown() -> None:
    testo = '```json\n{"pod": "IT001E12345678"}\n```'
    assert estrai_json(testo) == {"pod": "IT001E12345678"}


def test_estrai_json_non_parsabile_da_none() -> None:
    assert estrai_json("questo non e' JSON") is None


def test_estrai_json_lista_da_none() -> None:
    assert estrai_json("[1, 2, 3]") is None


def test_normalizza_risposta_json_non_parsabile_tutti_none() -> None:
    campi = _campi(("pod", "string"), ("importo_totale", "decimal"))
    valori = normalizza_risposta("non e' JSON", campi)
    assert valori == {"pod": None, "importo_totale": None}


def test_normalizza_risposta_campo_assente_e_none() -> None:
    campi = _campi(("pod", "string"), ("importo_totale", "decimal"))
    valori = normalizza_risposta('{"pod": "IT001E12345678"}', campi)
    assert valori == {"pod": "IT001E12345678", "importo_totale": None}


def test_normalizza_risposta_passa_per_repair() -> None:
    # "1.234" e' l'ambiguo documentato in repair.py: ne' migliaia ne'
    # decimale con certezza -> None, stessa regola del tier 0.
    campi = _campi(("importo_totale", "decimal"))
    valori = normalizza_risposta('{"importo_totale": "1.234"}', campi)
    assert valori == {"importo_totale": None}


# --- pricing ---------------------------------------------------------------


def test_carica_prezzi_reali_del_repo() -> None:
    prezzi = carica(PREZZI_PATH)
    assert prezzi.aggiornato_il
    assert prezzi.prezzo("claude-haiku-4-5").costo_input_per_milione > 0


def test_prezzo_modello_sconosciuto_solleva() -> None:
    prezzi = TabellaPrezzi(aggiornato_il="2026-01-01", prezzi={})
    with pytest.raises(PrezziError):
        prezzi.prezzo("modello-mai-sentito")


def test_carica_prezzi_file_mancante(tmp_path: Path) -> None:
    with pytest.raises(PrezziError):
        carica(tmp_path / "non_esiste.yaml")


def test_carica_prezzi_senza_data_aggiornamento(tmp_path: Path) -> None:
    path = tmp_path / "prezzi.yaml"
    path.write_text(
        "modelli:\n  x:\n    costo_input_per_milione: 1\n    costo_output_per_milione: 2\n"
    )
    with pytest.raises(PrezziError):
        carica(path)


def test_costo_calcolato_da_token() -> None:
    prezzo = PrezzoModello(costo_input_per_milione=1.0, costo_output_per_milione=2.0)
    assert prezzo.costo(token_input=1_000_000, token_output=500_000) == pytest.approx(2.0)


def test_carica_prezzi_reali_parsa_token_immagine() -> None:
    prezzi = carica(PREZZI_PATH)
    config = prezzi.prezzo("claude-haiku-4-5").token_immagine
    assert config is not None
    assert config.tipo == "lineare_wh_750"
    assert config.fonte
    assert config.verificato_il


def test_carica_prezzi_token_immagine_incompleto_solleva(tmp_path: Path) -> None:
    path = tmp_path / "prezzi.yaml"
    path.write_text(
        "aggiornato_il: '2026-01-01'\n"
        "modelli:\n"
        "  x:\n"
        "    costo_input_per_milione: 1\n"
        "    costo_output_per_milione: 2\n"
        "    token_immagine:\n"
        "      tipo: lineare_wh_750\n"  # manca formula/fonte/verificato_il
    )
    with pytest.raises(PrezziError):
        carica(path)


# --- token_stima.stima_token_immagine (T4.5, C1) --------------------------


def test_stima_token_immagine_anthropic_lineare() -> None:
    config = TokenImmagineConfig(
        tipo="lineare_wh_750", formula="...", fonte="...", verificato_il="2026-08-10"
    )
    prezzo = PrezzoModello(1.0, 2.0, token_immagine=config)
    # 1000x750 = 750_000 / 750 = 1000
    assert stima_token_immagine(prezzo, 1000, 750) == 1000


def test_stima_token_immagine_openai_tile() -> None:
    config = TokenImmagineConfig(
        tipo="tile_512_openai", formula="...", fonte="...", verificato_il="2026-08-10"
    )
    prezzo = PrezzoModello(1.0, 2.0, token_immagine=config)
    # 512x512 = 1 tile -> 85 + 170*1
    assert stima_token_immagine(prezzo, 512, 512) == 255


def test_stima_token_immagine_openai_al_rialzo_e_quadrupla() -> None:
    base = TokenImmagineConfig(
        tipo="tile_512_openai", formula="...", fonte="...", verificato_il="2026-08-10"
    )
    rialzo = TokenImmagineConfig(
        tipo="tile_512_openai_stima_al_rialzo",
        formula="...",
        fonte="...",
        verificato_il="2026-08-10",
    )
    prezzo_base = PrezzoModello(1.0, 2.0, token_immagine=base)
    prezzo_rialzo = PrezzoModello(1.0, 2.0, token_immagine=rialzo)
    atteso = stima_token_immagine(prezzo_base, 512, 512) * 4
    assert stima_token_immagine(prezzo_rialzo, 512, 512) == atteso


def test_stima_token_immagine_senza_config_solleva() -> None:
    prezzo = PrezzoModello(1.0, 2.0, token_immagine=None)
    with pytest.raises(TipoFormulaSconosciuto):
        stima_token_immagine(prezzo, 100, 100)


# --- AnthropicProvider / OpenAIProvider: SDK sempre mockato --------------


def test_anthropic_provider_senza_chiave_solleva(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ErroreProvider):
        AnthropicProvider("claude-haiku-4-5")


def test_openai_provider_senza_chiave_solleva(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ErroreProvider):
        OpenAIProvider("gpt-4o-mini")


def test_anthropic_provider_estrae_da_risposta_mockata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta-di-test")
    prezzi = TabellaPrezzi(
        aggiornato_il="2026-01-01",
        prezzi={"claude-haiku-4-5": PrezzoModello(1.0, 2.0)},
    )
    provider = AnthropicProvider("claude-haiku-4-5", prezzi=prezzi)

    risposta_finta = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"pod": "IT001E12345678"}')],
        usage=SimpleNamespace(input_tokens=100, output_tokens=10),
    )
    provider._client.messages.create = lambda **kwargs: risposta_finta  # type: ignore[method-assign]

    campi = _campi(("pod", "string"))
    risultato = provider.estrai([b"immagine finta"], "prompt", campi)

    assert risultato.valori == {"pod": "IT001E12345678"}
    assert risultato.token_input == 100
    assert risultato.token_output == 10
    assert risultato.costo_stimato == pytest.approx(100 / 1_000_000 + 10 * 2 / 1_000_000)
    assert risultato.modello == "claude-haiku-4-5"


def test_openai_provider_estrae_da_risposta_mockata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "chiave-finta-di-test")
    prezzi = TabellaPrezzi(
        aggiornato_il="2026-01-01",
        prezzi={"gpt-4o-mini": PrezzoModello(1.0, 2.0)},
    )
    provider = OpenAIProvider("gpt-4o-mini", prezzi=prezzi)

    risposta_finta = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"pod": "IT001E12345678"}'))],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10),
    )
    provider._client.chat.completions.create = lambda **kwargs: risposta_finta  # type: ignore[method-assign]

    campi = _campi(("pod", "string"))
    risultato = provider.estrai([b"immagine finta"], "prompt", campi)

    assert risultato.valori == {"pod": "IT001E12345678"}
    assert risultato.token_input == 100
    assert risultato.token_output == 10
    assert risultato.modello == "gpt-4o-mini"
