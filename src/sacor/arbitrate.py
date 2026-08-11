"""Strato Arbitrate (ADR-045 Fase 2): due provider sullo stesso documento,
confronto campo per campo. Nessun arbitro terzo qui — quando due letture
indipendenti discordano, il disaccordo stesso e' il segnale (confidenza
bassa), non qualcosa da risolvere scegliendo una delle due. Raddoppia il
costo della chiamata: chiamare solo dove serve (bakeoff/tier "1.5") resta
una decisione a valle, non di questo modulo."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import InvalidOperation

from sacor.compare import normalizza
from sacor.providers.base import ModelProvider, RispostaModello
from sacor.schema import Campo


@dataclass(frozen=True)
class RispostaArbitrata:
    # None sia per "entrambi None" sia per "in disaccordo" — chi legge deve
    # controllare 'disaccordi' per distinguere i due casi, non dedurlo da qui.
    valori: dict[str, str | None]
    disaccordi: tuple[str, ...]
    costo_totale: float
    latenza_secondi: float
    risposta_a: RispostaModello
    risposta_b: RispostaModello


def _concordano(a: str | None, b: str | None, tipo: str) -> bool:
    # Ne' a ne' b e' l'oracle (a differenza di sacor.compare.uguali): un
    # valore non normalizzabile non e' un errore di dato da segnalare come
    # OracleError, e' solo un disaccordo come un altro — o un accordo, se
    # i due grezzi sono identici (es. stesso errore di formato da entrambi).
    try:
        return normalizza(a, tipo) == normalizza(b, tipo)  # type: ignore[arg-type]
    except (InvalidOperation, ValueError):
        return a == b


def estrai_con_arbitrato(
    pagine: Sequence[bytes],
    prompt: str,
    campi: Sequence[Campo],
    provider_a: ModelProvider,
    provider_b: ModelProvider,
) -> RispostaArbitrata:
    risposta_a = provider_a.estrai(pagine, prompt, campi)
    risposta_b = provider_b.estrai(pagine, prompt, campi)

    valori: dict[str, str | None] = {}
    disaccordi: list[str] = []
    for campo in campi:
        va = risposta_a.valori.get(campo.nome)
        vb = risposta_b.valori.get(campo.nome)
        if _concordano(va, vb, campo.tipo):
            valori[campo.nome] = va
        else:
            disaccordi.append(campo.nome)
            valori[campo.nome] = None

    return RispostaArbitrata(
        valori=valori,
        disaccordi=tuple(disaccordi),
        costo_totale=risposta_a.costo_stimato + risposta_b.costo_stimato,
        latenza_secondi=risposta_a.latenza_secondi + risposta_b.latenza_secondi,
        risposta_a=risposta_a,
        risposta_b=risposta_b,
    )
