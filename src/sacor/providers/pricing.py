"""Tabella prezzi dei modelli reali (T4.3): letta da un file YAML separato
dal codice — 'i prezzi cambiano: non devono stare nel codice' (istruzione
utente verbatim). Vedi config/prezzi_modelli.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PREZZI_PATH = REPO_ROOT / "config" / "prezzi_modelli.yaml"


class PrezziError(Exception):
    """Errore di dominio nel caricamento della tabella prezzi."""


@dataclass(frozen=True)
class TokenImmagineConfig:
    """Documenta la formula usata per stimare i token di un'immagine (T4.5,
    C1): 'tipo' e' l'unico campo che il codice legge per decidere quale
    formula applicare (sacor.providers.token_stima); 'formula'/'fonte'/
    'verificato_il' sono per chi legge il file, non per il codice — vanno
    tenuti a mano in sincronia col 'tipo'."""

    tipo: str
    formula: str
    fonte: str
    verificato_il: str


@dataclass(frozen=True)
class PrezzoModello:
    costo_input_per_milione: float
    costo_output_per_milione: float
    token_immagine: TokenImmagineConfig | None = None
    # ADR-054: prompt caching (Anthropic cache_control). None = modello senza
    # cache configurata — ricevere token di cache con questi campi a None e'
    # un errore di dominio (PrezziError), mai un costo zero assunto in
    # silenzio (stesso principio di "mai indovinare" applicato al costo).
    costo_cache_scrittura_per_milione: float | None = None
    costo_cache_lettura_per_milione: float | None = None

    def costo(
        self,
        token_input: int,
        token_output: int,
        token_cache_scrittura: int = 0,
        token_cache_lettura: int = 0,
    ) -> float:
        totale = (
            token_input * self.costo_input_per_milione / 1_000_000
            + token_output * self.costo_output_per_milione / 1_000_000
        )
        if token_cache_scrittura:
            if self.costo_cache_scrittura_per_milione is None:
                raise PrezziError(
                    "token di cache in scrittura ricevuti ma "
                    "'costo_cache_scrittura_per_milione' non e' configurato per questo modello"
                )
            totale += token_cache_scrittura * self.costo_cache_scrittura_per_milione / 1_000_000
        if token_cache_lettura:
            if self.costo_cache_lettura_per_milione is None:
                raise PrezziError(
                    "token di cache in lettura ricevuti ma "
                    "'costo_cache_lettura_per_milione' non e' configurato per questo modello"
                )
            totale += token_cache_lettura * self.costo_cache_lettura_per_milione / 1_000_000
        return totale


@dataclass(frozen=True)
class TabellaPrezzi:
    aggiornato_il: str
    prezzi: dict[str, PrezzoModello]

    def prezzo(self, modello: str) -> PrezzoModello:
        trovato = self.prezzi.get(modello)
        if trovato is None:
            raise PrezziError(
                f"nessun prezzo per il modello '{modello}' in {PREZZI_PATH} "
                f"(aggiornato il {self.aggiornato_il}) — aggiungilo prima di usarlo"
            )
        return trovato


def carica(path: Path = PREZZI_PATH) -> TabellaPrezzi:
    if not path.is_file():
        raise PrezziError(f"file prezzi mancante: {path}")

    dati: Any = yaml.safe_load(path.read_text())
    if not isinstance(dati, dict):
        raise PrezziError(f"'{path}' non contiene un mapping YAML valido")

    aggiornato_il = dati.get("aggiornato_il")
    if not isinstance(aggiornato_il, str) or not aggiornato_il:
        raise PrezziError(f"'{path}': 'aggiornato_il' mancante o vuoto")

    grezzi = dati.get("modelli")
    if not isinstance(grezzi, dict) or not grezzi:
        raise PrezziError(f"'{path}': 'modelli' mancante o vuoto")

    prezzi: dict[str, PrezzoModello] = {}
    for nome, voce in grezzi.items():
        if not isinstance(voce, dict):
            raise PrezziError(f"'{path}': modello '{nome}' non e' un mapping YAML")
        costo_input = voce.get("costo_input_per_milione")
        costo_output = voce.get("costo_output_per_milione")
        if not isinstance(costo_input, int | float) or isinstance(costo_input, bool):
            raise PrezziError(f"'{path}': modello '{nome}' con 'costo_input_per_milione' invalido")
        if not isinstance(costo_output, int | float) or isinstance(costo_output, bool):
            raise PrezziError(
                f"'{path}': modello '{nome}' con 'costo_output_per_milione' invalido"
            )
        prezzi[nome] = PrezzoModello(
            costo_input_per_milione=float(costo_input),
            costo_output_per_milione=float(costo_output),
            token_immagine=_leggi_token_immagine(voce.get("token_immagine"), nome, path),
            costo_cache_scrittura_per_milione=_leggi_float_opzionale(
                voce.get("costo_cache_scrittura_per_milione"),
                "costo_cache_scrittura_per_milione",
                nome,
                path,
            ),
            costo_cache_lettura_per_milione=_leggi_float_opzionale(
                voce.get("costo_cache_lettura_per_milione"),
                "costo_cache_lettura_per_milione",
                nome,
                path,
            ),
        )

    return TabellaPrezzi(aggiornato_il=aggiornato_il, prezzi=prezzi)


def _leggi_float_opzionale(grezzo: Any, campo: str, nome_modello: str, path: Path) -> float | None:
    if grezzo is None:
        return None
    if not isinstance(grezzo, int | float) or isinstance(grezzo, bool):
        raise PrezziError(f"'{path}': modello '{nome_modello}' con '{campo}' invalido")
    return float(grezzo)


def _leggi_token_immagine(
    grezzo: Any, nome_modello: str, path: Path
) -> TokenImmagineConfig | None:
    if grezzo is None:
        return None
    if not isinstance(grezzo, dict):
        raise PrezziError(
            f"'{path}': modello '{nome_modello}': 'token_immagine' deve essere un mapping"
        )

    campi = {}
    for chiave in ("tipo", "formula", "fonte", "verificato_il"):
        valore = grezzo.get(chiave)
        if not isinstance(valore, str) or not valore:
            raise PrezziError(
                f"'{path}': modello '{nome_modello}': 'token_immagine.{chiave}' mancante o vuoto"
            )
        campi[chiave] = valore

    return TokenImmagineConfig(**campi)
