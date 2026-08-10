# 05 — Glossario

Termini di dominio e di progetto. CC aggiunge una riga quando incontra un
termine nuovo che ricorrerà.

## Progetto

**Oracle** — il file `corpus/attesi.json` con i valori corretti, scritti a mano.
È il riferimento contro cui si misura tutto. Se l'oracle è sbagliato, ogni
numero successivo è privo di significato.

**Eval harness** — `eval/run.py`. Confronta l'output dell'extractor con
l'oracle e produce accuratezza per campo, per documento e per gate.

**Gate** — esito di validazione a tre livelli:
`pass` (tutti gli invarianti rispettati), `warning` (invariante fuori tolleranza
ma documento utilizzabile), `reject` (campo obbligatorio mancante o invariante
violata gravemente).

**Escalation** — passaggio da extractor tier 1 (economico) a tier 2 (di punta)
dopo un fallimento del gate. Il *tasso di escalation* è la metrica economica
principale del progetto.

**Errore silenzioso** — estrazione formalmente valida ma sostanzialmente
sbagliata, che supera tutti i controlli. È la classe di errore che fa perdere
un cliente. Esempi noti: importo fantasma introdotto da una virgola letta come
migliaia; fornitura trimestrale interpretata come annuale.

**Invariante** — relazione aritmetica che deve valere all'interno del documento
(somma fasce ≈ totale, giorni = differenza date + 1). È ciò che permette la
verifica senza fonti esterne.

**Istanza documentale** — un file PDF non è un documento, è un contenitore di
una o più istanze documentali (caso reale: un PDF con due fatture su due
periodi distinti, ADR-013/ADR-014-bis). L'unità che l'estrazione tratta è
l'istanza, non il file: ha un id opaco proprio, un intervallo di pagine nel
file, e — quando la segmentazione non è certa (ADR-024) — una confidenza
esplicita sul fatto che quell'intervallo sia corretto.

## Dominio bollette

**POD** — Point of Delivery. Identificativo univoco del punto di prelievo
elettrico. Formato `IT` + 3 cifre distributore + `E` + 8 caratteri.
È il campo chiave: senza POD il documento è `reject`.

**PDR** — l'equivalente del POD per il gas.

**Fasce F1/F2/F3** — bande orarie di consumo elettrico. La loro somma deve
approssimare il consumo totale. È l'invariante principale.

**Separatore migliaia italiano** — in Italia `1.234,56` significa milleduecento-
trentaquattro virgola cinquantasei. Un parser anglosassone lo legge come 1,234.
Fonte nota di errori silenziosi.

**Giorni di fornitura** — si contano **inclusivi**: `data_a - data_da + 1`.
Il `+1` è dimenticato di frequente e produce uno scarto sistematico.

## Note tecniche

**Pagina ruotata a 180°** — una scansione capovolta è invisibile a Tesseract
senza rilevamento dell'orientamento: restituisce stringa vuota o rumore, senza
segnalare errore. Va rilevata nel triage, prima dell'estrazione.

**Text layer** — strato di testo selezionabile in un PDF. La sua assenza o
scarsità distingue un documento digitale da una scansione, e determina il
percorso nel triage.
