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


def _riga_campo(c: Campo) -> str:
    # T4.15 (ADR-043): la descrizione di dominio, quando dichiarata nello
    # schema, si aggiunge al tipo — non lo sostituisce. Il builder non sa
    # cosa significhi, la riporta soltanto (ADR-017).
    if c.descrizione:
        return f"- {c.nome}: {_DESCRIZIONE_TIPO[c.tipo]}. {c.descrizione}"
    return f"- {c.nome}: {_DESCRIZIONE_TIPO[c.tipo]}"


def costruisci_prompt(campi: Sequence[Campo]) -> str:
    elenco_campi = "\n".join(_riga_campo(c) for c in campi)
    chiavi_attese = ", ".join(f'"{c.nome}"' for c in campi)

    regole = [
        "- Se un campo non e' presente sul documento o non e' leggibile, il suo "
        "valore deve essere `null`. Non indovinare, non stimare, non dedurre da "
        "campi simili o dal contesto: un'astensione e' sempre preferibile a un "
        "valore inventato.",
        "- Rispondi con SOLO un oggetto JSON valido, nessun testo prima o dopo, "
        "nessun blocco di codice markdown.",
        f"- Le chiavi dell'oggetto devono essere esattamente: {chiavi_attese}.",
    ]
    if any(c.tipo == "date" for c in campi):
        # Misurato (T4.12): il modello a volte NON si astiene su una data
        # parziale ("giugno 2025", senza giorno) — deduce il primo o
        # l'ultimo giorno del mese invece di rispondere null. E' esattamente
        # il tipo di invenzione plausibile che il resto del prompt vieta in
        # generale; qui va vietato per nome, col caso concreto che l'ha
        # prodotta, non solo con la regola generica.
        regole.append(
            "- Un campo data richiede giorno, mese e anno ESATTI. Se il documento "
            "indica solo il mese e l'anno (es. 'giugno 2025'), senza un giorno "
            "specifico, il valore e' `null` — NON dedurre il primo o l'ultimo "
            "giorno del mese: sarebbe un valore inventato, non letto. QUESTA "
            "REGOLA VALE SOLO SE LA DESCRIZIONE DEL CAMPO SOPRA NON DICE IL "
            "CONTRARIO: se la descrizione di un campo autorizza esplicitamente "
            "una deduzione (es. mese di riferimento -> primo/ultimo giorno), "
            "quella descrizione prevale su questa regola generale, non il "
            "contrario — non sono in conflitto, la descrizione del campo e' "
            "un'eccezione dichiarata apposta."
        )

    return (
        "Sei un estrattore di dati da documenti. Ti vengono fornite una o piu' "
        "pagine di un documento come immagini.\n\n"
        "Estrai ESATTAMENTE questi campi, non altri:\n"
        f"{elenco_campi}\n\n"
        "Regole:\n" + "\n".join(regole) + "\n\n"
        'Esempio di formato risposta: {"campo_a": "valore letto", "campo_b": null}'
    )
