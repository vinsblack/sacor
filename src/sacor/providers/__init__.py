"""Provider di modello (Blocco 4). Importare da qui, mai dagli SDK
direttamente: `sacor.providers.ModelProvider`/`RispostaModello`, non un
client specifico sparso nei chiamanti.

AnthropicProvider e OpenAIProvider (T4.3) non sono ri-esportati qui: importano
gli SDK reali (`anthropic`, `openai`, extra opzionale `providers`), che i test
e l'uso base della libreria non devono richiedere. Importarli direttamente da
`sacor.providers.anthropic` / `sacor.providers.openai`."""

from sacor.providers.base import ModelProvider, RispostaModello
from sacor.providers.errors import ErroreProvider
from sacor.providers.fake import FakeProvider

__all__ = ["ErroreProvider", "FakeProvider", "ModelProvider", "RispostaModello"]
