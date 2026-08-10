"""Adattatore reale per l'API OpenAI (T4.3, ModelProvider di
sacor.providers.base). Chiave API da OPENAI_API_KEY — mai nel codice, mai
nei file, mai nei log (istruzione utente verbatim: 'il repo diventera'
pubblico'). Token e costo dalla risposta reale dell'API, mai stimati."""

from __future__ import annotations

import base64
import os
import time
from collections.abc import Sequence

import openai

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


class OpenAIProvider:
    nome = "openai"

    def __init__(self, modello: str, prezzi: TabellaPrezzi | None = None) -> None:
        chiave = os.environ.get("OPENAI_API_KEY")
        if not chiave:
            raise ErroreProvider("OPENAI_API_KEY non impostata")
        self._modello = modello
        self._prezzi = prezzi or carica_prezzi()
        self._client = openai.OpenAI(
            api_key=chiave, timeout=_TIMEOUT_SECONDI, max_retries=_MAX_RETRIES
        )

    def estrai(
        self, pagine: Sequence[bytes], prompt: str, campi: Sequence[Campo]
    ) -> RispostaModello:
        contenuto: list[dict[str, object]] = [
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        f"data:{_MEDIA_TYPE_IMMAGINE};base64,"
                        f"{base64.standard_b64encode(pagina).decode('ascii')}"
                    )
                },
            }
            for pagina in pagine
        ]
        contenuto.append({"type": "text", "text": prompt})

        inizio = time.monotonic()
        try:
            risposta = self._client.chat.completions.create(
                model=self._modello,
                max_tokens=_MAX_TOKEN_OUTPUT,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": contenuto}],  # type: ignore[call-overload]
            )
        except openai.RateLimitError as exc:
            raise ErroreProvider(f"rate limit OpenAI esaurito dopo i retry: {exc}") from exc
        except openai.APIConnectionError as exc:
            raise ErroreProvider(
                f"errore di connessione OpenAI (timeout incluso): {exc}"
            ) from exc
        except openai.APIStatusError as exc:
            raise ErroreProvider(f"errore API OpenAI ({exc.status_code}): {exc.message}") from exc
        latenza_secondi = time.monotonic() - inizio

        messaggio = risposta.choices[0].message.content
        testo = messaggio if isinstance(messaggio, str) else ""
        valori = normalizza_risposta(testo, campi)

        usage = risposta.usage
        token_input = usage.prompt_tokens if usage is not None else 0
        token_output = usage.completion_tokens if usage is not None else 0
        costo_stimato = self._prezzi.prezzo(self._modello).costo(token_input, token_output)

        return RispostaModello(
            valori=valori,
            token_input=token_input,
            token_output=token_output,
            costo_stimato=costo_stimato,
            latenza_secondi=latenza_secondi,
            modello=self._modello,
        )
