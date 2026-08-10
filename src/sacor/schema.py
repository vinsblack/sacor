"""Loader e validatore dello schema YAML di un tipo di documento."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, cast, get_args

import yaml

from sacor.invariants import TIPI_NOTI

TipoCampo = Literal["string", "date", "integer", "decimal"]
Severita = Literal["warning", "reject"]

_TIPI_CAMPO: tuple[str, ...] = get_args(TipoCampo)
_SEVERITA: tuple[str, ...] = get_args(Severita)


class SchemaError(Exception):
    """Errore di dominio nel caricamento o nella validazione di uno schema."""


@dataclass(frozen=True)
class Campo:
    nome: str
    tipo: TipoCampo
    obbligatorio: bool


@dataclass(frozen=True)
class Invariante:
    id: str
    tipo: str
    severita: Severita
    params: Mapping[str, Any]


@dataclass(frozen=True)
class Schema:
    schema_version: int
    documento: str
    campi: tuple[Campo, ...]
    invarianti: tuple[Invariante, ...]

    def campo(self, nome: str) -> Campo | None:
        for c in self.campi:
            if c.nome == nome:
                return c
        return None


def load(path: Path) -> Schema:
    if not path.is_file():
        raise SchemaError(f"file di schema mancante: {path}")

    try:
        testo = path.read_text()
    except OSError as exc:
        raise SchemaError(f"impossibile leggere '{path}': {exc}") from exc

    try:
        dati = yaml.safe_load(testo)
    except yaml.YAMLError as exc:
        raise SchemaError(f"YAML malformato in '{path}': {exc}") from exc

    if not isinstance(dati, dict):
        raise SchemaError(f"'{path}' non contiene un mapping YAML valido")

    campi = _leggi_campi(dati)
    return Schema(
        schema_version=_leggi_schema_version(dati),
        documento=_leggi_documento(dati),
        campi=campi,
        invarianti=_leggi_invarianti(dati, campi),
    )


def _leggi_schema_version(dati: dict[str, Any]) -> int:
    valore = dati.get("schema_version")
    if not isinstance(valore, int) or isinstance(valore, bool):
        raise SchemaError("'schema_version' mancante o non intero")
    return valore


def _leggi_documento(dati: dict[str, Any]) -> str:
    valore = dati.get("documento")
    if not isinstance(valore, str) or not valore:
        raise SchemaError("'documento' mancante o vuoto")
    return valore


def _leggi_campi(dati: dict[str, Any]) -> tuple[Campo, ...]:
    grezzi = dati.get("campi")
    if not isinstance(grezzi, list) or not grezzi:
        raise SchemaError("'campi' mancante o vuoto: serve almeno un campo")

    campi: list[Campo] = []
    nomi_visti: set[str] = set()
    for i, grezzo in enumerate(grezzi):
        if not isinstance(grezzo, dict):
            raise SchemaError(f"campo #{i}: non è un mapping YAML valido")

        nome = grezzo.get("nome")
        if not isinstance(nome, str) or not nome:
            raise SchemaError(f"campo #{i}: 'nome' mancante o vuoto")

        if nome in nomi_visti:
            raise SchemaError(f"campo '{nome}': nome duplicato")
        nomi_visti.add(nome)

        tipo = grezzo.get("tipo")
        if tipo not in _TIPI_CAMPO:
            raise SchemaError(
                f"campo '{nome}': tipo '{tipo}' sconosciuto "
                f"(ammessi: {', '.join(_TIPI_CAMPO)})"
            )

        obbligatorio = grezzo.get("obbligatorio")
        if not isinstance(obbligatorio, bool):
            raise SchemaError(f"campo '{nome}': 'obbligatorio' mancante o non booleano")

        campi.append(Campo(nome=nome, tipo=cast(TipoCampo, tipo), obbligatorio=obbligatorio))

    return tuple(campi)


def _leggi_invarianti(dati: dict[str, Any], campi: tuple[Campo, ...]) -> tuple[Invariante, ...]:
    grezzi = dati.get("invarianti", [])
    if not isinstance(grezzi, list):
        raise SchemaError("'invarianti' deve essere una lista")

    nomi_campo = {c.nome for c in campi}
    invarianti: list[Invariante] = []
    id_visti: set[str] = set()

    for i, grezzo in enumerate(grezzi):
        if not isinstance(grezzo, dict):
            raise SchemaError(f"invariante #{i}: non è un mapping YAML valido")

        id_ = grezzo.get("id")
        if not isinstance(id_, str) or not id_:
            raise SchemaError(f"invariante #{i}: 'id' mancante o vuoto")

        if id_ in id_visti:
            raise SchemaError(f"invariante '{id_}': id duplicato")
        id_visti.add(id_)

        tipo = grezzo.get("tipo")
        if tipo not in TIPI_NOTI:
            raise SchemaError(
                f"invariante '{id_}': tipo '{tipo}' sconosciuto "
                f"(ammessi: {', '.join(TIPI_NOTI)})"
            )

        severita = grezzo.get("severita")
        if severita not in _SEVERITA:
            raise SchemaError(
                f"invariante '{id_}': severita '{severita}' sconosciuta "
                f"(ammesse: {', '.join(_SEVERITA)})"
            )

        params = {k: v for k, v in grezzo.items() if k not in ("id", "tipo", "severita")}
        _valida_referenze_campo(id_, tipo, params, nomi_campo)

        invarianti.append(
            Invariante(
                id=id_,
                tipo=tipo,
                severita=cast(Severita, severita),
                params=MappingProxyType(params),
            )
        )

    return tuple(invarianti)


def _valida_referenze_campo(
    invariante_id: str, tipo: str, params: dict[str, Any], nomi_campo: set[str]
) -> None:
    for chiave in TIPI_NOTI[tipo]:
        valore = params.get(chiave)
        referenze = valore if isinstance(valore, list) else [valore]
        for campo_ref in referenze:
            if campo_ref not in nomi_campo:
                raise SchemaError(
                    f"invariante '{invariante_id}': il campo '{campo_ref}' non esiste"
                )
