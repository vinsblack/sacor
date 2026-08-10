"""Registro dei tipi di invariante noti.

Nessuna esecuzione qui: solo la dichiarazione di quali chiavi di `params`,
per ciascun tipo, sono referenze a nomi di campo. Usato da `sacor.schema`
per validare le referenze al load.
"""

TIPI_NOTI: dict[str, tuple[str, ...]] = {
    "somma_approssimata": ("addendi", "totale"),
    "differenza_giorni": ("da", "a", "risultato"),
}
