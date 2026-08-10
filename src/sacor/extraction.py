"""Registro dei tipi di estrazione noti (tier 0, ADR-032): il core non sa
cosa sia un POD, esegue solo il criterio dichiarato nello schema — stesso
principio di invarianti e segmentazione. Nuovo campo estraibile, nuovo
pattern nello YAML, non nuovo codice.
"""

from __future__ import annotations

from dataclasses import dataclass

TIPI_NOTI: tuple[str, ...] = ("regex",)


@dataclass(frozen=True)
class EstrazioneConfig:
    tipo: str
    pattern: str
