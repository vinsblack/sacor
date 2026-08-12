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

## ADR-042 — Corpus reale: oracle con consenso, PDF mai nel repo

**2026-08-11.** Prima misura di sacor contro bollette **vere**, non
generate dal progetto. Consenso esplicito ottenuto da Vincenzo Gallo dalle
persone che hanno fornito i 22 PDF dell'archivio ADR-040, per l'uso dei
dati tecnici delle loro bollette a fini di misura (non per la
pubblicazione dei PDF stessi — due consensi distinti, vedi sotto).

### Cosa entra nel repo, cosa no

- `corpus/reale/attesi.json` + `metadata.json`: SOLO i 10 campi schema +
  note tecniche (fasce, consumo stimato, anomalie). Mai nome, indirizzo,
  codice fiscale/P.IVA, IBAN, numero cliente/contratto, telefono, email.
- `corpus/reale/raw/` (i PDF): **mai nel repo**, `.gitignore`. Un PDF con
  POD/importi/date esatte resta un dato collegabile a una persona anche
  senza un nome scritto sopra — e il repo diventerà pubblico. Consenso
  all'uso per misurare ≠ consenso a pubblicare, due cose distinte, il
  secondo non è stato chiesto né dato.

### Scope: 14 documenti su 22, non tutti utilizzabili

Solo bollette **luce** valgono per questo schema (POD/kWh, non PDR/Smc).
Un file (assegnato R008 in estrazione) si è rivelato una fattura
FIBRA/telecom archiviata per errore tra le bollette — escluso durante
l'estrazione stessa, non prima: la verità del contenuto ha prevalso su
un'ipotesi di scope fatta a monte.

### Primo numero reale: 5.7%, non 45.3%

