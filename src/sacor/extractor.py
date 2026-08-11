"""Protocollo per gli extractor. Tier 0 (ADR-032): estrazione deterministica
via regex dichiarate nello schema, nessuna AI. Confinato all'istanza, non al
file (ADR-033): il Protocol e' stato definito nel Blocco 1, prima che
esistesse il concetto di istanza documentale (ADR-014-bis)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import pdfplumber

from sacor.repair import ripara
from sacor.schema import Schema
from sacor.segmentation import Istanza
from sacor.triage import TipoPagina, analizza, normalizza_testo


class Extractor(Protocol):
    def extract(self, istanza: Istanza, schema: Schema) -> dict[str, str | None]: ...


class DummyExtractor:
    """Restituisce None per ogni campo. Non legge il PDF."""

    def extract(self, istanza: Istanza, schema: Schema) -> dict[str, str | None]:
        return {campo.nome: None for campo in schema.campi}


class EsitoCampo(StrEnum):
    """Tre cause diverse di 'non ho un valore', T3.3: un numero unico le
    nasconde. Pattern assente/non trovato, Repair fallito, e successo sono
    problemi diversi da diagnosticare separatamente."""

    NON_ESTRATTO = "non_estratto"  # nessuna sezione estrazione, o pattern non trovato
    NON_NORMALIZZABILE = "non_normalizzabile"  # pattern trovato, Repair ha rifiutato
    NORMALIZZATO = "normalizzato"  # successo


@dataclass(frozen=True)
class DiagnosticaCampo:
    esito: EsitoCampo
    valore: str | None  # non None solo se esito e' NORMALIZZATO


def _valore_grezzo(pattern: str, testo: str) -> str | None:
    """re.search prende sempre il PRIMO match — sbagliato quando lo stesso
    pattern trova valori DIVERSI in punti diversi della stessa istanza (es.
    un 'Totale da pagare' di un mese precedente allegato prima di quello
    vero, T4.17/R015 sul corpus reale). Se i match non concordano tutti,
    il valore e' ambiguo: None (T3.2, mai indovinare) batte un valore
    preso a caso tra i due."""
    valori = {m.group(1) if m.groups() else m.group(0) for m in re.finditer(pattern, testo)}
    return valori.pop() if len(valori) == 1 else None


class TierZeroExtractor:
    """Tier 0 (ADR-032): nessuna AI. Applica le regex dichiarate nello
    schema (`campo.estrazione`) al testo normalizzato (ADR-030) delle
    pagine DIGITALE dell'ISTANZA (ADR-033: solo pagina_da..pagina_a, mai il
    file intero), poi Repair (sacor.repair) alla forma canonica dell'oracle.
    Regole dure (T3.2): pattern assente, non trovato o non normalizzabile
    -> None, mai un valore inventato o parziale; su pagine SCANSIONE/IBRIDA
    tutti i campi None, non e' il suo lavoro; nessuna euristica non
    dichiarata nello schema.
    """

    def estrai_diagnostica(self, istanza: Istanza, schema: Schema) -> dict[str, DiagnosticaCampo]:
        """Come extract(), ma distingue PERCHE' un campo non ha valore
        (T3.3): pattern mai trovato, o trovato-ma-non-normalizzabile da
        Repair. extract() proietta solo il valore finale; l'eval usa questo
        per il report a quattro cause."""
        diagnostica: dict[str, DiagnosticaCampo] = {
            campo.nome: DiagnosticaCampo(EsitoCampo.NON_ESTRATTO, None) for campo in schema.campi
        }

        # ADR-033: si guardano SOLO le pagine dell'istanza, mai il file intero
        # — ne' per classificare il tipo pagina, ne' per leggere il testo.
        indice_da = istanza.pagina_da - 1
        indice_a = istanza.pagina_a

        triage = analizza(istanza.file)
        pagine_istanza = triage.pagine[indice_da:indice_a]

        # T4.17 (diagnosi corpus reale, zero costo): T3.2 resta valido per
        # PAGINA (mai un valore letto da una pagina non digitale), ma prima
        # una sola pagina non digitale nell'istanza buttava via anche le
        # pagine digitali sorelle — 10/14 istanze reali sono miste, tutte
        # azzerate senza motivo. Se non resta nessuna pagina digitale,
        # 'testo' e' vuoto e ogni regex fallisce comunque: stesso esito di
        # prima (tutti None), nessun caso speciale da mantenere.
        with pdfplumber.open(istanza.file) as documento:
            pagine_pdf = documento.pages[indice_da:indice_a]
            testo = "\n".join(
                normalizza_testo(pagina_pdf)
                for pagina_pdf, pagina_triage in zip(pagine_pdf, pagine_istanza, strict=True)
                if pagina_triage.tipo is TipoPagina.DIGITALE
            )

        for campo in schema.campi:
            if campo.estrazione is None or campo.estrazione.tipo != "regex":
                continue
            grezzo = _valore_grezzo(campo.estrazione.pattern, testo)
            if grezzo is None:
                continue
            normalizzato = ripara(grezzo, campo.tipo)
            if normalizzato is None:
                diagnostica[campo.nome] = DiagnosticaCampo(EsitoCampo.NON_NORMALIZZABILE, None)
            else:
                diagnostica[campo.nome] = DiagnosticaCampo(EsitoCampo.NORMALIZZATO, normalizzato)

        return diagnostica

    def extract(self, istanza: Istanza, schema: Schema) -> dict[str, str | None]:
        diagnostica = self.estrai_diagnostica(istanza, schema)
        return {nome: diag.valore for nome, diag in diagnostica.items()}
