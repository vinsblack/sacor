# Changelog

Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/).
Versioning: [SemVer](https://semver.org/lang/it/) — con `0.x.y`, breaking
change possibili su ogni minor (pre-1.0, dichiarato).

## [Unreleased]

Prima release pubblica, in preparazione.

### Added
- CLI (`sacor extract file.pdf`): tier0 sempre gratis, `--tier1` opt-in
  (claude-opus-5, chiamata reale a pagamento).
- Schemi: bollette luce e gas italiane, CTE (condizioni tecnico-economiche).
- Classificazione documento automatica (luce/gas/CTE) prima dell'estrazione.
- Derivazione aritmetica: un campo mancante calcolabile da altri campi noti
  non genera una chiamata AI.
- **Result Contract v1** (ADR-056): ogni campo estratto porta con sé la
  propria evidenza — origine, riparazioni subite, derivazioni, invarianti
  valutate. Confidenza e Gate sono funzioni pure sopra questa evidenza,
  non calcoli sparsi nella pipeline.
- Prompt caching sul provider Anthropic (costo tier1 ridotto su chiamate
  che condividono lo stesso prompt).
- Corpus CTE pubblico (4 esempi committati, dataset completo inventariato).

### Measured
- Accuratezza reale (corpus reale, 15 documenti, tier0+tier1+derivazione):
  **68.7% per campo, 13.3% per documento completo**. Dettaglio per campo e
  cronologia dei tentativi in `docs/02-decisions.md`.
- Verification Campaign: il Result Contract v1 verificato su 39 documenti
  CTE reali (dominio diverso da quello di design) — 39/39, zero modifiche
  necessarie (`docs/verification-report-v1.md`).

### Known limits
- Pre-alpha: non usare in produzione.
- CTE e gas non hanno ancora un oracle/misura di accuratezza (solo luce).
- Nessuna segmentazione multi-fattura testata su un caso reale finora.
