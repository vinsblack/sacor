"""Costruttore di prompt per il tier 1 (T4.3): generato dallo schema, mai
scritto a mano per un tipo di documento specifico — 'un nuovo tipo di
documento non deve richiedere un nuovo prompt' (istruzione utente verbatim).
Chiede esattamente i campi passati (di norma quelli che il tier 0 ha
lasciato None), coi tipi dichiarati nello schema, e impone JSON puro."""

from __future__ import annotations

from collections.abc import Sequence

from sacor.schema import Campo, TipoCampo

_DESCRIZIONE_TIPO: dict[TipoCampo, str] = {
    "string": "testo libero",
    "date": "data in formato ISO 8601 (AAAA-MM-DD)",
    "integer": "numero intero",
    "decimal": "numero decimale, punto come separatore delle cifre decimali",
}


def costruisci_prompt(campi: Sequence[Campo]) -> str:
    elenco_campi = "\n".join(f"- {c.nome}: {_DESCRIZIONE_TIPO[c.tipo]}" for c in campi)
    chiavi_attese = ", ".join(f'"{c.nome}"' for c in campi)

    return (
        "Sei un estrattore di dati da documenti. Ti vengono fornite una o piu' "
        "pagine di un documento come immagini.\n\n"
        "Estrai ESATTAMENTE questi campi, non altri:\n"
        f"{elenco_campi}\n\n"
        "Regole:\n"
        "- Se un campo non e' presente sul documento o non e' leggibile, il suo "
        "valore deve essere `null`. Non indovinare, non stimare, non dedurre da "
        "campi simili o dal contesto: un'astensione e' sempre preferibile a un "
        "valore inventato.\n"
        "- Rispondi con SOLO un oggetto JSON valido, nessun testo prima o dopo, "
        "nessun blocco di codice markdown.\n"
        f"- Le chiavi dell'oggetto devono essere esattamente: {chiavi_attese}.\n\n"
        'Esempio di formato risposta: {"campo_a": "valore letto", "campo_b": null}'
    )
