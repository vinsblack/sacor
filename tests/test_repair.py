from decimal import Decimal

from sacor.repair import ripara


def test_data_slash_a_iso() -> None:
    assert ripara("19/04/2025", "date") == "2025-04-19"


def test_data_trattino_a_iso() -> None:
    assert ripara("19-04-2025", "date") == "2025-04-19"


def test_data_non_valida_none() -> None:
    assert ripara("31/02/2025", "date") is None  # 31 febbraio non esiste


def test_data_formato_sbagliato_none() -> None:
    assert ripara("2025/04/19", "date") is None


def test_decimale_virgola_con_migliaia() -> None:
    assert Decimal(ripara("1.234,56", "decimal")) == Decimal("1234.56")


def test_decimale_virgola_senza_migliaia() -> None:
    assert Decimal(ripara("48,5", "decimal")) == Decimal("48.5")


def test_decimale_punto_genuino_due_cifre() -> None:
    """Non ambiguo: un gruppo delle migliaia italiano e' sempre di 3 cifre,
    2 cifre dopo l'unico punto non possono esserlo."""
    assert Decimal(ripara("119.19", "decimal")) == Decimal("119.19")


def test_decimale_punto_tre_cifre_ambiguo_none() -> None:
    """Caso limite dichiarato: '1.234' con un solo punto e nessuna virgola
    ha esattamente 3 cifre dopo il punto — potrebbe essere 1234 (migliaia)
    o un decimale a tre cifre. Nessun modo di distinguerli: None."""
    assert ripara("1.234", "decimal") is None


def test_decimale_piu_punti_senza_virgola_sono_migliaia() -> None:
    """Piu' di un punto: un numero reale ne ha al piu' uno, quindi non
    ambiguo — tutti separatori delle migliaia."""
    assert Decimal(ripara("1.234.567", "decimal")) == Decimal("1234567")


def test_decimale_non_parsabile_none() -> None:
    assert ripara("non un numero", "decimal") is None


def test_intero_con_migliaia() -> None:
    assert ripara("1.095", "integer") == "1095"


def test_intero_semplice() -> None:
    assert ripara("62", "integer") == "62"


def test_intero_non_parsabile_none() -> None:
    assert ripara("62 giorni", "integer") is None


def test_stringa_trim_e_spazi_collassati() -> None:
    assert ripara("  Alfa   Energia  ", "string") == "Alfa Energia"


def test_none_passa_invariato() -> None:
    assert ripara(None, "string") is None
    assert ripara(None, "decimal") is None
