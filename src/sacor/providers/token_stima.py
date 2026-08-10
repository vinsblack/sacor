"""Stima dei token immagine per modello (T4.5, C1): le 5 chiamate del tier 1
sono su pagine SCANSIONE/IBRIDA, senza text layer — stimare dalla lunghezza
del testo misura la cosa sbagliata. Si renderizza la pagina (come fa
scripts/bakeoff.py) e si applica la formula del provider dichiarata in
config/prezzi_modelli.yaml (campo `token_immagine`, con fonte e data).

Il dispatch e' su `token_immagine.tipo`, non sul nome del modello: la
formula vive qui, il riferimento vive nello YAML — vanno tenuti a mano in
sincronia, non c'e' abbastanza varieta' di formule (3) per giustificare un
motore di valutazione.

Se la formula reale di un provider non e' verificabile, si dichiara una
stima al rialzo (mai al ribasso — istruzione utente verbatim: 'una stima
che sbaglia per eccesso e' utilizzabile; una che sbaglia per difetto no')."""

from __future__ import annotations

import math

from sacor.providers.pricing import PrezzoModello


class TipoFormulaSconosciuto(Exception):
    pass


def _tile_512_openai(larghezza_px: int, altezza_px: int) -> int:
    """85 + 170 per tile 512x512, dettaglio alto — formula pubblica OpenAI
    per gpt-4o (vedi 'fonte' nello YAML)."""
    tile_x = math.ceil(larghezza_px / 512)
    tile_y = math.ceil(altezza_px / 512)
    return 85 + 170 * tile_x * tile_y


def stima_token_immagine(prezzo: PrezzoModello, larghezza_px: int, altezza_px: int) -> int:
    config = prezzo.token_immagine
    if config is None:
        raise TipoFormulaSconosciuto(
            "nessuna formula 'token_immagine' dichiarata per questo modello "
            "in config/prezzi_modelli.yaml"
        )

    if config.tipo == "lineare_wh_750":
        # Formula pubblica Anthropic (vision guide): tutti i modelli Claude
        # attuali contano cosi'.
        return math.ceil((larghezza_px * altezza_px) / 750)

    if config.tipo == "tile_512_openai":
        return _tile_512_openai(larghezza_px, altezza_px)

    if config.tipo == "tile_512_openai_stima_al_rialzo":
        # C1: moltiplicatore specifico non verificabile in questa sessione
        # -> si applica x4 sulla formula base nota, per restare sempre
        # sopra, mai sotto.
        return _tile_512_openai(larghezza_px, altezza_px) * 4

    raise TipoFormulaSconosciuto(f"tipo di formula token immagine sconosciuto: '{config.tipo}'")
