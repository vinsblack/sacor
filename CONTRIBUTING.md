# Contribuire a sacor

Grazie per l'interesse. Questo documento spiega come proporre modifiche —
non è un manuale di stile astratto, riflette come il progetto è già
costruito (vedi `docs/02-decisions.md` per il perché di ogni scelta).

## Prima di scrivere codice

sacor ha una regola che precede tutte le altre: **misura prima di
dichiarare**. Se stai proponendo un fix che "dovrebbe migliorare
l'accuratezza", verificalo con un numero vero prima di aprire la PR — un
`print()` di prima/dopo su un caso concreto basta, non serve altro. Un PR
che dice "questo dovrebbe aiutare" senza una misura non verrà accettato
solo sulla fiducia.

Se stai proponendo una funzionalità grossa, apri prima una issue —
risparmia tempo a te e a chi revisiona.

## Setup

Richiede Python 3.12+ e [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/vinsblack/sacor
cd sacor
uv sync --all-extras
```

`uv sync` da solo disinstalla le dipendenze di sviluppo (ruff, mypy,
pytest) — usa sempre `--all-extras` quando risincronizzi.

## Test, lint, tipi

```bash
uv run pytest              # test (nessuna chiamata di rete: i provider AI
                            # sono sempre mockati nei test, mai reali)
uv run ruff check .        # lint
uv run mypy src/           # tipi (strict)
```

Tutti e tre girano in CI ad ogni push/PR (`.github/workflows/ci.yml`),
insieme a un report di accuratezza sul corpus sintetico. Una PR con test
rossi o lint/mypy che falliscono non viene guardata.

## Come è organizzato il codice

Prima di proporre codice nuovo, leggi `docs/01-architecture.md` — la
pipeline ha sette strati (triage → segmentazione → tier0 → repair →
derivazione → tier1 → invarianti → gate) e un principio che li attraversa
tutti: **mai indovinare, dichiarare l'incertezza invece di nasconderla**.
Un contributo che fa scegliere un valore plausibile al posto di `None`
quando il dato è davvero incerto va contro questo principio, anche se fa
salire un numero.

## Aggiungere un nuovo tipo di documento (schema)

Questo è il contributo più utile che si possa fare oggi. Un nuovo tipo di
documento è **uno schema YAML nuovo, non nuovo codice Python** — vedi
`src/sacor/schemas/bolletta_gas_it.yaml` o `cte_it.yaml` come esempi
recenti, costruiti in questo modo. In breve:

1. Leggi almeno un documento reale del tipo che vuoi aggiungere (con
   consenso a usarlo — vedi sotto) e annota le etichette esatte che usa
   per ogni campo che vuoi estrarre.
2. Scrivi lo schema (`campi`, `estrazione` con regex quando possibile,
   `invarianti` se ci sono relazioni aritmetiche tra campi, `descrizione`
   per i campi ambigui — guida il modello, non lo forza).
3. Aggiungi il tipo a `sacor.classifica` se serve una nuova categoria di
   documento riconoscibile, e collega lo schema in `sacor/cli.py`.
4. Verifica il tier0 (regex) sul documento reale, senza chiamare l'AI —
   è gratis e va sempre fatto per primo.
5. Se possibile, una verifica end-to-end con `--tier1` su almeno un
   documento reale, e dichiara onestamente quanti campi sono corretti —
   **un documento non è un corpus**: non dichiarare un'accuratezza
   misurata se hai verificato un solo esempio.

## Dati sensibili — regola dura, non negoziabile

**Nessun documento di terze parti finisce nel repo**, mai, nemmeno con
consenso — il consenso copre l'uso per misurare, non la pubblicazione dei
PDF stessi (sono due permessi diversi, vedi `docs/02-decisions.md`,
ADR-042). Se contribuisci un nuovo schema basato su documenti reali:

- I PDF restano locali, mai committati (verifica che siano in
  `.gitignore` prima di committare qualunque cosa).
- Se contribuisci un corpus con oracle (valori attesi), il file deve
  contenere **solo campi tecnici dello schema** (es. POD, importi, date)
  — mai nome, indirizzo, codice fiscale, IBAN.

Una PR che introduce anche solo per errore un documento reale o un dato
personale viene rifiutata, non semplicemente corretta.

## Commit e PR

- Messaggi di commit in italiano, coerenti con lo stile del repo
  (`git log` per esempi) — tipo convenzionale (`feat:`, `fix:`, `docs:`,
  `test:`) seguito da una riga che dice cosa cambia e perché, non solo
  cosa.
- Una decisione architetturale vincolante (non solo un bug fix) va
  registrata come nuovo ADR in `docs/02-decisions.md` — append-only, mai
  riscritto, anche quando una decisione precedente viene revocata (si
  registra la revoca, non si cancella la storia).
- PR piccole e mirate battono PR grandi — più facili da rivedere, più
  facili da misurare.

## Domande

Apri una issue. Non c'è ancora un canale chat pubblico.
