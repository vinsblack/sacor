"""Test di raggiungibilita' (ADR-028): la segmentazione deve essere
effettivamente esercitata dal corpus di default con lo schema reale, non
solo dai fixture sintetici dei test unitari di test_segmentation.py.

44 test unitari passavano mentre segmenta() prendeva sempre il ramo di
default in produzione (schema senza sezione segmentazione): nessuno di essi
verificava la raggiungibilita'. L'ha scoperto l'eval, non i test. Questo test
e' quello che avrebbe preso il bug.

Nota post-ADR-029: sul corpus di default tutti i file scansione/ibrida sono
di 1 pagina, quindi la scorciatoia aritmetica li rende certa per costruzione
— non_determinabile non compare piu' qui, correttamente (nessun file e'
multipagina con una pagina inaffidabile). Quel percorso resta comunque
testato direttamente in test_segmentation.py, a livello di funzione pura.
"""

from __future__ import annotations

import json
from pathlib import Path

import pdfplumber

from sacor.schema import load
from sacor.segmentation import segmenta
from sacor.triage import analizza, normalizza_testo
from scripts.genera_corpus import genera_corpus_composito

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"


def test_segmentazione_e_raggiungibile_dal_corpus_di_default(tmp_path: Path) -> None:
    genera_corpus_composito(
        seed=42,
        out_dir=tmp_path / "synth",
        oracle_path=tmp_path / "attesi.json",
        metadata_path=tmp_path / "metadata.json",
    )

    schema = load(SCHEMA_PATH)
    assert schema.segmentazione is not None, (
        "src/sacor/schemas/bolletta_luce_it.yaml non dichiara 'segmentazione': "
        "sacor.segmentation prenderebbe sempre il ramo di default (ADR-028)"
    )

    metadata = json.loads((tmp_path / "metadata.json").read_text())["documenti"]
    per_file: dict[str, list[str]] = {}
    for chiave, voce in metadata.items():
        per_file.setdefault(voce["file"], []).append(chiave)

    conteggi_istanze = []
    for nome_file in per_file:
        path = tmp_path / "synth" / nome_file
        pagine = analizza(path).pagine
        with pdfplumber.open(path) as documento:
            testi = [normalizza_testo(p) for p in documento.pages]
        esito = segmenta(path, pagine, testi, schema.segmentazione)
        conteggi_istanze.append(len(esito.istanze))

    assert any(n > 1 for n in conteggi_istanze), (
        "nessun documento del corpus di default produce piu' di 1 istanza: "
        "cambio_valore non viene mai esercitato sul corpus reale (ADR-028)"
    )
