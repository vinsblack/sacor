from sacor.compare import uguali


def test_decimal_con_zeri_finali_diversi_e_match() -> None:
    assert uguali("1234.56", "1234.560", "decimal") is True


def test_null_vs_null_e_match() -> None:
    assert uguali(None, None, "string") is True


def test_null_vs_stringa_vuota_non_e_match() -> None:
    assert uguali(None, "", "string") is False
