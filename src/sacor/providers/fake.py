"""Provider deterministico per i test: nessuna rete, MAI. Legge le risposte
attese da un file di fixture; simula token e costo in modo deterministico
(dalla lunghezza di pagine e prompt), mai casuale."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from sacor.providers.base import RispostaModello
from sacor.schema import Campo

# Placeholder di costo, non un prezzo reale di alcun modello (nessuna scelta
# di modello ancora, ADR-035/T4.2): serve solo a rendere RispostaModello.
# costo_stimato deterministico e diverso da zero nei test.
_COSTO_PER_TOKEN_INPUT = 0.0000005
_COSTO_PER_TOKEN_OUTPUT = 0.0000015


def chiave_pagine(pagine: Sequence[bytes]) -> str:
    """SHA-256 esadecimale del contenuto concatenato delle pagine — usata
    dalla fixture per identificare quale documento e' stato passato, senza
    che FakeProvider debba conoscere id o percorsi di file."""
    hasher = hashlib.sha256()
    for pagina in pagine:
        hasher.update(pagina)
    return hasher.hexdigest()


class FakeProvider:
    """fixture: {sha256_esadecimale(pagine concatenate): {nome_campo: valore}}."""

    nome = "fake"

    def __init__(self, fixture_path: Path, modello: str = "fake-model-v1") -> None:
        dati = json.loads(fixture_path.read_text())
        if not isinstance(dati, dict):
            raise ValueError(f"'{fixture_path}' non contiene un oggetto JSON valido")
        self._fixture: dict[str, dict[str, str | None]] = dati
        self._modello = modello

    def estrai(
        self, pagine: Sequence[bytes], prompt: str, campi: Sequence[Campo]
    ) -> RispostaModello:
        voce = self._fixture.get(chiave_pagine(pagine), {})
        valori = {campo.nome: voce.get(campo.nome) for campo in campi}

        token_input = sum(len(p) for p in pagine) // 4 + len(prompt) // 4
        token_output = sum(5 for v in valori.values() if v is not None) or 1
        costo_stimato = (
            token_input * _COSTO_PER_TOKEN_INPUT + token_output * _COSTO_PER_TOKEN_OUTPUT
        )

        return RispostaModello(
            valori=valori,
            token_input=token_input,
            token_output=token_output,
            costo_stimato=costo_stimato,
            latenza_secondi=0.0,
            modello=self._modello,
        )
