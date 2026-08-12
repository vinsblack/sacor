# 05 — Documento tecnico

**Data di riferimento: 12 agosto 2026.** Questo documento descrive sacor per
chi non conosce il progetto: cos'è, perché esiste, come funziona la pipeline
nel dettaglio, cosa è vero oggi e cosa no. È un documento tecnico, non un
materiale di vendita — dove il numero è basso, il numero è scritto. La fonte
di verità resta `docs/02-decisions.md` (log delle decisioni, append-only):
questo documento la riassume e la spiega, non la sostituisce.

## 1. Cos'è sacor

sacor è un motore di estrazione dati da documenti semi-strutturati — oggi
bollette luce, gas e condizioni contrattuali (CTE) italiane — che, per ogni
campo estratto, dichiara quanto ci si può fidare del valore. Non converte PDF
in testo e non è un parser generico: prende un documento, ne cava un insieme
di campi (POD, periodo di fatturazione, kWh, importo dovuto...) e per
ciascuno restituisce un livello di confidenza esplicito, oltre a un esito
complessivo del documento (`pass`/`warning`/`reject`).

La ragione per cui esiste, e non un ennesimo OCR o wrapper attorno a un
modello, è dichiarata in `docs/00-north-star.md` e ribadita in ADR-047: il
prodotto non è il parser, è **lo strato di fiducia che oggi manca tra i
modelli AI e il software gestionale**. Un modello linguistico, chiesto di
leggere un documento, non si astiene spontaneamente quando non è sicuro —
risponde comunque, con sicurezza apparente identica a quando ha ragione
(dimostrato sperimentalmente in ADR-037: davanti a un'immagine illeggibile il
modello ha prodotto 8 valori su 8 campi, zero corretti, zero astensioni).
sacor esiste per intercettare questo comportamento con verifiche
deterministiche che non dipendono dal modello stesso: regex, formule
aritmetiche, invarianti di dominio.

La classe di documenti a cui sacor si applica è vincolata esplicitamente
(`docs/00-north-star.md`): semi-strutturato, ripetitivo, con un costo
dell'errore misurabile in denaro, e soprattutto **aritmeticamente
verificabile** — numeri che devono tornare tra loro (fasce che sommano al
totale, giorni che derivano dalle date, importi che non possono essere
negativi). Senza questa proprietà lo strato di verifica non ha nulla su cui
lavorare, e il vantaggio del progetto sparisce. Fuori scope per design:
contratti e referti (nessuna invariante aritmetica), fatture B2B italiane
(già strutturate via XML/SDI dal 2019).

## 2. La visione, in tre fasi

ADR-047 fissa tre fasi:

1. **Open source** — credibilità tecnica, benchmark pubblici, community di
   sviluppatori. Fase in cui il progetto si trova oggi, 12 agosto 2026.
2. **Ecosistema** — pacchetto Python su PyPI, nodo n8n community, API,
   plugin per i principali workflow documentali. Il nodo n8n è pensato come
   "volantino": gratuito, la sua funzione è far conoscere il motore, non
   generare ricavo diretto.
3. **Business** — piattaforma enterprise (API gestite, supporto, monitoraggio,
   self-hosted, validazione avanzata). Si costruisce solo quando la fase 2 ha
   già utenti reali, non prima (ADR-004: niente billing, chiavi API o
   hosting prima che qualcuno abbia usato il motore).

**Dove si trova oggi, onestamente**: fase 1, e dentro la fase 1 ancora al suo
inizio. Il repository esiste su `github.com/vinsblack/sacor` (verificato nel
`pyproject.toml`, `Homepage`), il pacchetto **non è ancora su PyPI**
(README, ADR-048), non esiste un nodo n8n, non esiste un utilizzatore
esterno noto. Il criterio di stop dichiarato in `docs/00-north-star.md` è a
6 mesi: pacchetto pubblicato + almeno un utente esterno (G3). Se a 6 mesi
nessuno l'ha usato, il progetto lo dichiara esplicitamente non un fallimento
ma "un esito diverso" — resta comunque il lavoro tecnico più credibile del
profilo, per via della disciplina di misura.

