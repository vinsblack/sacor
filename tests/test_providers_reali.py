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
SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"
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


def test_prompt_con_campo_data_vieta_deduzione_da_mese_parziale() -> None:
    # T4.12: misurato che il modello deduce primo/ultimo giorno del mese da
    # una data parziale ("giugno 2025") invece di rispondere null — regola
    # esplicita per il caso concreto, non solo quella generica anti-invenzione.
    campi = _campi(("periodo_da", "date"))
    prompt = costruisci_prompt(campi)
    assert "primo o l'ultimo giorno del mese" in prompt


def test_prompt_senza_campi_data_non_menziona_la_regola_data() -> None:
    campi = _campi(("pod", "string"))
    prompt = costruisci_prompt(campi)
    assert "primo o l'ultimo giorno del mese" not in prompt


def test_prompt_include_la_descrizione_del_campo_se_presente() -> None:
    """T4.15 (ADR-043): un campo con guida di disambiguazione nello schema
    la porta nel prompt — il builder resta generico (ADR-017), la
    conoscenza di dominio vive nello schema, non nel codice."""
    campo = Campo(
        nome="importo_totale",
        tipo="decimal",
        obbligatorio=True,
        estrazione=None,
        descrizione="usa il totale energia, non un eventuale totale con extra",
    )
    prompt = costruisci_prompt([campo])
    assert "usa il totale energia, non un eventuale totale con extra" in prompt


def test_prompt_senza_descrizione_resta_solo_tipo() -> None:
    campi = _campi(("pod", "string"))
    prompt = costruisci_prompt(campi)
    assert "pod: testo libero" in prompt


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


def test_normalizza_risposta_accetta_numero_json_nativo_decimal() -> None:
    """T4.16 (trovato analizzando il dump grezzo di haiku-4-5 su bollette
    reali): il modello risponde spesso con un numero JSON nativo (48.5) e
    non una stringa ("48.5") per i campi numerici — JSON valido, comportamento
    naturale, non un errore del modello. Prima di questo fix veniva scartato
    a None regardless del valore, mai passato a ripara() — spiegava gran
    parte del basso field-accuracy sul corpus reale, non un problema di
    prompt (ADR-043/044)."""
    campi = _campi(("importo_totale", "decimal"))
    valori = normalizza_risposta('{"importo_totale": 36.11}', campi)
    assert valori == {"importo_totale": "36.11"}


def test_normalizza_risposta_accetta_numero_json_nativo_integer() -> None:
    campi = _campi(("giorni", "integer"))
    valori = normalizza_risposta('{"giorni": 30}', campi)
    assert valori == {"giorni": "30"}


def test_normalizza_risposta_accetta_intero_come_float_json() -> None:
    """Un integer talvolta arriva come float JSON (30.0) quando il modello
    non distingue i due tipi numerici nella risposta."""
    campi = _campi(("giorni", "integer"))
    valori = normalizza_risposta('{"giorni": 30.0}', campi)
    assert valori == {"giorni": "30"}


def test_normalizza_risposta_campo_stringa_non_accetta_numero() -> None:
    """Un numero al posto di un fornitore/data non e' normalizzabile — la
    tolleranza al tipo numerico JSON vale solo per i campi decimal/integer,
    mai per string/date (un 123 non diventa mai un nome fornitore)."""
    campi = _campi(("fornitore", "string"))
    valori = normalizza_risposta('{"fornitore": 123}', campi)
    assert valori == {"fornitore": None}


def test_normalizza_risposta_booleano_non_e_un_numero_valido() -> None:
    """bool e' sottoclasse di int in Python — deve restare escluso
    esplicitamente, mai normalizzato come se fosse 0/1."""
    campi = _campi(("giorni", "integer"))
    valori = normalizza_risposta('{"giorni": true}', campi)
    assert valori == {"giorni": None}


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


def test_costo_con_token_cache_configurati() -> None:
    prezzo = PrezzoModello(
        costo_input_per_milione=1.0,
        costo_output_per_milione=2.0,
        costo_cache_scrittura_per_milione=1.25,
        costo_cache_lettura_per_milione=0.10,
    )
    costo = prezzo.costo(
        token_input=0,
        token_output=0,
        token_cache_scrittura=1_000_000,
        token_cache_lettura=1_000_000,
    )
    assert costo == pytest.approx(1.25 + 0.10)


