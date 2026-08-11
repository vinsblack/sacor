"""Bake-off tra modelli (T4.4/T4.5): stesse chiamate reali, stesso prompt e
corpus, cache SEMPRE disattivata per il confronto (istruzione utente
verbatim). Nessun modello "scelto" nel codice: lo script produce solo la
tabella, la decisione resta a chi la legge.

L'accuratezza qui e' calcolata SOLO sui campi effettivamente chiesti al
tier 1 (quelli che il tier 0 ha lasciato None per ciascuna istanza) — non
l'accuratezza dell'intera pipeline (quella la riporta `python eval/run.py`).
E' la misura giusta per confrontare modelli: i campi che il tier 0 gia'
risolve sono identici per ogni modello e non discriminano nulla.

C2 (T4.5): tetto di spesa reale per l'intero giro (tutti i modelli insieme).
Superato -> ci si ferma, niente altre chiamate, si riporta cosa e' successo.
"""

from __future__ import annotations

import statistics
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.run import (  # noqa: E402
    MODELLI_BAKEOFF,
    ChiamataDaCompletare,
    StimaCostoModello,
    istanze_da_completare,
    renderizza_pagine_istanza,
    stima_costo_chiamate,
)
from sacor.compare import uguali  # noqa: E402
from sacor.invariants import valuta_tutte  # noqa: E402
from sacor.oracle import OracleError  # noqa: E402
from sacor.providers.base import ModelProvider  # noqa: E402
from sacor.providers.errors import ErroreProvider  # noqa: E402
from sacor.providers.prompt import costruisci_prompt  # noqa: E402
from sacor.schema import Schema  # noqa: E402
from sacor.segmentation import Istanza  # noqa: E402

# T4.5/T4.12, C2: se il costo REALE dell'intero giro supera questo tetto, ci
# si ferma. Alzato da $0.50 a $5 per lasciare margine a test piu' ampi
# (es. claude-opus-5, o corpus futuri piu' grandi) — resta un tetto basso in
# assoluto, monitorato ad ogni giro (costo reale vs stimato riportato sempre).
LIMITE_SPESA_USD = 5.0


def _provider_per_modello(modello: str) -> ModelProvider:
    # Dispatch per prefisso: un nuovo modello dello stesso provider non
    # richiede una nuova riga qui, solo una voce in prezzi_modelli.yaml.
    if modello.startswith("claude-"):
        from sacor.providers.anthropic import AnthropicProvider

        return AnthropicProvider(modello)
    if modello.startswith("gpt-"):
        from sacor.providers.openai import OpenAIProvider

        return OpenAIProvider(modello)
    raise ErroreProvider(f"nessun provider noto per il modello '{modello}'")


def _pagine_immagine(istanza: Istanza) -> list[bytes]:
    return [png for png, _larghezza, _altezza in renderizza_pagine_istanza(istanza)]


class TracciatoreSpesa:
    """Stato condiviso tra tutti i modelli del giro: una volta superato il
    limite nessuna chiamata successiva parte, per nessun modello."""

    def __init__(self, limite: float) -> None:
        self.limite = limite
        self.speso = 0.0
        self.fermato = False

    def puo_procedere(self) -> bool:
        return not self.fermato

    def registra(self, costo: float) -> None:
        self.speso += costo
        if self.speso > self.limite:
            self.fermato = True


@dataclass(frozen=True)
class RigaBakeoff:
    modello: str
    accuratezza_campo: float
    accuratezza_documento: float
    costo_totale: float
    costo_per_doc: float
    latenza_p50_secondi: float | None
    inventati: int
    chiamate_fallite: int
    chiamate_saltate: int  # non partite: tetto di spesa gia' raggiunto
    violazioni_invarianti: int = 0  # ADR-045: valutate solo sui campi chiesti
    # in questa chiamata (campi_mancanti) — se un'invariante referenzia anche
    # un campo gia' risolto dal tier 0 (non incluso qui), non e' valutabile:
    # limite noto, non un bug (serve il valore tier0 per calcolarla per intero).


