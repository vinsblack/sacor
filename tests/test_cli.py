"""TDD per sacor.cli (ADR-048): `sacor extract file.pdf`, il primo punto
d'ingresso pensato per chi integra sacor da fuori, non per chi lavora
dentro il repo."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from sacor.cli import main
from scripts.genera_corpus import Flags, genera_documento

REPO_ROOT = Path(__file__).parent.parent


def _scrivi(tmp_path: Path, nome: str, pdf_bytes: bytes) -> Path:
    p = tmp_path / nome
    p.write_bytes(pdf_bytes)
    return p


def test_extract_documento_pulito_esce_0_e_stampa_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(60), "S040", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S040.pdf", pdf_bytes)

    codice = main(["extract", str(path)])

    assert codice == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["esito"] == "pass"
    assert output[0]["valori"]["pod"] is not None


def test_extract_scansione_esce_1_reject(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf_bytes, _, _ = genera_documento(
        random.Random(61), "S041", "Beta Luce", Flags(scansione=True)
    )
    path = _scrivi(tmp_path, "S041.pdf", pdf_bytes)

    codice = main(["extract", str(path)])

    assert codice == 1
    output = json.loads(capsys.readouterr().out)
    assert output[0]["esito"] == "reject"
    assert output[0]["motivo"] is not None


def test_extract_file_inesistente_esce_2(capsys: pytest.CaptureFixture[str]) -> None:
    codice = main(["extract", "/non/esiste/davvero.pdf"])

    assert codice == 2
    assert "non trovato" in capsys.readouterr().err


def test_extract_schema_esplicito_sovrascrive_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(62), "S042", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S042.pdf", pdf_bytes)
    schema_path = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"

    codice = main(["extract", str(path), "--schema", str(schema_path)])

    assert codice == 0


def test_main_senza_comando_esce_con_errore_argparse() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_extract_output_include_confidenza_costo_e_errore_tier1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-048 punto 1/2: senza --tier1 la forma dell'output resta stabile
    (confidenza/costo/errore sempre presenti, non solo quando servono) —
    un consumatore esterno (n8n, API) non deve gestire chiavi opzionali."""
    pdf_bytes, _, _ = genera_documento(random.Random(64), "S044", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S044.pdf", pdf_bytes)

    main(["extract", str(path)])

    output = json.loads(capsys.readouterr().out)
    assert output[0]["confidenza"]["pod"] == "alta"
    assert output[0]["costo_tier1_usd"] == 0.0
    assert output[0]["tier1_errore"] is None


def _pdf_minimo_con_testo(path: Path, testo: str) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas

    c = Canvas(str(path), pagesize=A4, invariant=1)
    for i, riga in enumerate(testo.split("\n")):
        c.drawString(50, 800 - i * 15, riga)
    c.save()


def test_extract_documento_gas_senza_schema_esplicito_usa_schema_gas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-053: una bolletta gas senza --schema esplicito viene
    classificata e letta con bolletta_gas_it.yaml (kWh/Smc corretti),
    non forzata nel posto sbagliato (bug osservato in sessione: bolletta
    gas letta come luce, kWh al posto di Smc, nessun avviso)."""
    path = tmp_path / "gas.pdf"
    _pdf_minimo_con_testo(
        path,
        "Bolletta Gas Naturale\nTotale da pagare 37,14 EUR\n"
        "Consumo totale fatturato del periodo 35,97 Smc\nPDR: 00881900782465",
    )

    codice = main(["extract", str(path)])

    output = json.loads(capsys.readouterr().out)
    assert output[0]["valori"]["pdr"] == "00881900782465"
    assert output[0]["valori"]["smc_totale"] == "35.97"
    # obbligatori (periodo_da/periodo_a) mancanti su un PDF minimo -> reject,
    # ma con lo schema giusto, non quello luce sbagliato.
    assert codice == 1


def test_extract_documento_cte_senza_schema_esplicito_usa_schema_cte(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-053: un CTE (documento di condizioni/offerta, non una
    bolletta — niente importo da pagare) senza --schema esplicito viene
    classificato e letto con cte_it.yaml, non forzato nello schema luce."""
    path = tmp_path / "cte.pdf"
    _pdf_minimo_con_testo(
        path,
        "CONDIZIONI ECONOMICHE GENERALI\n"
        "Codice Offerta\nSingle ELE 001714ENFFL05XXFSOL0000500000000\n"
        "Durata del contratto\nIndeterminata",
    )

    codice = main(["extract", str(path)])

    assert codice == 0
    output = json.loads(capsys.readouterr().out)
    assert output[0]["valori"]["codice_offerta"] == "001714ENFFL05XXFSOL0000500000000"
    assert output[0]["valori"]["durata_contratto"] == "Indeterminata"


def test_extract_documento_sconosciuto_usa_luce_con_avviso(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Un documento senza segnali chiari (tier0-style classifica, nessun
    match) non esplode e non forza lo schema luce in silenzio — avviso
    esplicito su stderr (ADR-053)."""
    path = tmp_path / "sconosciuto.pdf"
    _pdf_minimo_con_testo(path, "Una lettera qualunque, nessun segnale di alcun tipo.")

    codice = main(["extract", str(path)])

    # SCONOSCIUTO -> default luce CON avviso (ADR-053), non un errore:
    # comportamento scelto per compatibilita' col corpus reale attuale.
    err = capsys.readouterr().err
    assert "avviso" in err
    assert codice in (0, 1)  # dipende dai campi obbligatori mancanti, non e' il punto qui


def test_extract_tier1_senza_chiave_api_riporta_errore_non_esplode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pdf_bytes, _, _ = genera_documento(
        random.Random(65), "S045", "Gamma Power", Flags(scansione=True)
    )
    path = _scrivi(tmp_path, "S045.pdf", pdf_bytes)

    codice = main(["extract", str(path), "--tier1"])

    assert codice == 1  # scansione: obbligatori restano mancanti, tier1 non ha potuto aiutare
    output = json.loads(capsys.readouterr().out)
    assert output[0]["tier1_errore"] is not None
