"""Protocollo per gli extractor e implementazione dummy. Nessuna AI in questo task."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from sacor.schema import Schema


class Extractor(Protocol):
    def extract(self, pdf: Path, schema: Schema) -> dict[str, str | None]: ...


class DummyExtractor:
    """Restituisce None per ogni campo. Non legge il PDF."""

    def extract(self, pdf: Path, schema: Schema) -> dict[str, str | None]:
        return {campo.nome: None for campo in schema.campi}
