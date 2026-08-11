# 02 — Decision log (append-only)

## ADR-001 — Nome: sacor
**2026-08-10.** Verificati 18 candidati. Scartati per collisione: DocCore,
DocKernel (`.odex`… no: si legge "Docker-nel", pacchetto esistente), Parseon,
Structa, Evident (Evident Corp + Evidently AI), Veridoc (VeriDoc Global),
Certis (Certis Group), Verifact (2 aziende attive), Provena, ODEX (formato
file Android), ODE, ODX, Crivo, Calibro (vicino a Calibre).
`sacor` non ha collisioni su GitHub né nel settore software. `.com` occupato
(Sacor Inc, forniture medicali) → usare `.ai`/`.dev`.
**Il nome è reversibile finché nessuno ha installato il pacchetto.**

## ADR-002 — Clean room rispetto a VERO
**2026-08-10.** Zero codice, zero dati, zero listini da VERO. Solo know-how.
Il know-how (pagine ruotate invisibili a Tesseract, separatore migliaia
italiano, giorni inclusivi, errori silenziosi) è trasferibile; l'implementazione
per Massimo no. Precondizione: accordo IP scritto.

## ADR-003 — Memoria nel repo, non in Notion
**2026-08-10.** Fonte di verità = file versionati in git, letti nativamente da
CC, allineati al commit. Notion introdurrebbe disallineamento tra stato
dichiarato e stato reale (problema già visto su VERO). Notion = mirror di sola
lettura.

## ADR-004 — Nessun SaaS iniziale
**2026-08-10.** Billing, API key, hosting e supporto sono mesi di lavoro non
tecnico prima che qualcuno abbia usato il motore. Si costruisce su richiesta.

## ADR-005 — Verifica nome eseguita
**2026-08-10.** Check live su T1.1: PyPI `sacor` libero, npm `sacor` libero,
`github.com/vinsblack/sacor` libero. Lo username GitHub `sacor` risulta preso da
utente non correlato — irrilevante, il repo sta sotto l'account personale.
ADR-001 confermato, nome fissato.

## ADR-006 — Test di smoke fin dal primo commit
**2026-08-10.** `pytest` senza test raccolti esce con codice 5, che fa fallire
la CI. Due strade: tollerare l'exit code 5 nel workflow, oppure introdurre
subito un test minimo.
Scelta: **test minimo**. Un workflow che ignora un exit code è un'eccezione
permanente che nasconderà un giorno un fallimento vero. Un test che verifica
`import sacor` e la presenza di `__version__` è legittimo di per sé, rende
`tests/` tracciato da git e mantiene la CI senza casi speciali.

## ADR-007 — Versione a sorgente unico
**2026-08-10.** La versione vive solo in `src/sacor/__init__.py` come
`__version__`; `pyproject.toml` la legge in modo dinamico via hatchling.
Motivo: due copie della stessa costante divergono sempre, e la versione è il
campo che comparirà nei report dell'eval e nei bug report degli utenti.

## ADR-008 — Dataclasses, non pydantic, per il modello di schema
**2026-08-10.** Il loader di schema potrebbe usare pydantic. Scelta: no.
Motivi: (a) sacor è una libreria che altri installeranno, e ogni dipendenza
runtime è una tassa su ogni utente; (b) gli errori di validazione devono essere
di dominio ("il campo kwh_f4 citato nell'invariante somma_fasce non esiste"),
non ValidationError generici; (c) con `mypy strict` le dataclass frozen danno
già garanzie sufficienti.
Unica dipendenza runtime introdotta ora: PyYAML.
Rivedibile se il numero di tipi di nodo nello schema supera ~6.

## ADR-009 — Le referenze dei campi si validano al load
**2026-08-10.** Un'invariante che cita un campo inesistente deve fallire al
caricamento dello schema, non durante l'eval. Un typo in un YAML scoperto tre
strati dopo costa un'ora di debug; scoperto al load costa zero.
Stesso principio per `tipo`: deve esistere nel registro delle invarianti.

## ADR-010 — Oracle: numeri come stringhe, null significa "assente"
**2026-08-10.** In `corpus/attesi.json` tutti i valori sono stringhe, anche i
decimali (`"1234.56"`, non `1234.56`). Motivo: JSON usa float IEEE-754, e
`0.1 + 0.2 != 0.3`. Un oracle che non è esatto per costruzione rende ogni numero
successivo discutibile. La conversione a `Decimal` avviene al confronto.

`null` ha un significato preciso: **il campo non è presente sul documento**.
Non significa "non lo so". Se l'extractor restituisce `null` e l'oracle dice
`null`, è una risposta **corretta**: il sistema ha correttamente rilevato
un'assenza. Senza questa distinzione l'accuratezza è ingannevole.

## ADR-011 — Definizione di accuratezza
**2026-08-10.** Due metriche, entrambe riportate. Mai una sola.

**Per campo:** match esatti / totale documenti, calcolato per ogni campo dello
schema. Il match è esatto dopo normalizzazione (trim, `Decimal` per i numerici,
ISO per le date). Nessuna tolleranza: la tolleranza vive nelle invarianti, non
nel confronto con l'oracle.

**Per documento:** un documento è corretto solo se **tutti** i campi lo sono.
È la metrica onesta e sarà molto più bassa dell'altra.

Motivo: dichiarare "99% di accuratezza" misurando per campo è il trucco
commerciale standard del settore. sacor pubblica entrambe, e mette per prima
quella per documento.

## ADR-012 — Nessun documento proveniente dalla commessa VERO
**2026-08-10.** Tre bollette reali (Plenitude, Sorgenia, Iren) provenienti dal
lavoro con Massimo sono state proposte per il corpus e **rifiutate**.
Motivi: (a) violano ADR-002; (b) i dati non sono di Massimo ma di clienti finali
identificabili, che non hanno acconsentito a un uso in un prodotto terzo;
(c) un corpus non pubblicabile annulla il differenziatore del progetto — un
numero che nessuno può verificare vale quanto quello dei concorrenti.
Le **osservazioni** ricavate dalla lettura restano acquisite (ADR-013): il
know-how è trasferibile, i documenti no.

