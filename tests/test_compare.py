import pytest

from sacor.compare import uguali
from sacor.oracle import OracleError


def test_decimal_con_zeri_finali_diversi_e_match() -> None:
    assert uguali("1234.56", "1234.560", "decimal") is True


def test_null_vs_null_e_match() -> None:
    assert uguali(None, None, "string") is True


def test_null_vs_stringa_vuota_non_e_match() -> None:
    assert uguali(None, "", "string") is False


def test_atteso_malformato_alza_oracle_error() -> None:
    """T4.13 (MEDIA, trovato in review): un oracle malformato (typo in un
    JSON scritto a mano, es. una data non valida) non deve diventare
    silenziosamente 'l'estrattore ha sbagliato' — e' un problema nei dati di
    test, non nel codice sotto misura, e va segnalato come tale."""
    with pytest.raises(OracleError, match="atteso"):
        uguali("2026-13-40", "2026-01-01", "date")


def test_effettivo_malformato_resta_un_semplice_mismatch() -> None:
    """L'estrattore che produce un valore non normalizzabile e' un errore
    vero da misurare (l'estrattore ha inventato/sbagliato formato) — resta
    un mismatch (False), non un'eccezione: e' esattamente cio' che l'eval
    deve contare come 'valore errato'."""
    assert uguali("2026-01-01", "non-una-data", "date") is False


def test_stringa_case_diversa_e_match() -> None:
    """T4.17-bis (diagnosi corpus reale): 'SMART ENERGY S.r.l.' vs 'Smart
    Energy S.r.l.' e' lo stesso fornitore, non un errore di lettura — solo
    maiuscole/minuscole diverse non e' un mismatch reale da contare."""
    assert uguali("Smart Energy S.r.l.", "SMART ENERGY S.R.L.", "string") is True


def test_stringa_diversa_anche_case_insensitive_resta_mismatch() -> None:
    assert uguali("Sorgenia", "Enel Energia", "string") is False
