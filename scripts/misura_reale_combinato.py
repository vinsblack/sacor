"""Accuratezza combinata tier0+tier1 sul corpus reale (ADR-048/049/051):
misura end-to-end di cio' che 'sacor extract --tier1' produce davvero.
scripts/bakeoff_reale.py misura solo i campi CHIESTI a tier1 (i confronti
sono piu' facili, e' un sottoinsieme); scripts/diagnosi_tier0_reale.py
solo tier0. Questo script chiama sacor.pipeline.estrai_file() DAVVERO —
un giro precedente reimplementava tier0+tier1 a mano e non passava mai
dalla derivazione aritmetica (ADR-051), misurando una pipeline diversa da
quella che 'sacor extract --tier1' esegue per un utente vero.

Stessa disciplina di scripts/bakeoff.py: cache sempre disattivata (ogni
chiamata e' reale), tetto di spesa, costo reale riportato sempre. Modello
fisso claude-opus-5 (ADR-049: l'arbitrato misurato sul reale non ha
migliorato l'accuratezza rispetto a opus da solo)."""

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


def main() -> int:
    if not CORPUS_RAW.is_dir():
        print("PDF reali non presenti in locale (corpus/reale/raw/, mai nel repo)")
        return 0

    esito = istanze_da_completare(SCHEMA_PATH, ORACLE_PATH, CORPUS_RAW, METADATA_PATH)
    if esito is None:
        print("corpus reale non presente: manca corpus/reale/attesi.json")
        return 0
    schema, oracle, chiamate, file_disallineati = esito

    # T4.17/ADR-046: escalation reale = 100%, quindi 'chiamate' (istanze con
    # >=1 campo mancante dopo il solo tier0) dovrebbe coprire tutti i
    # documenti valutabili. Se non fosse piu' vero, un doc risolto per
    # intero dal tier0 sparirebbe silenziosamente da questa misura — reso
    # visibile qui, non assunto. (ADR-051 non cambia questo: la derivazione
    # gira DENTRO estrai_file(), 'chiamate' qui serve solo a enumerare i
    # documenti da valutare, non a decidere se tier1 serve davvero.)
    attesi_valutabili = len(oracle.documenti) - file_disallineati
    if len(chiamate) != attesi_valutabili:
        print(
            f"ATTENZIONE: {attesi_valutabili - len(chiamate)} documento/i risolti "
            "per intero dal tier0 (escalation non piu' 100%) — ESCLUSI da questa "
            "misura, che conta solo le istanze con almeno una chiamata tier1.",
            file=sys.stderr,
        )

    try:
        provider = AnthropicProvider(MODELLO_TIER1)
    except ErroreProvider as exc:
        print(f"errore provider: {exc}", file=sys.stderr)
        return 1

    per_campo = {c.nome: {"corretti": 0, "totale": 0} for c in schema.campi}
    documenti_corretti = 0
    speso = 0.0
    chiamate_fallite = 0

    print(
        f"sacor extract --tier1 SU CORPUS REALE — {len(chiamate)} documenti, "
        f"modello {MODELLO_TIER1}, cache disattivata, chiamate reali.\n"
        f"Tetto di spesa: ${LIMITE_SPESA_USD:.2f}.\n"
    )

    for chiamata in chiamate:
        usa_tier1 = speso <= LIMITE_SPESA_USD
        if not usa_tier1:
            print(f"  [{chiamata.chiave_oracle}] tetto raggiunto: solo tier0+derivazione")

        # Un file reale = una sola istanza (nessun multi-fattura nel
        # corpus reale, vedi eval/run_reale.py) — chiamata.istanza.file e'
        # lo stesso PDF che segmentazione+tier0+tier1 rivedono qui identici.
        (risultato,) = estrai_file(
            chiamata.istanza.file, schema, usa_tier1=usa_tier1, provider=provider
        )
        speso += risultato.costo_tier1_usd
        if risultato.tier1_errore:
            chiamate_fallite += 1
            print(
                f"  [{chiamata.chiave_oracle}] tier1: {risultato.tier1_errore}",
                file=sys.stderr,
            )

        attesi = oracle.documenti[chiamata.chiave_oracle]
        documento_corretto = True
        for campo in schema.campi:
            per_campo[campo.nome]["totale"] += 1
            if uguali(attesi.get(campo.nome), risultato.valori.get(campo.nome), campo.tipo):
                per_campo[campo.nome]["corretti"] += 1
            else:
                documento_corretto = False
        if documento_corretto:
            documenti_corretti += 1

    print(f"{'Campo':<16}{'corretto':>10}{'totale':>8}{'%':>8}")
    tot_c = tot_t = 0
    for c in schema.campi:
        s = per_campo[c.nome]
        pct = s["corretti"] / s["totale"] * 100 if s["totale"] else 0.0
        print(f"{c.nome:<16}{s['corretti']:>10}{s['totale']:>8}{pct:>7.1f}%")
        tot_c += s["corretti"]
        tot_t += s["totale"]

    pct_campo = tot_c / tot_t * 100 if tot_t else 0.0
    pct_doc = documenti_corretti / len(chiamate) * 100 if chiamate else 0.0
    print("---")
    print(f"{'TOTALE CAMPI':<16}{tot_c:>10}{tot_t:>8}{pct_campo:>7.1f}%")
    print(f"\nAccuratezza per documento: {documenti_corretti}/{len(chiamate)} ({pct_doc:.1f}%)")
    print(f"File con segmentazione disallineata dall'oracle: {file_disallineati}")
    print(f"Chiamate tier1 fallite: {chiamate_fallite}")
    print(f"Speso reale: ${speso:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
