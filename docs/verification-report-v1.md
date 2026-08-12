# Verification Report v1

**12-08, sessione ADR-056→060.** Non un benchmark di accuratezza — una
verifica strutturale: il contratto Result/Evidence (ADR-056, corretto
da ADR-057/058/059/060) regge su un dominio diverso (CTE) da quello su
cui è stato disegnato (bollette luce/gas), senza modifiche?

## Metodo

39 documenti CTE reali (`corpus/cte/raw/`, 4 fornitori: Acea Energia,
Bluenergy, Edison, ENGIE), schema `cte_it.yaml`, **solo tier0** (zero
costo, nessuna chiamata a pagamento). Per ogni documento:

```
Documento → estrai_file() → Result (valori + evidenze + evidenza_documento)
                                  ↓
                    Il contratto è bastato senza modifiche? SI/NO — perché
```

"Bastato" qui significa: nessuna eccezione, `evidenza_documento`
presente, ogni campo del risultato ha un'`Evidenza` corrispondente,
`origine` coerente con la presenza/assenza del valore (mai un valore
senza origine dichiarata, mai un'origine senza valore), `confidenza`
presente per ogni campo. Regola dell'utente, rispettata: **nessuna
modifica al contratto durante la campagna** — se un problema fosse
emerso, andava annotato qui, non corretto sul momento.

Script: `scripts/verification_campaign.py`.

## Cosa questo report NON dice

- **Non è una misura di accuratezza.** `cte_it.yaml` è stato costruito
  leggendo un solo documento (ADR-053, ENGIE) — il tier0 su Acea/
  Bluenergy/Edison probabilmente lascia molti campi `None` (layout
  diversi, nessuna regex tarata su di loro). Questo report non lo
  misura: gli va bene comunque, perché un campo `None` con
  `origine=None` è un esito STRUTTURALMENTE corretto ("non ho trovato,
  non ho indovinato"), non un fallimento del contratto.
- **Non esercita tier1, derivazione, né i percorsi warning/reject del
  Gate su documenti CTE** (`usa_tier1=False` per costo zero). Quei
  percorsi sono già coperti dalla suite bollette (`tests/test_pipeline.py`,
  `tests/test_gate.py`) — non sono stati ri-verificati specificamente
  su CTE in questa campagna.

## Risultato

**39/39 — contratto bastato senza modifiche.**

Per fornitore: Acea Energia 8/8, Bluenergy 12/12, Edison 10/10, ENGIE
9/9. Log completo (per-documento) nell'output dello script — non
duplicato qui, riproducibile con `uv run python
scripts/verification_campaign.py`.

## Conclusione

Zero problemi trovati → **nessun ADR-061 necessario**. Il contratto
Result/Evidence, disegnato guardando bollette luce/gas, ha attraversato
un dominio diverso (schede di condizioni economiche) senza richiedere
modifiche strutturali. Non prova che il contratto sia perfetto per
sempre — prova che non si è rotto alla prima verifica reale fuori dal
dominio su cui è stato progettato, che è la domanda che questa
campagna doveva rispondere.

Prossimo passo naturale, non di questo report: oracle CTE (misura
vera, con consenso/verifica come fu fatto per luce, ADR-042) — lavoro
parallelo alla pubblicazione, non suo prerequisito (ADR-048/055).