`eval/run_reale.py` (nuovo, senza triage/segmentazione — ogni PDF reale è
un'unica istanza nota) misura **8/140 campi corretti = 5.7%** contro il
corpus reale, contro il 43.6-45.3% misurato finora sul solo corpus
sintetico. Non è un fallimento del lavoro fatto finora — è la conferma
diretta che **il numero sintetico non è mai stato predittivo**: le regex
tier 0 sono ancorate alle etichette esatte del generatore ("Importo
totale: EUR", "Energia F1: ... kWh"), i fornitori reali usano struttura e
lessico del tutto diversi (ADR-040). Un corpus autoconsistente misura se
il generatore e lo schema si parlano tra loro, non se il sistema legge
bollette vere — le due cose sono sempre state domande diverse, ora c'è un
numero che le distingue.

**Non affrontato qui**: rendere il tier 0 (o il tier 1) capace di leggere
le etichette reali è lavoro a parte, grande, non fatto in questa sessione.
Questo ADR fissa solo il metodo di misura e il primo numero onesto.

## ADR-043 — Bake-off tier 1 sul corpus reale: anche l'AI fatica

**2026-08-11.** `scripts/bakeoff_reale.py` (nuovo, stessa logica di
scripts/bakeoff.py puntata a `corpus/reale`), 14 chiamate, $2.05 spesi
(sotto il tetto $5). Nessuna chiamata fallita, nessun file saltato.

| Modello | Acc. campo | Acc. documento | Costo/doc | Inventati |
|---|---|---|---|---|
| claude-haiku-4-5 | 9.0% | 0.0% | $0.0142 | 14/14 |
| claude-opus-5 | 14.3% | 0.0% | $0.1322 | 7/14 |

**Non è un problema di tier0-vs-AI.** Il tier 1 (vera chiamata al modello,
non regex) resta comunque molto basso sui campi che gli sono stati chiesti
(quelli che il tier 0 non ha trovato — quasi tutti, vedi ADR-042). **0.0%
documenti corretti su entrambi i modelli.**

**Il segnale più serio non è l'accuratezza, è `inventati`**: 14/14 per
haiku, 7/14 per opus — il modello non si astiene su un campo che non
riconosce, risponde con un valore sbagliato con sicurezza. Per la
disciplina del progetto (ADR-037: "su input illeggibile il modello
inventa") è il fallimento peggiore possibile — peggio di un `None` onesto.

**Ipotesi, non verificata**: il prompt (`sacor.providers.prompt.
costruisci_prompt`) è generico sui 10 campi schema, non tarato sulla
diversità reale catalogata in ADR-040 — fasce F1/F23 vs F1/F2/F3, canone
RAI + doppio totale, formule di offerta diverse per fornitore, sotto-righe
"di cui vendita/rete". Un modello capace potrebbe comunque confondersi
senza indicazioni su QUALE dei più numeri candidati sulla pagina è il
campo richiesto.

**Non affrontato qui**: riprogettare il prompt per la diversità reale è
lavoro a parte, non fatto in questa sessione. Questo ADR fissa solo la
misura e la sua interpretazione onesta.

## ADR-044 — Il vero bug non era il prompt: parsing scartava numeri JSON

**2026-08-11.** Correzione di ADR-043. Il primo tentativo di fix
(disambiguazione nel prompt, ADR-043) non aveva spostato i numeri perché
non era quello il problema — nessuno aveva mai guardato una risposta vera
del modello prima di ipotizzare.

**Metodo che ha trovato il bug**: `scripts/diagnosi_reale.py` (nuovo) ha
dumpato la risposta grezza di claude-haiku-4-5 su 4 documenti reali, PRIMA
di qualunque parsing. Un agente ha letto quel dump riga per riga contro
l'oracle. Diagnosi concreta, non un'altra ipotesi: il modello rispondeva
correttamente (es. `"kwh_f1": 11.5`), ma `sacor.providers.parsing.
normalizza_risposta()` accettava SOLO valori JSON di tipo stringa
(`grezzo if isinstance(grezzo, str) else None`) — un numero JSON nativo
(comportamento normale, valido, non un errore del modello) veniva scartato
a `None` prima ancora di arrivare a `ripara()`. Nessun test esistente
copriva questo caso (solo "campo assente" e un campo `string`).

**Fix**: `_a_stringa()` accetta `int`/`float` per campi `decimal`, `int`
(o `float` intero, es. `30.0`) per campi `integer` — mai per `string`/
`date`, `bool` escluso esplicitamente (sottoclasse di `int` in Python).

**Impatto misurato** (`scripts/bakeoff_reale.py`, stesso corpus, stesso
prompt di ADR-043, $2.08 spesi):

| Modello | ADR-043 (bug presente) | Dopo il fix | Fattore |
|---|---|---|---|
| claude-haiku-4-5 | 9.0% | **43.6%** | 4.8x |
| claude-opus-5 | 14.3% | **51.9%** | 3.6x |

**Lezione di metodo, non solo di codice**: due cicli di misura-ipotesi-fix
falliti (ADR-042→043) prima di questo, entrambi basati su ipotesi mai
verificate contro un dato grezzo concreto. Il terzo ciclo, quello che ha
funzionato, è iniziato leggendo una risposta vera invece di ipotizzarne il
contenuto — "misura prima" vale anche per la diagnosi, non solo per
l'accuratezza finale.

**Non ancora risolto**: 0.0% documenti completamente corretti resta
(nessun documento ha TUTTI i campi giusti). Il dump diagnostico ha trovato
altri due pattern reali, non ancora affrontati: `giorni` risposto `null`
anche quando calcolabile dalle date presenti (mancanza di un'istruzione di
fallback nel prompt); `importo_totale` che in 2/4 casi prende un subtotale
invece del totale finale, per una differenza costante di €18.00 in due
bollette di fornitori diversi (probabile riga di onere fisso saltata).

**Addendum — fix `giorni` misurato**: descrizione aggiunta al campo
(calcolo da `periodo_da`/`periodo_a` quando non scritto esplicitamente).
Impatto: claude-haiku-4-5 invariato (43.6%), claude-opus-5 **51.9% →
54.9%**. Effetto reale ma piccolo — non risolve da solo lo 0.0% documenti.

**`importo_totale`/subtotale — RISOLTO, era un bug mio, non del modello.**
`pdftoppm` installato (utente), R010 e R013 ispezionati a occhio (immagine
vera, non solo testo). Entrambe hanno un "Canone di abbonamento alla
televisione" di **€18,00 esatto**, sommato sopra un "Totale Bolletta" per
dare il "Totale da Pagare" (R010: 98,20+18,00=116,20; R013:
138,22+18,00=156,22). Il modello aveva risposto 98,20 e 138,22 — **letto
giusto**, seguendo alla lettera la descrizione scritta in ADR-043 ("usa il
totale energia, MAI un importo con canone"). L'oracle invece usa sempre
"Totale da pagare" (con canone) — stessa scelta, con nota esplicita, già
fatta per R003/R005/R006/R007. **Prompt e oracle si contraddicevano**,
scritti in momenti diversi senza incrociarli — non un limite del modello.

Fix: descrizione invertita — "Totale FINALE da pagare... SEMPRE quello
finale/più alto", allineata alla convenzione che l'oracle già usava.

**Impatto misurato**: claude-haiku-4-5 **43.6% → 47.4%**, claude-opus-5
**54.9% → 60.9%**. `inventati` sceso in entrambi (haiku 34→26, opus
22→15) — coerente: un campo letto giusto ma scartato dalla vecchia
descrizione ora è corretto invece di sbagliato.

**Riepilogo dell'intero ciclo ADR-042→044** (stesso corpus, stesso
oracle, 4 giri di bake-off, ~$8.30 spesi in totale):

| | claude-haiku-4-5 | claude-opus-5 |
|---|---|---|
| Bug parsing presente (ADR-043) | 9.0% | 14.3% |
| Fix parsing (ADR-044) | 43.6% | 51.9% |
| + fix `giorni` | 43.6% | 54.9% |
| + fix `importo_totale` | **47.4%** | **60.9%** |

0.0% documenti completamente corretti resta su tutti e 4 i giri — nessun
pattern residuo grande quanto i tre risolti è stato ancora trovato.

## ADR-045 — Lo strato Arbitrate non esiste: piano per costruirlo

**2026-08-11.** Verifica del disegno a 7 strati (docs/01-architecture.md)
contro il codice reale: lo strato "Arbitrate" (confronto fonti, tolleranze)
è dichiarato ma non implementato. `sacor.invariants` è solo un registro di
TIPI noti (`somma_approssimata`, `differenza_giorni`), usato da
`sacor.schema` per validare che le invarianti dichiarate nello YAML
referenzino campi esistenti — nessun codice valuta mai un'invariante
contro un set di valori estratti. La conferma pratica di oggi (ADR-044,
R010): F1+F2+F3=91 contro un totale dichiarato 277 dallo stesso modello
nella stessa risposta — un'incongruenza aritmetica banale, trovata a mano
da un agente, che l'invariante `somma_fasce` avrebbe segnalato in
automatico se fosse mai stata eseguita.

Analogamente, "due provider sempre" (ADR di continuità di servizio) non è
mai stato usato come arbitrato reale: bake-off testa ogni modello contro
l'oracle separatamente, mai un modello contro l'altro. Il disaccordo tra
due letture indipendenti è il segnale di bassa confidenza più forte
disponibile — oggi scartato.

### Piano (atomico, in ordine)

**Fase 1 — motore invarianti (zero costo API, solo codice+test)**
1. `invariants.py::valuta(invariante, valori) -> Violazione | None` — una
   funzione per tipo, pura, TDD
2. `invariants.py::valuta_tutte(schema, valori) -> tuple[Violazione, ...]`
3. Wire post-estrazione (tier0 e tier1): ogni risposta porta anche le
   violazioni trovate, non solo i valori
4. Gate: severità `reject` su un'invariante violata rigetta il documento
   — oggi il gate reagisce solo a un campo obbligatorio assente, mai a
   un'incongruenza aritmetica
5. `eval/run.py`/`scripts/bakeoff*.py`: violazioni contate come metrica
   separata — segnale valido anche SENZA oracle (in produzione l'oracle
   non c'è, l'invariante sì)

**Fase 2 — arbitrato tra due provider (raddoppia il costo tier1, decisione
da prendere prima di costruire, non solo tecnica)**
6. `estrai_con_arbitrato(istanza, campi, provider_a, provider_b)` — chiama
   entrambi, confronta campo per campo
7. Misurare sul corpus reale (con oracle, solo ora misurabile): frequenza
   di disaccordo, e quando disaccordano chi ha ragione più spesso
8. Decisione: arbitrato sempre attivo, o solo quando il tier1 singolo
   viola già un'invariante (tier "1.5" più economico, innescato dal
   segnale della Fase 1)

**Fase 3 — bloccata da dati, non da codice**
9. Più bollette tue/consenzienti; rimisurare con arbitrato attivo

Si comincia dalla Fase 1: più preziosa, più economica, nessuna chiamata
API in più.

## ADR-046 — Tasso di escalation reale: 100%, non n/d

**2026-08-11.** `docs/03-current-state.md` e il mirror Notion riportano
"Tasso di escalation: n/d" da sempre — mai calcolato, non perché manchi
il dato ma perché nessuno l'ha chiesto esplicitamente. Il dato c'era già
in `eval/run.py::istanze_da_completare()`: **14 documenti reali su 14
hanno richiesto almeno una chiamata tier1** (`chiamate` non è mai vuoto
per nessun documento del corpus reale, prima e dopo i fix T4.17). Tasso
di escalation reale: **100%**, non "n/d".

Questo confronta direttamente con il criterio di stop già dichiarato nel
mirror Notion (North Star, mai scritto qui prima): *"tasso di
escalation — sopra il 20% il margine evapora"*. 100% è 5x sopra quel
limite. Non è un'anomalia di una release: è la situazione da quando
esiste un corpus reale (ADR-042).

**Cosa NON significa**: non che il prodotto sia inviabile. Il costo per
documento con tier1 economico (claude-haiku-4-5) è basso in assoluto
($0.005-0.015/doc misurato nei bake-off) — il problema non è il costo
della chiamata, è che l'architettura dichiarata ("tier0 assorbe l'80-90%,
tier1 solo il resto") descrive un sistema che il corpus reale non
conferma. tier0 su 14 documenti reali non ne ha chiuso NESSUNO da solo,
nemmeno dopo T4.17 (16.4%/campo, ancora lontano da chiudere un
documento intero senza tier1).

**Decisione (chiesta esplicitamente, non assunta)**: il bersaglio di G1
resta **accuratezza per campo alta su tutto lo schema**, non una
scorciatoia via gate/confidenza che accetti un'accuratezza più bassa
purché segnalata. Conseguenza diretta: la Fase 3 di ADR-045 (più corpus
reale — oggi 14 documenti, 11 fornitori diversi, n≈1.3/fornitore) passa
da "bloccata da dati, non urgente" a **il vero collo di bottiglia per
G1**. Continuare a ottimizzare tier0/tier1 sui 14 documenti attuali ha
reso rendimenti decrescenti già visibili (T4.17: `fornitore`/`kwh_f1-3`/
`giorni` non chiudibili senza overfit su questo campione). Senza più
bollette reali/consenzienti, il prossimo miglioramento di accuratezza
generalizzabile è strutturalmente difficile da ottenere, non solo da
misurare.

**Non ancora deciso, prossima sessione**: da dove arrivano più bollette
reali consenzienti (proprie dell'utente, community, altro canale) — è
una decisione di prodotto/canale, non tecnica, va presa esplicitamente
prima di continuare a scrivere codice sui 14 documenti attuali.

## ADR-047 — Visione di prodotto: infrastruttura di fiducia, non parser

**2026-08-11.** Decisione di prodotto dell'utente, testuale (non
riassunta, per non perdere sfumature): sacor non deve diventare un
semplice estrattore di documenti, ma **il livello di affidabilità che
oggi manca tra i modelli AI e i software gestionali**. Il vero prodotto
non è il parser, è la capacità di trasformare un documento in dati
verificati con un livello di fiducia misurabile.

**Tre fasi**:
1. Open source — credibilità tecnica, benchmark pubblici, community
2. Ecosistema — pacchetto Python, nodo n8n, API, plugin per i
   principali workflow documentali
3. Business — piattaforma enterprise: API gestite, supporto,
   monitoraggio, self-hosted, strumenti di validazione avanzata

**Posizionamento**: non competere con convertitori PDF/OCR generici
(mercato affollato, il prezzo è il fattore competitivo). Posizionarsi
dove un errore ha un costo economico misurabile — energia,
assicurazioni, banche, logistica, sanità, amministrazione. Bollette
luce resta il primo campo di prova, non il mercato finale — questo
riduce (non elimina) il dubbio sollevato in sessione sul mercato
stretto: la nicchia bollette è la dimostrazione, non il tetto.

**Caratteristica da rafforzare**: misurazione continua. Ogni rilascio
pubblica metriche verificabili, mostrando dove il sistema è affidabile
e dove richiede ancora supervisione — coerente con `docs/00-north-star.md`
("il gate è una feature"), qui reso esplicito come impegno permanente
di prodotto, non solo principio tecnico.

**Investimento fondamentale**: distribuzione. Integrazioni semplici,
documentazione eccellente, esempi concreti. L'obiettivo è diventare il
motore che altri sviluppatori scelgono di integrare perché si fidano
dei risultati — il business nasce sopra quella reputazione, non prima.

**Tensione esplicitamente sollevata e risolta nella stessa sessione**:
la Fase 1 (open source) potrebbe suggerire di pubblicare SUBITO con
benchmark onesti anche se imperfetti (trasparenza come credibilità
immediata). Chiesto esplicitamente: **G1 resta subordinato ad
accuratezza per campo alta** (decisione ADR-046 riconfermata, non
sostituita). La Fase 1 si costruisce con numeri buoni resi pubblici,
non con numeri onesti ma deboli — vedi `docs/00-north-star.md`.

**Effetto pratico su ADR-045/046**: nessuno immediato sul codice. Il
collo di bottiglia resta lo stesso (più corpus reale, Fase 3 ADR-045) —
questa visione ne conferma l'urgenza, non la cambia. Cambia però la
cornice con cui leggere le prossime decisioni tecniche: ogni scelta di
API/schema/plugin va giudicata anche su "aiuta l'ecosistema (Fase 2) a
integrarsi facilmente", non solo su accuratezza pura.

## ADR-048 — Revoca il gate G1 di ADR-046/047: si pubblica ora, il corpus è conseguenza dell'adozione

**2026-08-11, stessa sessione.** Decisione dell'utente, che revoca
esplicitamente la parte di ADR-046 e ADR-047 che subordinava G1 ad
"accuratezza per campo alta su tutto lo schema" (riconfermata due volte
in poche ore, prima di questa revoca — stesso pattern di ADR-031 che
revoca ADR-029: non si riscrive la storia, si registra il cambio idea).

**Argomento**: i 15 documenti reali hanno già assolto il loro scopo —
misurare il gap sintetico/reale, invalidare l'ipotesi "tier0 assorbe
l'80-90%" (ADR-046: escalation reale 100%), dimostrare che il motore di
misura funziona. Continuare a ottimizzare sugli stessi 15 documenti
produce rendimenti decrescenti (già osservato, T4.17) e rischio di
overfitting, non più segnale nuovo. **Il collo di bottiglia non è più
l'algoritmo — è la distribuzione.** Aspettare più dati prima di
pubblicare rischia di non pubblicare mai; il corpus deve crescere come
conseguenza dell'adozione, non come suo prerequisito.

**Riformulazione esplicita**: dove ADR-046/047 dicevano "non si pubblica
un benchmark con numeri deboli solo perché onesto", questa decisione
dice l'opposto — si pubblica un motore onesto, con i suoi limiti
dichiarati chiaramente (accuratezza reale attuale inclusa, non
nascosta), e si lascia che i primi utilizzatori esterni segnalino dove
migliorarlo. Non è "abbassare lo standard di onestà" (quello resta
intatto, anzi è il prodotto) — è cambiare COSA sblocca G1.

**Nuove priorità, in ordine** (sostituiscono "più corpus reale" come
prossimo passo):
1. Pacchetto PyPI installabile
2. CLI (`sacor extract file.pdf`)
3. Documentazione di integrazione (quickstart, esempi)
4. Nodo n8n
5. API stabile
6. Primo utilizzatore esterno

**Cosa NON cambia**: la disciplina di misura resta identica — si
pubblica CON i numeri reali attuali (50-61%/campo, 0% documento,
escalation 100%), dichiarati, non nascosti né minimizzati. Cambia solo
il criterio di stop per G1: non più "aspetta che i numeri siano alti",
ma "pubblica onesto, migliora in pubblico".

## ADR-049 — Arbitrato haiku/opus sul reale: il disaccordo non è un
segnale utile, si usa solo opus

**2026-08-12.** Prima esecuzione di `sacor.arbitrate` (ADR-045 Fase 2)
sul corpus reale — codice pronto da ADR-045, mai lanciato sul reale
prima d'ora. `scripts/bakeoff_reale.py --arbitrato claude-haiku-4-5
claude-opus-5 --solo-arbitrato` (nuovo flag: salta il bake-off
per-modello già misurato in ADR-044, misura solo la coppia in
arbitrato — evita di ripagare un numero già noto). 15/15 documenti,
126 campi confrontati, $2.2339 spesi (tetto $5, non raggiunto).

**Misura**:

| | |
|---|---|
| Disaccordo (campi) | 31.0% (39/126) |
| Quando disaccordano — opus ha ragione | 21/39 |
| Quando disaccordano — haiku ha ragione | 8/39 |
| Quando disaccordano — nessuno dei due | 10/39 |
| Accuratezza quando concordano | 56.3% |

**Interpretazione**: l'ipotesi di ADR-045 (il disaccordo tra due
provider è il segnale, non va risolto scegliendo uno dei due) regge
solo a metà sul reale. Regge la prima parte: quando concordano, sono
corretti solo il 56.3% delle volte — l'accordo non è affidabile quanto
sperato, quindi va bene non trattarlo come oracolo implicito. Ma la
conseguenza pratica è negativa: un arbitro che, in caso di disaccordo,
si fidasse sempre di opus otterrebbe 21/39 = 53.8% — peggio che
fidarsi di opus da solo su tutto (60.9%/campo, ADR-044). L'arbitrato
raddoppia il costo per chiamata e non migliora l'accuratezza rispetto
a un singolo modello forte.

**Decisione (dell'utente)**: tier1 usa **solo claude-opus-5**, non
arbitrato multi-provider. `sacor.arbitrate` resta nel codice (potrebbe
tornare utile con un corpus più grande o provider diversi — non
rimosso, YAGNI si applica a "usarlo ora", non a "cancellarlo"), ma non
è la strada per migliorare l'accuratezza con l'informazione attuale.

**Non cambia** la priorità di ADR-048 (distribuzione prima di altro
tuning) — questa misura chiude un pending item lasciato aperto
(arbitrato mai lanciato sul reale), non riapre la fase di
ottimizzazione sui 15 documenti.

## ADR-050 — Prima misura combinata tier0+tier1 sul reale: 62.7%/campo,
0% documento, periodo_da/periodo_a non risolto dopo tre tentativi

**2026-08-12.** Prima misura end-to-end di `sacor extract --tier1` sul
corpus reale (15 doc) — nessuno script precedente misurava il
combinato: `bakeoff_reale.py` solo i campi chiesti a tier1,
`diagnosi_tier0_reale.py` solo tier0. Nuovo script permanente
`scripts/misura_reale_combinato.py`.

**Numero onesto, aggiornato** (sostituisce il vecchio "0% documento"
tier0-only citato in ADR-046/048, che era superato dal lavoro di questa
stessa sessione — tier1 ora e' wired nella CLI):

| | tier0 solo (T4.17) | tier0+tier1 combinato (oggi) |
|---|---|---|
| Per campo | 16.4% | **62.7%** (94/150) |
| Per documento | 0% | **0%** (0/15) — invariato |

Campi forti: pod 100%, giorni 100%, importo_totale 100%. Campo debole
isolato: periodo_da 13.3%, periodo_a 20.0% — unico blocco reale del
62.7%→documento intero.

**Diagnosi vera** (`scripts/diagnosi_periodo_reale.py`, nuovo, 15 doc x
2 campi): 25/30 astensioni (null), **0 sbagliati**. tier1 non indovina
mai male su questo campo — si rifiuta sempre quando non trova un match
sicuro. I 5 corretti vengono tutti da tier0/regex, zero da tier1.

**Causa isolata, verificata sul testo reale (R001, zero costo)**: le
bollette dichiarano un mese di riferimento intero ("Periodo di
fatturazione Settembre 2025"), mai un range giorno-preciso esplicito —
e il periodo reale e' sempre primo→ultimo giorno di quel mese su tutti
e 15 i documenti (convenzione bolletta mensile italiana).

**Tre tentativi di fix, in ordine, TUTTI falliti a muovere il numero
(13.3%/20.0% costante su tutti e tre)**:
1. `descrizione` con esempi ed esclusioni (etichette da NON confondere)
2. `descrizione` con autorizzazione esplicita a dedurre primo/ultimo
   giorno da un mese di riferimento
3. Fix di un conflitto VERO nel prompt (trovato leggendo il prompt
   costruito davvero, non indovinato): la regola generale sui campi
   data ("NON dedurre mai il giorno da un mese") contraddiceva quasi
   parola per parola l'eccezione appena aggiunta al punto 2 — corretto
   in `sacor/providers/prompt.py` (la descrizione del campo ora dichiarata
   esplicitamente prevalente sulla regola generale). Bug reale, tenuto
   nel codice — ma zero impatto sul numero misurato.

**Costo di questa caccia**: ~$6 in chiamate reali su 4 giri di misura/
diagnosi in un pomeriggio, per zero guadagno sul campo bersaglio.
**Riconosciuto esplicitamente**: e' lo stesso pattern di rendimenti
decrescenti che ADR-048 aveva gia' nominato come motivo per fermare
l'ottimizzazione sui 15 documenti — ripetuto oggi nonostante fosse gia'
scritto. La causa vera di periodo_da/periodo_a non e' isolata (serve
vedere il *reasoning*/risposta grezza del modello, non solo il JSON
finale — un salto di diagnosi non ancora fatto).

**Decisione**: fermare la caccia a periodo_da/periodo_a per questa
sessione. Il fix del conflitto prompt resta (era un bug vero,
indipendente dal risultato). Tornare alla priorita' di ADR-048
(distribuzione) — periodo_da/periodo_a resta un gap noto e dichiarato,
non nascosto, candidato a essere il primo problema che un utilizzatore
esterno segnala con un caso reale nuovo (esattamente il meccanismo che
ADR-048 prevede per il miglioramento post-pubblicazione).

## ADR-051 — Riparazione aritmetica dai campi noti: 62.0%→65.3%/campo,
periodo_da/periodo_a 13-20%→33%

**2026-08-12, stessa sessione di ADR-050.** Analisi con l'utente
dell'approccio "passa la bolletta passo passo nella pipeline, osserva,
ripara" — ispirato ai guardrail di VERO (CONGUAGLIO, VOCI_DRIFT:
mai un solo segnale, sempre un secondo indipendente che veta il primo
se implausibile). Le invarianti gia' dichiarate in sacor
(`differenza_giorni`, `somma_approssimata`) diventano bidirezionali:
se esattamente un termine manca e gli altri sono noti e validi, si
calcola invece di lasciarlo a tier1/null — non e' un'indovinare, e' la
stessa formula gia' usata per validare, applicata al contrario.
Nuova funzione `sacor.invariants.deriva_mancanti()`, generica per
schema (ADR-017): risolve sia periodo_da/periodo_a/giorni sia
kwh_f1/f2/f3/totale con lo stesso codice. Girata PRIMA di tier1
(risparmia la chiamata se basta l'aritmetica) e di nuovo dopo (tier1
puo' sbloccare una derivazione prima impossibile). Confidenza
"derivato" -> media (eredita l'incertezza degli input).

**Due bug di misura trovati per strada, prima del numero vero**:
1. Prima "rimisura" contaminata da credito Anthropic esaurito a meta'
   giro (4/15 doc falliti) — scartata, non confrontabile.
2. Rimisura pulita (post-ricarica) mostrava ZERO cambiamento
   (62.0%→62.0%, periodo invariato) nonostante la derivazione fosse
   gia' committata e testata in isolamento (11 test verdi). Causa:
   `scripts/misura_reale_combinato.py` e `scripts/diagnosi_periodo_
   reale.py` REIMPLEMENTAVANO tier0+tier1 a mano (scritti prima di
   `deriva_mancanti()`, mai aggiornati) — non chiamavano mai
   `sacor.pipeline.estrai_file()`, quindi misuravano una pipeline
   diversa da quella che `sacor extract --tier1` esegue davvero.
   Trovato con un test isolato gratuito (nessuna chiamata reale) prima
   di sospettare la funzione — la funzione era giusta, lo script no.
   Riscritti entrambi per chiamare `estrai_file()` (DRY: restano
   sincronizzati con la pipeline vera, non la duplicano).

**Numero vero, dopo il fix degli script** (corpus reale, 15 doc,
$2.06):

| | prima (ADR-050) | dopo |
|---|---|---|
| Per campo | 62.0% | **65.3%** (98/150) |
| periodo_da | 13.3% | **33.3%** |
| periodo_a | 20.0% | **33.3%** |
| Per documento | 0% | **0%** — invariato |

Miglioramento reale sui campi bersaglio (+20 punti ciascuno), ma
insufficiente a chiudere un documento intero: fornitore (33%) e kwh_f1
(53%) restano il prossimo collo di bottiglia.

**Lezione sul processo, non solo sul numero**: il primo istinto ("il
numero non si muove, la funzione dev'essere sbagliata") era sbagliato
— la funzione era corretta (provata da 11 test unitari), lo strumento
di misura si era disallineato dalla pipeline reale. Verificato con un
test isolato gratuito PRIMA di sospettare altro — lo stesso principio
di "diagnosi vera prima del fix" di ADR-050, applicato questa volta
alla misura stessa, non solo al motore.

## ADR-052 — Confronto case-insensitive + descrizione fornitore:
65.3%→68.7%/campo, primo documento perfetto (0→2/15)

**2026-08-12, stessa sessione di ADR-050/051.** Diagnosi reale
(kwh_f1/f2/f3/totale + fornitore, $2.08): 32/40 "errori" kwh nel primo
giro erano **falsi allarmi dello script diagnostico stesso**
(confrontava stringhe con `==` invece di `sacor.compare.uguali()` —
la pipeline vera già confrontava correttamente via `Decimal`). Solo
8/40 errori kwh reali: 3 su R004 (già segnalati "bassa confidenza"
dal sistema, correttamente), 5 arrotondamenti minori (0.001-0.003).

Per fornitore, stesso pattern ma reale: `sacor.compare.normalizza`
per stringhe faceva solo `.strip()`, case-sensitive — `'SMART ENERGY
S.r.l.'` vs `'Smart Energy S.r.l.'` contava come errore per sole
maiuscole/minuscole. Fix: case-insensitive, applicabile a tutti i
campi string (bug di misura reale, non solo fornitore).

Inoltre `descrizione` per fornitore (stesso meccanismo di periodo_da/
periodo_a, ADR-050): nome commerciale/comune, non forma legale estesa
da note boilerplate ("società soggetta a direzione e coordinamento
di X", "Società Benefit") — il modello aggiungeva questi dettagli
trovati altrove nel documento, l'oracle non li aveva.

**Correzione oracle** (`corpus/reale/attesi.json`, R014/R015): il
gruppo societario tra parentesi non era sul documento come nome
fornitore, solo in una nota legale — corretto per coerenza con R009/
R010 (stesso fornitore, verificato nel testo del PDF prima di
toccare il file, non un tuning per far salire il numero).

**Numero vero, corpus reale, 15 doc, $2.09**:

| | ADR-051 | ADR-052 |
|---|---|---|
| Per campo | 65.3% | **68.7%** (103/150) |
| fornitore | 33.3% | **66.7%** |
| Per documento | 0/15 | **2/15** (13.3%) |

Prima volta nella storia del progetto che un documento reale esce
corretto su tutti e 10 i campi — due, non uno. Partenza di giornata
(tier0 solo, T4.17): 16.4%/campo, 0% documento. Arrivo: 68.7%/campo,
13.3% documento.

**Bilancio della sessione** (ADR-050/051/052, un pomeriggio): CI
riparata (era rotta da 10+ commit), tier1 wired nella CLI, confidenza
per campo reale, derivazione aritmetica, due bug di misura propri
trovati e corretti (non solo bug del motore), un'inconsistenza oracle
corretta con verifica prima di toccarla. Nessun numero corretto senza
prima misurarlo — inclusi i tre tentativi falliti su periodo_da/
periodo_a (ADR-050), lasciati nella storia, non cancellati.

## ADR-053 — Classificazione documento (gas/luce/CTE) prima di
estrarre: mai forzare lo schema sbagliato in silenzio

**2026-08-12, stessa sessione.** Prova empirica richiesta dall'utente:
tre documenti reali esterni al corpus (una bolletta luce, una gas,
una fattura d'acquisto CTE Engie — mai nel repo) passati a `sacor
extract --tier1`. Trovato un bug reale: una bolletta gas ("Borello
Simona", cartella "Bollette_Luce" per errore di chi l'ha archiviata)
letta comunque con lo schema luce — POD segnalato "bassa confidenza"
(giusto: era un PDR gas, formato diverso), ma `kwh_totale` ha preso il
consumo in Smc senza che nulla lo segnalasse. sacor non ha mai saputo
che tipo di documento avesse davanti — si fida sempre di `--schema`
(default: luce), mai controllato.

**Nuovo modulo `sacor.classifica`** (tier0-style: zero AI, un
`Enum TipoDocumento` — luce/gas/cte/sconosciuto). Segnali scelti
leggendo i tre documenti reali, poi verificati sui 15 documenti del
corpus reale prima di fissarli:
- `"periodo di fatturazione"` scartato dopo verifica: troppe varianti
  per fornitore (`periodo oggetto di fatturazione`, `periodo di
  competenza`, `periodo di riferimento`, bare `PERIODO:`) — fragile,
  stesso problema di T4.17 sulle etichette.
- `"totale da pagare"` verificato universale su 6+ fornitori reali
  diversi — unico cancello bolletta/non-bolletta.
- `smc`/`kwh` (parola intera) distinguono gas da luce dentro una
  bolletta.
- `"condizioni economiche"`/`"codice offerta"` senza `"totale da
  pagare"` → CTE (documento di condizioni contrattuali, non un
  consuntivo — per definizione niente importo dovuto).
- Alcuni fornitori (Eni Plenitude, Hera) anteponono una lettera di
  copertina (comunicazione, non dati) alla pagina con l'importo —
  lette le prime 3 pagine, non solo la prima.

**Risultato sul corpus reale** (15 doc, tutti noti essere luce): 6/15
classificati con certezza corretta, 9/15 onestamente "sconosciuto"
(6 completamente scansionati, nessun text layer da leggere — la
classificazione è tier0-style, non prova a indovinare da un'immagine;
3 dopo la lettera di copertina servirebbero più di 3 pagine). **Zero
falsi positivi** — nessun documento classificato nel tipo sbagliato.

**CLI**: senza `--schema` esplicito, classifica prima. `bolletta_luce`
→ schema esistente. `gas`/`cte` → errore chiaro, nessuno schema li
forza nel posto sbagliato (solo bolletta_luce ha uno schema oggi).
`sconosciuto` → resta luce per compatibilità (unico schema esistente,
corpus reale attuale è tutto luce), ma con avviso esplicito su
stderr, non in silenzio — coerente con "dichiara l'incertezza, non la
nascondere" (ADR-047).

**Cosa NON è stato fatto inizialmente**: schema gas e schema CTE non
esistevano — la classificazione era la struttura che li avrebbe resi
sicuri da aggiungere, non l'estrazione stessa.

**Seguito, stessa sessione — schema gas costruito**: `bolletta_gas_it.
yaml`, 7 campi (pdr, fornitore, periodo_da/a, giorni, smc_totale,
importo_totale), 5 invarianti — stesso disegno di luce (giorni_
inclusivi, valore_minimo, ordine_date, formato), zero codice nuovo
(ADR-017). Costruito leggendo i due documenti gas reali della prova
empirica, non un corpus con oracle come luce — **nessuna misura di
accuratezza esiste per questo schema**, dichiarato onestamente. Tier0
verificato sui 2 documenti: 5/7 campi su uno, 1/7 sull'altro (label
diverse per fornitore). Verifica reale end-to-end (`sacor extract
--tier1`, $0.14) sul documento Alperia: **7/7 campi corretti, esito
pass** — prima estrazione gas mai fatta dal motore, subito perfetta su
un documento digitale pulito.

**Seguito, stessa sessione — schema CTE costruito**: `cte_it.yaml`,
8 campi (codice_offerta, fornitore, valido_dal/al, durata_contratto,
tipologia_prezzo, corrispettivo_annuo, onere_recesso), 2 invarianti.
Costruito leggendo l'unico documento CTE reale della prova empirica
(ENGIE eFIX Luce) — stesso avviso di gas, nessun corpus/oracle, nessuna
accuratezza misurata. Layout CTE tabellare/multi-colonna: il testo
estratto da pdfplumber esce interlacciato/corrotto su alcuni campi
(es. "Venditore") anche se l'immagine (tier1) resta leggibile — quei
campi (fornitore) non hanno regex tier0, solo descrizione per tier1.
Tier0 verificato sul documento: 7/8 campi corretti. Verifica reale
end-to-end ($0.045): **8/8 campi corretti, esito pass**.

**Bilancio ADR-053 completo**: tutti e tre i tipi che la
classificazione sa riconoscere (luce/gas/CTE) hanno ora uno schema.
Luce ha una misura vera (corpus reale, 68.7%/campo). Gas e CTE hanno
solo una verifica puntuale (1 documento ciascuno, 7/7 e 8/8) — non
una misura, dichiarato esplicitamente ovunque nel codice e qui.
Prossimo passo naturale per renderli misurabili: un piccolo corpus
gas/CTE con oracle, come fu fatto per luce (ADR-042) — non fatto
stasera, richiede consenso sui documenti come per il reale luce.

## ADR-054 — Prompt caching (cache_control) sul provider Anthropic

**2026-08-12.** Confronto diretto: la spesa API mensile reale di un
altro progetto dell'autore (stesso account, stesso tipo di documenti
analizzati) risultava una frazione del costo per chiamata del tier 1
di sacor, a parita' di account Anthropic. Causa trovata leggendo
`src/sacor/providers/anthropic.py`, non ipotizzata: zero
`cache_control` da nessuna parte nel payload — ogni chiamata tier 1
paga prezzo pieno per tutto, anche quando prompt/istruzioni sono
identici chiamata dopo chiamata (stesso schema, stesso insieme di
campi mancanti, documenti diversi).

Non e' lo stesso meccanismo di ADR-034 (quella e' una cache di
dedup su disco lato eval: stesso `sha256(immagine+prompt+modello+
schema)` gia' visto -> costo zero, chiamata saltata del tutto).
Questa e' la prompt cache **lato server Anthropic**: anche per
chiamate genuinamente diverse (documenti diversi), la parte statica
del prompt (istruzioni/schema, generata da `costruisci_prompt`) puo'
essere riusata a sconto se il prefisso del `content` combacia
byte-per-byte con una chiamata recente. Le due cache sono
complementari, non alternative.

**Decisione.** Nel `content` inviato all'API, il blocco testo
(prompt) va PRIMA e porta `cache_control: {"type": "ephemeral"}`; le
immagini (che cambiano per ogni documento, mai identiche tra
chiamate) vengono DOPO. Il breakpoint di cache copre il prefisso fino
al blocco marcato incluso: mettendo il testo per primo, quel prefisso
e' la parte che si ripete tra documenti diversi con lo stesso insieme
di campi mancanti — le immagini restano fuori dal breakpoint e non
devono combaciare per ottenere lo sconto sulla parte cacheata.

Corollario di costo: `risposta.usage` separa `cache_creation_input_
tokens` (scrittura, 1.25x il prezzo input base) e `cache_read_input_
tokens` (lettura, 0.1x) da `input_tokens` (solo non cacheato).
Ignorarli avrebbe fatto sottostimare `costo_stimato` in silenzio non
appena la cache si fosse attivata — stesso principio di "mai
indovinare" applicato al costo dichiarato, non solo ai valori
estratti: `PrezzoModello.costo()` ora richiede prezzi di cache
espliciti in `config/prezzi_modelli.yaml` per contarli, e solleva
`PrezziError` (non assume zero) se li riceve senza un prezzo
configurato.

Non misurato quanto sconto reale la cache produca su un corpus vero
(richiede rilanciare il tier 1 su piu' documenti dello stesso schema
di seguito, non fatto stasera) — la correttezza del meccanismo e'
verificata via test (ordine del `content`, presenza del breakpoint,
conteggio del costo con e senza token di cache), non ancora la resa
economica reale.

## ADR-055 — Il gate di pubblicazione è il contratto, non l'accuratezza
(conferma ADR-048, non revoca)

**2026-08-12, stessa sessione di ADR-048/053/054.** Proposto (di
nuovo, la terza volta nella stessa sessione) di rimandare la
pubblicazione per "consolidare l'accuratezza" sul corpus reale
attuale. Stessa contraddizione già chiusa da ADR-048: il corpus dei
15 documenti luce ha già dato il segnale che doveva dare (l'ipotesi
tier0 falsificata), continuare a ottimizzarci sopra rischia
overfitting, non nuovo segnale — un criterio di rilascio che si
sposta implicitamente dall'architettura all'accuratezza ogni volta
che il numero attuale mette disagio non è una decisione, è
l'assenza di una decisione presa più volte di nascosto.

**Decisione.** ADR-048 non si revoca, si conferma con una postilla
esplicita: l'unico criterio di blocco rimasto prima della prima
release è la **stabilità del contratto pubblico** — schema YAML,
pipeline, e il modello Result/Evidence se e quando verrà introdotto
(vedi discussione Evidence Model, stessa sessione, non ancora
implementato). L'accuratezza attuale (68.7%/campo, 13.3%/documento,
corpus reale, dichiarata per intero nel README) NON è più un
criterio di rilascio — continuerà a crescere dopo la pubblicazione
tramite casi reali portati dai primi utilizzatori, non prima.