## ADR-013 — Casi limite osservati su documenti reali
**2026-08-10.** Riproducibili nel generatore sintetico. Nessun dato reale
conservato.

1. **Più fatture in un solo PDF.** Un PDF Plenitude conteneva due periodi
   distinti (gen-feb 2026 e nov-dic 2025) con due numeri fattura e due totali.
   L'assunzione "un file = un documento" è falsa. Il triage deve rilevare i
   confini di fattura, altrimenti l'estrattore mescola i periodi. Errore
   silenzioso: il risultato è formalmente coerente.
2. **Periodo espresso come mese, non come intervallo.** Sorgenia stampa
   "Periodo di fatturazione: Settembre 2025". Le date visibili sono date di
   lettura, non di periodo. `periodo_da`/`periodo_a` vanno derivati, e la
   derivazione va marcata come tale nella confidence.
3. **Fornitore ambiguo.** Logo "plenitude" vs ragione sociale "Eni Plenitude
   SpA Società Benefit"; "Sorgenia" vs "Sorgenia S.p.A."; "iren" vs "IREN
   MERCATO S.p.A.". Serve normalizzazione, o il campo sbaglia metà delle volte.
4. **Consumi stimati vs effettivi.** Iren dichiara "di cui consumo stimato 95
   kWh" e avverte che gli importi saranno ricalcolati. Un consumo stimato non
   ha lo stesso valore di uno effettivo: va esposto come metadato.
5. **Fascia unica con fasce a zero.** Offerta monoraria che riporta comunque
   F1/F2/F3 con F2=0 e F3=0. Zero non è assenza: la somma fasce resta valida.

## ADR-014 (proposta CC, da rivedere Opus) — Chiave oracle per --multi-fattura
**2026-08-10.** Con `--multi-fattura` un solo file PDF contiene due fatture,
quindi due voci oracle. `corpus/attesi.json` non può più usare il nome del
file come chiave univoca.

**Proposta:** chiave composita `"{doc_id}#{indice}"`, indice 1-based
nell'ordine di lettura nel PDF (es. `"S007#1"`, `"S007#2"`).

Motivi: (a) preserva la tracciabilità al file fisico (il prefisso prima di
`#` è sempre il nome del PDF, `{doc_id}.pdf`); (b) `oracle.documenti` resta
una mappa piatta stringa → campi, senza introdurre un secondo modello dati
annidato che l'eval harness (T1.8, `sacor.oracle`/`eval/run.py`) dovrebbe
gestire come caso speciale; (c) `#` non compare altrove nei doc_id (`S001`…),
zero rischio di collisione.

Alternativa scartata: nidificare le fatture sotto il doc_id
(`{"S007": {"1": {...}, "2": {...}}}`). Scartata perché rompe il contratto
attuale di `load_oracle`/`esegui_eval` (mappa piatta id → campi) senza
nessun beneficio proporzionato al costo di migrazione.

Nessuna modifica richiesta a `sacor/oracle.py`: la validazione dei campi
opera sul dict di ciascuna voce, non sul formato della chiave.

## ADR-014-bis — Chiave oracle opaca, supera ADR-014 (proposta CC)
**2026-08-10.** CC ha proposto `{doc_id}#{indice}` come chiave per i PDF
multi-fattura, con `eval/run.py` che fa split su `#` per risalire al file.
**Respinta.**

Motivo: è la stessa anti-pattern già rifiutata per le invarianti YAML
(vedi 01-architecture, "mai espressioni da parsare"). Codificare struttura
dentro una stringa e poi riparsarla crea un formato implicito che ogni
consumatore deve conoscere: l'eval oggi, il nodo n8n domani, l'API dopo.
Inoltre introduce un caso speciale — chiave semplice per documento singolo,
composita per multi-fattura — quindi due percorsi di codice per la stessa cosa.

**Decisione.** La chiave dell'oracle è un identificatore **opaco** di istanza
documentale (`S007a`, `S007b`), mai da interpretare. Il legame con il file
fisico vive in `corpus/metadata.json`:

    "S007a": { "file": "S007.pdf", "pagine": [1, 6], ... }
    "S007b": { "file": "S007.pdf", "pagine": [7, 8], ... }

`eval/run.py` legge il percorso dal metadata. Nessuno split, nessun caso
speciale: un documento singolo è semplicemente un'istanza le cui pagine
coprono l'intero file.

Corollario di dominio: un file PDF non è un documento. È un contenitore di una
o più istanze documentali. Il modello dati lo riflette da subito, perché
cambiarlo dopo significherebbe toccare oracle, eval, triage e API insieme.

## ADR-015 — Dipendenze dev pinnate
**2026-08-10.** Introdotte come dev-only: reportlab (rendering), pypdf
(rotazione), Pillow (degrado immagine), pdfplumber (verifica text layer).
Nessuna dipendenza runtime aggiunta oltre PyYAML.
CI ora è verde: da questo commit le dev-dependencies si pinnano alla minor,
così un rilascio a monte non rompe la build in un momento casuale.
Nota: `pdfplumber` diventerà dipendenza **runtime** con lo strato Triage.

## ADR-016 — Il triage ha un bersaglio misurabile: ricostruire i metadati
**2026-08-10.** In produzione `corpus/metadata.json` non esiste. Il triage deve
scoprire dal solo PDF ciò che oggi il metadata dichiara: quante istanze
documentali contiene, su quali pagine, se c'è text layer, se le pagine sono
ruotate, se è una scansione.

Questo dà al Blocco 2 una metrica propria a **costo di inferenza zero**:
accuratezza del triage = quanto il triage ricostruisce il metadata. Nessun
modello coinvolto, numero reale, regressioni visibili in CI.

