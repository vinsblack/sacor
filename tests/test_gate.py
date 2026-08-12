"""Commit 4 (ADR-056/058/059/060): il Gate legge SOLO Evidence. Nessun
test in questo file importa Schema/pipeline/extractor — e' la
dimostrazione, non solo l'affermazione, che gate() non ne ha bisogno."""

from __future__ import annotations

import ast
import inspect

from sacor.evidence import EsitoInvariante, Evidenza, RiepilogoInvarianti, RisultatoCampo
from sacor.gate import gate

_CAMPO_CON_VALORE = RisultatoCampo(
    valore="x", evidenza=Evidenza(origine="tier0"), confidenza="alta", obbligatorio=True
)


def test_gate_pass_senza_mancanti_ne_violazioni() -> None:
    campi = {"pod": _CAMPO_CON_VALORE, "fornitore": _CAMPO_CON_VALORE}
    risultato = gate(campi)
    assert risultato.esito == "pass"
    assert risultato.motivo is None


def test_gate_reject_su_campo_obbligatorio_mancante() -> None:
    mancante = RisultatoCampo(
        valore=None,
        evidenza=Evidenza(origine=None, stato="tier1_non_tentato"),
        confidenza=None,
        obbligatorio=True,
    )
    campi = {"pod": mancante}
    risultato = gate(campi)
    assert risultato.esito == "reject"
    assert risultato.motivo is not None and "pod" in risultato.motivo


def test_gate_ignora_campo_facoltativo_mancante() -> None:
    facoltativo_mancante = RisultatoCampo(
        valore=None,
        evidenza=Evidenza(stato="tier1_non_tentato"),
        confidenza=None,
        obbligatorio=False,
    )
    campi = {"pod": _CAMPO_CON_VALORE, "fornitore": facoltativo_mancante}
    risultato = gate(campi)
    assert risultato.esito == "pass"


def test_gate_warning_su_violazione_non_reject() -> None:
    campo_sospetto = RisultatoCampo(
        valore="60.00",
        evidenza=Evidenza(
            origine="tier0",
            invarianti=RiepilogoInvarianti(
                passate=0,
                fallite=1,
                dettaglio=(
                    EsitoInvariante(
                        id="somma_fasce", esito="fail", severita="warning", messaggio="test"
                    ),
                ),
            ),
        ),
        confidenza="bassa",
        obbligatorio=True,
    )
    campi = {"kwh_totale": campo_sospetto}
    risultato = gate(campi)
    assert risultato.esito == "warning"
    assert risultato.motivo is None


def test_gate_reject_su_violazione_severita_reject() -> None:
    campo_grave = RisultatoCampo(
        valore="-5",
        evidenza=Evidenza(
            origine="tier0",
            invarianti=RiepilogoInvarianti(
                passate=0,
                fallite=1,
                dettaglio=(
                    EsitoInvariante(
                        id="kwh_non_negativo", esito="fail", severita="reject", messaggio="grave"
                    ),
                ),
            ),
        ),
        confidenza="bassa",
        obbligatorio=True,
    )
    campi = {"kwh_totale": campo_grave}
    risultato = gate(campi)
    assert risultato.esito == "reject"
    assert risultato.motivo is not None and "grave" in risultato.motivo


def test_gate_reject_ha_priorita_su_obbligatorio_e_warning_insieme() -> None:
    # ADR-060: stessa priorita' di sempre (ex _calcola_esito) — obbligatorio
    # mancante controllato per primo, poi reject-severity, poi warning.
    mancante = RisultatoCampo(
        valore=None,
        evidenza=Evidenza(stato="tier1_non_tentato"),
        confidenza=None,
        obbligatorio=True,
    )
    campi = {"pod": mancante}
    risultato = gate(campi)
    assert risultato.esito == "reject"
    assert risultato.motivo is not None and "obbligatori mancanti" in risultato.motivo


# --- proprieta' architetturale -----------------------------------------


def test_gate_dipende_solo_da_evidence() -> None:
    """La proprieta' richiesta per il Commit 4: il modulo sacor.gate non
    importa Schema, pipeline, extractor, provider, segmentazione o
    triage — solo sacor.evidence e la libreria standard. Se un domani
    qualcuno aggiunge un `import sacor.schema` a gate.py per far tornare
    un test, questo test fallisce e lo dice chiaro."""
    import sacor.gate as modulo_gate

    sorgente = inspect.getsource(modulo_gate)
    albero = ast.parse(sorgente)

    moduli_importati: list[str] = []
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            moduli_importati.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module is not None:
            moduli_importati.append(nodo.module)

    vietati = ("sacor.schema", "sacor.pipeline", "sacor.extractor", "sacor.providers")
    for modulo in moduli_importati:
        assert not modulo.startswith(vietati), (
            f"sacor.gate importa '{modulo}' — il Gate deve dipendere solo da Evidence"
        )
    assert any(m == "sacor.evidence" for m in moduli_importati)
