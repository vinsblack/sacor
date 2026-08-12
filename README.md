# sacor

**The Open Document Extraction Engine.**

Un framework di affidabilità documentale: estrae dati da documenti
semi-strutturati e dichiara quanto si può fidare di ogni campo.

Primo schema implementato: bollette luce e gas italiane.

## Quickstart

Richiede Python 3.12+. Non ancora su PyPI (vedi `docs/02-decisions.md`,
ADR-048) — si installa da sorgente:

```bash
git clone https://github.com/vinsblack/sacor
cd sacor
pip install .
```

Estrai un PDF:

```bash
sacor extract bolletta.pdf
```

Output — JSON con un oggetto per istanza (una bolletta può contenerne più
di una), valori estratti, confidenza per campo, esito ed eventuali
violazioni:

```json
[
  {
    "istanza_id": "demo",
    "valori": {
      "pod": "IT121E66496171",
      "fornitore": "Alfa Energia",
      "periodo_da": "2025-03-19",
      "periodo_a": "2025-05-13",
      "giorni": "56",
      "kwh_totale": "174.74",
      "kwh_f1": "174.74",
      "kwh_f2": "0.00",
      "kwh_f3": "0.00",
      "importo_totale": "82.25"
    },
    "confidenza": {
      "pod": "alta", "fornitore": "alta", "periodo_da": "alta",
      "periodo_a": "alta", "giorni": "alta", "kwh_totale": "alta",
      "kwh_f1": "alta", "kwh_f2": "alta", "kwh_f3": "alta",
      "importo_totale": "alta"
    },
    "esito": "pass",
    "motivo": null,
    "violazioni": [],
    "costo_tier1_usd": 0.0,
    "tier1_errore": null
  }
]
```

`confidenza` per campo: `alta` (tier 0, regex deterministica), `media`
(tier 1, AI), `bassa` (il campo è coinvolto in un'invariante violata —
es. una somma che non torna), `null` se il campo non ha valore. `esito` è
`pass` / `warning` / `reject`. Exit code: `0` se tutte le istanze passano,
`1` se almeno una è `reject`, `2` per errori (file o schema non trovato).

Tier 0 (regex, zero costo, sempre disponibile) gira sempre. Con
`--tier1` completa i campi che il tier 0 lascia `None` chiamando
claude-opus-5 (ADR-049) — opt-in esplicito, mai automatico: chiamata
reale a pagamento, richiede `ANTHROPIC_API_KEY`. Un errore del provider
(chiave mancante, rate limit) non fa fallire l'estrazione: si vede in
`tier1_errore`, il resto del risultato resta utilizzabile.

Accuratezza reale attuale (tier0+tier1+riparazione aritmetica, corpus
reale, 15 doc): **68.7% per campo, 13.3% per documento completo**
(2/15). Campi più deboli: periodo_da/periodo_a 33%, kwh_f1 53%, gli
altri dal 67% al 100%. Vedi `docs/02-decisions.md` (ADR-046/048/050/
051/052) per il dettaglio — pubblicata per intero, non filtrata,
compresi i tentativi di fix falliti.

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
