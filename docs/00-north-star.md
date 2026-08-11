# 00 — North Star

**sacor** — *The Open Document Extraction Engine*

## Cos'è

Motore di estrazione dati da documenti semi-strutturati, dominio-agnostico,
con **accuratezza misurata e dimostrabile**.

Primo e unico modulo: bollette luce/gas italiane (`sacor-bollette`).

**Visione (ADR-047, 11-08)**: sacor non è, alla fine, un estrattore di
documenti — è lo strato di fiducia mancante tra i modelli AI e il software
gestionale. Il prodotto non è il parser, è la capacità di trasformare un
documento in dati verificati con un livello di fiducia misurabile. Le
bollette luce sono il primo campo di prova per dimostrare questo, non il
mercato finale.

### Le tre fasi

1. **Open source** — credibilità tecnica, benchmark pubblici, community di
   sviluppatori. Fase attuale, subordinata a G1/G2/G3 sotto.
2. **Ecosistema** — pacchetto Python, nodo n8n, API, plugin per i
   principali workflow documentali (coerente con "Distribuzione" sotto).
3. **Business** — piattaforma enterprise: API gestite, supporto,
   monitoraggio, self-hosted, strumenti di validazione avanzata. Si
   costruisce quando la fase 2 ha già utenti reali, non prima (ADR-004).

Posizionamento: non si compete con convertitori PDF/OCR generici (mercato
affollato, il prezzo è il fattore competitivo). Sacor si posiziona dove un
errore ha un costo economico misurabile — energia, assicurazioni, banche,
logistica, sanità, amministrazione. Bollette luce è il primo di questi
verticali, non l'unico previsto.

## Il differenziatore

Non è l'AI. È la **cultura della misurazione**.

In un mercato dove tutti dichiarano "99%" e nessuno mostra il breakdown, sacor
pubblica corpus, oracle e accuratezza per campo, in CI, a ogni commit.

Corollario di prodotto: un sistema che dice "non lo so, guardalo tu" sul 5% dei
casi vale più di uno che sbaglia in silenzio sul 3%. Il gate è una feature.

## Cosa NON è

- Non è un convertitore PDF. Mercato maturo e dominato: perso in partenza.
- Non è una piattaforma di Document Intelligence a 15 fasi.
- Non è un SaaS. Il SaaS si costruisce **quando qualcuno lo chiede**.
- Non è VERO né un suo derivato.

## Classe di documenti target

Un documento è adatto a sacor se ha **tutte e quattro** queste proprietà:

1. Semi-strutturato — layout ricorrente ma non fisso
2. **Aritmeticamente verificabile** — numeri che devono tornare tra loro
3. Ripetitivo e ad alto volume
4. Con un costo dell'errore misurabile in denaro

La proprietà 2 è il vincolo che distingue sacor. Senza invarianti interne lo
strato di arbitrato non ha nulla su cui lavorare e il vantaggio evapora.

**Fuori scope:** contratti, referti, atti (nessuna invariante aritmetica);
fatture B2B italiane (già XML via SDI dal 2019); CTE (mercato ~50 aziende e
zona IP di Massimo).

## Distribuzione

Il canale esiste prima del codice. Non è la SEO.

- Pacchetto PyPI + nodo n8n community, entrambi gratuiti e open source
- Il nodo è il volantino; l'eventuale API è il prodotto
- Un post tecnico sugli errori silenziosi nell'estrazione documentale italiana

## Gate e criteri di stop

| | Criterio | Se fallisce |
|---|---|---|
| **G1** | Nodo/pacchetto pubblicato entro 60 giorni | Rivedere lo scope, non la data |
| **G2** | Nessun 2° tipo di documento prima di un numero pubblicato + 1 utente esterno | — |
| **G3 (6 mesi)** | Numero pubblicato e ≥1 utente esterno | Il canale è sbagliato, non il prodotto |

Se a 6 mesi nessuno l'ha usato: il risultato è comunque il progetto tecnico più
credibile del profilo GitHub. Non è un fallimento, è un esito diverso.

**Rivisto (ADR-048, 11-08, stessa sessione di ADR-047 — revoca la nota
precedente qui, stesso schema di ADR-031 che revoca ADR-029)**: G1 NON
aspetta più accuratezza alta. I 15 documenti reali hanno già assolto il
loro scopo (misurare il gap, invalidare l'ipotesi tier0, ADR-046) —
continuare a ottimizzare sugli stessi produce overfitting, non segnale
nuovo. Il collo di bottiglia è la distribuzione, non l'algoritmo: si
pubblica un motore onesto (numeri reali attuali dichiarati, non
nascosti) e si lascia che l'adozione porti nuovi casi reali. Il corpus
è conseguenza della Fase 2, non prerequisito della Fase 1.
