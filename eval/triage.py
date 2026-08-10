"""Eval del triage: confronta sacor.triage.analizza (+ sacor.segmentation)
con corpus/metadata.json e riporta accuratezza per attributo, mai un numero
unico (stesso principio di eval/run.py, ADR-011, applicato al triage).

Costo di inferenza zero (ADR-016): nessun modello coinvolto, numero reale.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from sacor.schema import load
from sacor.segmentation import ConfidenzaSegmentazione, segmenta
from sacor.triage import TipoPagina, analizza, normalizza_testo

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"
METADATA_PATH = REPO_ROOT / "corpus" / "metadata.json"
CORPUS_SYNTH = REPO_ROOT / "corpus" / "synth"

_QUALITA_A_TIPO = {
    "digitale": TipoPagina.DIGITALE,
    "ibrida": TipoPagina.IBRIDA,
    "scansione_degradata": TipoPagina.SCANSIONE,
    "scansione_sporca": TipoPagina.SCANSIONE,
}


@dataclass(frozen=True)
class Metrica:
    """Copertura e accuratezza separate (ADR-027): un attributo che puo'
    essere non determinabile (es. rotazione senza Tesseract) non deve far
    contare un None come errore. None abbassa la copertura, non l'accuratezza
    — sono due domande diverse: "il sistema ha potuto rispondere?" e "quando
    ha risposto, ha risposto giusto?"."""

    corretti: int
    determinabili: int
    totale: int

    @property
    def copertura(self) -> float:
        return self.determinabili / self.totale * 100 if self.totale else 0.0

    @property
    def accuratezza(self) -> float:
        return self.corretti / self.determinabili * 100 if self.determinabili else 0.0


@dataclass(frozen=True)
class Report:
    n_documenti: int
    numero_istanze: Metrica
    intervalli_pagine: Metrica
    tipo_pagina: Metrica
    rotazione: Metrica
    confidenza: Counter[str] = field(default_factory=Counter)
    certa_ma_sbagliati_istanze: int = 0


def motivo_copertura_rotazione_bassa() -> str | None:
    """Motivo diagnosticabile di una copertura rotazione < 100% (ADR-027).
    None se non c'e' una causa nota da riportare."""
    if shutil.which("tesseract") is None:
        return "Tesseract non installato"
    return None


def _carica_metadata(path: Path) -> dict[str, dict[str, object]]:
    dati = json.loads(path.read_text())
    if not isinstance(dati, dict):
        raise ValueError(f"'{path}' non contiene un oggetto JSON valido")
    # ADR-025: blocco "composizione" in testa, voci per istanza sotto
    # "documenti". Formato piatto tollerato per compatibilita'.
    documenti = dati.get("documenti", dati)
    if not isinstance(documenti, dict):
        raise ValueError(f"'{path}': 'documenti' non e' un oggetto JSON valido")
    return documenti


def _raggruppa_per_file(metadata: dict[str, dict[str, object]]) -> dict[str, list[str]]:
    """file -> chiavi istanza che vi appartengono, nell'ordine di apparizione."""
    per_file: dict[str, list[str]] = {}
    for chiave, voce in metadata.items():
        per_file.setdefault(str(voce["file"]), []).append(chiave)
    return per_file