Corollario pratico: se in futuro si ripropone "aspettiamo un
numero migliore prima di pubblicare" senza revocare esplicitamente
questo ADR con un nuovo ADR che lo dica, la risposta di default è
no — il criterio è già stato deciso, discusso, e confermato tre
volte nella stessa sessione.

**Nota a margine, stessa sessione**: il corpus CTE (39 documenti,
4 fornitori, ADR odierno separato in `corpus/cte/README.md`) è stato
costruito ma non ancora passato alla pipeline — nessuna misura,
nessun oracle. Per lo stesso principio di questo ADR, questo NON
blocca la pubblicazione del pacchetto luce: è lavoro parallelo
successivo, non un prerequisito.

## ADR-056 — Result Contract v1 (Evidence Model, design prima del codice)

**2026-08-12, stessa sessione di ADR-055.** Prerequisito dichiarato
da ADR-055: il gate di pubblicazione è la stabilità del contratto
pubblico. Questo ADR è quel contratto — deciso PRIMA di scrivere
codice, non estratto a posteriori da un'implementazione.

### Lo stato di fatto oggi (la crepa che questo ADR chiude)

`RisultatoEstrazione` (`pipeline.py`) porta `valori` e `confidenza`
come due dict paralleli piatti. `confidenza` è già oggi, nel codice,
una funzione pura di tre segnali — solo che quei segnali vengono
calcolati e buttati via nello stesso respiro (`_calcola_confidenza`):

