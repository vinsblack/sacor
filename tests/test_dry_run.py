"""T4.13 (trovato in code review): il dry-run non deve mai sottostimare un
modello per difetto — se manca la formula token_immagine per una pagina, il
modello va escluso dalla stima, non sommato con un costo parziale."""

from __future__ import annotations

from pathlib import Path

import pytest

import eval.run as run_mod
from eval.run import esegui_dry_run
from sacor.providers.pricing import PrezzoModello, TabellaPrezzi, TokenImmagineConfig
from scripts.genera_corpus import Flags, genera_corpus

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"

_FORMULA_TEST = TokenImmagineConfig(
    tipo="lineare_wh_750", formula="...", fonte="test", verificato_il="2026-01-01"
)


def test_dry_run_esclude_modello_senza_formula_token_immagine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "corpus"
    oracle_path = tmp_path / "attesi.json"
    metadata_path = tmp_path / "metadata.json"
    genera_corpus(
        seed=1,
        n=1,
        out_dir=out_dir,
        oracle_path=oracle_path,
        metadata_path=metadata_path,
        flags=Flags(scansione=True),  # tier 0 non estrae nulla -> serve una chiamata
    )

    prezzi_test = TabellaPrezzi(
        aggiornato_il="2026-01-01",
        prezzi={
            "modello-con-formula": PrezzoModello(1.0, 2.0, token_immagine=_FORMULA_TEST),
            "modello-senza-formula": PrezzoModello(1.0, 2.0, token_immagine=None),
        },
    )
    monkeypatch.setattr(run_mod, "carica_prezzi", lambda: prezzi_test)

    stima = esegui_dry_run(
        schema_path=SCHEMA_PATH,
        oracle_path=oracle_path,
        corpus_raw=out_dir,
        metadata_path=metadata_path,
        cache_dir=tmp_path / "cache",
        modelli=("modello-con-formula", "modello-senza-formula"),
    )

    assert stima is not None
    assert "modello-senza-formula" in stima.modelli_esclusi
    assert "modello-senza-formula" not in stima.costo_per_modello
    assert "modello-con-formula" in stima.costo_per_modello
    assert "modello-con-formula" not in stima.modelli_esclusi


def test_formatta_dry_run_segnala_i_modelli_esclusi() -> None:
    from eval.run import StimaDryRun, formatta_dry_run

    stima = StimaDryRun(
        chiamate_necessarie=1,
        gia_in_cache=0,
        file_disallineati=0,
        costo_per_modello={},
        modelli_esclusi=("modello-senza-formula",),
    )
    testo = formatta_dry_run(stima)
    assert "modello-senza-formula" in testo
    assert "ATTENZIONE" in testo
