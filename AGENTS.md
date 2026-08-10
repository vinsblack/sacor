# AGENTS.md — Contratto operativo

Ogni agente che lavora su questo repo legge questo file per primo,
poi `docs/00-north-star.md`.

## Ruoli

| Agente | Responsabilità | Non fa |
|---|---|---|
| **Claude Opus** (chat) | Architettura, ADR, task atomici, criteri di accettazione | Non implementa, non riscrive file |
| **Claude Code** | Implementazione, test, commit, aggiorna `03-current-state.md` | Non allarga lo scope senza chiedere |
| **Codex** | Review | Non decide architettura |

## Invarianti (non negoziabili)

1. **Clean room.** Zero righe di codice, zero dati, zero listini provenienti da
   VERO o da Massimo. Solo know-how. Se un file sembra derivato da VERO, si ferma
   e si chiede.
2. **Nessun documento di terzi nel corpus.** Solo bollette proprie, di persone
   che hanno dato consenso esplicito, sintetiche o fac-simile pubblici.
3. **No push senza conferma esplicita.**
4. **No pubblicazione (PyPI/npm) senza conferma esplicita.**
5. **Il dominio sta nello schema YAML, mai nel codice.** Se serve un `if` con
   dentro "bolletta", "luce" o "gas", è un errore di design.
6. **L'AI non fa matematica.** Somme, IVA, riconciliazioni: solo Python.

## I due gate di progetto

- **G1** — Nodo n8n / pacchetto PyPI pubblicato entro **60 giorni** dall'inizio,
  anche se estrae solo 4 campi. Pubblicare prima di perfezionare.
- **G2** — Nessun secondo tipo di documento finché il primo non ha un numero di
  accuratezza pubblicato **e** almeno un utente esterno.

## Memoria

Fonte di verità = questo repo. Notion è solo mirror di lettura.

| File | Chi scrive | Quando |
|---|---|---|
| `AGENTS.md` | Opus | Su decisione |
| `docs/00-north-star.md` | Opus | Raramente |
| `docs/01-architecture.md` | Opus | Su ADR |
| `docs/02-decisions.md` | Opus | Append-only, mai riscritto |
| `docs/03-current-state.md` | `scripts/state.py` | Generato, mai a mano |
| `docs/04-roadmap.md` | Opus | A fine blocco |
| `docs/05-glossary.md` | CC | Quando emerge un termine nuovo |

## Stile

- Commenti nel codice solo se richiesti o se spiegano un *perché* non ovvio.
- Nessuna emoji.
- Type hints obbligatori. `ruff` + `mypy` in CI.
- Ogni PR: test verdi + eval harness eseguito, accuratezza riportata nel diff.