Un dettaglio di metodo rilevante: il gate G1 (pubblicazione) era stato
originariamente subordinato ad "accuratezza per campo alta su tutto lo
schema" (ADR-046, poi riconfermato in ADR-047), e nella stessa sessione
**revocato** (ADR-048): i 15 documenti reali avevano già assolto il loro
scopo di misura, continuare a ottimizzare su di essi produceva overfitting,
non segnale nuovo. Si è deciso di pubblicare un motore onesto — con i numeri
reali attuali dichiarati, non nascosti — invece di aspettare un numero che
forse non sarebbe mai arrivato. Il collo di bottiglia, si è concluso, non è
più l'algoritmo: è la distribuzione.

## 3. Il principio architetturale centrale

**Mai indovinare. Dichiarare l'incertezza invece di nasconderla.** Non è uno
slogan isolato in un README: attraversa ogni singolo strato del codice, ed è
tracciabile riga per riga.

- **Tier0** (`src/sacor/extractor.py:105-113`): se una regex non trova un
  match univoco, il campo resta `None`. Se lo stesso pattern trova valori
  *diversi* in punti diversi del documento (es. un totale di un mese
  precedente allegato prima di quello vero), il valore non viene scelto a
  caso tra i candidati — resta `None` (`_valore_grezzo`, riga 48-56).
- **Repair** (`src/sacor/repair.py:36-71`): il numero `"1.234"` (un punto,
  esattamente tre cifre dopo) è strutturalmente ambiguo tra "1234" (migliaia)
  e un decimale a tre cifre — nessun contesto per distinguerli, quindi
  rifiutato con `None` invece di indovinare la lettura più plausibile.
- **Triage** (`src/sacor/triage.py:19-26`): una pagina non è forzata in
  "digitale" o "scansione". Esiste un terzo stato, `IBRIDA` (ADR-022), per
  quando il segnale stesso è incerto — la banda 0,15–0,85 di copertura
  immagine.
- **Segmentazione** (`src/sacor/segmentation.py:29-35`): oltre a `CERTA`
  esiste `PRESUNTA` (il pattern non è mai stato trovato, ma le pagine erano
  leggibili) e `NON_DETERMINABILE` (almeno una pagina non è leggibile) —
  quest'ultima si propaga come `warning`, mai come `pass` silenzioso
  (ADR-024).
- **Tier1/prompt** (`src/sacor/providers/prompt.py:34-38`): l'istruzione
  esplicita al modello è "se un valore non è presente o non è leggibile, il
  suo valore deve essere `null`. Non indovinare, non stimare, non dedurre".
- **Parsing della risposta** (`src/sacor/providers/parsing.py:21-32`): un
  JSON malformato o non parsabile produce tutti i campi `None`, mai un
  tentativo di recuperare frammenti — "sarebbe indovinare" (commento nel
  codice).
- **Invarianti/gate**: un campo coinvolto in un'invariante violata riceve
  confidenza `bassa` a prescindere da dove viene (`src/sacor/pipeline.py:79-102`)
  — il disaccordo tra campi è un segnale di primo livello, non un dettaglio.

Il corollario di prodotto, ripetuto identico in `00-north-star.md` e in
ADR-047: *"un sistema che dice 'non lo so, guardalo tu' sul 5% dei casi vale
più di uno che sbaglia in silenzio sul 3%."* Il gate è una feature, non un
compromesso.

## 4. La pipeline, passo per passo

L'orchestrazione end-to-end vive in `src/sacor/pipeline.py::estrai_file()`
(righe 133-201), il punto d'ingresso usato dalla CLI. La sequenza:

### 4.1 Classificazione documento (ADR-053, novità di oggi)

