"""Adattatore reale per l'API Anthropic (T4.3, ModelProvider di
sacor.providers.base). Chiave API da ANTHROPIC_API_KEY — mai nel codice, mai
nei file, mai nei log (istruzione utente verbatim: 'il repo diventera'
pubblico'). Token e costo dalla risposta reale dell'API, mai stimati."""

from __future__ import annotations

import base64
import os
import time
from collections.abc import Sequence

import anthropic

from sacor.providers.base import RispostaModello
from sacor.providers.errors import ErroreProvider
from sacor.providers.parsing import normalizza_risposta
from sacor.providers.pricing import TabellaPrezzi
from sacor.providers.pricing import carica as carica_prezzi
from sacor.schema import Campo

_MEDIA_TYPE_IMMAGINE = "image/png"
_TIMEOUT_SECONDI = 60.0
_MAX_RETRIES = 5  # retry con backoff esponenziale: gestito dall'SDK ufficiale
_MAX_TOKEN_OUTPUT = 4096

# T4.13 (ALTA, trovato in review): stop_reason diversi da questi due
# significano che la risposta e' troncata (max_tokens) o non e' arrivata
# intera per un altro motivo (refusal, pause_turn, ...). Un JSON troncato
# diventa testo non parsabile -> normalizza_risposta lo legge come "il
# modello non ha trovato nulla" (tutti i campi None), indistinguibile da
# un'astensione legittima. La chiamata non e' andata a buon fine: va
# segnalata come tale (ErroreProvider), non confusa con un valore assente.
_STOP_REASON_OK = frozenset({"end_turn", "stop_sequence"})


class AnthropicProvider:
    nome = "anthropic"

    def __init__(self, modello: str, prezzi: TabellaPrezzi | None = None) -> None:
        chiave = os.environ.get("ANTHROPIC_API_KEY")
        if not chiave:
            raise ErroreProvider("ANTHROPIC_API_KEY non impostata")
        self._modello = modello
        self._prezzi = prezzi or carica_prezzi()
        self._client = anthropic.Anthropic(
            api_key=chiave, timeout=_TIMEOUT_SECONDI, max_retries=_MAX_RETRIES
        )

    def estrai(
        self, pagine: Sequence[bytes], prompt: str, campi: Sequence[Campo]
    ) -> RispostaModello:
        # ADR-054: il prompt (testo, non le immagini) va PRIMA nel content e
        # porta il breakpoint di cache_control. Anthropic cachea il prefisso
        # fino al blocco marcato incluso — mettere il testo per primo lo
        # rende quel prefisso: chiamate diverse con lo stesso insieme di
        # campi mancanti (stesso prompt generato da costruisci_prompt)
        # condividono la cache anche se le immagini (dopo, non cacheate)
        # cambiano documento per documento. Se il prompt e' sotto la soglia
        # minima cacheabile del modello, cache_control e' ignorato senza
        # errore ne' costo aggiuntivo.
        contenuto: list[dict[str, object]] = [
            {
                "type": "text",
                "text": prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        contenuto.extend(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": _MEDIA_TYPE_IMMAGINE,
                    "data": base64.standard_b64encode(pagina).decode("ascii"),
                },
            }
            for pagina in pagine
        )

        inizio = time.monotonic()
        try:
            risposta = self._client.messages.create(
                model=self._modello,
                max_tokens=_MAX_TOKEN_OUTPUT,
                messages=[{"role": "user", "content": contenuto}],  # type: ignore[typeddict-item]
            )
        except anthropic.RateLimitError as exc:
            raise ErroreProvider(f"rate limit Anthropic esaurito dopo i retry: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise ErroreProvider(
                f"errore di connessione Anthropic (timeout incluso): {exc}"
            ) from exc
        except anthropic.APIStatusError as exc:
            raise ErroreProvider(
                f"errore API Anthropic ({exc.status_code}): {exc.message}"
            ) from exc
        latenza_secondi = time.monotonic() - inizio

        if risposta.stop_reason not in _STOP_REASON_OK:
            raise ErroreProvider(
                f"risposta Anthropic incompleta o rifiutata (stop_reason={risposta.stop_reason})"
            )

        testo = "".join(blocco.text for blocco in risposta.content if blocco.type == "text")
        valori = normalizza_risposta(testo, campi)

        token_input = risposta.usage.input_tokens
        token_output = risposta.usage.output_tokens
        # ADR-054: la risposta separa i token di cache da input_tokens (che
        # resta "solo non cacheati") — vanno sommati a parte al costo, mai
        # ignorati: un costo_stimato che non li conta sottostimerebbe la
        # spesa reale in silenzio. getattr perche' l'SDK non li restituisce
        # affatto se la risposta non ha usato la cache.
        token_cache_scrittura = getattr(risposta.usage, "cache_creation_input_tokens", None) or 0
        token_cache_lettura = getattr(risposta.usage, "cache_read_input_tokens", None) or 0
        costo_stimato = self._prezzi.prezzo(self._modello).costo(
            token_input, token_output, token_cache_scrittura, token_cache_lettura
        )

        return RispostaModello(
            valori=valori,
            token_input=token_input,
            token_output=token_output,
            costo_stimato=costo_stimato,
            latenza_secondi=latenza_secondi,
            modello=self._modello,
        )
