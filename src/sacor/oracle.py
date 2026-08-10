"""Loader e validatore dell'oracle (corpus/attesi.json)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from sacor.schema import Schema


class OracleError(Exception):
    """Errore di dominio nel caricamento o nella validazione dell'oracle."""


@dataclass(frozen=True)
class Oracle:
    oracle_version: int
    documento: str
    documenti: Mapping[str, Mapping[str, str | None]]


def load_oracle(path: Path, schema: Schema) -> Oracle:
    try:
        testo = path.read_text()
    except OSError as exc:
        raise OracleError(f"impossibile leggere '{path}': {exc}") from exc

    try:
        dati = json.loads(testo)
    except json.JSONDecodeError as exc:
        raise OracleError(f"JSON malformato in '{path}': {exc}") from exc

    if not isinstance(dati, dict):
        raise OracleError(f"'{path}' non contiene un oggetto JSON valido")

    versione = dati.get("oracle_version")
    if not isinstance(versione, int) or isinstance(versione, bool):
        raise OracleError("'oracle_version' mancante o non intero")

    documento = dati.get("documento")
    if not isinstance(documento, str) or not documento:
        raise OracleError("'documento' mancante o vuoto")
    if documento != schema.documento:
        raise OracleError(
            f"oracle per '{documento}', schema per '{schema.documento}': non corrispondono"
        )

    grezzi = dati.get("documenti")
    if not isinstance(grezzi, dict):
        raise OracleError("'documenti' mancante o non è un oggetto")

    nomi_campo = {c.nome for c in schema.campi}
    documenti: dict[str, Mapping[str, str | None]] = {}
    for doc_id, campi_attesi in grezzi.items():
        if not isinstance(campi_attesi, dict):
            raise OracleError(f"documento '{doc_id}': non è un oggetto JSON valido")

        chiavi = set(campi_attesi.keys())
        mancanti = nomi_campo - chiavi
        extra = chiavi - nomi_campo
        if mancanti:
            raise OracleError(f"documento '{doc_id}': campi mancanti {sorted(mancanti)}")
        if extra:
            raise OracleError(f"documento '{doc_id}': campi in più {sorted(extra)}")

        for nome, valore in campi_attesi.items():
            if valore is not None and not isinstance(valore, str):
                raise OracleError(
                    f"documento '{doc_id}': campo '{nome}' deve essere stringa o null"
                )

        documenti[doc_id] = dict(campi_attesi)

    return Oracle(oracle_version=versione, documento=documento, documenti=documenti)