Prima ancora di scegliere uno schema, `src/sacor/classifica.py::classifica_file()`
determina se il documento è una bolletta luce, gas, un CTE, o "sconosciuto" —
leggendo solo le prime 3 pagine (`N_PAGINE_CLASSIFICAZIONE`, riga 32), zero
AI, zero costo. Esiste perché in sessione è stato trovato un bug reale: una
bolletta gas archiviata per errore nella cartella "Bollette_Luce" veniva letta
comunque con lo schema luce — il POD segnalava correttamente bassa
confidenza (formato sbagliato), ma `kwh_totale` catturava il consumo in Smc
senza che nulla lo segnalasse come errore. sacor non aveva mai saputo che
tipo di documento avesse davanti.

I segnali usati sono stati scelti leggendo tre documenti reali esterni al
corpus e poi **verificati** sui 15 documenti del corpus reale prima di
essere fissati (`src/sacor/classifica.py:9-16`). Il segnale iniziale
considerato — cercare "periodo di fatturazione" — è stato **scartato dopo
verifica**: troppe varianti per fornitore ("periodo oggetto di
fatturazione", "periodo di competenza", "periodo di riferimento", il bare
"PERIODO:"), lo stesso problema di fragilità già osservato per le etichette
tier0 sul corpus reale (T4.17). Al suo posto, "totale da pagare" si è
rivelato l'unico segnale davvero universale sui fornitori controllati: se
manca, il documento non è un consuntivo con importo dovuto — e solo a quel
punto, con un segnale positivo aggiuntivo ("condizioni economiche", "codice
offerta"), si classifica come CTE, mai per sola esclusione. Presente
"totale da pagare", `smc`/`kwh` (parola intera) distingue gas da luce.

Sul corpus reale (15 documenti, tutti noti essere luce): 6/15 classificati
con certezza corretta, 9/15 onestamente `sconosciuto` (6 completamente
scansionati, senza text layer da leggere — la classificazione è tier0-style,
non tenta di leggere un'immagine; 3 richiederebbero più delle 3 pagine
lette). **Zero falsi positivi**: nessun documento classificato nel tipo
sbagliato. La CLI, senza `--schema` esplicito, classifica prima
(`src/sacor/cli.py:50-73`): per `sconosciuto` ripiega su bolletta_luce con
avviso esplicito su stderr, mai in silenzio; per un tipo senza schema
pronto si ferma con errore chiaro invece di forzare uno schema sbagliato.

### 4.2 Triage (`src/sacor/triage.py`)

Ricostruisce dal solo PDF ciò che in produzione nessun metadato dichiara
(ADR-016): per ogni pagina, se ha un text layer, la densità di testo, la
copertura immagine, il tipo (`digitale`/`ibrida`/`scansione`, ADR-022), la
rotazione. Il segnale primario è la copertura immagine, non la densità di
testo (ADR-020): soglie 0,15 e 0,85 su una griglia 64×64
(`_copertura_immagine`, righe 80-107), con margini misurati e annotati nel
codice, non scelti a occhio. Zero AI, costo zero — circa il 30% dei
fallimenti si evita già qui secondo `01-architecture.md`.

La rotazione, se `/Rotate` non è dichiarata nei metadati e la pagina è
scansione o ibrida, viene stimata via OSD Tesseract — binario esterno
opzionale, mai un'eccezione se assente (`_rotazione_via_osd`, righe
121-152). `normalizza_testo()` (righe 213-256) corregge un bug sottile: a
180 gradi `pdfminer` inverte l'ordine di lettura dei caratteri
("Importo totale" diventa "elatot otropmI") — la segmentazione legge sempre
da questa funzione, mai da `extract_text()` diretto, altrimenti un pattern
non trova mai nulla su una pagina capovolta.

### 4.3 Segmentazione (`src/sacor/segmentation.py`)

Un PDF non è un documento — è un contenitore di una o più istanze
documentali (ADR-014-bis). Il criterio di separazione è dichiarato nello
schema, mai nel codice (ADR-017): per bolletta_luce_it, `cambio_valore` su
`'Fattura n\.?\s*([0-9]+)'` (`schemas/bolletta_luce_it.yaml:207-210`) — una
nuova istanza inizia dove il numero di fattura cambia; le pagine senza match
vengono "riempite in avanti" nell'istanza aperta dall'ultimo match visto
(`_riempi_in_avanti`, righe 100-126), perché il marcatore compare tipicamente
solo sulla prima pagina di ogni fattura multipagina.

