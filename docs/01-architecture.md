# 01 — Architettura

**Aggiornato 12-08 (ADR-056→060)** — riscritto per intero: la versione
precedente descriveva un disegno (due provider sempre, escalation
tier1→tier2, layer "Ingest" con cache) mai costruito così. Quello che
segue riflette il codice reale (`src/sacor/`), non l'intenzione
iniziale.

## Principio

Il codice non sa cosa sia una bolletta. Sa solo eseguire uno **schema**
(`sacor.schema.Schema`, YAML).

Nuovo tipo di documento = nuovo YAML, non nuovo codice (ADR-017). Gas e
CTE (`bolletta_gas_it.yaml`, `cte_it.yaml`) l'hanno confermato: zero
righe di logica dominio-specifica aggiunte per costruirli.

## Pipeline

```
Classificazione   luce / gas / CTE / sconosciuto        [deterministico]
Triage            pagina digitale / ibrida / scansione  [deterministico]
Segmentazione     un file può contenere N documenti     [deterministico]
Tier0             regex dichiarate nello schema         [deterministico]
Derivazione       aritmetica da campi noti (ADR-051)     [deterministico]
Tier1 (opt-in)    completa i campi mancanti              [AI]
Derivazione       di nuovo — tier1 può sbloccarne altri  [deterministico]
Invarianti        valuta tutte, non solo le fallite       [deterministico]
Evidenza          per campo: origine/repair/derivazione/  [deterministico]
                  invarianti; per documento: triage
Confidenza        funzione pura di Evidenza (ADR-059)     [deterministico]
Gate              funzione pura di Evidenza (ADR-060)     [deterministico]
Output            JSON — Result Contract v1 (ADR-056)
```

L'AI (tier1) è **uno solo dei dieci passi**, opt-in esplicito
(`--tier1`), mai automatico — una chiamata reale a pagamento. Il resto
è codice deterministico, verificabile, gratis.

## Note per passo

**Classificazione (`sacor.classifica`) — nessuna AI.** Regex su
segnali universali ("totale da pagare", unità kWh/Smc, "condizioni
economiche") per distinguere luce/gas/CTE prima di scegliere lo
schema — bug reale chiuso da questo passo: una bolletta gas letta con
lo schema luce, nessun avviso (ADR-053).

**Triage (`sacor.triage`) — nessuna AI.** Densità testo con
`pdfplumber`: digitale (text layer affidabile) / ibrida / scansione.

**Tier0 (`sacor.extractor.TierZeroExtractor`) — regex, mai AI.**
Applica `campo.estrazione.pattern` dallo schema al testo delle pagine
digitali dell'istanza. Un pattern assente, non trovato, o non
normalizzabile da Repair (`sacor.repair`) → `None`, mai un valore
indovinato o parziale (ADR T3.2).

**Derivazione (`sacor.invariants.deriva_mancanti_con_provenienza`) —
mai AI.** Un campo mancante con esattamente un'incognita in
un'invariante nota (`differenza_giorni`, `somma_approssimata`) si
deriva aritmeticamente — stessa formula già usata per validare,
applicata al contrario (ADR-051). Gira prima di tier1 (risparmia la
chiamata se basta) e dopo (tier1 può sbloccare una derivazione).

**Tier1 (`sacor.providers.anthropic.AnthropicProvider`) — un solo
provider in produzione.** claude-opus-5, fisso (ADR-049: l'arbitrato
multi-provider misurato sul reale non ha migliorato l'accuratezza
rispetto a opus da solo, non vale il doppio costo). Vision sulla
pagina renderizzata, non OCR intermedio — l'OCR distrugge il layout,
e in una bolletta il layout è informazione. Prompt caching
(`cache_control`, ADR-054) sulla parte statica del prompt.

**Invarianti (`sacor.invariants.valuta_tutte_con_esito`) — mai AI.**
Somme, IVA, giorni, ordine date: solo Python. Valuta OGNI invariante
dello schema, non solo le fallite — Evidenza (sotto) ha bisogno anche
delle passate.

**Evidenza (`sacor.evidence`) — il contratto pubblico.** Ogni campo
porta `origine` (tier0/tier1/derivato), `repair` (trasformazioni
subite), `derivazione` (invariante e campi usati, se derivato),
`invarianti` (passate/fallite/dettaglio). A livello documento:
classificazione + triage per pagina. Descrive, non decide — nessun
`if` dentro (ADR-058, Evidenza è monotona: un layer aggiunge, mai
corregge quanto scritto da un layer precedente).

**Confidenza (`sacor.evidence.confidenza_da_evidenza`) — funzione
pura.** `null` se il valore è assente; `bassa` se il campo è coinvolto
in un'invariante fallita, a prescindere dall'origine; `media` se
`tier1` o `derivato`; `alta` altrimenti (ADR-059).

**Gate (`sacor.gate.gate`) — funzione pura, il componente più
"stupido" del progetto per costruzione.** Legge solo `RisultatoCampo`
(valore + evidenza + confidenza + obbligatorio) — non importa Schema,
pipeline, extractor, provider (verificato via test AST, non solo
dichiarato, ADR-060). `pass` / `warning` / `reject`.

## Schema YAML

```yaml
# schemas/bolletta_luce_it.yaml
schema_version: 1
documento: bolletta_luce_it

campi:
  - nome: pod
    tipo: string
    obbligatorio: true      # implica reject se assente
    estrazione:
      tipo: regex
      pattern: 'IT\d{3}E\d{8}'
  - nome: kwh_totale
    tipo: decimal
    obbligatorio: false

invarianti:
  - id: somma_fasce
    tipo: somma_approssimata
    addendi: [kwh_f1, kwh_f2, kwh_f3]
    totale: kwh_totale
    tolleranza_relativa: 0.005
    severita: warning
```

**Le invarianti sono dichiarative, mai espressioni da parsare.** Ogni
`tipo` corrisponde a una funzione Python registrata in
`sacor.invariants`. Una stringa tipo `somma(a,b) ~= c` obbligherebbe a
scrivere un parser di espressioni: debito tecnico immediato e schema
non estendibile.

**Ogni invariante dichiara la propria `severita`** (`warning` o
`reject`) — il Gate non ha altro modo per decidere.

**Una sola fonte di verità per l'obbligatorietà:** `obbligatorio: true`
sul campo. Nessuna lista `reject_se` separata che possa divergere.

**`descrizione` (opzionale)** guida il tier1 su ambiguità di dominio
(es. quale "totale" tra due sulla stessa pagina) — il prompt builder
resta generico, la conoscenza di dominio vive nello schema, mai nel
codice (ADR-017/043).

## Layout repo

```
src/sacor/          core agnostico (17 moduli, vedi sopra per i principali)
src/sacor/schemas/  YAML per tipo di documento (luce, gas, CTE)
src/sacor/providers/ adattatori AI (Anthropic, OpenAI, prezzi)
corpus/reale/        bollette reali con consenso, mai pubblicate (ADR-042)
corpus/cte/           CTE pubbliche, esempi committati + dataset locale
corpus/synth/         corpus sintetico, generato, committato
docs/                 ADR, north-star, roadmap, report
eval/                 harness di misura, guidato da oracle
scripts/              strumenti standalone (bakeoff, verification campaign, ...)
tests/                pytest, nessuna chiamata di rete reale
```
