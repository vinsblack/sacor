"""Normalizzazione e confronto oracle vs extractor. Match esatto, nessuna
tolleranza: la tolleranza vive nelle invarianti, non qui (ADR-011)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

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
    try:
        return normalizza(atteso, tipo) == normalizza(effettivo, tipo)
    except (InvalidOperation, ValueError):
        return False