La segmentazione espone tre livelli di confidenza (ADR-024): `certa` (text
layer ovunque, pattern trovato), `presunta` (text layer ovunque, pattern mai
trovato) e `non_determinabile` (almeno una pagina è scansione o ibrida —
niente testo da cercare). Il terzo caso è deliberatamente **non** trattato
come "un solo documento per default": un tentativo precedente di introdurre
proprio questa scorciatoia (ADR-029) è stato scritto, misurato e poi
**revocato** nella stessa giornata (ADR-031) quando ha trasformato un caso
reale — due fatture sulla stessa pagina fisica scansionata — da
un'incertezza dichiarata onestamente a un errore silenzioso e sicuro di sé:
esattamente il fallimento che il progetto esiste per prevenire.

### 4.4 Tier0 — estrazione deterministica (`src/sacor/extractor.py`)

Regex dichiarate nello schema, zero AI, zero costo, girano sempre prima di
qualunque chiamata a un modello (ADR-032). Tre motivi dichiarati per
costruirlo prima di un modello: (1) senza una base di confronto senza AI,
ogni numero prodotto da un modello è un valore assoluto senza riferimento;
(2) su una bolletta digitale, POD/date/totali hanno spesso formati e
posizioni vincolate — parte del lavoro non richiede comprensione semantica;
(3) definisce fin dal primo giorno il tasso di escalation, la metrica
economica che decide se il progetto è sostenibile (`01-architecture.md`:
"sopra il 20% il margine per documento evapora").

`TierZeroExtractor.extract()` lavora sull'**istanza**, non sul file
(ADR-033: un bug storico faceva leggere sempre i valori di pagina 1 anche
per istanze successive), e solo sulle pagine `DIGITALE` dell'istanza — se
una pagina non ha testo affidabile, i suoi campi restano `None`, mai un
tentativo di leggerla comunque (`estrai_diagnostica`, righe 70-114). Ogni
campo mancante ha una causa tracciata separatamente (`EsitoCampo`:
`non_estratto` / `non_normalizzabile` / `normalizzato`, righe 32-39) — un
numero unico di accuratezza nasconderebbe se il problema è nel pattern o nel
Repair.

### 4.5 Repair — normalizzazione formati italiani (`src/sacor/repair.py`)

Trasforma il valore grezzo catturato dalla regex nella forma canonica
(ISO per le date, `Decimal` per i numeri). La parte più delicata è il
separatore decimale/migliaia italiano: con la virgola presente non c'è
ambiguità (la virgola è sempre il separatore decimale, ogni punto prima è
migliaia); senza virgola e con un solo punto, se le cifre dopo il punto sono
esattamente 3 la stringa è **strutturalmente ambigua** ("1.234" può essere
1234 o un decimale a tre cifre) e viene rifiutata invece di indovinata
(`_ripara_decimale`, righe 32-71). Questo bug — la regex tier0 cercava solo
`[\d.]+`, senza virgola nella classe di caratteri — era stato scoperto
ispezionando 22 bollette reali di terzi (ADR-040): il generatore sintetico
usava sempre il punto, le bollette vere usano sempre la virgola italiana.

### 4.6 Derivazione aritmetica (ADR-051, `deriva_mancanti`)

Prima ancora di chiamare un modello, `sacor.invariants.deriva_mancanti()`
prova a risolvere un campo mancante per via aritmetica, se esattamente un
termine di un'invariante bidirezionale (`differenza_giorni` o
`somma_approssimata`) manca e gli altri sono noti e validi. Non è
un'invenzione: è la stessa formula già usata per **validare** l'invariante,
applicata al contrario quando l'incognita è una sola. Esempio concreto — lo
stesso citato nel README:

```
periodo_da = 2025-03-19, giorni = 56, periodo_a = None
→ periodo_a = periodo_da + (giorni - offset) = 2025-03-19 + 55 giorni = 2025-05-13
```

