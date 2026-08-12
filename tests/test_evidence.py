"""Commit 1 (ADR-056/057): solo strutture dati + funzione pura, nessun
collegamento alla pipeline. confidenza_da_evidenza() e' verificata contro
la stessa tabella di regole gia' in produzione in
pipeline._calcola_confidenza() — stesso comportamento, luogo diverso."""

from __future__ import annotations

from sacor.evidence import (
    Derivazione,
    EsitoInvariante,
    Evidenza,
    EvidenzaDocumento,
    PaginaEvidenza,
    RiepilogoInvarianti,
    Riparazione,
    RisultatoCampo,
    confidenza_da_evidenza,
)


def test_valore_assente_e_sempre_confidenza_null() -> None:
    evidenza = Evidenza(origine="tier0")
    assert confidenza_da_evidenza(None, evidenza) is None


def test_invariante_fallita_da_confidenza_bassa_a_prescindere_dall_origine() -> None:
    evidenza = Evidenza(origine="tier0", invarianti=RiepilogoInvarianti(passate=0, fallite=1))
    assert confidenza_da_evidenza("100.00", evidenza) == "bassa"


def test_origine_tier1_da_confidenza_media() -> None:
    evidenza = Evidenza(origine="tier1")
    assert confidenza_da_evidenza("100.00", evidenza) == "media"


def test_origine_derivato_da_confidenza_media() -> None:
    evidenza = Evidenza(origine="derivato")
    assert confidenza_da_evidenza("100.00", evidenza) == "media"


def test_origine_tier0_senza_violazioni_da_confidenza_alta() -> None:
    evidenza = Evidenza(origine="tier0", invarianti=RiepilogoInvarianti(passate=2, fallite=0))
    assert confidenza_da_evidenza("100.00", evidenza) == "alta"


def test_evidenza_di_default_ha_liste_vuote_non_assenti() -> None:
    # ADR-056: un consumatore non deve mai fare .get(x, default) su una
    # chiave che potrebbe non esistere — repair/derivazione sono sempre
    # presenti, vuote se non applicabili.
    evidenza = Evidenza()
    assert evidenza.repair == ()
    assert evidenza.derivazione == ()
    assert evidenza.invarianti == RiepilogoInvarianti(passate=0, fallite=0, dettaglio=())


def test_riparazione_e_derivazione_sono_liste_non_booleani() -> None:
    evidenza = Evidenza(
        origine="tier0",
        repair=(Riparazione(tipo="normalizza_decimale_it", da="1.234,56", a="1234.56"),),
        derivazione=(
            Derivazione(
                tipo="somma_approssimata",
                invariante_id="somma_fasce",
                da_campi=("kwh_f1", "kwh_f2"),
            ),
        ),
    )
    assert len(evidenza.repair) == 1
    assert evidenza.repair[0].tipo == "normalizza_decimale_it"
    assert len(evidenza.derivazione) == 1
    assert evidenza.derivazione[0].da_campi == ("kwh_f1", "kwh_f2")


def test_evidenza_origine_stato_separati_adr_057() -> None:
    evidenza = Evidenza(origine=None, stato="tier1_non_tentato")
    assert evidenza.origine is None
    assert evidenza.stato == "tier1_non_tentato"
    assert confidenza_da_evidenza(None, evidenza) is None


def test_riepilogo_invarianti_porta_anche_le_passate() -> None:
    riepilogo = RiepilogoInvarianti(
        passate=2,
        fallite=1,
        dettaglio=(
            EsitoInvariante(id="somma_fasce", esito="pass", severita="warning"),
            EsitoInvariante(id="periodo_coerente", esito="pass", severita="warning"),
            EsitoInvariante(
                id="corrispettivo_annuo_non_negativo", esito="fail", severita="warning"
            ),
        ),
    )
    assert riepilogo.passate == 2
    assert riepilogo.fallite == 1
    assert len(riepilogo.dettaglio) == 3


def test_evidenza_documento_distingue_documento_da_campo() -> None:
    doc = EvidenzaDocumento(
        schema="bolletta_luce_it",
        schema_versione=1,
        classificazione="bolletta_luce",
        pagine=(
            PaginaEvidenza(indice=0, tipo="digitale"),
            PaginaEvidenza(indice=1, tipo="scansione"),
        ),
    )
    assert doc.schema == "bolletta_luce_it"
    assert len(doc.pagine) == 2
    assert doc.pagine[1].tipo == "scansione"


def test_risultato_campo_compone_valore_evidenza_confidenza() -> None:
    evidenza = Evidenza(origine="tier0")
    campo = RisultatoCampo(
        valore="174.74", evidenza=evidenza, confidenza=confidenza_da_evidenza("174.74", evidenza)
    )
    assert campo.valore == "174.74"
    assert campo.confidenza == "alta"
