import random
from pathlib import Path

from sacor.extractor import EsitoCampo, TierZeroExtractor
from sacor.schema import load
from sacor.segmentation import Istanza
from scripts.genera_corpus import Flags, genera_documento

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"


def _scrivi(tmp_path: Path, nome: str, pdf_bytes: bytes) -> Path:
    p = tmp_path / nome
    p.write_bytes(pdf_bytes)
    return p


def _istanza_intero_file(path: Path, pagina_da: int = 1, pagina_a: int = 1) -> Istanza:
    return Istanza(id=path.stem, file=path, pagina_da=pagina_da, pagina_a=pagina_a)


def test_documento_digitale_estrae_tutti_i_campi_correttamente(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    pdf_bytes, oracle_entries, _ = genera_documento(
        random.Random(20), "S001", "Alfa Energia", Flags()
    )
    path = _scrivi(tmp_path, "S001.pdf", pdf_bytes)

    estratti = TierZeroExtractor().extract(_istanza_intero_file(path), schema)

    assert estratti == oracle_entries["S001"]


def test_pagina_scansione_restituisce_tutti_none(tmp_path: Path) -> None:
    """T3.2: non e' il suo lavoro su pagine non affidabili."""
    schema = load(SCHEMA_PATH)
    pdf_bytes, _, _ = genera_documento(
        random.Random(21), "S002", "Beta Luce", Flags(scansione=True)
    )
    path = _scrivi(tmp_path, "S002.pdf", pdf_bytes)

    estratti = TierZeroExtractor().extract(_istanza_intero_file(path), schema)

    assert all(valore is None for valore in estratti.values())


def test_diagnostica_distingue_non_estratto_da_normalizzato(tmp_path: Path) -> None:
    schema = load(SCHEMA_PATH)
    pdf_bytes, _, _ = genera_documento(random.Random(22), "S003", "Gamma Power", Flags())
    path = _scrivi(tmp_path, "S003.pdf", pdf_bytes)

    diagnostica = TierZeroExtractor().estrai_diagnostica(_istanza_intero_file(path), schema)

    assert diagnostica["pod"].esito is EsitoCampo.NORMALIZZATO
    assert diagnostica["pod"].valore is not None


def test_campo_senza_sezione_estrazione_e_non_estratto(tmp_path: Path) -> None:
    """T3.1: campo senza 'estrazione' -> tier 0 restituisce None per quel
    campo (non_estratto), senza tentare nulla."""
    p = tmp_path / "schema.yaml"
    p.write_text(
        """
schema_version: 1
documento: test
campi:
  - nome: pod
    tipo: string
    obbligatorio: true
    estrazione:
      tipo: regex
      pattern: 'IT\\d{3}E\\d{8}'
  - nome: fornitore
    tipo: string
    obbligatorio: false
invarianti: []
"""
    )
    schema = load(p)
    pdf_bytes, _, _ = genera_documento(random.Random(23), "S004", "Alfa Energia", Flags())
    path = _scrivi(tmp_path, "S004.pdf", pdf_bytes)

    diagnostica = TierZeroExtractor().estrai_diagnostica(_istanza_intero_file(path), schema)

    assert diagnostica["fornitore"].esito is EsitoCampo.NON_ESTRATTO
    assert diagnostica["fornitore"].valore is None
    assert diagnostica["pod"].esito is EsitoCampo.NORMALIZZATO


def test_estrattore_confinato_non_legge_oltre_la_propria_istanza(tmp_path: Path) -> None:
    """T3.4/C2 — il caso che ha prodotto i 9 errori (ADR-033): un file con
    due fatture su due pagine digitali (--multi-fattura). L'istanza di
    pagina 2 (equivalente a S010b) non deve MAI restituire i valori di
    pagina 1 (S010a): con la vecchia firma extract(pdf, schema) sull'intero
    file, re.search trovava sempre il primo match, quello di pagina 1."""
    schema = load(SCHEMA_PATH)
    pdf_bytes, oracle_entries, metadata_entries = genera_documento(
        random.Random(1), "S010", "Beta Luce", Flags(multi_fattura=True)
    )
    path = _scrivi(tmp_path, "S010.pdf", pdf_bytes)

    chiave_a, chiave_b = sorted(metadata_entries)
    pagina_a = metadata_entries[chiave_a]["pagine"]
    pagina_b = metadata_entries[chiave_b]["pagine"]
    assert pagina_a == [1, 1]
    assert pagina_b == [2, 2]

    istanza_pagina_1 = Istanza(id=chiave_a, file=path, pagina_da=1, pagina_a=1)
    istanza_pagina_2 = Istanza(id=chiave_b, file=path, pagina_da=2, pagina_a=2)

    estratti_1 = TierZeroExtractor().extract(istanza_pagina_1, schema)
    estratti_2 = TierZeroExtractor().extract(istanza_pagina_2, schema)

    assert estratti_1 == oracle_entries[chiave_a]
    assert estratti_2 == oracle_entries[chiave_b]
    assert estratti_2["pod"] != estratti_1["pod"]
    assert estratti_2 != estratti_1
