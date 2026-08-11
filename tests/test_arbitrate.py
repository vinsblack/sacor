"""TDD per lo strato Arbitrate (ADR-045 Fase 2): due provider, stesso
documento, confronto campo per campo. Nessuna rete: provider stub in
memoria, stesso principio di FakeProvider ma senza fixture su disco."""

from __future__ import annotations

from dataclasses import dataclass

from sacor.arbitrate import estrai_con_arbitrato
from sacor.providers.base import RispostaModello
from sacor.schema import Campo


@dataclass
class _ProviderStub:
    nome: str
    valori: dict[str, str | None]
    costo_stimato: float = 0.01
    latenza_secondi: float = 1.0

    def estrai(self, pagine, prompt, campi):
        return RispostaModello(
            valori=dict(self.valori),
            token_input=10,
            token_output=5,
            costo_stimato=self.costo_stimato,
            latenza_secondi=self.latenza_secondi,
            modello=self.nome,
        )


_CAMPI = (
    Campo(nome="pod", tipo="string", obbligatorio=True, estrazione=None),
    Campo(nome="kwh_totale", tipo="decimal", obbligatorio=True, estrazione=None),
)


def test_valori_concordi_restano_nel_risultato():
    a = _ProviderStub("a", {"pod": "IT001E12345678", "kwh_totale": "100.5"})
    b = _ProviderStub("b", {"pod": "IT001E12345678", "kwh_totale": "100.50"})

    esito = estrai_con_arbitrato([], "prompt", _CAMPI, a, b)

    assert esito.valori == {"pod": "IT001E12345678", "kwh_totale": "100.5"}
    assert esito.disaccordi == ()


def test_valori_discordi_segnalati_e_non_arbitrati():
    a = _ProviderStub("a", {"pod": "IT001E12345678", "kwh_totale": "100.5"})
    b = _ProviderStub("b", {"pod": "IT001E99999999", "kwh_totale": "100.5"})

    esito = estrai_con_arbitrato([], "prompt", _CAMPI, a, b)

    assert esito.disaccordi == ("pod",)
    assert esito.valori["pod"] is None  # ADR-045: segnala, non sceglie (no arbitro terzo)
    assert esito.valori["kwh_totale"] == "100.5"


def test_costo_e_latenza_sommano_entrambe_le_chiamate():
    a = _ProviderStub("a", {"pod": "x", "kwh_totale": "1"}, costo_stimato=0.02, latenza_secondi=2.0)
    b = _ProviderStub("b", {"pod": "x", "kwh_totale": "1"}, costo_stimato=0.03, latenza_secondi=3.0)

    esito = estrai_con_arbitrato([], "prompt", _CAMPI, a, b)

    assert esito.costo_totale == 0.05
    assert esito.latenza_secondi == 5.0
    assert esito.risposta_a.modello == "a"
    assert esito.risposta_b.modello == "b"


def test_valore_non_normalizzabile_confrontato_come_testo_grezzo():
    # ne' a ne' b sono l'oracle qui (ADR-045): un valore malformato non e'
    # un errore di dato, e' solo un disaccordo come un altro (o un accordo,
    # se identico) — mai un'eccezione.
    a = _ProviderStub("a", {"pod": "x", "kwh_totale": "non-un-numero"})
    b = _ProviderStub("b", {"pod": "x", "kwh_totale": "non-un-numero"})

    esito = estrai_con_arbitrato([], "prompt", _CAMPI, a, b)

    assert esito.disaccordi == ()
    assert esito.valori["kwh_totale"] == "non-un-numero"


def test_none_su_entrambi_conta_come_accordo():
    a = _ProviderStub("a", {"pod": "x", "kwh_totale": None})
    b = _ProviderStub("b", {"pod": "x", "kwh_totale": None})

    esito = estrai_con_arbitrato([], "prompt", _CAMPI, a, b)

    assert esito.disaccordi == ()
    assert esito.valori["kwh_totale"] is None
