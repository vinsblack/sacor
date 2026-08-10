"""Errore di dominio per i provider reali (T4.3): chiave mancante, rate
limit esaurito dopo i retry, timeout, errore di connessione. Distinto da un
campo None nella risposta — quello e' 'il modello si e' astenuto', questo e'
'la chiamata non e' andata a buon fine'. Non vanno confusi nel bake-off
(T4.4)."""

from __future__ import annotations


class ErroreProvider(Exception):
    pass
