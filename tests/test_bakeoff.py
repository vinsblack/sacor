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