```
None                              se valore assente
"bassa"                           se il campo è coinvolto in una
                                   invariante VIOLATA (a prescindere
                                   dall'origine — il disaccordo tra
                                   campi è il segnale, ADR-045)
"media"                           se origine in {tier1, derivato}
"alta"                            altrimenti (origine == tier0)
```

Non tracciati oggi, calcolati e scartati: quali riparazioni
(`repair.py`) sono state applicate, quante invarianti sono state
VALUTATE (solo le fallite sopravvivono, come `violazioni`), la
classificazione triage (`digitale`/`ibrida`/`scansione`) della
pagina, il tipo documento deciso da `classifica.py`. Il campo
"evidenza" di cui parla questo ADR non è un concetto nuovo da
inventare — è quello che il sistema già sa e già dimentica.

### Cos'è Result

Un `Result` è l'output di `estrai_file()` per UNA istanza
documentale (una bolletta, un CTE — la segmentazione, ADR-014-bis,
può produrre più istanze per file). Non è "i valori estratti" — è
**tutto ciò che il sistema sa giustificare** su quei valori.

### Cos'è Evidence

Evidence è la struttura che ogni singolo campo porta con sé, dalla
quale la confidenza si CALCOLA (funzione pura, non un dato di
input indipendente):

- `origin` — chi ha prodotto il valore: `"tier0"` / `"tier1"` /
  `"derivato"` oggi, stringa aperta non enum chiuso (un domani
  `"tier2"`, `"arbitrato"` si aggiungono senza rompere nulla).
