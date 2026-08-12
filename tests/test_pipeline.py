"""TDD per sacor.pipeline (ADR-048): primo punto d'ingresso pubblico
single-file, prima esistevano solo script batch guidati da oracle
(eval/run.py, scripts/bakeoff.py). Usato dalla CLI."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from pathlib import Path

from sacor.invariants import Violazione
from sacor.pipeline import _calcola_esito, estrai_file
from sacor.providers.base import RispostaModello
from sacor.providers.errors import ErroreProvider
from sacor.schema import load
from scripts.genera_corpus import Flags, genera_documento

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"


@dataclass
class _ProviderStub:
    """Stesso principio di tests/test_arbitrate.py::_ProviderStub: nessuna
    rete, valori fissi indipendenti dalle pagine/prompt passati."""

    valori: dict[str, str | None]
    costo_stimato: float = 0.01
    chiamate: int = 0

    def estrai(self, pagine, prompt, campi):  # type: ignore[no-untyped-def]
        self.chiamate += 1
        return RispostaModello(
            valori=dict(self.valori),
            token_input=10,
            token_output=5,
            costo_stimato=self.costo_stimato,
            latenza_secondi=0.1,
            modello="stub",
        )


class _ProviderCheFallisce:
    def estrai(self, pagine, prompt, campi):  # type: ignore[no-untyped-def]
        raise ErroreProvider("chiave API non valida")


def _schema_senza_estrazione(schema, nome_campo: str):  # type: ignore[no-untyped-def]
    """Simula un campo che il tier0 lascia sempre None (es. 'fornitore',
    T4.17) senza dover costruire un PDF apposta: rimuove solo la regex,
    l'obbligo/tipo/invarianti restano quelli reali dello schema."""
    campi = tuple(
        replace(c, estrazione=None) if c.nome == nome_campo else c for c in schema.campi
    )
    return replace(schema, campi=campi)


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


def test_estrai_file_senza_tier1_confidenza_alta_su_campi_tier0(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    pdf_bytes, _, _ = genera_documento(random.Random(52), "S032", "Gamma Power", Flags())
    path = _scrivi(tmp_path, "S032.pdf", pdf_bytes)

    (risultato,) = estrai_file(path, schema)

    assert risultato.valori["pod"] is not None
    assert risultato.confidenza["pod"] == "alta"
    assert risultato.costo_tier1_usd == 0.0
    assert risultato.tier1_errore is None


# --- estrai_file con tier1 (ADR-048 punto 1/2) ------------------------------


def test_tier1_non_chiamato_se_tier0_ha_gia_tutto(tmp_path: Path) -> None:
    """Nessuna chiamata a pagamento sprecata quando non serve — anche con
    usa_tier1=True esplicito."""
    schema = load(SCHEMA_PATH)
    pdf_bytes, _, _ = genera_documento(random.Random(53), "S033", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S033.pdf", pdf_bytes)
    provider = _ProviderStub(valori={c.nome: "non-dovrebbe-servire" for c in schema.campi})

    (risultato,) = estrai_file(path, schema, usa_tier1=True, provider=provider)

    assert provider.chiamate == 0
    assert risultato.costo_tier1_usd == 0.0


def test_tier1_completa_campo_mancante_e_lo_marca_confidenza_media(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    schema_senza_fornitore = _schema_senza_estrazione(schema, "fornitore")
    pdf_bytes, _, _ = genera_documento(random.Random(54), "S034", "Beta Luce", Flags())
    path = _scrivi(tmp_path, "S034.pdf", pdf_bytes)
    provider = _ProviderStub(valori={"fornitore": "Epsilon Luce (da tier1)"})

    (risultato,) = estrai_file(
        path, schema_senza_fornitore, usa_tier1=True, provider=provider
    )

    assert provider.chiamate == 1
    assert risultato.valori["fornitore"] == "Epsilon Luce (da tier1)"
    assert risultato.confidenza["fornitore"] == "media"
    assert risultato.costo_tier1_usd == provider.costo_stimato
    assert risultato.tier1_errore is None
    # i campi che il tier0 aveva gia' risolto restano ad alta confidenza:
    assert risultato.confidenza["pod"] == "alta"


def test_tier1_errore_provider_non_esplode_e_si_vede_nel_risultato(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    schema_senza_fornitore = _schema_senza_estrazione(schema, "fornitore")
    pdf_bytes, _, _ = genera_documento(random.Random(55), "S035", "Gamma Power", Flags())
    path = _scrivi(tmp_path, "S035.pdf", pdf_bytes)

    (risultato,) = estrai_file(
        path, schema_senza_fornitore, usa_tier1=True, provider=_ProviderCheFallisce()
    )

    assert risultato.valori["fornitore"] is None
    assert risultato.tier1_errore is not None
    assert risultato.costo_tier1_usd == 0.0


def test_confidenza_bassa_su_campo_coinvolto_in_invariante_violata(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    # kwh_f1 E kwh_f2 mancano dal tier0 (due incognite su 'somma_fasce' a 4
    # termini: sottodeterminato, ADR-051 non deriva — deve andare a tier1).
    # Il provider restituisce due valori che non tornano con kwh_totale/
    # kwh_f3 gia' risolti dal tier0 — la violazione coinvolge tutti e 4
    # (campi_coinvolti di 'somma_fasce'), non solo quelli scritti da tier1.
    schema_ridotto = schema
    for nome in ("kwh_f1", "kwh_f2"):
        schema_ridotto = _schema_senza_estrazione(schema_ridotto, nome)
    pdf_bytes, _, _ = genera_documento(random.Random(56), "S036", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S036.pdf", pdf_bytes)
    provider = _ProviderStub(valori={"kwh_f1": "999999.99", "kwh_f2": "888888.88"})

    (risultato,) = estrai_file(path, schema_ridotto, usa_tier1=True, provider=provider)

    assert any(v.invariante_id == "somma_fasce" for v in risultato.violazioni)
    assert risultato.confidenza["kwh_f1"] == "bassa"  # tier1, ma bassa vince su media
    assert risultato.confidenza["kwh_totale"] == "bassa"  # tier0, ma bassa vince su alta
    assert risultato.confidenza["kwh_f2"] == "bassa"
    assert risultato.confidenza["kwh_f3"] == "bassa"


def test_deriva_mancanti_end_to_end_senza_chiamare_tier1(tmp_path: Path) -> None:
    """ADR-051: periodo_a manca dal tier0, ma periodo_da e giorni ci sono
    gia' — deve derivarlo aritmeticamente, senza nessuna chiamata tier1
    (anche con usa_tier1=True e un provider che esploderebbe se chiamato)."""
    schema = load(SCHEMA_PATH)
    schema_senza_periodo_a = _schema_senza_estrazione(schema, "periodo_a")
    pdf_bytes, _, _ = genera_documento(random.Random(57), "S037", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S037.pdf", pdf_bytes)
    provider = _ProviderCheFallisce()

    (risultato,) = estrai_file(
        path, schema_senza_periodo_a, usa_tier1=True, provider=provider
    )

    assert risultato.tier1_errore is None  # provider mai chiamato, quindi mai fallito
    assert risultato.valori["periodo_a"] is not None
    assert risultato.confidenza["periodo_a"] == "media"  # derivato, non letto direttamente
    assert risultato.costo_tier1_usd == 0.0
