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
- Non è un derivato di un altro progetto privato dell'autore.

## Classe di documenti target

Un documento è adatto a sacor se ha **tutte e quattro** queste proprietà:

1. Semi-strutturato — layout ricorrente ma non fisso
2. **Aritmeticamente verificabile** — numeri che devono tornare tra loro
3. Ripetitivo e ad alto volume
4. Con un costo dell'errore misurabile in denaro

La proprietà 2 è il vincolo che distingue sacor. Senza invarianti interne lo
strato di arbitrato non ha nulla su cui lavorare e il vantaggio evapora.

**Fuori scope:** contratti, referti, atti (nessuna invariante
aritmetica); fatture B2B italiane (già XML via SDI dal 2019).

**CTE (12-08): dentro lo scope, non più fuori.** La nota precedente
("zona coperta da un impegno commerciale") non vale più come vincolo —
CTE è ora uno schema sacor costruito e verificato (39 documenti reali,
`docs/verification-report-v1.md`), coerente con la proprietà 2
(condizioni economiche/prezzi sono verificabili tra loro).

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

## Mandato attuale (12-08, lettera dell'utente — vale come vincolo,
non solo come nota)

Il corpus dei 15 documenti ha già dato la risposta che doveva dare:
l'ipotesi sintetica era sbagliata, il tier0 non generalizza come
previsto, alcune scelte architetturali erano giuste, altre sono state
riviste. Non sono sconfitte — sono il motivo per cui esiste un
processo di misura. **Continuare a ottimizzare il motore sugli stessi
15 documenti produce sempre meno informazione e sempre più rischio di
overfitting.** Il collo di bottiglia oggi non è l'algoritmo, è
l'assenza di nuovi utilizzatori — nuovi documenti reali arriveranno
solo quando altre persone useranno sacor. Il corpus non è più il
prerequisito della pubblicazione: è una sua conseguenza.

**Cambia il criterio di successo.** Non più "far salire un numero".
Da ora: permettere a uno sviluppatore esterno di installare sacor,
provarlo su un proprio documento, e capire immediatamente cosa
funziona e cosa no.

**Il vero prodotto non è la pipeline, non sono le invarianti, non sono
le regex — è la fiducia.** sacor deve essere riconosciuto come il
motore che permette di usare modelli AI in processi dove un errore ha
un costo economico reale. Se un domani i modelli miglioreranno del
30%, sacor continuerà ad avere valore perché il suo compito non è
leggere un documento meglio di un modello — è verificare, misurare e
qualificare il risultato. Questo non si copia leggendo un prompt.

**Priorità della fase attuale, in ordine** (sostituisce qualunque
lettura che tratti ancora il corpus come lavoro da chiudere):

1. Pubblicazione del pacchetto
2. Documentazione eccellente
3. Nodo n8n
4. API stabile
5. Primi utilizzatori esterni
6. Raccolta di nuovi casi reali provenienti dall'utilizzo — non prima

Il progetto non sarà giudicato dal numero di regole nello schema YAML
o dalla complessità della pipeline, ma dalla capacità di diventare uno
strumento che altri sviluppatori scelgono di integrare perché si
fidano dei suoi risultati. La fiducia non nasce dalla promessa di
essere perfetti — nasce dalla capacità di dichiarare con precisione
ciò che il sistema sa, ciò che non sa, e di migliorare continuamente
sulla base di dati reali (non di dati raccolti in laboratorio sugli
stessi 15 documenti).
