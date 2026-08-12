"""ADR-045 (Fase 1): il motore che valuta le invarianti dichiarate nello
schema contro un set di valori estratti veri — mai esistito prima, solo
il registro dei tipi noti (usato per validare le referenze al load)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sacor.invariants import (
    campi_coinvolti,
    deriva_mancanti,
    deriva_mancanti_con_provenienza,
    valuta,
    valuta_tutte,
    valuta_tutte_con_esito,
)
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


# --- campi_coinvolti (usato dalla confidenza per campo, ADR-048 punto 2) --


def test_campi_coinvolti_somma_approssimata_addendi_e_totale() -> None:
    assert set(campi_coinvolti(_somma_fasce())) == {"kwh_f1", "kwh_f2", "kwh_f3", "kwh_totale"}


def test_campi_coinvolti_differenza_giorni() -> None:
    assert set(campi_coinvolti(_giorni_inclusivi())) == {"periodo_da", "periodo_a", "giorni"}


def test_campi_coinvolti_campo_singolo() -> None:
    assert campi_coinvolti(_formato_pod()) == ("pod",)


# --- deriva_mancanti (ADR-051: mai indovinare quando e' matematica) -------


def test_deriva_periodo_a_da_periodo_da_e_giorni() -> None:
    schema = load(SCHEMA_REALE)
    valori = {
        "periodo_da": "2025-10-01",
        "periodo_a": None,
        "giorni": "31",
    }
    derivati = deriva_mancanti(schema, valori)
    assert derivati["periodo_a"] == "2025-10-31"


def test_deriva_periodo_da_da_periodo_a_e_giorni() -> None:
    schema = load(SCHEMA_REALE)
    valori = {
        "periodo_da": None,
        "periodo_a": "2025-10-31",
        "giorni": "31",
    }
    derivati = deriva_mancanti(schema, valori)
    assert derivati["periodo_da"] == "2025-10-01"


def test_deriva_giorni_da_periodo_da_e_periodo_a() -> None:
    schema = load(SCHEMA_REALE)
    valori = {
        "periodo_da": "2025-10-01",
        "periodo_a": "2025-10-31",
        "giorni": None,
    }
    derivati = deriva_mancanti(schema, valori)
    assert derivati["giorni"] == "31"


def test_non_deriva_addendo_mancante_somma_fasce() -> None:
    """Bug trovato in audit (12-08): derivare un addendo mancante (es.
    kwh_f1 = kwh_totale - kwh_f2 - kwh_f3) inventerebbe un valore quando
    l'addendo None significa 'non applicabile', non 'non ancora letto' —
    caso reale: bolletta bioraria, kwh_f2 e' GIA' l'aggregato F2+F3
    (descrizione del campo nello schema), kwh_f3 resta None per design.
    Solo il totale si deriva (nessuna ambiguita' analoga)."""
    schema = load(SCHEMA_REALE)
    valori = {
        "kwh_f1": None,
        "kwh_f2": "20.00",
        "kwh_f3": "10.00",
        "kwh_totale": "50.00",
    }
    derivati = deriva_mancanti(schema, valori)
    assert derivati["kwh_f1"] is None


def test_non_inventa_terza_fascia_su_bolletta_bioraria() -> None:
    """Caso concreto trovato in audit: kwh_f2 aggregato F2+F3 (bioraria),
    kwh_f3 strutturalmente assente — non deve uscire un valore plausibile
    ma falso con confidenza 'media'."""
    schema = load(SCHEMA_REALE)
    valori = {
        "kwh_f1": "31.61",
        "kwh_f2": "71.28",
        "kwh_f3": None,
        "kwh_totale": "102.91",
    }
    derivati = deriva_mancanti(schema, valori)
    assert derivati["kwh_f3"] is None


def test_deriva_totale_mancante_somma_fasce() -> None:
    schema = load(SCHEMA_REALE)
    valori = {
        "kwh_f1": "20.00",
        "kwh_f2": "20.00",
        "kwh_f3": "10.00",
        "kwh_totale": None,
    }
    derivati = deriva_mancanti(schema, valori)
    assert Decimal(derivati["kwh_totale"]) == Decimal("50.00")


def test_non_deriva_se_piu_di_un_campo_mancante() -> None:
    schema = load(SCHEMA_REALE)
    valori = {"periodo_da": "2025-10-01", "periodo_a": None, "giorni": None}
    derivati = deriva_mancanti(schema, valori)
    assert derivati["periodo_a"] is None
    assert derivati["giorni"] is None


def test_non_deriva_se_nessun_campo_mancante() -> None:
    schema = load(SCHEMA_REALE)
    valori = {"periodo_da": "2025-10-01", "periodo_a": "2025-10-31", "giorni": "31"}
    derivati = deriva_mancanti(schema, valori)
    assert derivati == valori


def test_non_esplode_su_valore_presente_non_parsabile() -> None:
    schema = load(SCHEMA_REALE)
    valori = {"periodo_da": "non-una-data", "periodo_a": None, "giorni": "31"}
    derivati = deriva_mancanti(schema, valori)
    assert derivati["periodo_a"] is None


def test_deriva_mancanti_non_muta_linput() -> None:
    schema = load(SCHEMA_REALE)
    valori = {"periodo_da": "2025-10-01", "periodo_a": None, "giorni": "31"}
    deriva_mancanti(schema, valori)
    assert valori["periodo_a"] is None  # l'originale non e' toccato


# --- valuta_tutte_con_esito (ADR-056/058) -----------------------------------


def test_valuta_tutte_con_esito_su_valori_perfetti_tutte_passate() -> None:
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
    risultati = valuta_tutte_con_esito(schema, valori)
    assert len(risultati) == len(schema.invarianti)
    assert all(r.valutata for r in risultati)
    assert all(r.violazione is None for r in risultati)


def test_valuta_tutte_con_esito_coerente_con_valuta_tutte() -> None:
    # Stessa fonte di verita': valuta_tutte e' ora un filtro sopra
    # valuta_tutte_con_esito, deve produrre lo stesso output di prima.
    schema = load(SCHEMA_REALE)
    valori = {
        "pod": "IT001E12345678",
        "fornitore": "Alfa Energia",
        "periodo_da": "2025-09-01",
        "periodo_a": "2025-09-30",
        "giorni": "31",  # sbagliato: la violazione attesa
        "kwh_totale": "60.00",
        "kwh_f1": "10.00",
        "kwh_f2": "20.00",
        "kwh_f3": "30.00",
        "importo_totale": "50.00",
    }
    violazioni = valuta_tutte(schema, valori)
    con_esito = valuta_tutte_con_esito(schema, valori)
    fallite = tuple(r.violazione for r in con_esito if r.violazione is not None)
    assert fallite == violazioni
    assert len(violazioni) >= 1


def test_valuta_tutte_con_esito_campo_mancante_non_e_ne_passata_ne_fallita() -> None:
    schema = load(SCHEMA_REALE)
    valori: dict[str, str | None] = {"periodo_da": "2025-09-01", "periodo_a": None, "giorni": None}
    risultati = valuta_tutte_con_esito(schema, valori)
    per_id = {r.invariante_id: r for r in risultati}
    assert per_id["giorni_inclusivi"].valutata is False
    assert per_id["giorni_inclusivi"].violazione is None


# --- deriva_mancanti_con_provenienza (ADR-056/058) --------------------------


def test_deriva_con_provenienza_registra_invariante_e_campi_di_input() -> None:
    schema = load(SCHEMA_REALE)
    valori = {"periodo_da": "2025-10-01", "periodo_a": None, "giorni": "31"}
    derivati, provenienza = deriva_mancanti_con_provenienza(schema, valori)
    assert derivati["periodo_a"] == "2025-10-31"
    assert len(provenienza) == 1
    assert provenienza[0].campo == "periodo_a"
    assert provenienza[0].tipo == "differenza_giorni"
    assert provenienza[0].invariante_id == "giorni_inclusivi"
    assert set(provenienza[0].da_campi) == {"periodo_da", "giorni"}


def test_deriva_con_provenienza_vuota_se_nulla_derivato() -> None:
    schema = load(SCHEMA_REALE)
    valori = {"periodo_da": "2025-10-01", "periodo_a": "2025-10-31", "giorni": "31"}
    _, provenienza = deriva_mancanti_con_provenienza(schema, valori)
    assert provenienza == ()


def test_deriva_mancanti_coerente_con_deriva_con_provenienza() -> None:
    schema = load(SCHEMA_REALE)
    valori = {"periodo_da": "2025-10-01", "periodo_a": None, "giorni": "31"}
    derivati_semplice = deriva_mancanti(schema, valori)
    derivati_con_prov, _ = deriva_mancanti_con_provenienza(schema, valori)
    assert derivati_semplice == derivati_con_prov
