# sacor

**The Open Document Extraction Engine.**

Un framework di affidabilità documentale: estrae dati da documenti
semi-strutturati e dichiara quanto si può fidare di ogni campo.

Primo schema implementato: bollette luce e gas italiane.

## Perché

La maggior parte degli estrattori dichiara "99% di accuratezza" senza mostrare
come è stato calcolato. sacor pubblica corpus, oracle e accuratezza per singolo
campo, rieseguiti in CI a ogni commit.

Accuratezza corrente: vedi `docs/03-current-state.md`.

E quando non è sicuro, lo dichiara. Ogni campo esce con un livello di
confidenza, ogni documento con un esito `pass` / `warning` / `reject`, ogni
pagina classificata `digitale` / `ibrida` / `scansione`.

Il principio è sempre lo stesso: **dove il segnale è incerto, il sistema lo
dice invece di scegliere in silenzio.** Un sistema che dice "guardalo tu" sul
5% dei casi è più utile di uno che sbaglia in silenzio sul 3%.

## Architettura

Il core è indipendente dal tipo di documento. Il dominio vive negli schemi
YAML — campi, invarianti aritmetiche, criteri di segmentazione — mai nel
codice. Un nuovo tipo di documento è un nuovo schema, non un nuovo sprint.

La pipeline ha sette strati e l'AI è uno solo di essi:

    Ingest      hash, dedup, cache                    deterministico
    Triage      digitale / ibrida / scansione         deterministico
    Extract     tier 1 economico -> gate -> tier 2    AI
    Repair      formati numerici e date italiani      deterministico
    Arbitrate   confronto fonti, tolleranze           deterministico
    Gate        pass / warning / reject               deterministico
    Output      JSON + confidence per campo

Il valore sta negli altri sei. Somme, IVA e riconciliazioni non passano mai da
un modello: il modello estrae, il codice verifica.

Ogni soglia del sistema è misurata prima di essere scelta, e annotata con il
margine osservato — un numero senza margine non è monitorabile nel tempo. Le
decisioni e le misure sono tracciate in `docs/02-decisions.md`.

Dettagli in `docs/01-architecture.md`.

## Stato

Pre-alpha. Non usare in produzione.

## Licenza

Apache-2.0
