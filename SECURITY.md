# Security Policy

## Segnalare una vulnerabilità

Non aprire una issue pubblica per una vulnerabilità di sicurezza.

Scrivi invece un'email a chi mantiene il progetto (vedi profilo GitHub
[@vinsblack](https://github.com/vinsblack)) con:

- una descrizione del problema;
- i passi per riprodurlo;
- l'impatto potenziale, se lo conosci.

Risposta entro 5 giorni lavorativi. Se confermata, la vulnerabilità
viene corretta e pubblicata come release patch prima di essere
descritta pubblicamente.

## Cosa è rilevante qui

sacor esegue codice locale su file forniti dall'utente (parsing PDF)
e, opzionalmente (`--tier1`), invia contenuto del documento a un
provider AI esterno (Anthropic) — mai automaticamente, solo con
`ANTHROPIC_API_KEY` impostata esplicitamente. Aree sensibili:

- parsing PDF (`pdfplumber`) — un PDF malformato che causa
  comportamento anomalo;
- gestione della chiave API (mai loggata, mai scritta su disco da
  sacor — verifica comunque il tuo ambiente);
- dipendenze (`pyproject.toml`) — segnala se ne trovi una con una CVE
  nota non ancora aggiornata.

## Versioni supportate

Pre-alpha: solo l'ultima versione pubblicata riceve fix di sicurezza.
