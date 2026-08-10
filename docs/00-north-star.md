# 00 — North Star

**sacor** — *The Open Document Extraction Engine*

## Cos'è

Motore di estrazione dati da documenti semi-strutturati, dominio-agnostico,
con **accuratezza misurata e dimostrabile**.

Primo e unico modulo: bollette luce/gas italiane (`sacor-bollette`).

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