(`_deriva_differenza_giorni`, `src/sacor/invariants.py:199-226` — l'offset
`1` incorpora la convenzione "giorni inclusivi": dal 1 al 5 del mese sono 5
giorni, non 4). Se mancano zero termini non c'è nulla da fare; se ne mancano
due o più il sistema è sottodeterminato e non è più matematica, quindi non
tenta nulla. La funzione gira **prima** di tier1 (risparmia la chiamata se
l'aritmetica basta da sola) e **di nuovo dopo** (tier1 può sbloccare una
derivazione prima impossibile, es. trovando `periodo_da` che permette di
derivare `periodo_a` da `giorni`). Un valore derivato riceve confidenza
`media`, non `alta`: eredita l'incertezza dei valori usati per calcolarlo,
non è più affidabile di un valore semplicemente letto
(`src/sacor/pipeline.py:96-99`).

### 4.7 Tier1 — AI, opt-in, solo claude-opus-5 (ADR-049)

Mai automatico: `usa_tier1=False` di default in `estrai_file()`, va
richiesto esplicitamente (`--tier1` da CLI), perché è una chiamata reale a
pagamento. Completa **solo** i campi che tier0 (più la derivazione
aritmetica) ha lasciato `None` — un valore deterministico non viene mai
sovrascritto da uno probabilistico (ADR-035). Il prompt è generato
interamente dallo schema (`src/sacor/providers/prompt.py::costruisci_prompt`),
mai scritto a mano per un tipo di documento specifico: la conoscenza di
dominio (es. "quale dei più totali sulla pagina è quello richiesto") vive
nella `descrizione` opzionale del campo nello YAML, non nel codice del
prompt builder.

Perché **solo opus e non arbitrato multi-provider**: `01-architecture.md`
dichiarava "due provider sempre" come principio di continuità di servizio, e
ADR-045 aveva costruito `sacor.arbitrate` proprio per usare il disaccordo
tra due modelli come segnale di bassa confidenza. Misurato sul corpus reale
(ADR-049, 15 documenti, 126 campi, $2.23 spesi): il disaccordo si verifica
nel 31,0% dei campi; quando i due modelli concordano, sono corretti solo il
56,3% delle volte (l'accordo non è un oracolo implicito, come sperato); ma
un arbitro che, in caso di disaccordo, si fidasse sempre di opus otterrebbe
53,8% di accuratezza sui casi contesi — **peggio** che fidarsi di opus da
solo su tutto lo schema (60,9%/campo). L'arbitrato raddoppia il costo per
chiamata e non migliora l'accuratezza rispetto a un singolo modello forte.
Decisione: tier1 usa solo `claude-opus-5`. Il codice dell'arbitrato non è
stato rimosso (potrebbe tornare utile con un corpus più grande o provider
diversi) — YAGNI si applica a "usarlo ora", non a "cancellarlo".

Un errore del provider (chiave API mancante, rate limit, risposta troncata)
non fa fallire l'intera estrazione: viene catturato come `ErroreProvider` e
riportato in `tier1_errore`, il resto del risultato resta utilizzabile
(`src/sacor/pipeline.py:167-183`).

### 4.8 Invarianti — il motore di validazione (`src/sacor/invariants.py`)

Cinque tipi dichiarativi, registrati in `TIPI_NOTI` (riga 18-24), mai
espressioni libere da parsare (principio esplicito in `01-architecture.md`:
un formato `somma(a,b) ~= c` da interpretare sarebbe debito tecnico
immediato):

- `somma_approssimata` — addendi che devono sommare al totale entro una
  tolleranza relativa (es. `kwh_f1+kwh_f2+kwh_f3 ≈ kwh_totale`, tolleranza
  0,5%).
- `differenza_giorni` — una differenza di date che deve coincidere con un
  campo intero, con offset (`giorni_inclusivi`).
- `valore_minimo` — un campo numerico non può essere sotto una soglia (es.
  kWh/importi non negativi — un valore negativo è quasi sempre un errore di
  lettura, non un dato reale).
- `ordine_date` — una data non può precedere un'altra (`periodo_da` prima di
  `periodo_a`).
