"""Diagnosi puntuale per campo sul corpus reale, PER DOCUMENTO (seguito di
scripts/misura_reale_combinato.py): mostra il risultato finale (dopo
tier0+tier1+derivazione, ADR-051) confrontato con l'atteso, per capire
dove un campo si rompe — astensione (null) o valore sbagliato sono due
problemi diversi da risolvere diversamente. Chiama sacor.pipeline.
estrai_file() davvero — un giro precedente reimplementava tier0+tier1 a
mano, misurando una pipeline diversa da quella vera (ADR-051).

Uso: python scripts/diagnosi_periodo_reale.py [campo ...]
Default: periodo_da periodo_a. Qualunque nome di campo dello schema va
bene (es. kwh_f1) — script generico, non specifico al periodo nonostante
il nome storico del file.

Stessa disciplina di scripts/bakeoff.py: cache disattivata, tetto di
spesa, costo reale riportato. Modello fisso claude-opus-5 (ADR-049)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.run import SCHEMA_PATH, istanze_da_completare  # noqa: E402
from sacor.compare import uguali  # noqa: E402
from sacor.pipeline import MODELLO_TIER1, estrai_file  # noqa: E402
from sacor.providers.anthropic import AnthropicProvider  # noqa: E402
from sacor.providers.errors import ErroreProvider  # noqa: E402

ORACLE_PATH = REPO_ROOT / "corpus" / "reale" / "attesi.json"
CORPUS_RAW = REPO_ROOT / "corpus" / "reale" / "raw"
METADATA_PATH = REPO_ROOT / "corpus" / "reale" / "metadata.json"

LIMITE_SPESA_USD = 5.0
CAMPI_DEFAULT = ("periodo_da", "periodo_a")


def main() -> int:
    campi_sotto_esame = tuple(sys.argv[1:]) or CAMPI_DEFAULT

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

    speso = 0.0
    astensioni = 0
    sbagliati = 0
    corretti = 0

    print(
        f"diagnosi {', '.join(campi_sotto_esame)} SU CORPUS REALE — {len(chiamate)} "
        f"documenti, modello {MODELLO_TIER1}, chiamate reali.\n"
        f"Tetto di spesa: ${LIMITE_SPESA_USD:.2f}.\n"
    )

    for chiamata in chiamate:
        usa_tier1 = speso <= LIMITE_SPESA_USD
        (risultato,) = estrai_file(
            chiamata.istanza.file, schema, usa_tier1=usa_tier1, provider=provider
        )
        speso += risultato.costo_tier1_usd
        if risultato.tier1_errore:
            print(f"  [{chiamata.chiave_oracle}] chiamata fallita: {risultato.tier1_errore}")

        attesi = oracle.documenti[chiamata.chiave_oracle]
        print(f"\n=== {chiamata.chiave_oracle} ===")
        for nome_campo in campi_sotto_esame:
            valore_finale = risultato.valori.get(nome_campo)
            atteso = attesi.get(nome_campo)
            fonte = risultato.confidenza.get(nome_campo)
            campo_schema = schema.campo(nome_campo)
            assert campo_schema is not None, f"campo '{nome_campo}' non nello schema"

            if uguali(atteso, valore_finale, campo_schema.tipo):
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
                f"letto={valore_finale!r:<14} (confidenza={fonte}) -> {esito_diagnosi}"
            )

    totale = astensioni + sbagliati + corretti
    print(f"\n{'=' * 60}")
    print(
        f"Totale valutati: {totale} "
        f"(su {len(chiamate)} documenti x {len(campi_sotto_esame)} campi)"
    )
    print(f"Corretti:  {corretti}")
    print(f"Astenuti (null): {astensioni}")
    print(f"Sbagliati (valore letto ma diverso dall'atteso): {sbagliati}")
    print(f"\nSpeso reale: ${speso:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
