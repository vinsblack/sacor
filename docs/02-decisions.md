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
