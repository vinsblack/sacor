"""Cache disco per le risposte dei ModelProvider (ADR-034): precondizione
del tier 1, non un'ottimizzazione. Senza, il costo di ogni rilancio
dell'eval diventa una ragione per non rilanciarlo — e il metodo del
progetto si regge sul rieseguire la misura ad ogni modifica.

Chiave: SHA-256 di (contenuto pagina + prompt + identificativo modello +
versione schema). Un cambio di prompt o modello produce una chiave diversa
per costruzione: e' un esperimento diverso, non serve un percorso di
invalidazione dedicato.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Sequence
from pathlib import Path

# Fuori dal repo (ADR-034: "ignorata da git"): non ha senso versionare
# risposte di modello, e la home utente sopravvive a `git clean`.
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "sacor" / "provider"

# Il corpus non cambia da solo: un TTL lungo di default, non un'ora.
DEFAULT_TTL_SECONDI = 30 * 24 * 60 * 60  # 30 giorni


def chiave_cache(pagine: Sequence[bytes], prompt: str, modello: str, schema_version: int) -> str:
    hasher = hashlib.sha256()
    for pagina in pagine:
        hasher.update(pagina)
    hasher.update(b"\0")
    hasher.update(prompt.encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(modello.encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(str(schema_version).encode("utf-8"))
    return hasher.hexdigest()


class CacheDisco:
    """Una voce per file, nome = chiave. Nessun database: il corpus e' di
    poche decine di documenti, non serve altro."""

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        ttl_secondi: int = DEFAULT_TTL_SECONDI,
    ) -> None:
        self._dir = cache_dir
        self._ttl = ttl_secondi

    def _percorso(self, chiave: str) -> Path:
        return self._dir / f"{chiave}.json"

    def leggi(self, chiave: str) -> dict[str, object] | None:
        percorso = self._percorso(chiave)
        if not percorso.is_file():
            return None
        try:
            voce = json.loads(percorso.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(voce, dict) or "scritta_il" not in voce or "risposta" not in voce:
            return None

        eta_secondi = time.time() - voce["scritta_il"]
        if eta_secondi > self._ttl:
            return None

        risposta = voce["risposta"]
        return risposta if isinstance(risposta, dict) else None

    def scrivi(self, chiave: str, risposta: dict[str, object]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        voce = {"risposta": risposta, "scritta_il": time.time()}
        self._percorso(chiave).write_text(json.dumps(voce))

    def contiene(self, chiave: str) -> bool:
        return self.leggi(chiave) is not None