def _valuta_modello(
    modello: str,
    chiamate: list[ChiamataDaCompletare],
    oracle_documenti: Mapping[str, Mapping[str, str | None]],
    tracciatore: TracciatoreSpesa,
    schema: Schema,
) -> RigaBakeoff:
    try:
        provider = _provider_per_modello(modello)
    except ErroreProvider as exc:
        print(f"  [{modello}] provider non disponibile: {exc}", file=sys.stderr)
        return RigaBakeoff(modello, 0.0, 0.0, 0.0, 0.0, None, 0, len(chiamate), 0)

    campi_totali = campi_corretti = inventati = 0
    documenti_corretti = 0
    chiamate_fallite = chiamate_saltate = 0
    costo_totale = 0.0
    violazioni_invarianti = 0
    latenze: list[float] = []

    for chiamata in chiamate:
        if not tracciatore.puo_procedere():
            chiamate_saltate += 1
            continue

        prompt = costruisci_prompt(chiamata.campi_mancanti)
        pagine = _pagine_immagine(chiamata.istanza)
        try:
            risposta = provider.estrai(pagine, prompt, chiamata.campi_mancanti)
        except ErroreProvider as exc:
            chiamate_fallite += 1
            print(f"  [{modello}] chiamata fallita: {exc}", file=sys.stderr)
            continue

        costo_totale += risposta.costo_stimato
        tracciatore.registra(risposta.costo_stimato)
        if tracciatore.fermato:
            print(
                f"  [{modello}] TETTO DI SPESA (${tracciatore.limite:.2f}) RAGGIUNTO "
                f"— speso ${tracciatore.speso:.4f}, nessuna altra chiamata partira'.",
                file=sys.stderr,
            )
        latenze.append(risposta.latenza_secondi)

        # ADR-045: valutata solo sui campi chiesti in QUESTA chiamata (vedi
        # commento su RigaBakeoff.violazioni_invarianti per il limite noto).
        violazioni_invarianti += len(valuta_tutte(schema, risposta.valori))

        attesi = oracle_documenti[chiamata.chiave_oracle]
        documento_corretto = True
        for campo in chiamata.campi_mancanti:
            valore = risposta.valori.get(campo.nome)
            campi_totali += 1
            if uguali(attesi.get(campo.nome), valore, campo.tipo):
                campi_corretti += 1
            else:
                documento_corretto = False
                if valore is not None:
                    inventati += 1  # non-None ma sbagliato: il modello ha indovinato
        if documento_corretto:
            documenti_corretti += 1

    return RigaBakeoff(
        modello=modello,
        accuratezza_campo=campi_corretti / campi_totali if campi_totali else 0.0,
        accuratezza_documento=documenti_corretti / len(chiamate) if chiamate else 0.0,
        costo_totale=costo_totale,
        costo_per_doc=costo_totale / len(chiamate) if chiamate else 0.0,
        latenza_p50_secondi=statistics.median(latenze) if latenze else None,
        inventati=inventati,
        chiamate_fallite=chiamate_fallite,
        chiamate_saltate=chiamate_saltate,
        violazioni_invarianti=violazioni_invarianti,
    )


@dataclass(frozen=True)
class RisultatoBakeoff:
    righe: list[RigaBakeoff]
    speso_totale: float
    tetto_raggiunto: bool
    stima_per_modello: dict[str, StimaCostoModello]


