"""Normalizzazione e confronto oracle vs extractor. Match esatto, nessuna
tolleranza: la tolleranza vive nelle invarianti, non qui (ADR-011)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from sacor.oracle import OracleError
from sacor.schema import TipoCampo


def normalizza(valore: str | None, tipo: TipoCampo) -> str | Decimal | int | None:
    if valore is None:
        return None
    if tipo == "string":
        return valore.strip()
    if tipo == "decimal":
        return Decimal(valore)
    if tipo == "integer":
        return int(valore)
    if tipo == "date":
        return date.fromisoformat(valore).isoformat()
    raise AssertionError(f"tipo campo non gestito: {tipo}")


def uguali(atteso: str | None, effettivo: str | None, tipo: TipoCampo) -> bool:
    # T4.13 (MEDIA, trovato in review): un 'atteso' che non normalizza e' un
    # oracle malformato (dato di test scritto a male), non un estrattore
    # sbagliato — le due cose vanno distinte, non confuse in un unico False
    # silenzioso. Solo l'errore su 'effettivo' e' un mismatch legittimo.
    try:
        valore_atteso = normalizza(atteso, tipo)
    except (InvalidOperation, ValueError) as exc:
        raise OracleError(
            f"valore atteso {atteso!r} non normalizzabile come {tipo}: {exc}"
        ) from exc
    try:
        valore_effettivo = normalizza(effettivo, tipo)
    except (InvalidOperation, ValueError):
        return False
    return valore_atteso == valore_effettivo