- `formato` — un campo deve rispettare un pattern regex (es. il POD deve
  avere la forma `IT\d{3}E\d{8}` anche dopo l'estrazione).

Ogni invariante dichiara la propria `severita` (`warning` o `reject`) — è
l'unico modo con cui il gate a tre livelli sa decidere. Un termine mancante
o non valido rende l'invariante **non valutabile**, non violata: un `None`
non è un errore (stesso principio di ADR-010 applicato qui).

Questo strato — dichiarato nell'architettura fin dal Blocco 1 come
"Arbitrate" — è rimasto **codice morto per gran parte della vita del
progetto**: `sacor.invariants` esisteva solo come registro di tipi usato dal
loader per validare che le invarianti referenzino campi esistenti, nessun
codice le valutava mai contro valori estratti veri (ADR-045). È stato
costruito solo l'11-08, quando un'incongruenza aritmetica banale (F1+F2+F3=91
contro un totale dichiarato 277 dallo stesso modello, nella stessa risposta)
è stata trovata a mano da un agente invece che dal sistema stesso.

Come diventano segnale di "bassa confidenza": `campi_coinvolti()` mappa ogni
invariante ai campi che referenzia; se un'invariante è violata, **tutti** i
suoi campi coinvolti ricevono confidenza `bassa`, a prescindere dalla loro
origine (tier0, tier1 o derivato) — il disaccordo tra campi è il segnale, non
solo l'affidabilità della singola fonte (`src/sacor/pipeline.py:84-102`).

### 4.9 Confidenza per campo

La vera promessa di prodotto (ADR-048, punto 2 dell'architettura North Star):
ogni campo esce con un livello — `alta` (tier0, regex deterministica), `media`
(tier1 o derivato, eredita l'incertezza dell'AI o degli input usati per
calcolarlo), `bassa` (coinvolto in un'invariante violata, indipendentemente
da come è stato ottenuto), `null` se il campo non ha valore. Prima della
sessione dell'11-12 agosto, questo livello non esisteva quasi per nulla nel
sistema — solo la segmentazione aveva una nozione simile di confidenza.

### 4.10 Gate finale

`_calcola_esito()` (`src/sacor/pipeline.py:57-70`): un campo obbligatorio
assente forza `reject` con motivo esplicito; un'invariante violata con
`severita: reject` forza `reject`; qualunque altra violazione produce
`warning`; altrimenti `pass`. L'exit code della CLI riflette il gate: `0` se
tutte le istanze passano, `1` se almeno una è `reject`, `2` per errori di
file o schema.

## 5. I tre schemi esistenti

**`bolletta_luce_it`** (`src/sacor/schemas/bolletta_luce_it.yaml`) — 10
campi (pod, fornitore, periodo_da/a, giorni, kwh_totale, kwh_f1/f2/f3,
importo_totale), 8 invarianti. È l'unico dei tre con una misura vera: corpus
reale di 15 documenti (14 fornitori diversi), consenso esplicito ottenuto
per l'uso dei dati tecnici a fini di misura (ADR-042 — i PDF originali non
entrano mai nel repo, solo l'oracle con i 10 campi schema, `.gitignore` sul
resto). Accuratezza attuale: **68,7% per campo, 13,3% per documento** (2/15
— la prima volta nella storia del progetto che un documento reale esce
corretto su tutti i campi, ADR-052).

**`bolletta_gas_it`** e **`cte_it`** (stessi file in `src/sacor/schemas/`) —
costruiti nella stessa sessione (ADR-053), leggendo rispettivamente due
documenti gas reali (Alperia, Iren) e un documento CTE reale (ENGIE eFIX
Luce), tutti esterni al corpus con consenso. **Nessuna misura di accuratezza
esiste per questi due schemi** — solo una verifica puntuale, dichiarata come
tale nel codice e qui: gas 7/7 campi corretti su un documento (Alperia, con
tier1, $0,14), CTE 8/8 campi corretti su un documento (con tier1, $0,045).
Un documento non è un corpus. Il prossimo passo naturale per renderli
misurabili — un piccolo corpus con oracle, come fatto per luce — richiede lo
stesso consenso già ottenuto per il reale luce, e non è ancora stato fatto.

## 6. Stato reale oggi (12 agosto 2026)

**Numeri**, senza filtro:

| Metrica | Valore | Fonte |
|---|---|---|
| Accuratezza per campo (luce, corpus reale, 15 doc, tier0+tier1+derivazione) | 68,7% (103/150) | ADR-052 |
| Accuratezza per documento (luce, stesso corpus) | 13,3% (2/15) | ADR-052 |
| Tasso di escalation tier0→tier1 | 100% (14/14 documenti hanno richiesto tier1) | ADR-046 |
| Campo più debole | periodo_da/periodo_a, 33,3% ciascuno | ADR-051 |
| Gas/CTE | 7/7 e 8/8 su 1 documento ciascuno — nessuna misura di corpus | ADR-053 |
| Test unitari | 216 (`pytest`) | verificato sul repo |
| CI | GitHub Actions, verde su push/PR (`.github/workflows/ci.yml`) | verificato sul repo |
| Repo | **ancora privato** su `github.com/vinsblack/sacor` | verificato (`gh repo view --json visibility`) |
| PyPI | non pubblicato | README, ADR-048 |
| Nodo n8n | non costruito | ADR-048 (priorità 4) |
| Utenti esterni | nessuno noto | — |

Cosa manca, dichiarato senza ambiguità: il pacchetto non è installabile via
`pip install sacor`, non c'è documentazione di integrazione oltre il README,
non c'è un nodo n8n, non c'è un solo utilizzatore esterno confermato. Cosa è
pronto: il motore (sette strati, con l'Arbitrate/invarianti costruito e
misurato), 216 test, CI verde, una CLI funzionante (`sacor extract
file.pdf`), un corpus reale con consenso per lo schema luce.

Un dato di metodo rilevante per capire l'affidabilità di questi numeri:
l'intero ciclo ADR-042→052 (dal primo numero reale al 68,7% attuale) è
costato circa **$16-18 in chiamate API reali** su più giri di
misura-diagnosi-fix, e almeno due di quei giri hanno trovato **bug nello
strumento di misura stesso**, non nel motore (ADR-051: gli script di misura
reimplementavano la pipeline a mano invece di chiamare `estrai_file()`,
misurando quindi una pipeline diversa da quella reale; ADR-052: uno script
diagnostico confrontava stringhe con `==` invece che via `Decimal`,
producendo 32 falsi allarmi su 40). Il progetto tratta questi errori di
misura come parte della cronologia pubblica, non li nasconde.

## 7. Punti di forza

- **Disciplina di misura reale, non dichiarata.** Ogni soglia (copertura
  immagine 0,15/0,85, tolleranza somma fasce 0,5%) è annotata nel codice con
  il margine osservato al momento della misura, non solo il valore — un
  numero senza margine non è monitorabile nel tempo (`triage.py:29-43`).
- **Architettura dichiarativa, verificata due volte.** Un nuovo tipo di
  documento è un nuovo YAML, non nuovo codice — dimostrato concretamente:
  gli schemi gas e CTE sono stati aggiunti in una sessione con zero righe
  di codice Python nuove nel core (solo YAML).
- **Onestà sotto pressione misurata.** Tre tentativi falliti di far salire
  `periodo_da`/`periodo_a` (ADR-050) sono stati lasciati nella cronologia
  invece che cancellati; una decisione di prodotto (ADR-046) è stata
  revocata nella stessa giornata quando l'argomento si è rivelato debole
  (ADR-048) — entrambi i casi documentati, non nascosti.
- **Costo per documento basso in assoluto.** $0,005-0,015 con il modello
  economico misurato nei bake-off; anche con opus (unico modello usato oggi)
  i costi per singolo test restano nell'ordine dei centesimi.
- **Zero AI dove l'AI non serve.** Somme, IVA, giorni, riconciliazioni non
  passano mai da un modello — sono Python puro, deterministico, testabile.

## 8. Punti deboli e rischi

**Tecnici:**

- **13,3% di documenti completamente corretti è basso in assoluto**, anche
  se il numero per campo (68,7%) è più alto. Per un utilizzatore che deve
  automatizzare senza revisione umana, il numero che conta di più è quello
  per documento, ed è quello dichiarato più debole (ADR-011: la metrica per
  documento è "quella onesta", messa per prima non a caso).
  Non usare il numero per campo da solo — sarebbe esattamente il trucco
  commerciale che il progetto denuncia.
- **Tasso di escalation al 100%** contro un criterio di sostenibilità
  dichiarato del 20% (`01-architecture.md`). L'architettura originaria
  ("tier0 assorbe l'80-90%") descrive un sistema che il corpus reale non
  conferma — non ha mai chiuso da solo un documento intero anche dopo
  ottimizzazioni mirate (T4.17).
- **Corpus piccolo, per un solo schema.** 15 documenti, 14 fornitori — n≈1
  fornitore. Gas e CTE hanno zero misura di corpus, solo verifica su un
  documento ciascuno: i numeri 7/7 e 8/8 sono incoraggianti ma statisticamente
  non significativi.
- **`periodo_da`/`periodo_a` è un gap noto, non risolto** dopo tre tentativi
  di fix nella stessa sessione (~$6 spesi, zero movimento sul numero,
  ADR-050) — la causa vera non è isolata (serve leggere il *reasoning*
  grezzo del modello, mai fatto finora).
- **Segmentazione non affidabile su scansioni**: senza text layer, la
  divisione tra più fatture nello stesso PDF resta `non_determinabile`
  finché non esiste una ri-segmentazione basata su OCR (limite noto dal
  Blocco 3, ADR-024, mai risolto).
- **Rischio di overfitting sul corpus attuale**: rendimenti già decrescenti
  osservati (T4.17, ADR-046) — ogni ulteriore ottimizzazione sugli stessi 15
  documenti rischia di migliorare un numero senza migliorare la
  generalizzazione.

**Di prodotto/mercato:**

- **Zero utenti esterni, zero pacchetto pubblicato.** La fase 1 (open
  source) è appena iniziata; il criterio G3 (utente esterno entro 6 mesi) è
  ancora tutto da raggiungere.
- **Posizionamento di nicchia deliberato** ("framework" non è una query che
  qualcuno digita, riconosciuto in ADR-023) — mitigato solo dal fatto che il
  README apre col caso concreto e il numero misurato, non con l'ambizione
  architetturale.
- **Dipendenza da un solo provider AI** (Anthropic, claude-opus-5) dopo
  l'abbandono dell'arbitrato multi-provider — il principio "due provider
  sempre" dichiarato in architettura non è più applicato nella pratica per
  il tier1 di produzione, solo nel codice non usato di `sacor.arbitrate`.

## 9. Prossimi passi dichiarati

L'ordine esplicito fissato in ADR-048, che sostituisce "più corpus reale"
come priorità precedente:

1. Pacchetto PyPI installabile
2. CLI (`sacor extract file.pdf`) — **fatto**, commit `e46a5c0`
3. Documentazione di integrazione (quickstart, esempi) — **fatto**, commit `b377701`
4. Nodo n8n
5. API stabile
6. Primo utilizzatore esterno

La logica dichiarata: il collo di bottiglia non è più l'accuratezza — è
farsi trovare da qualcuno che abbia un documento reale diverso dai 15 già
visti. Il corpus, in questa visione, cresce come **conseguenza**
dell'adozione (nuovi casi segnalati da chi usa il motore), non come suo
prerequisito. `periodo_da`/`periodo_a`, il gap più visibile oggi, è
lasciato esplicitamente come "candidato a essere il primo problema che un
utilizzatore esterno segnala con un caso reale nuovo" (ADR-050) — non un
problema da chiudere in laboratorio sugli stessi 15 documenti.
