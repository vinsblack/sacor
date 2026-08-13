"""TDD per sacor.pipeline (ADR-048): primo punto d'ingresso pubblico
single-file, prima esistevano solo script batch guidati da oracle
(eval/run.py, scripts/bakeoff.py). Usato dalla CLI."""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from sacor.evidence import confidenza_da_evidenza
from sacor.pipeline import estrai_file
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


# --- _calcola_esito e' stata rimossa (Commit 4, ADR-060): il Gate legge
# solo Evidence, vive in sacor.gate, testato in tests/test_gate.py.
# estrai_file() sotto verifica l'integrazione end-to-end (gate() chiamato
# con Evidence vera), non la regola pura in isolamento (quella e' li').


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


def test_tier1_senza_anthropic_installato_non_esplode_con_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Adoption report v1, P0#1: `sacor extract file.pdf --tier1` senza il
    package anthropic installato (extra 'providers' non richiesto da
    `pip install sacor`) crashava con ModuleNotFoundError grezzo invece di
    passare per ErroreProvider come ogni altro fallimento tier1."""
    monkeypatch.delitem(sys.modules, "sacor.providers.anthropic", raising=False)
    monkeypatch.setitem(sys.modules, "anthropic", None)
    schema = load(SCHEMA_PATH)
    schema_senza_fornitore = _schema_senza_estrazione(schema, "fornitore")
    pdf_bytes, _, _ = genera_documento(random.Random(70), "S099", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S099.pdf", pdf_bytes)

    (risultato,) = estrai_file(path, schema_senza_fornitore, usa_tier1=True)

    assert risultato.tier1_errore is not None
    assert "sacor[providers]" in risultato.tier1_errore


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


# --- Evidence Model (ADR-056/057/058, Commit 2) -----------------------------


def test_evidenza_documento_popolata_con_schema_e_pagine(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    pdf_bytes, _, _ = genera_documento(random.Random(58), "S038", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S038.pdf", pdf_bytes)

    (risultato,) = estrai_file(path, schema)

    doc = risultato.evidenza_documento
    assert doc is not None
    assert doc.schema == schema.documento
    assert doc.schema_versione == schema.schema_version
    assert len(doc.pagine) >= 1


def test_evidenza_campo_tier0_origine_e_coerente_con_confidenza(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    pdf_bytes, _, _ = genera_documento(random.Random(59), "S039", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S039.pdf", pdf_bytes)

    (risultato,) = estrai_file(path, schema)

    ev = risultato.evidenze["pod"]
    assert ev.origine == "tier0"
    assert ev.stato is None  # ha un valore, niente da giustificare
    assert confidenza_da_evidenza(risultato.valori["pod"], ev) == risultato.confidenza["pod"]


def test_evidenza_derivazione_registra_invariante_e_campi_di_input(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    schema_senza_periodo_a = _schema_senza_estrazione(schema, "periodo_a")
    pdf_bytes, _, _ = genera_documento(random.Random(60), "S040", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S040.pdf", pdf_bytes)

    (risultato,) = estrai_file(
        path, schema_senza_periodo_a, usa_tier1=True, provider=_ProviderCheFallisce()
    )

    ev = risultato.evidenze["periodo_a"]
    assert ev.origine == "derivato"
    assert len(ev.derivazione) == 1
    assert ev.derivazione[0].tipo == "differenza_giorni"
    assert ev.derivazione[0].invariante_id == "giorni_inclusivi"
    assert set(ev.derivazione[0].da_campi) == {"periodo_da", "giorni"}
    assert confidenza_da_evidenza(risultato.valori["periodo_a"], ev) == "media"


def test_evidenza_tier1_origine(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    schema_senza_fornitore = _schema_senza_estrazione(schema, "fornitore")
    pdf_bytes, _, _ = genera_documento(random.Random(61), "S041", "Beta Luce", Flags())
    path = _scrivi(tmp_path, "S041.pdf", pdf_bytes)
    provider = _ProviderStub(valori={"fornitore": "Epsilon Luce (da tier1)"})

    (risultato,) = estrai_file(path, schema_senza_fornitore, usa_tier1=True, provider=provider)

    ev = risultato.evidenze["fornitore"]
    assert ev.origine == "tier1"
    assert confidenza_da_evidenza(risultato.valori["fornitore"], ev) == "media"


def test_evidenza_invarianti_fallite_su_campo_coinvolto(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    schema_ridotto = schema
    for nome in ("kwh_f1", "kwh_f2"):
        schema_ridotto = _schema_senza_estrazione(schema_ridotto, nome)
    pdf_bytes, _, _ = genera_documento(random.Random(62), "S042", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S042.pdf", pdf_bytes)
    provider = _ProviderStub(valori={"kwh_f1": "999999.99", "kwh_f2": "888888.88"})

    (risultato,) = estrai_file(path, schema_ridotto, usa_tier1=True, provider=provider)

    ev = risultato.evidenze["kwh_totale"]
    assert ev.invarianti.fallite >= 1
    assert any(d.id == "somma_fasce" and d.esito == "fail" for d in ev.invarianti.dettaglio)
    assert confidenza_da_evidenza(risultato.valori["kwh_totale"], ev) == "bassa"


def test_evidenza_stato_tier1_non_tentato_se_usa_tier1_falso(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    schema_senza_fornitore = _schema_senza_estrazione(schema, "fornitore")
    pdf_bytes, _, _ = genera_documento(random.Random(63), "S043", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S043.pdf", pdf_bytes)

    (risultato,) = estrai_file(path, schema_senza_fornitore)  # usa_tier1 default False

    ev = risultato.evidenze["fornitore"]
    assert risultato.valori["fornitore"] is None
    assert ev.origine is None
    assert ev.stato == "tier1_non_tentato"


def test_evidenza_stato_tier1_fallito_si_distingue_da_non_tentato(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    schema_senza_fornitore = _schema_senza_estrazione(schema, "fornitore")
    pdf_bytes, _, _ = genera_documento(random.Random(64), "S044", "Gamma Power", Flags())
    path = _scrivi(tmp_path, "S044.pdf", pdf_bytes)

    (risultato,) = estrai_file(
        path, schema_senza_fornitore, usa_tier1=True, provider=_ProviderCheFallisce()
    )

    ev = risultato.evidenze["fornitore"]
    assert ev.stato == "tier1_fallito"


def test_evidenza_racconta_la_storia_del_campo_senza_altro_contesto(tmp_path: Path) -> None:
    """La proprieta' richiesta per il Commit 2: dato un campo derivato,
    tutta la sua storia (chi l'ha prodotto, da cosa, con quale
    invariante) deve leggersi dalla sua Evidenza da sola — nessun altro
    oggetto (extractor, pipeline) va consultato."""
    schema = load(SCHEMA_PATH)
    schema_senza_periodo_a = _schema_senza_estrazione(schema, "periodo_a")
    pdf_bytes, _, _ = genera_documento(random.Random(65), "S045", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S045.pdf", pdf_bytes)

    (risultato,) = estrai_file(path, schema_senza_periodo_a)

    ev = risultato.evidenze["periodo_a"]
    storia = {
        "origine": ev.origine,
        "riparazioni": [r.tipo for r in ev.repair],
        "derivazioni": [(d.tipo, d.invariante_id, d.da_campi) for d in ev.derivazione],
        "invarianti_passate": ev.invarianti.passate,
        "invarianti_fallite": ev.invarianti.fallite,
    }
    assert storia["origine"] == "derivato"
    assert storia["derivazioni"] == [
        ("differenza_giorni", "giorni_inclusivi", ("periodo_da", "giorni"))
    ]
    assert storia["invarianti_fallite"] == 0


def test_confidenza_e_funzione_di_evidenza_su_un_ventaglio_di_documenti(
    tmp_path: Path,
) -> None:
    """Commit 3 (ADR-056/058/059): confidenza_da_evidenza(evidenze[nome])
    deve essere BIT-IDENTICA a _calcola_confidenza() (l'algoritmo ancora
    in uso in pipeline.py) su ogni campo di ogni documento — non 'quasi
    uguale'. Copre: documento pulito, scansione (tutto None), bioraria
    (kwh_f3 strutturalmente assente), tier1 che completa un campo, tier1
    che fallisce, e una violazione che degrada un gruppo di campi a
    'bassa'. Se anche un solo campo diverge, il commit di sostituzione
    (usare confidenza_da_evidenza al posto di _calcola_confidenza dentro
    estrai_file) non e' behavior-preserving e non va fatto."""
    schema = load(SCHEMA_PATH)
    schema_senza_fornitore = _schema_senza_estrazione(schema, "fornitore")
    schema_senza_kwh_f1_f2 = schema
    for nome in ("kwh_f1", "kwh_f2"):
        schema_senza_kwh_f1_f2 = _schema_senza_estrazione(schema_senza_kwh_f1_f2, nome)

    casi: list[tuple[str, object, bool, object]] = [
        ("pulito", schema, False, None),
        ("scansione", schema, False, None),
        (
            "tier1_completa_fornitore",
            schema_senza_fornitore,
            True,
            _ProviderStub(valori={"fornitore": "Epsilon Luce (da tier1)"}),
        ),
        ("tier1_fallisce", schema_senza_fornitore, True, _ProviderCheFallisce()),
        (
            "invariante_violata",
            schema_senza_kwh_f1_f2,
            True,
            _ProviderStub(valori={"kwh_f1": "999999.99", "kwh_f2": "888888.88"}),
        ),
    ]

    confronti = 0
    for indice, (nome_caso, schema_caso, usa_tier1, provider) in enumerate(casi):
        flags = Flags(scansione=(nome_caso == "scansione"), monoraria=(indice % 2 == 0))
        pdf_bytes, _, _ = genera_documento(
            random.Random(200 + indice), f"SEED{indice}", "Alfa Energia", flags
        )
        path = _scrivi(tmp_path, f"corpus_{indice}.pdf", pdf_bytes)

        risultati = estrai_file(path, schema_caso, usa_tier1=usa_tier1, provider=provider)

        for risultato in risultati:
            for campo_nome, valore in risultato.valori.items():
                vecchia = risultato.confidenza[campo_nome]
                nuova = confidenza_da_evidenza(valore, risultato.evidenze[campo_nome])
                assert nuova == vecchia, (
                    f"caso={nome_caso} campo={campo_nome}: "
                    f"vecchia={vecchia!r} nuova={nuova!r}"
                )
                confronti += 1

    assert confronti > 20  # prova che il test ha davvero confrontato qualcosa
