# Corpus — regole di provenienza

Questo file è vincolante. Nessun documento entra nel corpus senza una riga qui.

## Fonti ammesse

| Codice | Fonte | Condizione |
|---|---|---|
| `PROPRIO` | Bolletta intestata a Vins | Nessuna |
| `CONSENSO` | Bolletta di terzi | Consenso scritto, anche via messaggio, archiviato |
| `SINTETICO` | Generato da script | Dati inventati, nessun POD reale |
| `PUBBLICO` | Fac-simile ARERA o fornitore | Verificare che sia pubblicato come esempio |

## Fonti vietate

- Qualsiasi documento proveniente da VERO o dai clienti di Massimo
- Qualsiasi bolletta trovata online che non sia un fac-simile ufficiale
- Documenti ricevuti per lavoro da chiunque, in qualunque contesto

## Anonimizzazione

Ogni documento `PROPRIO` o `CONSENSO` va anonimizzato prima del commit:
POD, codice cliente, nome, indirizzo, IBAN, numero cliente.

Regola dei due passaggi: prima si redige, poi si **verifica sul PDF renderizzato
a immagine** che la redazione sia effettiva. La verifica solo testuale non basta
per PDF scansionati — il testo può non esserci e i dati restare visibili.

## Registro
| ID | Fonte | Fornitore | Anonimizzato | Note |
|---|---|---|---|---|
| B001 | | | | |
