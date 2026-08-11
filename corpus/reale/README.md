# corpus/reale — oracle su bollette reali (T4.14, ADR-042)

**Cosa c'è qui**: `attesi.json` con i 10 campi schema estratti da 14
bollette luce reali, con **consenso esplicito** delle persone che hanno
fornito i PDF a Vincenzo Gallo. `metadata.json` con note tecniche (fasce,
consumo stimato, anomalie) per documento.

**Cosa NON c'è qui, mai**: nome/cognome, indirizzo, codice fiscale/P.IVA,
IBAN, numero cliente/contratto, telefono, email. Solo dati tecnici: POD,
fornitore (azienda, non persona), periodo, kWh per fascia, importo totale.

**I PDF originali NON sono in questo repository.** Restano solo in locale
(`corpus/reale/raw/`, in `.gitignore`, mai committati). Il repo diventerà
pubblico (ADR/istruzione utente) — un PDF reale con POD/importi/date esatte
è comunque un dato collegabile a una persona anche senza nome scritto sopra,
e resta fuori dal repo per costruzione.

**Consenso a due livelli, non uno**: le persone hanno acconsentito all'uso
dei dati tecnici delle loro bollette per misurare l'accuratezza (questo
oracle). Non è stato chiesto/dato consenso a pubblicare i PDF stessi né una
loro versione redatta — se un giorno serve, va richiesto separatamente ed
esplicitamente (ADR-042).

**Perché esiste**: fino a questa sessione, ogni numero di accuratezza
pubblicato era misurato solo su corpus sintetico (`corpus/attesi.json`) —
generatore e schema si parlano sempre, per costruzione. Questo oracle è la
prima misura contro bollette vere, non generate dal progetto stesso.

**Come si usa**: `python eval/run_reale.py` (gira solo se `corpus/reale/raw/`
esiste in locale — mai nel repo). Nessun triage/segmentazione: ogni PDF
reale è un'unica istanza nota (un file = una bolletta), l'estrazione copre
tutte le pagine del documento.

**Primo numero reale misurato (T4.14)**: 8/140 = **5.7%** per campo — contro
45.3% sul corpus sintetico. Atteso, non un fallimento del progetto: le regex
del tier 0 sono tarate sulle etichette esatte del generatore ("Importo
totale: EUR", "Energia F1: ... kWh") — i fornitori reali usano etichette
del tutto diverse ("TOTALE DA PAGARE", "Scontrino dell'energia" con
struttura a sotto-righe, ecc., ADR-040). È la prima prova concreta che il
numero sintetico non è mai stato predittivo del comportamento su bollette
vere — motivo di più per cui questo oracle esiste.

**14 documenti, non 15**: un file (assegnato R008 durante l'estrazione) si
è rivelato una fattura FIBRA/telecom, non luce — escluso, fuori schema.

**Fornitori rappresentati**: Sorgenia, NWG Energia, Poste Energia, Smart
Energy, Gelsia, Acea Energia, EstEnergy/Hera, Fintel/Alperia, Eni
Plenitude, Enel Energia — 10 fornitori diversi.
