"""ADR-045 (Fase 1): il motore che valuta le invarianti dichiarate nello
schema contro un set di valori estratti veri — mai esistito prima, solo
il registro dei tipi noti (usato per validare le referenze al load)."""

from __future__ import annotations

from pathlib import Path

from sacor.invariants import valuta, valuta_tutte
from sacor.schema import Invariante, load

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_REALE = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"


def _somma_fasce(tolleranza: float = 0.005) -> Invariante:
    return Invariante(
        id="somma_fasce",
        tipo="somma_approssimata",
        severita="warning",
        params={
            "addendi": ["kwh_f1", "kwh_f2", "kwh_f3"],
            "totale": "kwh_totale",
            "tolleranza_relativa": tolleranza,
        },
    )


def _giorni_inclusivi(offset: int = 1) -> Invariante:
    return Invariante(
        id="giorni_inclusivi",
        tipo="differenza_giorni",
        severita="warning",
        params={"da": "periodo_da", "a": "periodo_a", "risultato": "giorni", "offset": offset},
    )


# --- somma_approssimata -----------------------------------------------


def test_somma_fasce_entro_tolleranza_nessuna_violazione() -> None:
    valori = {"kwh_f1": "10.00", "kwh_f2": "20.00", "kwh_f3": "30.00", "kwh_totale": "60.00"}
    assert valuta(_somma_fasce(), valori) is None


def test_somma_fasce_fuori_tolleranza_e_violazione() -> None:
    """T4.16 (ADR-045): caso reale trovato ADR-044 — F1+F2+F3=91 contro
    kwh_totale=277 nella stessa risposta del modello, mai intercettato
    perche' questo motore non esisteva."""
    valori = {"kwh_f1": "27.00", "kwh_f2": "23.00", "kwh_f3": "41.00", "kwh_totale": "277.00"}
    violazione = valuta(_somma_fasce(), valori)
    assert violazione is not None
    assert violazione.invariante_id == "somma_fasce"
    assert violazione.severita == "warning"


def test_somma_fasce_con_un_addendo_none_non_e_determinabile() -> None:
    valori = {"kwh_f1": "10.00", "kwh_f2": None, "kwh_f3": "30.00", "kwh_totale": "60.00"}
    assert valuta(_somma_fasce(), valori) is None


def test_somma_fasce_con_totale_none_non_e_determinabile() -> None:
    valori = {"kwh_f1": "10.00", "kwh_f2": "20.00", "kwh_f3": "30.00", "kwh_totale": None}
    assert valuta(_somma_fasce(), valori) is None


def test_somma_fasce_valore_non_decimale_non_e_determinabile() -> None:
    """Mai un crash su un valore malformato: non determinabile, non un
    errore (stesso principio di repair.py)."""
    valori = {"kwh_f1": "non-un-numero", "kwh_f2": "20.00", "kwh_f3": "30.00", "kwh_totale": "50"}
    assert valuta(_somma_fasce(), valori) is None


# --- differenza_giorni ---------------------------------------------------


def test_giorni_corretti_nessuna_violazione() -> None:
    valori = {"periodo_da": "2025-09-01", "periodo_a": "2025-09-30", "giorni": "30"}
    assert valuta(_giorni_inclusivi(), valori) is None


def test_giorni_sbagliati_e_violazione() -> None:
    valori = {"periodo_da": "2025-09-01", "periodo_a": "2025-09-30", "giorni": "29"}
    violazione = valuta(_giorni_inclusivi(), valori)
    assert violazione is not None
    assert violazione.invariante_id == "giorni_inclusivi"


def test_giorni_con_data_mancante_non_e_determinabile() -> None:
    valori = {"periodo_da": None, "periodo_a": "2025-09-30", "giorni": "30"}
    assert valuta(_giorni_inclusivi(), valori) is None


def test_giorni_data_malformata_non_e_determinabile() -> None:
    valori = {"periodo_da": "non-una-data", "periodo_a": "2025-09-30", "giorni": "30"}
    assert valuta(_giorni_inclusivi(), valori) is None


# --- valuta_tutte, sullo schema reale --------------------------------------


def test_valuta_tutte_su_valori_perfetti_nessuna_violazione() -> None:
    schema = load(SCHEMA_REALE)
    valori = {
        "pod": "IT001E12345678",
        "fornitore": "Alfa Energia",
        "periodo_da": "2025-09-01",
        "periodo_a": "2025-09-30",
        "giorni": "30",
        "kwh_totale": "60.00",
        "kwh_f1": "10.00",
        "kwh_f2": "20.00",
        "kwh_f3": "30.00",
        "importo_totale": "50.00",
    }
    assert valuta_tutte(schema, valori) == ()