def test_costo_con_token_cache_senza_prezzo_configurato_solleva() -> None:
    """Mai assumere costo zero per token di cache non prezzati (stesso
    principio di 'mai indovinare' applicato al costo, non solo ai valori
    estratti)."""
    prezzo = PrezzoModello(costo_input_per_milione=1.0, costo_output_per_milione=2.0)
    with pytest.raises(PrezziError):
        prezzo.costo(token_input=0, token_output=0, token_cache_scrittura=100)
    with pytest.raises(PrezziError):
        prezzo.costo(token_input=0, token_output=0, token_cache_lettura=100)


def test_carica_prezzi_reali_parsa_costi_cache() -> None:
    prezzi = carica(PREZZI_PATH)
    prezzo = prezzi.prezzo("claude-opus-5")
    assert prezzo.costo_cache_scrittura_per_milione == pytest.approx(6.25)
    assert prezzo.costo_cache_lettura_per_milione == pytest.approx(0.50)


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
        stop_reason="end_turn",
    )
    provider._client.messages.create = lambda **kwargs: risposta_finta  # type: ignore[method-assign]

    campi = _campi(("pod", "string"))
    risultato = provider.estrai([b"immagine finta"], "prompt", campi)

    assert risultato.valori == {"pod": "IT001E12345678"}
    assert risultato.token_input == 100
    assert risultato.token_output == 10
    assert risultato.costo_stimato == pytest.approx(100 / 1_000_000 + 10 * 2 / 1_000_000)
    assert risultato.modello == "claude-haiku-4-5"


def test_anthropic_provider_manda_prompt_prima_delle_immagini_con_cache_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-054: il testo deve essere il PRIMO blocco del content e portare
    cache_control — e' lui il prefisso cacheabile, le immagini (variabili
    per documento) vengono dopo e restano fuori dal breakpoint."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta-di-test")
    prezzi = TabellaPrezzi(
        aggiornato_il="2026-01-01",
        prezzi={"claude-haiku-4-5": PrezzoModello(1.0, 2.0)},
    )
    provider = AnthropicProvider("claude-haiku-4-5", prezzi=prezzi)

    risposta_finta = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"pod": "IT001E12345678"}')],
        usage=SimpleNamespace(input_tokens=100, output_tokens=10),
        stop_reason="end_turn",
    )
    content_ricevuto: list[dict[str, object]] = []

    def _create(**kwargs: object) -> SimpleNamespace:
        content_ricevuto.extend(kwargs["messages"][0]["content"])  # type: ignore[index]
        return risposta_finta

    provider._client.messages.create = _create  # type: ignore[method-assign]

    campi = _campi(("pod", "string"))
    provider.estrai([b"immagine finta 1", b"immagine finta 2"], "prompt", campi)

    assert content_ricevuto[0]["type"] == "text"
    assert content_ricevuto[0]["cache_control"] == {"type": "ephemeral"}
    assert [b["type"] for b in content_ricevuto[1:]] == ["image", "image"]
    assert "cache_control" not in content_ricevuto[1]


def test_anthropic_provider_conta_costo_dei_token_di_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta-di-test")
    prezzi = TabellaPrezzi(
        aggiornato_il="2026-01-01",
        prezzi={
            "claude-haiku-4-5": PrezzoModello(
                1.0,
                2.0,
                costo_cache_scrittura_per_milione=1.25,
                costo_cache_lettura_per_milione=0.10,
            )
        },
    )
    provider = AnthropicProvider("claude-haiku-4-5", prezzi=prezzi)

    risposta_finta = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"pod": "IT001E12345678"}')],
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=10,
            cache_creation_input_tokens=500,
            cache_read_input_tokens=1000,
        ),
        stop_reason="end_turn",
    )
    provider._client.messages.create = lambda **kwargs: risposta_finta  # type: ignore[method-assign]

    campi = _campi(("pod", "string"))
    risultato = provider.estrai([b"immagine finta"], "prompt", campi)

    atteso = 100 / 1_000_000 + 10 * 2 / 1_000_000 + 500 * 1.25 / 1_000_000 + 1000 * 0.10 / 1_000_000
    assert risultato.costo_stimato == pytest.approx(atteso)


