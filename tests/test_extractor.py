import io
import random
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from sacor.extractor import EsitoCampo, TierZeroExtractor, _valore_grezzo
from sacor.schema import load
from sacor.segmentation import Istanza
from scripts.genera_corpus import Flags, genera_documento

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"


def _scrivi(tmp_path: Path, nome: str, pdf_bytes: bytes) -> Path:
    p = tmp_path / nome
    p.write_bytes(pdf_bytes)
    return p


def _istanza_intero_file(path: Path, pagina_da: int = 1, pagina_a: int = 3) -> Istanza:
    # ADR-039: una fattura digitale/scansione non ibrida e' sempre a tre
    # pagine — il default copre l'intero documento a fattura singola.
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


def test_importo_totale_corretto_nonostante_canone_extra(tmp_path: Path) -> None:
    """T4.14 (ADR-040): bollette reali (Rossi Eleonora e altre) aggiungono un
    canone RAI sopra il totale energia, con un secondo 'Totale da pagare'
    diverso da 'Totale scontrino' — pattern a due totali, mai modellato
    prima. Il campo tracciato (regex ancorata a 'Importo totale:') deve
    restare quello giusto anche con questo rumore vicino."""
    schema = load(SCHEMA_PATH)
    pdf_bytes, oracle_entries, _ = genera_documento(
        random.Random(31), "S003", "Gamma Power", Flags()
    )
    path = _scrivi(tmp_path, "S003.pdf", pdf_bytes)

    estratti = TierZeroExtractor().extract(_istanza_intero_file(path), schema)

    assert estratti["importo_totale"] == oracle_entries["S003"]["importo_totale"]


def test_campi_corretti_nonostante_pagina_allegata_in_piu(tmp_path: Path) -> None:
    """T4.14 (ADR-041): la segmentazione assorbe la pagina allegata
    nell'istanza (gap noto, misurato, non corretto qui — vedi ADR-041). I
    campi tracciati devono restare corretti comunque: le regex cercano
    etichette specifiche, non l'intero testo, e la pagina allegata non ne
    contiene nessuna."""
    schema = load(SCHEMA_PATH)
    pdf_bytes, oracle_entries, _ = genera_documento(
        random.Random(32), "S002", "Beta Luce", Flags(pagine_allegate=True)
    )
    path = _scrivi(tmp_path, "S002.pdf", pdf_bytes)
    istanza_con_allegato = _istanza_intero_file(path, pagina_da=1, pagina_a=4)

    estratti = TierZeroExtractor().extract(istanza_con_allegato, schema)

    assert estratti["pod"] == oracle_entries["S002"]["pod"]
    assert estratti["importo_totale"] == oracle_entries["S002"]["importo_totale"]


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
    # Alfa Energia, non Beta Luce: lo stile di default di Beta (T4.9, C2) e'
    # periodo scritto come nome del mese, che il tier 0 non estrae per
    # costruzione — irrilevante qui, il confinamento e' l'unica cosa sotto
    # test, e con Alfa il confronto con l'oracle resta un'uguaglianza piena.
    pdf_bytes, oracle_entries, metadata_entries = genera_documento(
        random.Random(1), "S010", "Alfa Energia", Flags(multi_fattura=True)
    )
    path = _scrivi(tmp_path, "S010.pdf", pdf_bytes)

    chiave_a, chiave_b = sorted(metadata_entries)
    pagina_a = metadata_entries[chiave_a]["pagine"]
    pagina_b = metadata_entries[chiave_b]["pagine"]
    # ADR-039: ogni fattura e' a tre pagine (totale/periodo, POD/scontrino,
    # letture/imposte) — la seconda fattura inizia dopo le tre della prima.
    assert pagina_a == [1, 3]
    assert pagina_b == [4, 6]

    istanza_pagina_1 = Istanza(id=chiave_a, file=path, pagina_da=1, pagina_a=3)
    istanza_pagina_2 = Istanza(id=chiave_b, file=path, pagina_da=4, pagina_a=6)

    estratti_1 = TierZeroExtractor().extract(istanza_pagina_1, schema)
    estratti_2 = TierZeroExtractor().extract(istanza_pagina_2, schema)

    assert estratti_1 == oracle_entries[chiave_a]
    assert estratti_2 == oracle_entries[chiave_b]
    assert estratti_2["pod"] != estratti_1["pod"]
    assert estratti_2 != estratti_1


def test_istanza_con_pagina_scansione_estrae_comunque_dalle_pagine_digitali(
    tmp_path: Path,
) -> None:
    """T4.17 (diagnosi zero-costo corpus reale, 11-08): 10 istanze reali su
    14 mescolano pagine digitali e scansionate nella STESSA istanza (es.
    lettera di riepilogo digitale + scontrino scansionato in allegato). La
    regola precedente ('un'istanza con ANCHE UNA SOLA pagina non digitale
    -> tutti i campi None') buttava via pagine digitali perfettamente
    leggibili solo perche' una pagina sorella era una scansione. Tier 0
    resta fedele a T3.2 (mai un valore da una pagina non digitale) ma ora
    lo applica per pagina, non per istanza."""
    schema = load(SCHEMA_PATH)
    pdf_digitale, oracle_entries, _ = genera_documento(
        random.Random(40), "S020", "Alfa Energia", Flags()
    )
    pdf_scansione, _, _ = genera_documento(
        random.Random(41), "S021", "Beta Luce", Flags(scansione=True)
    )

    writer = PdfWriter()
    for pagina in PdfReader(io.BytesIO(pdf_digitale)).pages:
        writer.add_page(pagina)
    for pagina in PdfReader(io.BytesIO(pdf_scansione)).pages:
        writer.add_page(pagina)
    buf = io.BytesIO()
    writer.write(buf)
    path = tmp_path / "misto.pdf"
    path.write_bytes(buf.getvalue())

    # ADR-039: 3 pagine digitali (S020) + 3 pagine scansione (S021) nella
    # STESSA istanza — non due istanze separate, il caso reale e' proprio
    # questo mix dentro un'unica istanza documentale.
    istanza_mista = Istanza(id="misto", file=path, pagina_da=1, pagina_a=6)

    estratti = TierZeroExtractor().extract(istanza_mista, schema)

    assert estratti == oracle_entries["S020"]


def test_valore_grezzo_nessun_match_none() -> None:
    assert _valore_grezzo(r"Totale:\s*(\d+)", "nulla qui") is None


def test_valore_grezzo_un_match_lo_restituisce() -> None:
    assert _valore_grezzo(r"Totale:\s*(\d+)", "Totale: 42") == "42"


def test_valore_grezzo_match_ripetuti_identici_restituisce_il_valore() -> None:
    # stessa cifra su piu' pagine (es. riepilogo + dettaglio) e' coerenza,
    # non ambiguita'.
    assert _valore_grezzo(r"Totale:\s*(\d+)", "Totale: 42\nTotale: 42") == "42"


def test_valore_grezzo_match_diversi_e_ambiguo_restituisce_none() -> None:
    # T4.17 (R015, corpus reale): due 'Totale da pagare' con importi DIVERSI
    # nella stessa istanza (mese precedente allegato + quello vero) — il
    # primo match trovato da re.search non e' affidabile. Meglio None
    # (T3.2, mai indovinare) che il valore sbagliato preso a caso.
    assert _valore_grezzo(r"Totale:\s*(\d+)", "Totale: 125\nTotale: 64") is None