Conseguenza sull'ordine di lavoro: il triage viene prima dell'estrattore. Se
l'estrattore riceve due fatture credendole una, nessuna qualità di modello
salva il risultato.

## ADR-017 — La segmentazione è guidata dallo schema
**2026-08-10.** Separare due fatture dentro un PDF richiede conoscenza di
dominio ("una nuova fattura inizia dove cambia il numero fattura"). Il core
però non deve sapere cosa sia una fattura.

Soluzione: lo schema dichiara il criterio, il codice lo esegue.

    segmentazione:
      tipo: cambio_valore
      pattern: 'Fattura(?: elettronica)? n\.?\s*([0-9]+)'
      minimo_pagine: 1

`tipo` mappa su una funzione registrata, come per le invarianti (ADR-014-bis,
01-architecture). Nuovo tipo di documento = nuovo pattern nello YAML, non nuovo
codice.

Se lo schema non dichiara `segmentazione`, il default è una sola istanza per
file. Il comportamento semplice resta il default, non un caso speciale.

## ADR-018 — "Scansione" è proprietà della pagina, non del file
**2026-08-10.** `e_scansione` era un booleano di documento calcolato sulla
mediana delle densità. Sbagliato: un PDF può essere misto — pagine digitali e
pagine scansionate nello stesso file (caso reale osservato in ADR-013, dove un
contenitore ospitava documenti eterogenei).

Con un flag unico di documento l'estrattore instrada l'intero file su un solo
percorso e sbaglia sistematicamente sulle pagine dell'altro tipo. Errore
silenzioso: nessuna eccezione, risultato plausibile.