def test_anthropic_provider_senza_cache_nella_risposta_non_rompe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una risposta che non ha mai usato cache_control (o un SDK vecchio)
    non ha gli attributi cache_*_input_tokens sull'oggetto usage: deve
    trattarsi come zero, non far esplodere getattr."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta-di-test")
    prezzi = TabellaPrezzi(
        aggiornato_il="2026-01-01",
        prezzi={"claude-haiku-4-5": PrezzoModello(1.0, 2.0)},
    )
    provider = AnthropicProvider("claude-haiku-4-5", prezzi=prezzi)

    risposta_finta = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"pod": "IT001E12345678"}')],
        usage=SimpleNamespace(input_tokens=100, output_tokens=10),
        stop_reason="end_turn",
    )
    provider._client.messages.create = lambda **kwargs: risposta_finta  # type: ignore[method-assign]

    campi = _campi(("pod", "string"))
    risultato = provider.estrai([b"immagine finta"], "prompt", campi)

    assert risultato.costo_stimato == pytest.approx(100 / 1_000_000 + 10 * 2 / 1_000_000)


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal", "pause_turn"])
def test_anthropic_provider_stop_reason_anomalo_solleva(
    monkeypatch: pytest.MonkeyPatch, stop_reason: str
) -> None:
    """T4.13 (trovato in review): una risposta troncata (max_tokens) o
    rifiutata non deve diventare silenziosamente 'tutti i campi None' —
    indistinguibile da 'il modello non ha trovato nulla'. La chiamata non e'
    andata a buon fine: ErroreProvider, non un RispostaModello con valori
    vuoti."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta-di-test")
    prezzi = TabellaPrezzi(
        aggiornato_il="2026-01-01",
        prezzi={"claude-haiku-4-5": PrezzoModello(1.0, 2.0)},
    )
    provider = AnthropicProvider("claude-haiku-4-5", prezzi=prezzi)

    risposta_finta = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"pod": "IT001E12345678"}')],
        usage=SimpleNamespace(input_tokens=100, output_tokens=10),
        stop_reason=stop_reason,
    )
    provider._client.messages.create = lambda **kwargs: risposta_finta  # type: ignore[method-assign]

    campi = _campi(("pod", "string"))
    with pytest.raises(ErroreProvider, match=stop_reason):
        provider.estrai([b"immagine finta"], "prompt", campi)


def test_openai_provider_estrae_da_risposta_mockata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "chiave-finta-di-test")
    prezzi = TabellaPrezzi(
        aggiornato_il="2026-01-01",
        prezzi={"gpt-4o-mini": PrezzoModello(1.0, 2.0)},
    )
    provider = OpenAIProvider("gpt-4o-mini", prezzi=prezzi)

    risposta_finta = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='{"pod": "IT001E12345678"}'),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10),
    )
    provider._client.chat.completions.create = lambda **kwargs: risposta_finta  # type: ignore[method-assign]

    campi = _campi(("pod", "string"))
    risultato = provider.estrai([b"immagine finta"], "prompt", campi)

    assert risultato.valori == {"pod": "IT001E12345678"}
    assert risultato.token_input == 100
    assert risultato.token_output == 10
    assert risultato.modello == "gpt-4o-mini"


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", "tool_calls"])
def test_openai_provider_finish_reason_anomalo_solleva(
    monkeypatch: pytest.MonkeyPatch, finish_reason: str
) -> None:
    """Stesso principio del provider Anthropic: una risposta troncata
    (length) o filtrata dal content moderation non deve diventare
    silenziosamente 'tutti i campi None'."""
    monkeypatch.setenv("OPENAI_API_KEY", "chiave-finta-di-test")
    prezzi = TabellaPrezzi(
        aggiornato_il="2026-01-01",
        prezzi={"gpt-4o-mini": PrezzoModello(1.0, 2.0)},
    )
    provider = OpenAIProvider("gpt-4o-mini", prezzi=prezzi)

    risposta_finta = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='{"pod": "IT001E12345678"}'),
                finish_reason=finish_reason,
            )
        ],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10),
    )
    provider._client.chat.completions.create = lambda **kwargs: risposta_finta  # type: ignore[method-assign]

    campi = _campi(("pod", "string"))
    with pytest.raises(ErroreProvider, match=finish_reason):
        provider.estrai([b"immagine finta"], "prompt", campi)
