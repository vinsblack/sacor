import random
from pathlib import Path

import pdfplumber

from sacor.segmentation import ConfidenzaSegmentazione, SegmentazioneConfig, segmenta
from sacor.triage import PaginaInfo, TipoPagina, analizza, normalizza_testo
from scripts.genera_corpus import Flags, genera_documento

PATTERN_FATTURA = r"Fattura(?: elettronica)? n\.?\s*([0-9]+)"


def _scrivi_e_estrai_testi(tmp_path: Path, nome: str, pdf_bytes: bytes) -> tuple[Path, list[str]]:
    path = tmp_path / nome
    path.write_bytes(pdf_bytes)
    with pdfplumber.open(path) as documento:
        testi = [normalizza_testo(p) for p in documento.pages]
    return path, testi


def test_multi_fattura_produce_due_istanze_identiche_a_metadata_certa(tmp_path: Path) -> None:
    pdf_bytes, _, metadata_entries = genera_documento(
        random.Random(1), "S007", "Beta Luce", Flags(multi_fattura=True)
    )
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S007.pdf", pdf_bytes)
    pagine = analizza(path).pagine
    config = SegmentazioneConfig(tipo="cambio_valore", pattern=PATTERN_FATTURA, minimo_pagine=1)

    risultato = segmenta(path, pagine, testi, config)

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

    risultato = segmenta(path, pagine, testi, config)

    assert risultato.confidenza is ConfidenzaSegmentazione.CERTA
    assert len(risultato.istanze) == 1
    assert risultato.istanze[0].pagina_da == 1
    assert risultato.istanze[0].pagina_a == 1


def test_schema_senza_segmentazione_produce_una_istanza(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(3), "S002", "Beta Luce", Flags())
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S002.pdf", pdf_bytes)
    pagine = analizza(path).pagine

    risultato = segmenta(path, pagine, testi, None)

    assert len(risultato.istanze) == 1
    assert risultato.confidenza is ConfidenzaSegmentazione.CERTA


def test_pagina_singola_digitale_e_certa_per_scorciatoia(tmp_path: Path) -> None:
    """ADR-031: la scorciatoia aritmetica resta valida, ma solo quando la
    pagina e' leggibile. Su 1 pagina DIGITALE con minimo_pagine=1, CERTA
    senza leggere il testo."""
    pdf_bytes, _, _ = genera_documento(random.Random(9), "S010", "Beta Luce", Flags())
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S010.pdf", pdf_bytes)
    pagine = analizza(path).pagine
    config = SegmentazioneConfig(tipo="cambio_valore", pattern=PATTERN_FATTURA, minimo_pagine=1)

    risultato = segmenta(path, pagine, testi, config)

    assert risultato.confidenza is ConfidenzaSegmentazione.CERTA
    assert len(risultato.istanze) == 1


def test_pagina_scansionata_singola_e_non_determinabile(tmp_path: Path) -> None:
    """ADR-031 revoca ADR-029: su una pagina illeggibile l'incertezza e'
    reale anche se e' l'unica pagina del file. Dichiarare certa qui
    presuppone che una pagina contenga al piu' un'istanza — falso (vedi
    S011 piu' sotto): e' l'errore silenzioso che ADR-029 introduceva."""
    pdf_bytes, _, _ = genera_documento(
        random.Random(4), "S003", "Gamma Power", Flags(scansione=True)
    )
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S003.pdf", pdf_bytes)
    pagine = analizza(path).pagine
    config = SegmentazioneConfig(tipo="cambio_valore", pattern=PATTERN_FATTURA, minimo_pagine=1)

    risultato = segmenta(path, pagine, testi, config)

    assert risultato.confidenza is ConfidenzaSegmentazione.NON_DETERMINABILE
    assert len(risultato.istanze) == 1


def test_multi_fattura_scansionato_resta_non_determinabile_regressione(tmp_path: Path) -> None:
    """Regressione ADR-031 (era S011 nel corpus di default): due fatture
    reali sulla stessa pagina fisica scansionata. ADR-029 dichiarava questo
    caso CERTA/1 istanza — confidentemente sbagliato, la verita' e' 2. La
    premessa "pagina singola => al piu' un'istanza" era falsa esattamente
    qui: e' il caso che ha fatto revocare la scorciatoia."""
    pdf_bytes, _, metadata_entries = genera_documento(
        random.Random(1), "S011", "Beta Luce", Flags(multi_fattura=True, scansione=True)
    )
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S011.pdf", pdf_bytes)
    pagine = analizza(path).pagine
    config = SegmentazioneConfig(tipo="cambio_valore", pattern=PATTERN_FATTURA, minimo_pagine=1)

    assert len(metadata_entries) == 2  # la verita': due fatture vere

    risultato = segmenta(path, pagine, testi, config)

    assert risultato.confidenza is ConfidenzaSegmentazione.NON_DETERMINABILE
    assert len(risultato.istanze) == 1  # dichiarato incerto, non affermato falso


def test_multipagina_con_pagina_scansionata_resta_non_determinabile() -> None:
    """La scorciatoia (ADR-031) non si applica mai su pagine SCANSIONE/IBRIDA,
    ne' sotto ne' sopra la soglia di pagine. Con una pagina non affidabile la
    regola ADR-024 resta in vigore. Costruito a mano: il generatore non
    produce ancora un file multipagina con una pagina di tipo
    scansione/ibrida."""
    pagine = (
        PaginaInfo(
            numero=1,
            ha_text_layer=True,
            densita_testo=5e-4,
            copertura_immagine=0.03,
            tipo=TipoPagina.DIGITALE,
            rotazione=0,
        ),
        PaginaInfo(
            numero=2,
            ha_text_layer=False,
            densita_testo=0.0,
            copertura_immagine=1.0,
            tipo=TipoPagina.SCANSIONE,
            rotazione=0,
        ),
    )
    testi = ["Fattura n. 111", ""]
    config = SegmentazioneConfig(tipo="cambio_valore", pattern=PATTERN_FATTURA, minimo_pagine=1)

    risultato = segmenta(Path("XXX.pdf"), pagine, testi, config)

    assert risultato.confidenza is ConfidenzaSegmentazione.NON_DETERMINABILE
    assert len(risultato.istanze) == 1


def test_pattern_mai_trovato_e_presunta(tmp_path: Path) -> None:
    """Su 1 sola pagina digitale la scorciatoia (ADR-031) intercetterebbe
    prima ancora di leggere il testo (CERTA per costruzione). Per esercitare
    davvero la ricerca del pattern serve un file con pagine sufficienti a
    contenere piu' di un'istanza (qui: --multi-fattura, 2 pagine, entrambe
    digitali)."""
    pdf_bytes, _, _ = genera_documento(
        random.Random(5), "S004", "Alfa Energia", Flags(multi_fattura=True)
    )
    path, testi = _scrivi_e_estrai_testi(tmp_path, "S004.pdf", pdf_bytes)
    pagine = analizza(path).pagine
    config = SegmentazioneConfig(
        tipo="cambio_valore", pattern=r"PATTERN-CHE-NON-COMPARE-MAI-([0-9]+)", minimo_pagine=1
    )

    risultato = segmenta(path, pagine, testi, config)

    assert risultato.confidenza is ConfidenzaSegmentazione.PRESUNTA
    assert len(risultato.istanze) == 1