# --- valore_minimo -----------------------------------------------------


def _kwh_non_negativo() -> Invariante:
    return Invariante(
        id="kwh_totale_non_negativo",
        tipo="valore_minimo",
        severita="warning",
        params={"campo": "kwh_totale", "minimo": 0},
    )


def test_valore_minimo_sopra_soglia_nessuna_violazione() -> None:
    assert valuta(_kwh_non_negativo(), {"kwh_totale": "60.00"}) is None


def test_valore_minimo_esattamente_sulla_soglia_nessuna_violazione() -> None:
    assert valuta(_kwh_non_negativo(), {"kwh_totale": "0"}) is None


def test_valore_minimo_sotto_soglia_e_violazione() -> None:
    violazione = valuta(_kwh_non_negativo(), {"kwh_totale": "-5.00"})
    assert violazione is not None
    assert violazione.invariante_id == "kwh_totale_non_negativo"


def test_valore_minimo_con_campo_none_non_e_determinabile() -> None:
    assert valuta(_kwh_non_negativo(), {"kwh_totale": None}) is None


def test_valore_minimo_valore_non_decimale_non_e_determinabile() -> None:
    assert valuta(_kwh_non_negativo(), {"kwh_totale": "non-un-numero"}) is None


# --- ordine_date ---------------------------------------------------------


def _periodo_ordinato() -> Invariante:
    return Invariante(
        id="periodo_ordinato",
        tipo="ordine_date",
        severita="warning",
        params={"precedente": "periodo_da", "successiva": "periodo_a"},
    )


def test_ordine_date_corretto_nessuna_violazione() -> None:
    valori = {"periodo_da": "2025-09-01", "periodo_a": "2025-09-30"}
    assert valuta(_periodo_ordinato(), valori) is None


def test_ordine_date_uguali_nessuna_violazione() -> None:
    valori = {"periodo_da": "2025-09-01", "periodo_a": "2025-09-01"}
    assert valuta(_periodo_ordinato(), valori) is None


def test_ordine_date_invertite_e_violazione() -> None:
    valori = {"periodo_da": "2025-09-30", "periodo_a": "2025-09-01"}
    violazione = valuta(_periodo_ordinato(), valori)
    assert violazione is not None
    assert violazione.invariante_id == "periodo_ordinato"


def test_ordine_date_con_data_mancante_non_e_determinabile() -> None:
    valori = {"periodo_da": None, "periodo_a": "2025-09-01"}
    assert valuta(_periodo_ordinato(), valori) is None


def test_ordine_date_malformata_non_e_determinabile() -> None:
    valori = {"periodo_da": "non-una-data", "periodo_a": "2025-09-01"}
    assert valuta(_periodo_ordinato(), valori) is None


# --- formato ---------------------------------------------------------


def _formato_pod() -> Invariante:
    return Invariante(
        id="formato_pod",
        tipo="formato",
        severita="warning",
        params={"campo": "pod", "pattern": r"IT\d{3}E\d{8}"},
    )


def test_formato_valido_nessuna_violazione() -> None:
    assert valuta(_formato_pod(), {"pod": "IT001E12345678"}) is None


def test_formato_non_valido_e_violazione() -> None:
    violazione = valuta(_formato_pod(), {"pod": "non-un-pod"})
    assert violazione is not None
    assert violazione.invariante_id == "formato_pod"


def test_formato_con_campo_none_non_e_determinabile() -> None:
    assert valuta(_formato_pod(), {"pod": None}) is None


def test_valuta_tutte_su_valori_incongruenti_trova_entrambe() -> None:
    schema = load(SCHEMA_REALE)
    valori = {
        "pod": "IT001E12345678",
        "fornitore": "Alfa Energia",
        "periodo_da": "2025-09-01",
        "periodo_a": "2025-09-30",
        "giorni": "5",  # sbagliato, atteso 30
        "kwh_totale": "277.00",
        "kwh_f1": "27.00",
        "kwh_f2": "23.00",
        "kwh_f3": "41.00",  # somma 91, non 277
        "importo_totale": "50.00",
    }
    violazioni = valuta_tutte(schema, valori)
    assert {v.invariante_id for v in violazioni} == {"somma_fasce", "giorni_inclusivi"}