def esegui_bakeoff(
    modelli: tuple[str, ...] = MODELLI_BAKEOFF, limite_spesa: float = LIMITE_SPESA_USD
) -> RisultatoBakeoff:
    esito = istanze_da_completare()
    if esito is None:
        raise RuntimeError("corpus non ancora presente: manca corpus/attesi.json")
    schema, oracle, chiamate, file_disallineati = esito

    # Stessa stima di --dry-run, sulle stesse chiamate: per confrontare costo
    # reale vs stimato dopo il giro (C2). T4.13 (BASSA, trovato in review):
    # riusa le chiamate appena calcolate sopra invece di richiamare
    # istanze_da_completare() una seconda volta (che rifaceva triage,
    # segmentazione e rendering PNG di ogni pagina di ogni file da capo).
    stima = stima_costo_chiamate(schema, chiamate, file_disallineati, modelli=modelli)
    stima_per_modello = stima.costo_per_modello

    tracciatore = TracciatoreSpesa(limite_spesa)
    righe = [_valuta_modello(m, chiamate, oracle.documenti, tracciatore, schema) for m in modelli]

    return RisultatoBakeoff(
        righe=righe,
        speso_totale=tracciatore.speso,
        tetto_raggiunto=tracciatore.fermato,
        stima_per_modello=stima_per_modello,
    )


def formatta_tabella(righe: list[RigaBakeoff]) -> str:
    intestazione = (
        f"{'modello':<20}{'acc. campo':>12}{'acc. doc':>10}"
        f"{'costo/doc':>12}{'lat. p50':>10}{'inventati':>11}{'fallite':>9}{'saltate':>9}"
        f"{'inv. viol.':>11}"
    )
    linee = [intestazione, "-" * len(intestazione)]
    for r in righe:
        lat = f"{r.latenza_p50_secondi:.2f}s" if r.latenza_p50_secondi is not None else "n/d"
        linee.append(
            f"{r.modello:<20}{r.accuratezza_campo * 100:>11.1f}%"
            f"{r.accuratezza_documento * 100:>9.1f}%"
            f"{r.costo_per_doc:>12.4f}{lat:>10}{r.inventati:>11}"
            f"{r.chiamate_fallite:>9}{r.chiamate_saltate:>9}{r.violazioni_invarianti:>11}"
        )
    return "\n".join(linee)


def formatta_confronto_costo(righe: list[RigaBakeoff], stima: dict[str, StimaCostoModello]) -> str:
    linee = ["", "Costo reale vs stimato (per modello, giro completo):"]
    for r in righe:
        s = stima.get(r.modello)
        stimato = f"${s.costo_stimato:.4f}" if s is not None else "n/d"
        linee.append(f"  {r.modello:<20} reale ${r.costo_totale:.4f}  |  stimato {stimato}")
    return "\n".join(linee)


def main() -> int:
    print(
        "sacor bake-off (T4.4/T4.5) — cache disattivata, chiamate reali.\n"
        "Accuratezza calcolata SOLO sui campi chiesti al tier 1 (quelli "
        f"che il tier 0 ha lasciato None), non sull'intera pipeline.\n"
        f"Tetto di spesa per il giro completo: ${LIMITE_SPESA_USD:.2f}.\n"
    )
    try:
        risultato = esegui_bakeoff()
    except RuntimeError as exc:
        print(f"errore: {exc}", file=sys.stderr)
        return 1
    except OracleError as exc:
        # T4.13: uguali() ora distingue oracle malformato da estrattore
        # sbagliato (vedi sacor.compare) — un oracle rotto qui interrompe il
        # giro, non lo maschera da modello che ha sbagliato tutto.
        print(f"errore oracle: {exc}", file=sys.stderr)
        return 1

    print(formatta_tabella(risultato.righe))
    print(formatta_confronto_costo(risultato.righe, risultato.stima_per_modello))
    print(f"\nSpeso reale totale: ${risultato.speso_totale:.4f}")
    if risultato.tetto_raggiunto:
        print(
            f"TETTO DI SPESA (${LIMITE_SPESA_USD:.2f}) RAGGIUNTO — giro interrotto in anticipo. "
            "Vedi 'saltate' nella tabella per le chiamate non fatte.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
