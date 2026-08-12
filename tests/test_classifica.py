"""TDD per sacor.classifica (ADR-053). Frammenti di testo sintetici che
riproducono i segnali reali verificati su tre documenti veri (bolletta
luce, bolletta gas, CTE Engie) — non i documenti stessi, mai nel repo."""

from __future__ import annotations

import random
from pathlib import Path

from sacor.classifica import TipoDocumento, classifica_file, classifica_testo
from scripts.genera_corpus import Flags, genera_documento


def test_bolletta_luce_riconosciuta() -> None:
    testo = """
    BOLLETTA PER LA FORNITURA DI ENERGIA ELETTRICA nr. E047584 del 15/04/2026.
    Periodo di fatturazione a Conguaglio dal 01/03/2026 al 31/03/2026. Consumo 0,530 kWh
    TOTALE DA PAGARE € 25,56
    """
    assert classifica_testo(testo) == TipoDocumento.BOLLETTA_LUCE


def test_bolletta_gas_riconosciuta() -> None:
    testo = """
    Gas Naturale Mercato Libero
    Bolletta n.AGL2600216201 del 13/04/2026
    Periodo di competenza della bolletta 01/02/2026-28/02/2026
    Totale da pagare 37,14 €
    Consumo totale fatturato del periodo 35,97 Smc
    """
    assert classifica_testo(testo) == TipoDocumento.BOLLETTA_GAS


def test_cte_riconosciuto_senza_totale_ne_periodo() -> None:
    testo = """
    Codice Offerta Single ELE 001714ENFFL05XXFSOL0000500000000
    CONDIZIONI ECONOMICHE GENERALI
    CONDIZIONI ECONOMICHE ENERGIA ELETTRICA valide fino al 16/09/2026
    """
    assert classifica_testo(testo) == TipoDocumento.CTE


def test_documento_senza_segnali_e_sconosciuto() -> None:
    assert classifica_testo("Una lettera qualunque, nessun segnale.") == TipoDocumento.SCONOSCIUTO


def test_entrambe_le_unita_presenti_e_sconosciuto() -> None:
    """Un documento con sia smc sia kWh, ma con totale/periodo (quindi non
    CTE) — es. un'offerta dual-fuel fatturata insieme, mai visto nel
    corpus reale ma non impossibile: non si indovina, si dichiara incerto."""
    testo = """
    Periodo di fatturazione dal 01/03/2026 al 31/03/2026.
    Totale da pagare € 50,00
    Consumo 10 Smc e 20 kWh
    """
    assert classifica_testo(testo) == TipoDocumento.SCONOSCIUTO


def test_periodo_di_riferimento_riconosciuto_come_periodo() -> None:
    """Terza etichetta reale (Borello Simona, oltre a 'fatturazione' e
    'competenza') — trovata solo verificando il documento vero, non
    indovinata: senza questa il gas veniva scambiato per CTE."""
    testo = """
    GAS METANO MERCATO LIBERO
    Periodo di riferimento: 01 aprile 2026 - 31 maggio 2026
    Totale da pagare 107,71 €
    Consumo totale fatturato nel periodo 37 Smc
    """
    assert classifica_testo(testo) == TipoDocumento.BOLLETTA_GAS


def test_case_insensitive() -> None:
    testo = "TOTALE DA PAGARE € 1 PERIODO DI FATTURAZIONE dal 1 al 2. Consumo 5 KWH."
    assert classifica_testo(testo) == TipoDocumento.BOLLETTA_LUCE


def test_classifica_file_su_documento_sintetico(tmp_path: Path) -> None:
    pdf_bytes, _, _ = genera_documento(random.Random(70), "S050", "Alfa Energia", Flags())
    path = tmp_path / "S050.pdf"
    path.write_bytes(pdf_bytes)

    assert classifica_file(path) == TipoDocumento.BOLLETTA_LUCE