def valuta(
    schema_path: Path = SCHEMA_PATH,
    metadata_path: Path = METADATA_PATH,
    corpus_synth: Path = CORPUS_SYNTH,
) -> Report:
    schema = load(schema_path)
    metadata = _carica_metadata(metadata_path)
    per_file = _raggruppa_per_file(metadata)

    corretti_istanze = totale_istanze = 0
    corretti_intervalli = totale_intervalli = 0
    corretti_tipo = totale_tipo = 0
    corretti_rotazione = determinabili_rotazione = totale_rotazione = 0
    confidenza_conteggi: Counter[str] = Counter()
    certa_ma_sbagliati_istanze = 0

    for nome_file, chiavi in per_file.items():
        path = corpus_synth / nome_file
        triage_result = analizza(path)

        with pdfplumber.open(path) as documento:
            testi = [normalizza_testo(p) for p in documento.pages]

        esito_segmentazione = segmenta(
            path.stem, triage_result.pagine, testi, schema.segmentazione
        )
        confidenza_conteggi[esito_segmentazione.confidenza.value] += 1

        totale_istanze += 1
        istanze_corrette = len(esito_segmentazione.istanze) == len(chiavi)
        if istanze_corrette:
            corretti_istanze += 1
        elif esito_segmentazione.confidenza is ConfidenzaSegmentazione.CERTA:
            # ADR-031: il rilevatore di errori silenziosi. CERTA e sbagliata
            # e' peggio di NON_DETERMINABILE — afferma con sicurezza il
            # falso invece di dichiarare incertezza.
            certa_ma_sbagliati_istanze += 1

        totale_intervalli += 1
        attesi = {tuple(metadata[c]["pagine"]) for c in chiavi}  # type: ignore[arg-type]
        ottenuti = {(i.pagina_da, i.pagina_a) for i in esito_segmentazione.istanze}
        if attesi == ottenuti:
            corretti_intervalli += 1

        # Ground truth per pagina: il generatore non produce ancora file con
        # pagine di qualita'/rotazione miste, quindi tutte le istanze dello
        # stesso file condividono lo stesso atteso (prima voce, per costruzione).
        voce_riferimento = metadata[chiavi[0]]
        tipo_atteso = _QUALITA_A_TIPO[str(voce_riferimento["qualita"])]
        rotazione_attesa = 180 if "ruotata" in voce_riferimento["flag_attivi"] else 0  # type: ignore[operator]

        for pagina in triage_result.pagine:
            totale_tipo += 1
            if pagina.tipo is tipo_atteso:
                corretti_tipo += 1

            totale_rotazione += 1
            if pagina.rotazione is not None:
                determinabili_rotazione += 1
                if pagina.rotazione == rotazione_attesa:
                    corretti_rotazione += 1

    return Report(
        n_documenti=len(per_file),
        numero_istanze=Metrica(corretti_istanze, totale_istanze, totale_istanze),
        intervalli_pagine=Metrica(corretti_intervalli, totale_intervalli, totale_intervalli),
        tipo_pagina=Metrica(corretti_tipo, totale_tipo, totale_tipo),
        rotazione=Metrica(corretti_rotazione, determinabili_rotazione, totale_rotazione),
        confidenza=confidenza_conteggi,
        certa_ma_sbagliati_istanze=certa_ma_sbagliati_istanze,
    )


def _riga(nome: str, corretti: int, totale: int, pct: float) -> str:
    frazione = f"{corretti}/{totale}"
    return f"{nome:<24}{frazione:>10}   {pct:>10.1f}%"


def formatta_report(report: Report) -> str:
    righe = [
        f"sacor triage eval — {report.n_documenti} documenti",
        "",
        f"{'Attributo':<24}{'Corretti':>10}   {'Accuratezza':>11}",
        _riga(
            "numero istanze",
            report.numero_istanze.corretti,
            report.numero_istanze.totale,
            report.numero_istanze.accuratezza,
        ),
        _riga(
            "intervalli pagine",
            report.intervalli_pagine.corretti,
            report.intervalli_pagine.totale,
            report.intervalli_pagine.accuratezza,
        ),
        _riga(
            "tipo pagina",
            report.tipo_pagina.corretti,
            report.tipo_pagina.totale,
            report.tipo_pagina.accuratezza,
        ),
        # ADR-027: rotazione puo' essere non determinabile (Tesseract
        # assente). Due righe, mai un numero solo.
        _riga(
            "rotazione — copertura",
            report.rotazione.determinabili,
            report.rotazione.totale,
            report.rotazione.copertura,
        ),
        _riga(
            "rotazione — accuratezza",
            report.rotazione.corretti,
            report.rotazione.determinabili,
            report.rotazione.accuratezza,
        ),
        "---",
    ]

    parti = " | ".join(
        f"{stato.value} {report.confidenza.get(stato.value, 0)}"
        for stato in ConfidenzaSegmentazione
    )
    righe.append(f"Confidenza segmentazione: {parti}")
    # ADR-031: il rilevatore di errori silenziosi nella segmentazione. Se
    # sale sopra zero, qualcosa afferma con sicurezza una cosa falsa.
    righe.append(f"Di cui CERTA ma errati su numero istanze: {report.certa_ma_sbagliati_istanze}")
    return "\n".join(righe)


def main() -> int:
    if not METADATA_PATH.is_file():
        print("corpus non ancora presente: manca corpus/metadata.json")
        return 0

    report = valuta()
    print(formatta_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
