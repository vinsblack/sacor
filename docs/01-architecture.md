# 01 — Architettura

## Principio

Il codice non sa cosa sia una bolletta. Sa solo eseguire uno **schema**.

Nuovo tipo di documento = nuovo YAML, non nuovo sprint.

## Pipeline a strati

```
Ingest      hash SHA-256, dedup, cache            [deterministico]
Triage      text-layer o scansione? rotazione?    [deterministico]
Extract     tier 1 economico -> gate -> tier 2    [AI]
Repair      numeri IT, date, normalizzazioni      [deterministico]
Arbitrate   confronto fonti, tolleranze           [deterministico]
Gate        pass / warning / reject               [deterministico]
Output      JSON conforme a schema + confidence per campo
```

L'AI è **uno solo dei sette strati**. Il valore sta negli altri sei.

## Note per strato

**Triage — nessuna AI.** Densità testo con `pdfplumber`, orientamento via OSD.
Circa il 30% dei fallimenti si risolve qui a costo zero.

**Extract — VLM sull'immagine di pagina**, non OCR → testo → LLM. L'OCR
intermedio distrugge il layout, e in una bolletta il layout *è* informazione.
L'OCR resta come segnale di supporto, non come input primario.

**Escalation a due stadi.** Tier 1 = modello veloce ed economico (risolve
l'80-90%). Tier 2 = modello di punta, solo su fallimento del gate.

> **Metrica che decide l'economia del progetto: il tasso di escalation.**
> Sopra il 20% il margine per documento evapora. Va misurato ogni giorno.

**Due provider, sempre.** Interfaccia astratta (`Extractor` protocol), mai
chiamate dirette al SDK. Serve per continuità di servizio e potere negoziale.
Terza opzione: modello open-weights self-hosted — non per risparmiare, ma per
vendere ("i documenti non escono dalla vostra infrastruttura").

**Repair e Arbitrate — mai AI.** Somme, IVA, giorni, riconciliazioni: Python.
Il modello estrae, il codice verifica.

## Schema YAML

```yaml
# schemas/bolletta_luce_it.yaml
campi:
  - nome: pod
    tipo: string
    obbligatorio: true
  - nome: kwh_totale
    tipo: decimal
invarianti:
  - somma(kwh_f1, kwh_f2, kwh_f3) ~= kwh_totale  tolleranza: 0.5%
  - giorni == (data_a - data_da) + 1
gate:
  reject_se: [pod, periodo_da, periodo_a]
```

## Layout repo

```
src/sacor/          core agnostico
schemas/            YAML per tipo di documento
corpus/             documenti + attesi.json (oracle)
eval/               harness + report per campo
scripts/state.py    genera docs/03-current-state.md
```