Decisione: `PaginaInfo.e_scansione` per pagina. Il flag di documento resta come
proprietà **derivata** (`all(...)` / `any(...)` esplicito al punto d'uso), mai
come unico dato disponibile.

## ADR-019 — Il corpus deve contenere scansioni sporche
**2026-08-10.** Il flag `--scansione` genera pagine con **zero** caratteri.
Su un corpus così, la densità è indistinguibile da un booleano
`ha_text_layer`: qualunque soglia tra 0 e 4e-4 supera i test. La soglia è
quindi non falsificabile — nessun test può dire se è giusta o sbagliata.

Le scansioni reali non sono pulite: OCR parziale del driver di stampa,
intestazioni digitali sopra corpo immagine, watermark testuali. Producono
densità basse ma diverse da zero — esattamente la zona dove la soglia conta.

Decisione: nuovo flag `--scansione-sporca` che inserisce un text layer rado e
rumoroso (poche decine di caratteri per pagina). Senza questo caso, la soglia
di T2.2 resta un numero non verificato.

## ADR-020 — Copertura immagine come segnale primario, densità secondario
**2026-08-10.** Misurazione su corpus sintetico (`scripts/misura_triage.py`):

| feature | digitale | scans. pulita | scans. sporca | margine |
|---|---|---|---|---|
| densità testo | 4,17–4,91e-4 | 0 | 6,78e-5 | 6,15× |
| copertura immagine | 0,00 | 1,00 | 1,00 | separazione totale |

**La soglia precedente era sbagliata, e ora è dimostrato.** 5e-5 sta *sotto*
la densità della scansione sporca (6,78e-5): quella pagina veniva classificata
come digitale. È esattamente il buco di falsificabilità previsto da ADR-019 —
e la conferma che scegliere una soglia prima di misurare non funziona.

**Decisione.** `copertura_immagine` è il segnale primario, soglia **0,5**.
Non dipende da quanta scrittura c'è sulla pagina, che è il difetto della
densità.

`densita_testo` resta segnale secondario, con soglia spostata a **1,7e-4**:
media geometrica tra i due estremi osservati (6,78e-5 e 4,17e-4), cioè il punto
centrale in scala logaritmica. Margine registrato: 2,5× per lato.

Regola generale: **ogni soglia si annota con il margine osservato, non solo col
valore.** Un numero senza margine non è monitorabile — se domani un documento
reale cade a 1,6e-4, il margine è chiuso e il modello va rivisto, ma senza il
margine registrato nessuno se ne accorge.

## ADR-021 — Il corpus sintetico è troppo pulito, e la separazione è in parte circolare
**2026-08-10.** `copertura_immagine` = 0,00 esatto sui digitali e 1,00 esatto
sulle scansioni. Nessun documento reale si comporta così:

- **I digitali non sono a zero.** Tutte e tre le bollette reali esaminate
  contenevano loghi e QR code. Copertura reale attesa: 0,02–0,15.
- **La separazione perfetta è quasi tautologica.** Il flag `--scansione`
  disegna un'immagine a piena pagina, quindi la copertura *deve* risultare 1,0.
  Stiamo misurando il generatore, non il mondo.
- **Il caso ibrido non esiste nel corpus.** Pagina immagine con intestazione
  digitale sopra: copertura ~0,85, densità nella norma. È il caso che rompe
  entrambe le feature, e non è mai stato generato.

Decisioni: (a) i layout digitali includono logo e QR; (b) nuovo flag
`--pagina-ibrida`; (c) il margine "infinito" non va citato da nessuna parte
come risultato — è un artefatto del generatore.

## ADR-022 — Triage a tre stati: il binario scansione/digitale è sbagliato
**2026-08-10.** Misura del caso ibrido: copertura 0,79, densità 3,87e-4
(paragonabile al digitale). Con soglia binaria a 0,5 finisce in "scansione".

La domanda "questa pagina è una scansione?" è **mal posta** per una pagina
ibrida: la pagina è entrambe le cose. Qualunque risposta binaria perde
informazione.

**I due errori non costano uguale.**
- Ibrida classificata *scansione* → si paga inferenza su una pagina che aveva
  del testo affidabile. Costa denaro, non correttezza.
- Ibrida classificata *digitale* → l'estrazione testuale restituisce le 28
  parole dell'intestazione e ignora l'85% del contenuto. Nessuna eccezione,
  risultato plausibile. **Errore silenzioso.**

Ma la soluzione non è spostare la soglia: è non forzare un binario. Un sistema
che risponde `pass`/`warning`/`reject` sui documenti non può poi decidere in
modo binario su un segnale altrettanto incerto — sarebbe incoerente con la
tesi stessa del progetto.

**Decisione: `TipoPagina` a tre stati**, per copertura immagine.

| stato | banda | instradamento |
|---|---|---|
| `digitale` | < 0,15 | solo parser testuale |
| `ibrida` | 0,15 – 0,85 | entrambi i percorsi, esito arbitrato |
| `scansione` | > 0,85 | solo percorso immagine |

Margini osservati: digitale 0,0266 contro 0,15 → 5,6×; scansione 1,00 contro
0,85 → 1,18× (sottile, ma il caso scansione è a piena pagina per costruzione:
va rimisurato su documenti reali). Ibrido osservato 0,79, dentro la banda.

La banda ibrida non è un ripiego: è lo stesso principio dell'arbitrato e del
gate a tre livelli. Dove il segnale è incerto, il sistema lo dichiara invece di
scegliere in silenzio.

## ADR-023 — Posizionamento: framework di affidabilità, bollette come primo schema
**2026-08-10.** Decisione di Vins, contro la raccomandazione di Opus (che
suggeriva racconto verticale e ambizione implicita).

sacor si presenta come **framework di affidabilità documentale**: il valore è
la pipeline deterministica, le soglie misurate, l'incertezza dichiarata. Le
bollette sono il primo schema, non l'identità.

Argomento a favore: l'architettura è già agnostica, e il racconto verticale la
sottorappresenta. Le ADR 016–022 non parlano di kWh ma di margini, errori
silenziosi e stati intermedi.

Rischio accettato: "framework" non è una query che qualcuno digita, e un
progetto generico non produce il numero che è il differenziatore. Mitigazione
vincolante: **il README apre comunque con il caso concreto e il numero
misurato.** L'ambizione sta nella sezione architettura, mai al posto del dato.

G2 resta invariato: nessun secondo schema prima di un numero pubblicato e un
utente esterno. Il posizionamento cambia il racconto, non la roadmap.

## ADR-024 — La segmentazione non è affidabile senza text layer
**2026-08-10.** `cambio_valore` (ADR-017) cerca un pattern nel testo di ogni
pagina. Su pagine `SCANSIONE` non c'è testo: la regex non trova nulla e il
risultato è "una sola istanza" — indistinguibile dal caso in cui davvero c'è
un solo documento.

È un errore silenzioso della stessa famiglia già vista due volte: due fatture
lette come una, nessuna eccezione, risultato plausibile. E qui il danno è
massimo, perché tutti gli strati successivi lavorano su confini sbagliati.

**Decisione.** La segmentazione espone una confidenza esplicita:

| esito | quando |
|---|---|
| `certa` | tutte le pagine hanno text layer e il pattern è stato trovato |
| `presunta` | tutte le pagine hanno text layer ma il pattern non compare mai |
| `non_determinabile` | almeno una pagina è `SCANSIONE` o `IBRIDA` |

In tutti e tre i casi si produce comunque un risultato: il default resta una
istanza per file. Ma `non_determinabile` deve propagarsi fino al gate del
documento come `warning`, mai come `pass` silenzioso.

Conseguenza sull'ordine della pipeline: sui documenti scansionati la
segmentazione corretta richiede l'OCR, quindi va **dopo** l'estrazione, non
prima. Il triage produce una segmentazione provvisoria; una ri-segmentazione
sul testo estratto è lavoro del Blocco 3.

## ADR-025 — Il corpus di valutazione contiene i casi difficili per costruzione
**2026-08-10.** `eval/triage.py` riporta 100% su tutti e quattro gli attributi.
Il numero è vuoto: il corpus base generato con `--seed 42` non contiene
nessuna scansione, nessuna pagina ibrida, nessuna ruotata, nessun
multi-fattura. Ogni attributo ha una risposta di default ovvia, e il triage la
indovina senza fare nulla.

I casi difficili esistono nel generatore, ma dietro flag opzionali. Quindi la
configurazione di default del benchmark **esclude esattamente ciò che il
benchmark dovrebbe misurare**.

Questo è il trucco del "99% di accuratezza" applicato a noi stessi: un numero
alto ottenuto scegliendo cosa misurare. Un progetto che esiste per denunciarlo
non può commetterlo.

**Decisione.** Il corpus generato di default è una miscela dichiarata:

| casi | n | copre |
|---|---|---|
| digitale pulito | 4 | baseline, un layout ciascuno |
| scansione pulita | 2 | tipo pagina |
| scansione sporca | 2 | soglia copertura |
| pagina ibrida | 1 | banda intermedia |
| multi-fattura digitale | 1 | segmentazione CERTA |
| multi-fattura scansionato | 1 | segmentazione NON_DETERMINABILE |
| ruotato | 1 | OSD |

`corpus/metadata.json` dichiara la composizione in testa. I flag restano, ma
servono a generare casi isolati nei test unitari, non a definire il corpus.

Regola generale: **se un caso difficile è opt-in, la metrica di default non lo
misura.** Vale per ogni benchmark che il progetto pubblicherà.

## ADR-026 — Mai una media unica nello stato del progetto
**2026-08-10.** `scripts/state.py` riportava l'accuratezza triage come
micro-media sui quattro attributi. Una media nasconde quale attributo sta
fallendo: 100/100/100/60 e 90/90/90/90 danno numeri simili e significano cose
opposte.

È lo stesso errore vietato da ADR-011 per l'estrazione. Vale ovunque:
`03-current-state.md` riporta gli attributi separatamente, più il **peggiore**
in evidenza. Nessuna media aggregata come dato principale.

## ADR-027 — Accuratezza e copertura sono due numeri diversi
**2026-08-10.** La rotazione segna 53,8%. Ma i 6 fallimenti sono tutti `None`
prodotti dall'assenza di Tesseract: il sistema non ha sbagliato, **non ha
potuto rispondere**. Mischiare le due cose produce un numero che sembra un
difetto del triage e non lo è.

È la stessa distinzione di ADR-010 (`null` = assente, non "non lo so"),
applicata alle metriche.

**Decisione.** Ogni attributo che può essere non determinabile riporta due
numeri:

    rotazione — copertura 53,8% (7/13 determinabili)
                accuratezza 100,0% (7/7 sui determinabili)

Mai un numero solo. La copertura misura la capacità dell'ambiente, l'accuratezza
la correttezza del sistema. Una copertura bassa è un problema di installazione;
un'accuratezza bassa è un problema di codice. Confonderle manda a debuggare la
cosa sbagliata.

Corollario: `03-current-state.md` deve dire perché la copertura è bassa
("Tesseract non installato"), altrimenti il numero resta inspiegabile.

## ADR-028 — Una feature non raggiungibile dalla configurazione reale è codice morto
**2026-08-10.** `schemas/bolletta_luce_it.yaml` non dichiara la sezione
`segmentazione`. Quindi `segmenta()` prende sempre il ramo di default e tutto
T2.4 — `cambio_valore`, il percorso `NON_DETERMINABILE`, la segmentazione
multi-fattura — **non viene mai eseguito in produzione**. La confidenza mostra
`certa 12` per assenza di logica, non per certezza.

44 test unitari passavano. Nessuno di essi verificava che la feature fosse
*raggiungibile* dalla configurazione reale. L'ha scoperto l'eval.

Questo è il principale argomento a favore dell'eval harness come test di
integrazione, non solo come metrica commerciale: i test unitari dimostrano che
il codice funziona, l'eval dimostra che il codice viene usato.

Regola: ogni feature introdotta deve essere accompagnata dalla configurazione
che la attiva, e l'eval deve mostrarne l'effetto. Se un percorso di codice non
compare mai nei conteggi dell'eval, va trattato come sospetto.

## ADR-029 — L'incertezza dichiarata di troppo distrugge il valore del warning
**2026-08-10.** `NON_DETERMINABILE` è uscito su 6 documenti su 12: ogni file
con almeno una pagina `SCANSIONE` o `IBRIDA`, come prescritto da ADR-024.
Corretto rispetto alla regola, sbagliato come prodotto.

Su un file di **una sola pagina** con `minimo_pagine: 1`, il numero di istanze
è determinabile per aritmetica: non ci può stare più di un'istanza,
indipendentemente da cosa contenga il testo. Dichiarare incertezza lì è un
falso allarme.

Un gate che segnala tutto non segnala nulla: l'utente impara a ignorare il
flag, e il warning perde valore proprio quando serve. È il rovescio esatto
dell'errore silenzioso, e danneggia il prodotto allo stesso modo.

**Decisione.** Prima della regola su ADR-024 si applica una scorciatoia
deterministica: se `pagine_totali < 2 * minimo_pagine`, la confidenza è
`CERTA` per costruzione, senza leggere alcun testo.
`NON_DETERMINABILE` resta solo dove la segmentazione è davvero possibile e non
verificabile.

Regola generale: prima di dichiarare incertezza, verificare che la domanda non
abbia già una risposta certa per vincoli strutturali.

## ADR-030 — La rotazione va normalizzata prima di leggere il testo
**2026-08-10.** Su S012 (pagina con `/Rotate 180`) la segmentazione è uscita
`PRESUNTA`: `pdfplumber.extract_text()` restituisce il testo invertito
carattere per carattere (`23.45 RUE :elatot otropmI`), quindi il pattern
`Fattura n. X` non viene mai trovato — non perché manchi, ma perché la
rotazione corrompe la lettura prima che la regex entri in gioco.

È la stessa famiglia di ADR-013 caso 1 (pagine ruotate invisibili a Tesseract),
in una forma nuova: la rotazione non degrada solo l'OCR, degrada **qualsiasi**
lettura testuale a valle.

Oggi il triage *rileva* la rotazione ma nessuno la *applica*. Il rilevamento
senza correzione è inutile.

**Decisione.** La normalizzazione della rotazione è uno step della pipeline,
subito dopo il triage e prima di ogni lettura di testo o invio a un modello.
Ogni consumatore riceve pagine già raddrizzate.

Nota: il sistema ha comunque risposto `PRESUNTA` invece di affermare
`1 istanza, CERTA`. La confidenza esplicita ha fatto il suo lavoro — senza,
questo sarebbe stato un errore silenzioso.

## ADR-031 — Revoca ADR-029: la scorciatoia aritmetica produceva errori silenziosi
**2026-08-10.** ADR-029 introduceva: `pagine_totali < 2 * minimo_pagine`
→ `CERTA` senza leggere il testo. Sbagliata. **Revocata.**

Effetto misurato su S011 (multi-fattura scansionato, due fatture sulla stessa
pagina fisica): prima riportava `NON_DETERMINABILE` — onesto. Dopo la
scorciatoia riporta `1 istanza, CERTA`, mentre la verità è 2. La modifica ha
trasformato un'incertezza dichiarata in un **errore silenzioso e sicuro di sé**:
esattamente il fallimento che il progetto esiste per prevenire.

La premessa era falsa: "un'istanza occupa almeno `minimo_pagine` pagine" non
implica "una pagina contiene al più un'istanza". Due fatture possono stare
sulla stessa pagina, e il caso era già nel corpus.

L'errore di ragionamento a monte: ADR-029 partiva da un problema reale
(6 warning su 12 svuotano il valore del warning) e ha scelto la soluzione
sbagliata — **sopprimere il segnale invece di risolverne la causa**.

**Decisione corretta.** La scorciatoia si applica solo se la pagina è
leggibile:

| condizione | esito |
|---|---|
| `pagine_totali < 2*minimo_pagine` e tutte le pagine `DIGITALE` | `CERTA` |
| altrimenti, pagine `SCANSIONE`/`IBRIDA` presenti | `NON_DETERMINABILE` |

Su una pagina illeggibile l'incertezza è reale, non un falso allarme.

E il modo giusto di ridurre quei warning non è assumere: è **rendere leggibile
la pagina**. La ri-segmentazione sul testo estratto via OCR è già prevista nel
Blocco 3 (ADR-024). Fino ad allora, 6 `NON_DETERMINABILE` su 12 è il numero
onesto.

Nota di metodo: questa regressione è stata introdotta da Opus e trovata
dall'eval in un solo giro, perché il report confronta i conteggi di confidenza
tra esecuzioni. Un cambiamento che *migliora* una metrica (warning da 6 a 0)
può peggiorare il sistema. Le metriche vanno lette in coppia: mai la
riduzione dei warning senza l'accuratezza dei casi coinvolti.

## ADR-032 — Tier 0: un estrattore deterministico come base di confronto
**2026-08-10.** Il Blocco 3 potrebbe passare direttamente a un modello. Scelta:
no. Prima si costruisce un estrattore **senza AI**, che lavora sul text layer
delle pagine `DIGITALE` con pattern dichiarati nello schema.

Tre motivi.

**1. È la domanda che nessun concorrente si pone.** "Quanto aggiunge davvero
l'AI?" ha una risposta solo se esiste una base di confronto misurata. Senza
tier 0, ogni numero prodotto da un modello è un valore assoluto senza
riferimento: sembra buono e non si sa rispetto a cosa.

**2. Sposta l'accuratezza sopra zero a costo nullo.** Su una bolletta digitale
POD, date e totali sono in posizioni ricorrenti e con formati vincolati. Una
parte del lavoro non richiede comprensione semantica.

**3. Definisce la soglia economica del tier 1.** Se il tier 0 prende il 70% dei
campi, il modello deve giustificare il proprio costo sul 30% restante. Questo
rende il tasso di escalation (ADR: metrica economica principale) calcolabile
fin dal primo giorno di inferenza, invece che a posteriori.

I pattern vivono nello schema, accanto ai campi — stesso principio di
invarianti e segmentazione. Il codice non sa cosa sia un POD.

    - nome: pod
      tipo: string
      obbligatorio: true
      estrazione:
        tipo: regex
        pattern: 'IT\d{3}E\d{8}'

Tier 0 non deve mai indovinare: se il pattern non trova, restituisce `None`.
Un campo mancante è un dato onesto che il gate sa gestire; un campo inventato
no.

## ADR-033 — L'estrattore lavora su istanze, non su file
**2026-08-10.** Primo numero reale del motore: 42,9% per documento, 43,6% per
campo. I 9 campi errati hanno una sola causa, e non è nei pattern né nel Repair.

`Extractor.extract(pdf: Path, schema: Schema)` legge l'intero PDF. Su S010
(due fatture su due pagine digitali) `re.search` restituisce sempre i valori
di pagina 1: S010a è corretto perché *è* pagina 1, S010b riceve i valori
sbagliati. Un documento errato × 9 campi = i 9 errori osservati.

Il Protocol è stato definito nel Blocco 1, **prima** che esistesse il concetto
di istanza documentale. ADR-014-bis ha stabilito che un PDF è un contenitore
di istanze, ma la firma dell'estrattore non è mai stata allineata: è rimasta a
parlare di file.

**Decisione.** La firma diventa:

    def extract(self, istanza: Istanza, schema: Schema) -> dict[str, str | None]

`Istanza` porta file e intervallo di pagine. L'estrattore non vede mai il PDF
intero, e non ha modo di leggere fuori dai propri confini.

Nota di metodo: il tetto era architetturale, non di configurazione. Nessuna
regolazione dei pattern avrebbe alzato il numero — l'avrebbe solo mascherato,
facendo sembrare risolto un difetto strutturale. Il report a quattro colonne
(non estratto / non normalizzabile / normalizzato / corretto) ha permesso di
distinguerlo in un colpo solo: `non normalizzabile` a zero ovunque escludeva
il Repair, e `normalizzato 70/140` con `corretto 61/140` isolava il problema
ai soli valori letti dal posto sbagliato.

## ADR-034 — La cache è una precondizione del tier 1, non un'ottimizzazione
**2026-08-10.** Dal Blocco 4 ogni esecuzione dell'eval chiama un modello a
pagamento. Su 14 documenti × N rilanci al giorno, il costo diventa una ragione
per **non rilanciare l'eval** — e l'eval eseguito di rado è l'eval che smette
di trovare regressioni.

L'intero metodo di questo progetto si regge sul rieseguire la misura a ogni
modifica. Un attrito economico su quel gesto disattiva il metodo, senza che
nessuno decida di disattivarlo.

**Decisione.** La cache entra insieme alla prima chiamata a un modello, non
dopo. Chiave: SHA-256 di (immagine/testo della pagina + prompt + identificativo
modello + versione schema). Persistente su disco, ignorata da git.

Corollario: l'eval su corpus invariato dopo il primo giro costa zero. Un cambio
di prompt o di modello invalida la cache per costruzione, ed è corretto: è un
esperimento diverso.

Serve anche `--dry-run`, che stima il costo senza chiamare nulla. Sapere quanto
si sta per spendere prima di spenderlo.

## ADR-035 — Tier 1 riempie, non sovrascrive (provvisorio)
**2026-08-10.** Il tier 0 chiude il Blocco 3 con `corretto == normalizzato` su
ogni campo: **100% di precisione su 50% di copertura**. Si astiene sulle
scansioni e non sbaglia mai dove agisce.

Regola per il Blocco 4: il tier 1 viene invocato **solo sui campi dove il tier 0
ha restituito `None`**. Un valore deterministico non viene mai sovrascritto da
un valore probabilistico.

**Provvisoria, e va detto perché.** Regge finché la precisione del tier 0 è
100%, e quel 100% è misurato su corpus sintetico, dove i pattern sono stati
scritti guardando il generatore. Su bollette reali una regex sbaglierà —
`IT\d{3}E\d{8}` cattura il POD anche dentro un'intestazione di pagina 3 che
appartiene a un'altra fornitura.

Quando arriverà il primo corpus reale, la regola va rimisurata. Se la
precisione del tier 0 scende, i due tier diventano **due fonti in disaccordo**
e la decisione passa allo strato Arbitrate, che è il posto giusto per farla.

## ADR-036 — I parametri del generatore vanno calibrati come le soglie del codice
**2026-08-10.** Il bake-off ha dato 0% con 8 campi inventati. Causa: le pagine
`--scansione` sono degradate al punto che **un umano non legge il POD**. Non è
un fallimento del sistema, è un difetto del corpus.

È la terza volta che il generatore invalida una misura: la copertura immagine
perfetta (ADR-021), le scansioni a zero caratteri (ADR-019), ora il degrado
illeggibile. Ogni volta la causa è la stessa: **i parametri del generatore sono
stati scelti a occhio e mai verificati**, mentre ogni soglia del codice è stata
misurata prima di essere fissata.

Un generatore non calibrato è un oracolo non calibrato: produce numeri che
sembrano misure del sistema e sono misure di se stesso.

**Decisione.** Il degrado ha un criterio di accettazione esplicito e
verificabile: una pagina `scansione` deve restare **leggibile da un umano** sui
campi dello schema. Il criterio operativo, in assenza di un umano nel ciclo di
CI: il testo dei campi obbligatori deve essere recuperabile da un OCR di
riferimento sopra una soglia dichiarata.

Una scansione illeggibile è un caso legittimo, ma è un caso **diverso** —
`--scansione-illeggibile` — e il comportamento atteso lì non è "estrarre bene",
è **`reject`**.

Regola generale: ogni parametro del generatore che influenza una metrica va
trattato come una soglia, quindi misurato e annotato con il proprio margine.

## ADR-037 — Su input illeggibile il modello inventa, non si astiene
**2026-08-10.** Scoperta indipendente dal difetto del corpus, e più importante:
davanti a un'immagine da cui un umano non ricava nulla, il modello ha prodotto
**8 valori** invece di dichiarare di non vedere. Zero corretti, zero
astensioni sui campi che ha compilato.

Questa è la conferma sperimentale della tesi del progetto: un modello non
segnala la propria incertezza spontaneamente. Riempie.

Conseguenze:
1. Il prompt deve imporre esplicitamente l'astensione: "se un valore non è
   leggibile, restituisci null; non dedurlo, non stimarlo".
2. **Non ci si può fidare comunque.** L'istruzione riduce il fenomeno, non lo
   elimina. Le invarianti aritmetiche e il gate restano l'unica difesa reale,
   e la colonna `inventati` va monitorata a ogni giro come metrica di prima
   classe.
3. Il tier 1 non può essere valutato sulla sola accuratezza. Un modello con
   accuratezza più alta e più invenzioni è peggiore, per questo progetto, di
   uno più conservativo.

## ADR-038 — Una scansione è il rendering dello stesso documento, non un documento diverso
**2026-08-10.** Lo sweep sul degrado ha trovato che i parametri (blur,
downscale, qualità JPEG) non sono il collo di bottiglia: anche a
quasi-lossless il recupero OCR resta al 13%, POD 2/10. Il muro è il **font**:
`_pdf_scansione` disegna il testo con `ImageFont.load_default()`, la bitmap
minuscola integrata in PIL (~11px). Il tetto è fissato prima che qualunque
degrado entri in gioco.

Il difetto non è parametrico, è di modello. Il generatore costruisce la pagina
scansionata come **un documento diverso**, disegnato con altri strumenti. Una
scansione reale non è questo: è **la stessa pagina stampata, fotografata**.
Stessa tipografia, stesso impaginato, poi rumore.

**Decisione.** Il percorso scansione si ottiene per rasterizzazione:

    layout reportlab (identico al digitale)
      -> render PNG ad alta risoluzione
      -> degrado (blur / downscale / JPEG)
      -> pagina immagine

Nessun disegno di testo con PIL. Il contenuto della versione scansionata è per
costruzione identico a quello digitale, il che rende confrontabili le due
metà del corpus: stessa verità, due qualità di input.

Solo dopo questa correzione lo sweep sul degrado ha senso, perché il tetto
diventa la tipografia reale del documento invece di un font giocattolo.

**Quarto difetto del generatore in quattro misure.** Copertura immagine
tautologica (ADR-021), scansioni a zero caratteri (ADR-019), degrado
illeggibile (ADR-036), ora il font. Il codice è stato revisionato a ogni
passo; il generatore quasi mai — eppure è la base di ogni numero pubblicato.
Da qui in avanti riceve la stessa disciplina: ogni suo parametro è una soglia,
ogni sua scelta di rendering è una decisione da motivare.

## ADR-039 — Struttura osservata: luce e gas (nessun dato reale)
**2026-08-10.** Osservazione strutturale su bollette reali. **Nessun valore
reale è riportato qui né entra nel repo**: solo la forma, che è know-how
trasferibile (ADR-002, ADR-012).

### Luce — invarianti di layout

- POD in pagina 2, in un blocco con potenza impegnata e disponibile
- "Scontrino dell'energia": quota per consumi / quota fissa / quota potenza /
  accise e IVA / totale, con colonne quantità - prezzo medio - importo
- "Box dell'offerta": nome, tipologia (fisso/variabile), tipologia prezzo
  (monoraria/fasce), codice offerta, scadenze, formula, indice PUN
- "Letture e consumi": tabella con lettura precedente e attuale, segnanti per
  fascia, consumo fatturato per fascia
- Imposte: accisa per scaglioni di periodo, poi IVA con base imponibile

### Gas — differenze sostanziali dal luce

| | luce | gas |
|---|---|---|
| identificativo | POD, `IT` + 3 cifre + `E` + 8 | PDR, 14 cifre numeriche |
| unità | kWh | Smc |
| fasce | F1/F2/F3 | assenti, sempre monorario |
| indice | PUN | PSV |
| quota potenza | presente | assente |
| coefficiente | — | coefficiente C (mc → Smc) |
| pronto intervento | distributore elettrico | distributore gas, numero diverso |

Il gas **non è il luce con altri nomi di campo**: sparisce l'intera dimensione
fasce (3 campi su 10), sparisce la quota potenza, compare la conversione
volumetrica. Uno schema gas non si ottiene rinominando quello luce.

Conferma dell'impostazione dichiarativa: sono due YAML diversi, zero codice
nuovo. Ma resta subordinato a G2 — nessun secondo schema prima di un numero
pubblicato e un utente esterno.

### Casi limite aggiuntivi osservati
- Stesso fornitore, stesso cliente, luce e gas in due fatture separate con
  codice utenza diverso e numero fattura contiguo
- Periodo espresso come nome del mese anche sul gas
- Consumo annuo dichiarato su finestra mobile di 12 mesi, distinto dal periodo
  fatturato — fonte del caso "trimestrale dichiarato annuale" (ADR-013)

## ADR-040 — Bollette reali di terzi: solo struttura, mai dato personale
**2026-08-11.** Estensione di ADR-012/ADR-039 a un corpus di 22 bollette
reali di terzi (16 fornitori, luce e gas) ricevuto in un archivio fuori dal
repo. ADR-012 aveva già rifiutato 3 bollette reali non consenzienti; questo
archivio ne conteneva di più, con nominativi nei nomi file — stesso problema
a scala maggiore, non un'eccezione.

**Regola applicata, vincolante per ogni ispezione futura di documenti reali
di terzi:** l'ispezione avviene per estrarre *solo* forma — layout, posizione
campi, formati data/numero, elementi grafici, struttura del documento — mai
un valore reale (nome, indirizzo, POD/PDR, codice fiscale, IBAN, importo o
consumo esatto, numero cliente/contratto). Il report di chi ispeziona deve
essere verificabile come privo di PII prima di essere letto o salvato in
qualunque file del progetto (memoria inclusa). L'archivio originale resta
fuori dal repo, mai copiato dentro; l'estrazione avviene in una scratchpad
temporanea fuori da git, cancellata a fine sessione.

### Esito dell'ispezione (22 file, 16 fornitori)

Qualità del lotto grezzo: 4 file fuori perimetro (2 bollette gas archiviate
nella cartella luce, 1 fattura fibra non energia, 1 file con pagine di un
documento d'identità scansionato allegate) — segnalazione sulla cura del
lotto, non un dato su cui decidere.

**Gap più rilevante, priorità ALTA:** il generatore sintetico
(`scripts/genera_corpus.py`) rende ogni importo con `str(Decimal(...))`,
quindi sempre punto decimale (`123.45`). Le 22 bollette reali usano **sempre**
la virgola decimale italiana (`123,45`), mai il punto. La regex del tier 0
per i campi decimali (`schemas/bolletta_luce_it.yaml`) cerca `[\d.]+` — non
contiene la virgola nella classe di caratteri, quindi su un vero numero
italiano non troverebbe nulla, non un valore sbagliato: un buco di copertura
del corpus che nasconde un probabile buco reale nell'estrazione. `repair.py`
gestisce già correttamente la virgola (mai esercitato dal corpus finora).

Altri gap osservati, non affrontati in questa sessione (vedi
`docs/04-roadmap.md`): formati data più vari, IVA su aliquote miste nello
stesso documento, canone RAI/sconti come righe extra, documenti 4-16 pagine
con allegati (moduli SEPA/pagoPA) contro le 3 fisse del generatore, un
generatore gas (bloccato da G2), grafici che portano dati (barre/torta,
mai renderizzati dal generatore).

## ADR-041 — Pagina allegata: assorbita nella segmentazione per costruzione
**2026-08-11.** Estende ADR-040 (T4.14): il generatore ora sa produrre una
pagina di modulo di pagamento allegata dopo le `PAGINE_PER_FATTURA` (3)
pagine vere di una fattura (`Flags.pagine_allegate`, caso
`documento_con_allegato` in `COMPOSIZIONE_DEFAULT`) — pattern osservato su
piu' bollette reali (bollettino postale, modulo SEPA, avviso pagoPA).

**Non contraddice ADR-039** ("una fattura digitale e' sempre a tre pagine"):
resta vero per il CONTENUTO della fattura. La pagina allegata e' aggiuntiva,
non parte del conteggio.

**Comportamento atteso, non un difetto da correggere qui**: la pagina
allegata non contiene alcun marcatore "Fattura n." — la segmentazione
(`sacor.segmentation._riempi_in_avanti`) la assorbe per costruzione
nell'istanza precedente (nessun nuovo match = stessa istanza aperta).
L'intervallo di pagine rilevato (es. 1-4) non combacia con la verita' dei
metadata (1-3, ADR-025: ground truth esclude l'allegato) — un mismatch
`intervalli_pagine` atteso e misurato, stesso principio di S011 (ADR-024).
Costruire un rilevatore di "pagina non-fattura" e' un item MEDIA a se',
non incluso qui: servirebbe classificare il contenuto della pagina, non solo
misurare l'assenza del marcatore.

**Verificato**: l'estrazione dei campi tracciati (pod, importo_totale, ecc.)
resta corretta nonostante l'istanza si estenda anche sulla pagina allegata
— le regex cercano etichette specifiche, non l'intero contenuto della
pagina, e la pagina allegata non ne contiene nessuna.
