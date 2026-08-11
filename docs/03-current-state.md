# 03 — Stato corrente

> **File generato da `scripts/state.py`. Non modificare a mano.**

| | |
|---|---|
| Commit | 3803521 |
| Test | 127 passed in 85.14s (0:01:25) |
| Accuratezza (per campo) | 43.6% |
| Accuratezza (per documento) | 28.6% |
| Triage — numero istanze | 91.7% |
| Triage — intervalli pagine | 91.7% |
| Triage — tipo pagina | 100.0% |
| Triage — rotazione (copertura) | 97.5% |
| Triage — rotazione (motivo copertura bassa) | motivo non determinato |
| Triage — rotazione (accuratezza) | 100.0% |
| Triage — attributo peggiore (per accuratezza) | numero istanze, 91.7% |
| Degrado scansione (produzione, ADR-036) | medio (blur 0.6, downscale 1.5, jpeg 70) |
| Tasso di escalation | n/d |
| Generato il | 2026-08-11 09:58 UTC |

## Blocco corrente

Blocco 4 — Tier 1, provider e corpus realistico. Vedi `docs/04-roadmap.md`.

## Cali noti, non correzioni (T4.11, C2)

- Periodo mensile su Beta/Gamma (`periodo_da`/`periodo_a`/`giorni` non
  estratti dal tier 0): e' il caso reale che il tier 1 esiste per coprire,
  non un difetto del layout.
- `S011.pdf` (multi-fattura scansionato): segmentazione non determinabile su
  pagine senza text layer — limite noto (ADR-024), si risolve con la
  ri-segmentazione su testo OCR nel prossimo blocco, non nel generatore.
