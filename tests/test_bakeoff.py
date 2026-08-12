"""Regressione T4.13 (BASSA, trovato in review): esegui_bakeoff() rifaceva
triage/segmentazione/rendering PDF per ogni file del corpus DUE volte in un
solo giro — una volta per calcolare le chiamate necessarie (istanze_da_
completare), una seconda identica dentro esegui_dry_run() per la sola stima
di costo. Nessuna chiamata di rete qui: un modello con prefisso sconosciuto
fallisce dentro _provider_per_modello PRIMA di qualunque tentativo di rete
(stessa garanzia di 'SDK sempre mockato' di test_providers_reali.py)."""

from __future__ import annotations

import pytest

import eval.run as run_mod
import scripts.bakeoff_reale as bakeoff_reale_mod
from scripts.bakeoff import esegui_bakeoff


def test_bakeoff_non_rifa_triage_due_volte_per_file(monkeypatch: pytest.MonkeyPatch) -> None:
    analizza_originale = run_mod.analizza
    chiamate_per_file: dict[str, int] = {}

    def _analizza_contata(path):  # type: ignore[no-untyped-def]
        chiamate_per_file[path.name] = chiamate_per_file.get(path.name, 0) + 1
        return analizza_originale(path)

    monkeypatch.setattr(run_mod, "analizza", _analizza_contata)

    esegui_bakeoff(modelli=("modello-prefisso-sconosciuto",))

    assert chiamate_per_file, "il corpus reale deve produrre almeno un file da triagiare"
    assert all(n == 1 for n in chiamate_per_file.values()), (
        f"triage rifatto piu' di una volta per file nello stesso giro: {chiamate_per_file}"
    )


def test_solo_arbitrato_salta_il_bakeoff_per_modello(monkeypatch: pytest.MonkeyPatch) -> None:
    """--solo-arbitrato non deve rifare (e ripagare) il bake-off per-modello
    gia' misurato in un giro precedente — solo la coppia in arbitrato."""
    if not bakeoff_reale_mod.CORPUS_RAW.is_dir():
        pytest.skip("PDF reali non presenti in locale (corpus/reale/raw/, mai nel repo)")

    chiamate_valuta_modello = 0
    chiamate_valuta_arbitrato = 0

    def _finto_valuta_modello(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal chiamate_valuta_modello
        chiamate_valuta_modello += 1
        raise AssertionError("non deve essere chiamato con --solo-arbitrato")

    def _finto_valuta_arbitrato(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        nonlocal chiamate_valuta_arbitrato
        chiamate_valuta_arbitrato += 1
        return None

    monkeypatch.setattr(bakeoff_reale_mod, "_valuta_modello", _finto_valuta_modello)
    monkeypatch.setattr(bakeoff_reale_mod, "_valuta_arbitrato", _finto_valuta_arbitrato)
    monkeypatch.setattr(bakeoff_reale_mod, "formatta_tabella_arbitrato", lambda _riga: "")

    codice = bakeoff_reale_mod.main(["--arbitrato", "modello-a", "modello-b", "--solo-arbitrato"])

    assert codice == 0
    assert chiamate_valuta_modello == 0
    assert chiamate_valuta_arbitrato == 1