- `repair` — lista, non booleano (un domani più trasformazioni in
  sequenza sullo stesso campo): ogni voce `{"tipo": ..., "da": ...,
  "a": ...}`.
- `derivation` — lista, stessa ragione: ogni voce `{"tipo":
  "somma_approssimata" | "differenza_giorni", "invariante_id": ...,
  "da_campi": [...]}`.
- `invariants` — non solo le fallite: `{"passed": N, "failed": M,
  "dettaglio": [{"id", "esito": "pass"|"fail", "severita"}]}`. Oggi
  il sistema valuta TUTTE le invarianti e tiene solo le fallite
  (`violazioni`); questo è il motivo per cui "invarianti: 3/3" non è
  rappresentabile ora.

Document-level evidence (nuovo, oggi non esposto affatto):
`triage` (classificazione pagina per pagina, già calcolata da
`analizza()` e già scartata dopo aver deciso la segmentazione) e
`classificazione` (tipo documento deciso da `classifica.py`, se la
CLI l'ha eseguita). Serve a distinguere un problema di DOCUMENTO
(scansione illeggibile) da un problema di CAMPO (regex non ha
trovato nulla su un documento perfettamente leggibile) — oggi
questi due casi sono indistinguibili nell'output.

### Regola di derivazione della confidenza (dichiarata, stabile)

```
confidence(campo) =
    null    se evidence.value è null
    "bassa" se evidence.invariants.failed > 0 per un vincolo che
            coinvolge questo campo
    "media" se evidence.origin in {"tier1", "derivato"}
    "alta"  altrimenti
```

Identica alla regola già in produzione oggi — cambia dove vive
(funzione dichiarata sopra Evidence, non calcolo interno perso) non
cosa calcola. Nessuna regressione comportamentale in questo ADR.

### Esempio JSON completo

```json
{
  "istanza_id": "demo",
  "documento": {
    "schema": "bolletta_luce_it",
    "schema_versione": 1,
    "classificazione": "bolletta_luce",
    "pagine": [
      {"indice": 0, "tipo": "digitale"},
      {"indice": 1, "tipo": "digitale"}
    ]
  },
  "campi": {
    "kwh_totale": {
      "value": "174.74",
      "evidence": {
        "origin": "tier0",
        "repair": [],
        "derivation": [],
        "invariants": {
          "passed": 1,
          "failed": 0,
          "dettaglio": [{"id": "somma_fasce", "esito": "pass", "severita": "warning"}]
        }
      },
      "confidence": "alta"
    },
    "periodo_a": {
      "value": "2025-05-13",
      "evidence": {
        "origin": "derivato",
        "repair": [],
        "derivation": [
          {"tipo": "differenza_giorni", "invariante_id": "periodo_coerente", "da_campi": ["periodo_da", "giorni"]}
        ],
        "invariants": {"passed": 1, "failed": 0, "dettaglio": [{"id": "periodo_coerente", "esito": "pass", "severita": "warning"}]}
      },
      "confidence": "media"
    },
    "kwh_f3": {
      "value": null,
      "evidence": {"origin": null, "repair": [], "derivation": [], "invariants": {"passed": 0, "failed": 0, "dettaglio": []}},
      "confidence": null
    }
  },
  "esito": "pass",
  "motivo": null,
  "chiamate_tier1": [],
  "costo_tier1_usd": 0.0,
  "tier1_errore": null
}
```

### Cosa è stabile (v1, il contratto — rompere questo è un major)

- Forma di `campi`: mappa `nome_campo -> {value, evidence, confidence}`.
- Dentro `evidence`: le quattro chiavi `origin`/`repair`/`derivation`/
  `invariants`, sempre presenti (liste vuote, non assenti, se non
  applicabile — un consumatore non deve mai fare `.get(x, default)`
  su una chiave che potrebbe non esistere).
- `confidence` valori possibili: `"alta"`/`"media"`/`"bassa"`/`null`
  — la REGOLA sopra è stabile, cambiarla è la stessa gravità di
  cambiare la forma.
- `esito`: `"pass"`/`"warning"`/`"reject"`, e la sua semantica
  (obbligatorio mancante o invariante `reject` → reject; altre
  violazioni → warning; altrimenti pass).
- `istanza_id`, top-level per file: una lista di `Result`, uno per
  istanza segmentata.

### Cosa può cambiare senza rompere nulla (additivo, non un major)

- Nuovi valori di `origin` oltre i 3 attuali (client legge stringa,
  non un enum chiuso lato consumatore).
- Nuove chiavi dentro le voci di `repair`/`derivation` (sono dict
  aperti, un consumatore legge `tipo` e ignora il resto).
- `documento.classificazione`/`documento.pagine`: assenti oggi in
  pratica se la CLI non ha classificato (es. `--schema` esplicito) —
  trattare come opzionali fin da subito.
- `chiamate_tier1`: lista di chiamate con costo/tempo/errore
  attribuiti alla CHIAMATA (un tier1 oggi risolve N campi in una
  sola chiamata — il costo non è attribuibile a un singolo campo
  senza inventare un'euristica di riparto arbitraria, quindi non
  si finge una precisione che non c'è). Un campo può riferire quale
  chiamata l'ha risolto (`evidence.chiamata_id`, opzionale) se in
  futuro arriva l'arbitrato multi-provider.
- Un punteggio numerico di confidenza (0-1) potrà aggiungersi
  ACCANTO alla categoria testuale, mai sostituirla in v1.

### Esplicitamente fuori scope v1 (non costruire ora)

- Attribuzione di costo/tempo per singolo campo (vedi sopra —
  richiederebbe un riparto inventato, vietato dal principio "mai
  indovinare" applicato al costo, ADR-054).
- Confidenza come probabilità continua invece che categoriale.
- Evidence per sotto-oggetti annidati (uno schema con campi
  strutturati/ripetuti — nessuno schema attuale ne ha bisogno).

### Il test richiesto: fra 3 anni, 20 tipi di documento, questo Result basta?

Sì, e la ragione è verificabile riga per riga sopra: zero concetti
specifici del dominio energia in questo contratto (niente "kwh",
niente "POD" — `campi` è una mappa generica sui nomi dichiarati
nello SCHEMA, mai nel contratto). Le quattro chiavi di Evidence
(origin/repair/derivation/invariants) sono linguaggio di PIPELINE,
non di dominio: si applicano identiche a un CTE (già verificato,
zero campi economia-specifici nel modello) e a un ventesimo tipo
documento non ancora immaginato, perché descrivono COME un valore è
stato ottenuto e verificato, non COSA rappresenta.

### Breaking change dichiarato

Il JSON di oggi (README, `valori`+`confidenza` piatti e paralleli)
NON è compatibile con questo — è il momento giusto per romperlo:
pre-alpha dichiarato, zero utenti esterni ancora (ADR-048), prima
del tag `0.1.0-alpha`. Romperlo dopo la prima release sarebbe la
stessa violazione di contratto che questo ADR esiste per evitare.

### Ordine deciso (non ancora eseguito, solo il design)

1. Questo ADR (fatto).
2. Implementare Evidence Model come feature, non refactoring
   interno silenzioso: `pipeline.py`, `invariants.py` (deve
   restituire passed/failed per invariante, non solo le fallite),
   `base.py`/`anthropic.py` (chiamate come lista con id), CLI/JSON
   output, README aggiornato con l'esempio sopra, test.
3. Validare il contratto sui 39 CTE — non solo per misurarli, ma
   come prova che il contratto regge su un dominio diverso da
   quello su cui è stato disegnato.
4. Release `0.1.0-alpha`: API dichiarata instabile, contratto
   Result dichiarato stabile, benchmark pubblico, roadmap.

## ADR-057 — Evidence: origin e status separati (correzione ad ADR-056)

**2026-08-12, stessa sessione, prima di scrivere codice.** ADR-056
non distingue "il campo non ha origine" da "il campo non ha origine
PERCHÉ": oggi indistinguibili sono "tier0 ha cercato e non trovato",
"tier1 non è stato tentato (`--tier1` assente)", "tier1 tentato e
fallito (`tier1_errore`)", "il valore è stato scartato dal gate".
Tutte informazioni reali, oggi non ricostruibili dall'output.

**Decisione.** `origin` risponde SOLO a "da dove proviene questo
valore" (rimane `"tier0"` / `"tier1"` / `"derivato"` / `null`).
Aggiunta chiave separata `status`, stringa aperta, che risponde a
"perché l'origine è assente o inutilizzabile" quando `origin` è
`null` o quando un tentativo è fallito pur avendo un'origine:
`"tier0_non_trovato"`, `"tier1_non_tentato"`, `"tier1_fallito"`,
altri in futuro senza rompere nulla (stesso principio stringa-aperta
di `origin`, ADR-056). Mai un solo campo che porta due significati
diversi — la lezione è la stessa di "confidenza calcolata e
buttata via": non comprimere due domande in una risposta.

Aggiornamento all'esempio JSON di ADR-056: ogni voce `evidence`
guadagna `"status": null | "<motivo>"` accanto a `"origin"`. Nessun
altro campo del contratto cambia.
