# Corpus CTE

Documenti CTE (Condizioni Tecnico-Economiche) pubblicamente disponibili
sui siti ufficiali dei fornitori italiani — schede di offerta/condizioni
contrattuali, non bollette: descrivono un'offerta commerciale, non un
cliente, zero dati personali per costruzione (ADR-053).

Scopo del corpus: sviluppo, test, validazione del contratto pubblico di
SACOR (ADR-056→060) — vedi `docs/verification-report-v1.md` (39/39,
Verification Campaign).

## Struttura

- **`examples/`** — 4 documenti, uno per fornitore, **committati nel
  repository**. Confermato dall'utente (12-08): scaricati direttamente
  dai siti ufficiali dei fornitori, documenti precontrattuali pubblici,
  nessun dato riservato.
- **`inventario.json`** — hash SHA-256, numero pagine, fornitore, per
  l'intero dataset (39 documenti). Committato: rende il dataset
  tracciabile anche senza tenere ogni file dentro git.
- **`raw/`** — il dataset completo (39, in crescita), **non
  committato** (`.gitignore`). Un repository di codice non è il posto
  giusto per un dataset che crescerà nel tempo (39 oggi, di più domani)
  — resta locale, la sua identità è nell'inventario, non nei byte.

## Verifica PII (12-08)

Scansione automatica di tutti i 39 documenti (`pdftotext` + grep su
pattern CF/IBAN/nome-cognome/indirizzo) prima del commit: nessun dato
personale di cliente trovato. Gli unici hit sono dati societari del
fornitore stesso (P.IVA/CF/REA propri, IBAN per i pagamenti in entrata
— dati pubblici per legge) e clausole privacy generiche che
*menzionano* le categorie "nome, cognome, indirizzo" senza contenere
valori reali. Nessuna verifica manuale documento-per-documento oltre
questa — se un fornitore aggiunge in futuro un facsimile con dati
precompilati, va riverificato.

## Registro fornitori (dataset completo, 39 in `raw/`)

| Fornitore | N. documenti | Tipi | Segmenti | Esempio in `examples/` |
|---|---|---|---|---|
| Acea Energia | 8 | luce, gas | casa, business | `acea.pdf` |
| Bluenergy | 12 | luce, gas | casa, business | `bluenergy.pdf` |
| Edison | 10 | luce, gas | casa, business | `edison.pdf` |
| ENGIE | 9 | luce, gas | casa, business | `engie.pdf` |

Convenzione filename originale (in `raw/`, non in `examples/`):
`<nome offerta>_<Tipo>_<Segmento>.pdf` (es. `Jump Casa_Luce_Casa.pdf` =
offerta "Jump Casa", luce, segmento casa).

## Stato oracle

**Non ancora costruito.** La Verification Campaign (39/39, tier0,
`docs/verification-report-v1.md`) ha verificato che il contratto
Result/Evidence regge — non ha misurato accuratezza. Prossimo passo:
passare i documenti alla pipeline (`sacor extract --tier1`), leggere
l'output, e costruire `attesi.json` verificando i valori estratti
contro il PDF (non il contrario — non si scrive un oracle "a occhio"
prima di aver visto cosa il motore produce).
