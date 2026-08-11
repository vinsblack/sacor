import io
import json
import random
import re
from pathlib import Path

import pdfplumber

from scripts.genera_corpus import Flags, genera_corpus, genera_documento


def test_stesso_seed_produce_pdf_byte_identici() -> None:
    pdf1, _, _ = genera_documento(random.Random(42), "S001", "Alfa Energia", Flags())
    pdf2, _, _ = genera_documento(random.Random(42), "S001", "Alfa Energia", Flags())
    assert pdf1 == pdf2


def test_multi_fattura_produce_due_istanze_con_chiave_opaca() -> None:
    _, oracle_entries, metadata_entries = genera_documento(
        random.Random(1), "S007", "Beta Luce", Flags(multi_fattura=True)
    )
    assert set(oracle_entries) == {"S007a", "S007b"}
    assert oracle_entries["S007a"]["periodo_da"] != oracle_entries["S007b"]["periodo_da"]

    # ADR-014-bis: il legame col file fisico vive solo in metadata, mai
    # ricavato interpretando la chiave.
    assert metadata_entries["S007a"]["file"] == "S007.pdf"
    assert metadata_entries["S007b"]["file"] == "S007.pdf"


def test_documento_singolo_ha_chiave_uguale_al_doc_id() -> None:
    _, oracle_entries, metadata_entries = genera_documento(
        random.Random(8), "S001", "Alfa Energia", Flags()
    )
    assert set(oracle_entries) == {"S001"}
    assert metadata_entries["S001"]["file"] == "S001.pdf"


def test_periodo_mensile_scrive_il_nome_del_mese() -> None:
    pdf, _, _ = genera_documento(
        random.Random(2), "S002", "Alfa Energia", Flags(periodo_mensile=True)
    )
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        testo = doc.pages[0].extract_text() or ""
    mesi = (
        "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
    )
    assert any(mese in testo for mese in mesi)


def test_fornitore_esteso_usa_la_ragione_sociale_estesa() -> None:
    _, oracle_entries, _ = genera_documento(
        random.Random(3), "S003", "Gamma Power", Flags(fornitore_esteso=True)
    )
    assert oracle_entries["S003"]["fornitore"] == "Gamma Power Societa' Benefit S.p.A."


def test_consumo_stimato_segnala_tipo_lettura_e_nota_in_pdf() -> None:
    pdf, _, metadata_entries = genera_documento(
        random.Random(4), "S004", "Alfa Energia", Flags(consumo_stimato=True)
    )
    assert metadata_entries["S004"]["tipo_lettura"] == "stimata"
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        testo = doc.pages[0].extract_text() or ""
    assert "stimato" in testo


def test_monoraria_fasce_2_e_3_sono_zero_non_null() -> None:
    _, oracle_entries, metadata_entries = genera_documento(
        random.Random(5), "S005", "Beta Luce", Flags(monoraria=True)
    )
    campi = oracle_entries["S005"]
    assert campi["kwh_f2"] == "0.00"
    assert campi["kwh_f3"] == "0.00"
    assert campi["kwh_totale"] == campi["kwh_f1"]
    assert metadata_entries["S005"]["monoraria"] is True


def test_ruotata_imposta_rotazione_180_nel_pdf() -> None:
    pdf, _, _ = genera_documento(random.Random(6), "S006", "Gamma Power", Flags(ruotata=True))
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        assert doc.pages[0].rotation == 180


def test_scansione_non_ha_text_layer() -> None:
    pdf, _, metadata_entries = genera_documento(
        random.Random(7), "S008", "Alfa Energia", Flags(scansione=True)
    )
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        testo = doc.pages[0].extract_text()
    assert not testo
    assert metadata_entries["S008"]["qualita"] == "scansione_degradata"


def test_importo_renderizzato_usa_la_virgola_decimale_italiana() -> None:
    """ADR-040 (T4.14, trovato ispezionando 22 bollette reali): tutte usano
    la virgola come separatore decimale, mai il punto — il generatore
    renderizzava con str(Decimal(...)) (punto), un formato mai osservato in
    nessuna bolletta reale. La regex del tier 0 ([\\d.]+) non lo avrebbe mai
    trovato su un vero numero italiano: un buco di copertura che nascondeva
    un probabile buco reale nell'estrazione."""
    pdf, oracle_entries, _ = genera_documento(random.Random(10), "S001", "Alfa Energia", Flags())
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        testo = "\n".join(p.extract_text() or "" for p in doc.pages)

    assert re.search(r"Importo totale: EUR \d[\d.]*,\d{2}\b", testo)
    assert f"EUR {oracle_entries['S001']['importo_totale']}" not in testo  # mai piu' col punto


def test_periodo_alfa_usa_punti_come_separatore_data() -> None:
    """T4.14 (ADR-040): tra le 22 bollette reali ispezionate, Hera/EstEnergy
    usa gg.mm.aaaa (punti), non gg/mm/aaaa — un secondo formato data reale
    oltre a slash e mese-esteso. Assegnato ad Alfa Energia per introdurre
    diversita' reale nel corpus, non per sostituire lo slash ovunque: Beta/
    Gamma restano su 'mese esteso anno' (periodo_mensile)."""
    pdf, _, _ = genera_documento(random.Random(11), "S001", "Alfa Energia", Flags())
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        testo = doc.pages[0].extract_text() or ""
    assert re.search(r"Dal \d{2}\.\d{2}\.\d{4} al \d{2}\.\d{2}\.\d{4}", testo)
    assert not re.search(r"Dal \d{2}/\d{2}/\d{4}", testo)


def test_pagine_allegate_aggiunge_una_pagina_oltre_le_tre_vere() -> None:
    """T4.14 (ADR-041): pagina di modulo di pagamento allegata dopo le 3
    pagine vere — osservata su piu' bollette reali (bollettino postale,
    SEPA, pagoPA). Non fa parte del conteggio ADR-039 (3 pagine per
    fattura), e' aggiuntiva."""
    pdf, _, _ = genera_documento(
        random.Random(12), "S001", "Beta Luce", Flags(pagine_allegate=True)
    )
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        assert len(doc.pages) == 4
        testo_ultima = doc.pages[3].extract_text() or ""
    assert "MODULO DI PAGAMENTO" in testo_ultima


def test_genera_corpus_scrive_una_voce_metadata_per_documento(tmp_path: Path) -> None:
    genera_corpus(
        seed=99,
        n=3,
        out_dir=tmp_path / "synth",
        oracle_path=tmp_path / "attesi.json",
        metadata_path=tmp_path / "metadata.json",
    )

    pdf_files = sorted((tmp_path / "synth").glob("*.pdf"))
    assert len(pdf_files) == 3

    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert set(metadata) == {"S001", "S002", "S003"}
    for chiave, voce in metadata.items():
        assert set(voce) == {
            "file",
            "pagine",
            "layout",
            "tipo_lettura",
            "monoraria",
            "qualita",
            "flag_attivi",
        }
        assert voce["file"] == f"{chiave}.pdf"

    oracle = json.loads((tmp_path / "attesi.json").read_text())
    assert oracle["oracle_version"] == 1
    assert oracle["documento"] == "bolletta_luce_it"
    assert set(oracle["documenti"]) == {"S001", "S002", "S003"}
