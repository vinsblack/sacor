# 04 — Roadmap

## Blocco 1 — Il metro (prima di ciò che misura)

Nessun VLM in questo blocco. Prima si costruisce lo strumento di misura, poi
si misura. Ordine obbligatorio.

---

### T1.1 — Verifica disponibilità nome
Controllare `sacor` su PyPI, npm e GitHub.
**Accettazione:** esito riportato in `docs/02-decisions.md` sotto ADR-001. Se
occupato su PyPI → proporre 2 alternative e fermarsi.

### T1.2 — Scaffold repo
`pyproject.toml` (Python 3.12, package `sacor`), `ruff`, `mypy`, `pytest`,
`.gitignore`, `LICENSE` (Apache-2.0), `README.md` minimo.
**Accettazione:** `pip install -e .` funziona; `ruff check` e `mypy src/` verdi
su repo vuoto; `pytest` gira con 0 test senza errori.

### T1.3 — CI GitHub Actions
Workflow su push e PR: install, ruff, mypy, pytest.
**Accettazione:** badge verde sul primo commit. Nessun deploy, nessun publish.

### T1.4 — Schema `bolletta_luce_it.yaml`
Massimo **10 campi**, non 40. Proposta iniziale: `pod`, `fornitore`,
`periodo_da`, `periodo_a`, `giorni`, `kwh_totale`, `kwh_f1`, `kwh_f2`,
`kwh_f3`, `importo_totale`.
Più 2 invarianti: somma fasce ≈ totale (tolleranza 0.5%); giorni = differenza
date + 1.
**Accettazione:** il file YAML esiste e non contiene logica, solo dichiarazioni.

### T1.5 — Loader e validatore di schema
`sacor.schema.load(path) -> Schema`. Parsa il YAML, valida la struttura,
solleva errori chiari su schema malformato.
**Accettazione:** 5 test — schema valido; campo senza tipo; tipo sconosciuto;
invariante malformata; file mancante.

### T1.6 — Corpus iniziale
5 bollette **proprie**, in `corpus/raw/`. Nessun documento di terzi.
Naming: `B001.pdf` … `B005.pdf`.
**Accettazione:** 5 file presenti; `corpus/README.md` dichiara provenienza e
consenso per ciascuno.

### T1.7 — Oracle scritto a mano
`corpus/attesi.json`: per ognuna delle 5 bollette, i 10 campi dello schema con
il valore corretto letto a occhio da Vins.
**Accettazione:** JSON valido; ogni campo dello schema presente per ogni
documento; valori `null` ammessi solo se il campo davvero non c'è sul documento.

### T1.8 — Eval harness
`eval/run.py`: carica schema + oracle, esegue un extractor, stampa accuratezza
**per campo** e per documento, più il conteggio dei gate (pass/warning/reject).
In questo blocco l'extractor è un **dummy** che restituisce valori vuoti.
**Accettazione:** `python eval/run.py` gira e stampa una tabella; con
l'extractor dummy l'accuratezza è 0% su tutti i campi — e il report lo mostra
correttamente invece di crashare.

### T1.9 — `scripts/state.py`
Genera `docs/03-current-state.md` da: git SHA corrente, output `pytest`,
ultima accuratezza dell'eval.
**Accettazione:** il file viene generato e non è mai scritto a mano.

---

**Fine Blocco 1 quando:** CI verde + `python eval/run.py` produce un report
leggibile. Il numero sarà 0%. È corretto: adesso esiste il metro.

Il Blocco 2 (primo extractor reale, tier 1) si progetta solo dopo.
