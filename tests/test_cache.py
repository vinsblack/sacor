import json
import time
from pathlib import Path

from sacor.cache import CacheDisco, chiave_cache


def test_cache_miss_ritorna_none(tmp_path: Path) -> None:
    cache = CacheDisco(cache_dir=tmp_path)
    chiave = chiave_cache([b"pagina"], "prompt", "modello-x", 1)

    assert cache.leggi(chiave) is None
    assert cache.contiene(chiave) is False


def test_cache_hit_ritorna_la_risposta_scritta(tmp_path: Path) -> None:
    cache = CacheDisco(cache_dir=tmp_path)
    chiave = chiave_cache([b"pagina"], "prompt", "modello-x", 1)

    cache.scrivi(chiave, {"pod": "IT001E12345678"})

    assert cache.leggi(chiave) == {"pod": "IT001E12345678"}
    assert cache.contiene(chiave) is True


def test_cambio_prompt_invalida_per_costruzione(tmp_path: Path) -> None:
    cache = CacheDisco(cache_dir=tmp_path)
    chiave_a = chiave_cache([b"pagina"], "prompt A", "modello-x", 1)
    chiave_b = chiave_cache([b"pagina"], "prompt B", "modello-x", 1)

    cache.scrivi(chiave_a, {"pod": "X"})

    assert chiave_a != chiave_b
    assert cache.leggi(chiave_b) is None


def test_cambio_modello_invalida_per_costruzione(tmp_path: Path) -> None:
    cache = CacheDisco(cache_dir=tmp_path)
    chiave_a = chiave_cache([b"pagina"], "prompt", "modello-A", 1)
    chiave_b = chiave_cache([b"pagina"], "prompt", "modello-B", 1)

    cache.scrivi(chiave_a, {"pod": "X"})

    assert chiave_a != chiave_b
    assert cache.leggi(chiave_b) is None


def test_cambio_versione_schema_invalida_per_costruzione(tmp_path: Path) -> None:
    cache = CacheDisco(cache_dir=tmp_path)
    chiave_v1 = chiave_cache([b"pagina"], "prompt", "modello-x", 1)
    chiave_v2 = chiave_cache([b"pagina"], "prompt", "modello-x", 2)

    cache.scrivi(chiave_v1, {"pod": "X"})

    assert chiave_v1 != chiave_v2
    assert cache.leggi(chiave_v2) is None


def test_voce_scaduta_oltre_ttl_e_un_miss(tmp_path: Path) -> None:
    cache = CacheDisco(cache_dir=tmp_path, ttl_secondi=60)
    chiave = chiave_cache([b"pagina"], "prompt", "modello-x", 1)

    # Scrive direttamente una voce con timestamp vecchio, senza aspettare.
    tmp_path.mkdir(parents=True, exist_ok=True)
    percorso = tmp_path / f"{chiave}.json"
    voce_vecchia = {"risposta": {"pod": "X"}, "scritta_il": time.time() - 3600}
    percorso.write_text(json.dumps(voce_vecchia))

    assert cache.leggi(chiave) is None


def test_voce_entro_ttl_e_un_hit(tmp_path: Path) -> None:
    cache = CacheDisco(cache_dir=tmp_path, ttl_secondi=3600)
    chiave = chiave_cache([b"pagina"], "prompt", "modello-x", 1)

    cache.scrivi(chiave, {"pod": "X"})

    assert cache.leggi(chiave) == {"pod": "X"}


def test_confine_tra_pagine_non_e_ambiguo() -> None:
    """T4.13 (BASSA, trovato in review): chiave_cache concatenava i byte
    delle pagine senza delimitatore tra una e l'altra — [b'AB', b'C'] e
    [b'A', b'BC'] producevano lo stesso hash (stessa sequenza di byte in
    ingresso a sha256.update, chiamata piu' volte o una sola non fa
    differenza). Non e' solo teorico: e' riproducibile con questo esempio
    minimo."""
    chiave_1 = chiave_cache([b"AB", b"C"], "prompt", "modello-x", 1)
    chiave_2 = chiave_cache([b"A", b"BC"], "prompt", "modello-x", 1)
    assert chiave_1 != chiave_2


def test_scritta_il_non_numerico_e_un_miss_non_un_crash(tmp_path: Path) -> None:
    """T4.13 (trovato in code review): un file di cache scritto a mano (o da
    una versione futura) con 'scritta_il' non numerico faceva sollevare un
    TypeError non gestito invece di un cache miss."""
    cache = CacheDisco(cache_dir=tmp_path, ttl_secondi=3600)
    chiave = chiave_cache([b"pagina"], "prompt", "modello-x", 1)

    tmp_path.mkdir(parents=True, exist_ok=True)
    percorso = tmp_path / f"{chiave}.json"
    voce = {"risposta": {"pod": "X"}, "scritta_il": "non-un-numero"}
    percorso.write_text(json.dumps(voce))

    assert cache.leggi(chiave) is None
