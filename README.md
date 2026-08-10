# sacor

**The Open Document Extraction Engine.**

Estrazione dati da documenti semi-strutturati, con accuratezza misurata e
pubblicata. Primo modulo: bollette luce e gas italiane.

## Perché

La maggior parte degli estrattori dichiara "99% di accuratezza" senza mostrare
come è stato calcolato. sacor pubblica il corpus, l'oracle e l'accuratezza per
singolo campo, rieseguiti in CI a ogni commit.

E quando non è sicuro, lo dichiara: ogni campo esce con un livello di
confidenza, e il documento con un esito `pass` / `warning` / `reject`.

Un sistema che dice "guardalo tu" sul 5% dei casi è più utile di uno che
sbaglia in silenzio sul 3%.

## Stato

Pre-alpha. Non usare in produzione.

Accuratezza corrente: vedi `docs/03-current-state.md`.

## Come funziona

L'AI è uno solo dei sette strati della pipeline. Gli altri sei sono
deterministici: triage, riparazione dei formati italiani, arbitrato aritmetico,
gate di validazione. Il dominio vive negli schemi YAML, non nel codice.

Dettagli in `docs/01-architecture.md`.

## Licenza

Apache-2.0
