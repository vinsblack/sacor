"""Astrazione dei provider di modello (Blocco 4). Protocol comune: nessun
chiamante parla mai direttamente con l'SDK di un provider — stesso principio
di Extractor (ADR-033) e ModelProvider concreti (sacor.providers.fake, e i
provider reali che arriveranno)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sacor.schema import Campo


@dataclass(frozen=True)
class RispostaModello:
    """Il costo si traccia dalla prima riga di codice, non si aggiunge dopo
    (ADR-034 lo presuppone per la cache; qui e' la fonte del dato). Un
    provider che non sa dire quanto e' costato non e' usabile."""

    valori: dict[str, str | None]
    token_input: int
    token_output: int
    costo_stimato: float
    latenza_secondi: float
    modello: str


class ModelProvider(Protocol):
    nome: str

    def estrai(
        self, pagine: Sequence[bytes], prompt: str, campi: Sequence[Campo]
    ) -> RispostaModello: ...
