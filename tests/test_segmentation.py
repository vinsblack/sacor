import random
from pathlib import Path

import pdfplumber

from sacor.segmentation import ConfidenzaSegmentazione, SegmentazioneConfig, segmenta
from sacor.triage import analizza
from scripts.genera_corpus import Flags, genera_documento

PATTERN_FATTURA = r"Fattura(?: elettronica)? n\.?\s*([0-9]+)"


def _scrivi_e_estrai_testi(tmp_path: Path, nome: str, pdf_bytes: bytes) -> tuple[Path, list[str]]:
    path = tmp_path / nome
    path.write_bytes(pdf_bytes)
    with pdfplumber.open(path) as documento:
        testi = [p.extract_text() or "" for p in documento.pages]
    return path, testi


def test_multi_fattura_produce_due_istanze_identiche_a_metadata_certa(tmp_path: Path) -> None:
    pdf_bytes, _, metadata_entries = genera_documento(
        random.Random(1), "S007", "Beta Luce", Flags(multi_fattura=True)
    )
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S007.pdf", pdf_bytes)
    pagine = analizza(path).pagine
    config = SegmentazioneConfig(tipo="cambio_valore", pattern=PATTERN_FATTURA, minimo_pagine=1)

    risultato = segmenta("S007", pagine, testi, config)

    assert risultato.confidenza is ConfidenzaSegmentazione.CERTA
    assert len(risultato.istanze) == 2

    intervalli_segmentazione = {(i.pagina_da, i.pagina_a) for i in risultato.istanze}
    intervalli_metadata = {tuple(v["pagine"]) for v in metadata_entries.values()}
    assert intervalli_segmentazione == intervalli_metadata


def test_documento_normale_produce_una_istanza_certa(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(2), "S001", "Alfa Energia", Flags())
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S001.pdf", pdf_bytes)
    pagine = analizza(path).pagine
    config = SegmentazioneConfig(tipo="cambio_valore", pattern=PATTERN_FATTURA, minimo_pagine=1)

    risultato = segmenta("S001", pagine, testi, config)

    assert risultato.confidenza is ConfidenzaSegmentazione.CERTA
    assert len(risultato.istanze) == 1
    assert risultato.istanze[0].pagina_da == 1
    assert risultato.istanze[0].pagina_a == 1


def test_schema_senza_segmentazione_produce_una_istanza(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(3), "S002", "Beta Luce", Flags())
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S002.pdf", pdf_bytes)
    pagine = analizza(path).pagine

    risultato = segmenta("S002", pagine, testi, None)

    assert len(risultato.istanze) == 1
    assert risultato.confidenza is ConfidenzaSegmentazione.CERTA


def test_pagina_scansionata_e_non_determinabile(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(
        random.Random(4), "S003", "Gamma Power", Flags(scansione=True)
    )
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S003.pdf", pdf_bytes)
    pagine = analizza(path).pagine
    config = SegmentazioneConfig(tipo="cambio_valore", pattern=PATTERN_FATTURA, minimo_pagine=1)

    risultato = segmenta("S003", pagine, testi, config)

    assert risultato.confidenza is ConfidenzaSegmentazione.NON_DETERMINABILE
    assert len(risultato.istanze) == 1


def test_pattern_mai_trovato_e_presunta(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(5), "S004", "Alfa Energia", Flags())
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S004.pdf", pdf_bytes)
    pagine = analizza(path).pagine
    config = SegmentazioneConfig(
        tipo="cambio_valore", pattern=r"PATTERN-CHE-NON-COMPARE-MAI-([0-9]+)", minimo_pagine=1
    )

    risultato = segmenta("S004", pagine, testi, config)

    assert risultato.confidenza is ConfidenzaSegmentazione.PRESUNTA
    assert len(risultato.istanze) == 1
