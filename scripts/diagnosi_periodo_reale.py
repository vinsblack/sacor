"""Diagnosi puntuale periodo_da/periodo_a sul corpus reale (seguito di
scripts/misura_reale_combinato.py): il fix di 'descrizione' nello schema
non ha spostato l'accuratezza (13.3%/20.3% invariati) — prima di provare
un altro fix alla cieca, questo script mostra PER DOCUMENTO tier0, la
risposta di tier1 (opus) e l'atteso, per capire se il modello si astiene
(null) o sbaglia il valore. Sono due problemi diversi da risolvere in modo
diverso (vedi commento in fondo all'output).

Stessa disciplina di scripts/bakeoff.py: cache disattivata, tetto di
spesa, costo reale riportato. Modello fisso claude-opus-5 (ADR-049)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.run import SCHEMA_PATH, istanze_da_completare  # noqa: E402
from sacor.extractor import TierZeroExtractor  # noqa: E402
from sacor.pipeline import MODELLO_TIER1  # noqa: E402
from sacor.providers.anthropic import AnthropicProvider  # noqa: E402
from sacor.providers.errors import ErroreProvider  # noqa: E402
from sacor.providers.prompt import costruisci_prompt  # noqa: E402
from sacor.render import renderizza_pagine_istanza  # noqa: E402

ORACLE_PATH = REPO_ROOT / "corpus" / "reale" / "attesi.json"
CORPUS_RAW = REPO_ROOT / "corpus" / "reale" / "raw"
METADATA_PATH = REPO_ROOT / "corpus" / "reale" / "metadata.json"

LIMITE_SPESA_USD = 5.0
CAMPI_SOTTO_ESAME = ("periodo_da", "periodo_a")


def main() -> int:
    if not CORPUS_RAW.is_dir():
        print("PDF reali non presenti in locale (corpus/reale/raw/, mai nel repo)")
        return 0

    esito = istanze_da_completare(SCHEMA_PATH, ORACLE_PATH, CORPUS_RAW, METADATA_PATH)
    if esito is None:
        print("corpus reale non presente: manca corpus/reale/attesi.json")
        return 0
    schema, oracle, chiamate, _file_disallineati = esito

    try:
        provider = AnthropicProvider(MODELLO_TIER1)
    except ErroreProvider as exc:
        print(f"errore provider: {exc}", file=sys.stderr)
        return 1

    tier0 = TierZeroExtractor()
    speso = 0.0
    astensioni = 0  # tier1 ha risposto null
    sbagliati = 0  # tier1 (o tier0) ha risposto un valore diverso dall'atteso
    corretti = 0

    print(
        f"diagnosi periodo_da/periodo_a SU CORPUS REALE — {len(chiamate)} documenti, "
        f"modello {MODELLO_TIER1}, chiamate reali.\n"
        f"Tetto di spesa: ${LIMITE_SPESA_USD:.2f}.\n"
    )

    for chiamata in chiamate:
        valori_tier0 = tier0.extract(chiamata.istanza, schema)
        attesi = oracle.documenti[chiamata.chiave_oracle]

        valori_tier1: dict[str, str | None] = {}
        if speso <= LIMITE_SPESA_USD:
            try:
                pagine = [png for png, _l, _a in renderizza_pagine_istanza(chiamata.istanza)]
                prompt = costruisci_prompt(chiamata.campi_mancanti)
                risposta = provider.estrai(pagine, prompt, chiamata.campi_mancanti)
                speso += risposta.costo_stimato
                valori_tier1 = risposta.valori
            except ErroreProvider as exc:
                print(f"  [{chiamata.chiave_oracle}] chiamata fallita: {exc}", file=sys.stderr)
        else:
            print(f"  [{chiamata.chiave_oracle}] SALTATO: tetto di spesa raggiunto")

        print(f"\n=== {chiamata.chiave_oracle} ===")
        for nome_campo in CAMPI_SOTTO_ESAME:
            valore_finale = valori_tier0.get(nome_campo) or valori_tier1.get(nome_campo)
            atteso = attesi.get(nome_campo)
            fonte = "tier0" if valori_tier0.get(nome_campo) is not None else "tier1"

            if valore_finale == atteso:
                esito_diagnosi = "CORRETTO"
                corretti += 1
            elif valore_finale is None:
                esito_diagnosi = "ASTENUTO (null)"
                astensioni += 1
            else:
                esito_diagnosi = "SBAGLIATO"
                sbagliati += 1

            print(
                f"  {nome_campo:<12} atteso={atteso!r:<14} "
                f"letto={valore_finale!r:<14} ({fonte}) -> {esito_diagnosi}"
            )

    totale = astensioni + sbagliati + corretti
    print(f"\n{'=' * 60}")
    print(f"Totale valutati: {totale} (su {len(chiamate)} documenti x 2 campi)")
    print(f"Corretti:  {corretti}")
    print(f"Astenuti (null, il modello non ha indovinato invece di sbagliare): {astensioni}")
    print(f"Sbagliati (valore letto ma diverso dall'atteso): {sbagliati}")
    print(f"\nSpeso reale: ${speso:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
