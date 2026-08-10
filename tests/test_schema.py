from pathlib import Path

import pytest

from sacor.schema import SchemaError, load

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_REALE = REPO_ROOT / "schemas" / "bolletta_luce_it.yaml"


def test_schema_bolletta_luce_carica_10_campi_2_invarianti() -> None:
    schema = load(SCHEMA_REALE)
    assert len(schema.campi) == 10
    assert len(schema.invarianti) == 2
    assert schema.segmentazione is not None  # ADR-028: attivata sullo schema reale
    assert schema.segmentazione.tipo == "cambio_valore"


def test_file_mancante_alza_schema_error(tmp_path: Path) -> None:
    with pytest.raises(SchemaError):
        load(tmp_path / "non_esiste.yaml")


def test_yaml_malformato_alza_schema_error(tmp_path: Path) -> None:
    p = tmp_path / "malformato.yaml"
    p.write_text("campi: [\n  - nome: pod\n tipo: string")
    with pytest.raises(SchemaError):
        load(p)


def test_campo_senza_tipo_alza_schema_error(tmp_path: Path) -> None:
    p = tmp_path / "schema.yaml"
    p.write_text(
        """
schema_version: 1
documento: test
campi:
  - nome: pod
    obbligatorio: true
invarianti: []
"""
    )
    with pytest.raises(SchemaError):
        load(p)


def test_tipo_campo_sconosciuto_alza_schema_error(tmp_path: Path) -> None:
    p = tmp_path / "schema.yaml"
    p.write_text(
        """
schema_version: 1
documento: test
campi:
  - nome: pod
    tipo: fantasia
    obbligatorio: true
invarianti: []
"""
    )
    with pytest.raises(SchemaError):
        load(p)


def test_nomi_campo_duplicati_alza_schema_error(tmp_path: Path) -> None:
    p = tmp_path / "schema.yaml"
    p.write_text(
        """
schema_version: 1
documento: test
campi:
  - nome: pod
    tipo: string
    obbligatorio: true
  - nome: pod
    tipo: string
    obbligatorio: false
invarianti: []
"""
    )
    with pytest.raises(SchemaError):
        load(p)


def test_invariante_tipo_sconosciuto_alza_schema_error(tmp_path: Path) -> None:
    p = tmp_path / "schema.yaml"
    p.write_text(
        """
schema_version: 1
documento: test
campi:
  - nome: kwh_totale
    tipo: decimal
    obbligatorio: false
invarianti:
  - id: inv1
    tipo: tipo_inesistente
    severita: warning
"""
    )
    with pytest.raises(SchemaError):
        load(p)


def test_invariante_referenzia_campo_inesistente(tmp_path: Path) -> None:
    p = tmp_path / "schema.yaml"
    p.write_text(
        """
schema_version: 1
documento: test
campi:
  - nome: kwh_f1
    tipo: decimal
    obbligatorio: false
  - nome: kwh_totale
    tipo: decimal
    obbligatorio: false
invarianti:
  - id: somma_fasce
    tipo: somma_approssimata
    addendi: [kwh_f1, kwh_f4]
    totale: kwh_totale
    severita: warning
"""
    )
    with pytest.raises(SchemaError) as exc_info:
        load(p)
    messaggio = str(exc_info.value)
    assert "somma_fasce" in messaggio
    assert "kwh_f4" in messaggio


def _schema_base_con_segmentazione(segmentazione_yaml: str) -> str:
    return f"""
schema_version: 1
documento: test
campi:
  - nome: pod
    tipo: string
    obbligatorio: true
invarianti: []
{segmentazione_yaml}
"""


def test_segmentazione_valida_carica(tmp_path: Path) -> None:
    p = tmp_path / "schema.yaml"
    p.write_text(
        _schema_base_con_segmentazione(
            """
segmentazione:
  tipo: cambio_valore
  pattern: 'Fattura(?: elettronica)? n\\.?\\s*([0-9]+)'
  minimo_pagine: 1
"""
        )
    )
    schema = load(p)
    assert schema.segmentazione is not None
    assert schema.segmentazione.tipo == "cambio_valore"
    assert schema.segmentazione.minimo_pagine == 1


def test_segmentazione_tipo_sconosciuto_alza_schema_error(tmp_path: Path) -> None:
    p = tmp_path / "schema.yaml"
    p.write_text(
        _schema_base_con_segmentazione(
            """
segmentazione:
  tipo: tipo_inesistente
  pattern: 'abc'
"""
        )
    )
    with pytest.raises(SchemaError):
        load(p)


def test_segmentazione_pattern_non_compilabile_alza_schema_error(tmp_path: Path) -> None:
    p = tmp_path / "schema.yaml"
    p.write_text(
        _schema_base_con_segmentazione(
            """
segmentazione:
  tipo: cambio_valore
  pattern: '(['
"""
        )
    )
    with pytest.raises(SchemaError):
        load(p)


def test_segmentazione_minimo_pagine_invalido_alza_schema_error(tmp_path: Path) -> None:
    p = tmp_path / "schema.yaml"
    p.write_text(
        _schema_base_con_segmentazione(
            """
segmentazione:
  tipo: cambio_valore
  pattern: 'abc'
  minimo_pagine: 0
"""
        )
    )
    with pytest.raises(SchemaError):
        load(p)


def test_estrazione_valida_carica(tmp_path: Path) -> None:
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
invarianti: []
"""
    )
    schema = load(p)
    campo = schema.campo("pod")
    assert campo is not None
    assert campo.estrazione is not None
    assert campo.estrazione.tipo == "regex"


def test_campo_senza_estrazione_ha_estrazione_none(tmp_path: Path) -> None:
    p = tmp_path / "schema.yaml"
    p.write_text(
        """
schema_version: 1
documento: test
campi:
  - nome: pod
    tipo: string
    obbligatorio: true
invarianti: []
"""
    )
    schema = load(p)
    campo = schema.campo("pod")
    assert campo is not None
    assert campo.estrazione is None


def test_estrazione_tipo_sconosciuto_alza_schema_error(tmp_path: Path) -> None:
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
      tipo: magia
      pattern: 'abc'
invarianti: []
"""
    )
    with pytest.raises(SchemaError):
        load(p)


def test_estrazione_pattern_non_compilabile_alza_schema_error(tmp_path: Path) -> None:
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
      pattern: '(['
invarianti: []
"""
    )
    with pytest.raises(SchemaError):
        load(p)
