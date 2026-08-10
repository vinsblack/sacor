import random
from pathlib import Path

import pdfplumber
import pytest

from sacor.triage import TipoPagina, analizza, normalizza_testo
from scripts.genera_corpus import Flags, genera_documento


def _scrivi(tmp_path: Path, nome: str, pdf_bytes: bytes) -> Path:
    p = tmp_path / nome
    p.write_bytes(pdf_bytes)
    return p


def test_pdf_digitale_con_logo_e_qr_e_classificato_digitale(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(10), "S001", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S001.pdf", pdf_bytes)

    risultato = analizza(path)

    assert all(p.tipo is TipoPagina.DIGITALE for p in risultato.pagine)
    assert risultato.file == "S001.pdf"
    assert all(p.ha_text_layer for p in risultato.pagine)
    # logo + QR danno copertura non nulla ma bassa (ADR-021), sotto la banda.
    assert all(0.0 < p.copertura_immagine < 0.15 for p in risultato.pagine)


def test_pdf_scansione_pulita_e_classificato_scansione(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(
        random.Random(11), "S002", "Beta Luce", Flags(scansione=True)
    )
    path = _scrivi(tmp_path, "S002.pdf", pdf_bytes)

    risultato = analizza(path)

    assert all(p.tipo is TipoPagina.SCANSIONE for p in risultato.pagine)
    assert all(not p.ha_text_layer for p in risultato.pagine)
    assert all(p.densita_testo == 0.0 for p in risultato.pagine)
    assert all(p.copertura_immagine > 0.85 for p in risultato.pagine)


def test_pdf_scansione_sporca_e_classificato_scansione(tmp_path: Path) -> None:
    """Il vecchio criterio a densita' sbagliava questo caso (ADR-019/020): la
    copertura immagine lo classifica correttamente nonostante il text layer
    rado e rumoroso."""
    pdf_bytes, _, _ = genera_documento(
        random.Random(13), "S004", "Gamma Power", Flags(scansione_sporca=True)
    )
    path = _scrivi(tmp_path, "S004.pdf", pdf_bytes)

    risultato = analizza(path)

    assert all(p.tipo is TipoPagina.SCANSIONE for p in risultato.pagine)
    assert all(p.ha_text_layer for p in risultato.pagine)
    assert all(p.densita_testo > 0.0 for p in risultato.pagine)
    assert all(p.copertura_immagine > 0.85 for p in risultato.pagine)


def test_pagina_ibrida_e_classificata_ibrida(tmp_path: Path) -> None:
    """ADR-022: la banda ibrida esiste esattamente per questo caso — copertura
    alta ma non totale, densita' paragonabile al digitale. Ora la
    classificazione a tre stati la coglie senza forzare un binario."""
    pdf_bytes, _, _ = genera_documento(
        random.Random(14), "S005", "Alfa Energia", Flags(pagina_ibrida=True)
    )
    path = _scrivi(tmp_path, "S005.pdf", pdf_bytes)

    risultato = analizza(path)

    assert all(p.tipo is TipoPagina.IBRIDA for p in risultato.pagine)
    assert all(p.ha_text_layer for p in risultato.pagine)
    assert all(0.15 <= p.copertura_immagine <= 0.85 for p in risultato.pagine)


def test_ruotata_rileva_rotazione_180(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(
        random.Random(15), "S006", "Beta Luce", Flags(ruotata=True)
    )
    path = _scrivi(tmp_path, "S006.pdf", pdf_bytes)

    risultato = analizza(path)

    assert all(p.rotazione == 180 for p in risultato.pagine)


def test_normalizza_testo_su_pagina_ruotata_180_legge_nel_verso_giusto(tmp_path: Path) -> None:
    """ADR-030: extract_text() puro su /Rotate=180 restituisce il testo
    invertito carattere per carattere ("elatot otropmI"); normalizza_testo()
    deve correggerlo."""
    pdf_bytes, _, _ = genera_documento(
        random.Random(18), "S009", "Gamma Power", Flags(ruotata=True)
    )
    path = _scrivi(tmp_path, "S009.pdf", pdf_bytes)

    with pdfplumber.open(path) as documento:
        pagina = documento.pages[0]
        testo_grezzo = pagina.extract_text() or ""
        testo = normalizza_testo(pagina)

    assert "Fattura n." in testo
    assert "Fattura n." not in testo_grezzo  # conferma che senza normalizzare si perde


def test_pdf_non_ruotato_ha_rotazione_zero(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(16), "S007", "Gamma Power", Flags())
    path = _scrivi(tmp_path, "S007.pdf", pdf_bytes)

    risultato = analizza(path)

    assert all(p.rotazione == 0 for p in risultato.pagine)


def test_rotazione_none_se_tesseract_non_disponibile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SCANSIONE senza /Rotate esplicito richiede OSD (T2.3). Se il binario
    Tesseract non e' installato, il risultato e' None — mai un'eccezione."""
    pdf_bytes, _, _ = genera_documento(
        random.Random(17), "S008", "Alfa Energia", Flags(scansione=True)
    )
    path = _scrivi(tmp_path, "S008.pdf", pdf_bytes)

    monkeypatch.setattr("sacor.triage.shutil.which", lambda *_args: None)

    risultato = analizza(path)

    assert all(p.rotazione is None for p in risultato.pagine)


def test_istanza_di_default_copre_tutto_il_file(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(12), "S003", "Gamma Power", Flags())
    path = _scrivi(tmp_path, "S003.pdf", pdf_bytes)

    risultato = analizza(path)

    assert len(risultato.istanze) == 1
    istanza = risultato.istanze[0]
    assert istanza.pagina_da == 1
    assert istanza.pagina_a == len(risultato.pagine)
