"""Verification Campaign (ADR-056->060, sessione 12-08): non misura
accuratezza, verifica se il contratto Result/Evidence regge su un
dominio diverso (CTE) da quello su cui e' stato disegnato (bollette).

Regola esplicita dell'utente: e' vietato correggere il contratto durante
la campagna. Ogni problema si annota, non si risolve qui. Solo tier0
(nessuna chiamata a pagamento) - lo scopo e' stressare la STRUTTURA,
non l'accuratezza dei valori.

Uso: uv run python scripts/verification_campaign.py
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sacor.pipeline import estrai_file  # noqa: E402
from sacor.schema import load  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "cte_it.yaml"
CORPUS_DIR = REPO_ROOT / "corpus" / "cte" / "raw"


@dataclass
class EsitoVerifica:
    file: str
    contratto_bastato: bool
    nota: str


def _verifica_documento(schema: object, path: Path) -> EsitoVerifica:
    nome_rel = str(path.relative_to(CORPUS_DIR))
    try:
        risultati = estrai_file(path, schema)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 — la campagna deve continuare sugli altri file
        dettaglio = traceback.format_exception_only(type(exc), exc)[-1].strip()
        return EsitoVerifica(nome_rel, False, f"eccezione durante estrai_file: {dettaglio}")

    if not risultati:
        return EsitoVerifica(nome_rel, False, "nessuna istanza segmentata (0 risultati)")

    problemi: list[str] = []
    for r in risultati:
        if r.evidenza_documento is None:
            problemi.append(f"{r.istanza_id}: evidenza_documento assente")
        for campo_nome in r.valori:
            if campo_nome not in r.evidenze:
                problemi.append(f"{r.istanza_id}: campo '{campo_nome}' senza Evidenza")
                continue
            ev = r.evidenze[campo_nome]
            if r.valori[campo_nome] is None and ev.origine is not None:
                problemi.append(
                    f"{r.istanza_id}: campo '{campo_nome}' senza valore ma origine={ev.origine!r}"
                )
            if r.valori[campo_nome] is not None and ev.origine is None:
                problemi.append(
                    f"{r.istanza_id}: campo '{campo_nome}' ha un valore ma origine=None"
                )
            if campo_nome not in r.confidenza:
                problemi.append(f"{r.istanza_id}: confidenza mancante per '{campo_nome}'")

    if problemi:
        return EsitoVerifica(nome_rel, False, "; ".join(problemi))
    return EsitoVerifica(nome_rel, True, f"{len(risultati)} istanza/e, contratto coerente")


def main() -> None:
    schema = load(SCHEMA_PATH)
    pdf_paths = sorted(CORPUS_DIR.rglob("*.pdf"))
    if not pdf_paths:
        print(f"nessun PDF trovato in {CORPUS_DIR}")
        return

    esiti = [_verifica_documento(schema, p) for p in pdf_paths]

    ok = sum(1 for e in esiti if e.contratto_bastato)
    print(f"Verification Campaign — {len(esiti)} documenti, schema {SCHEMA_PATH.name}\n")
    for e in esiti:
        simbolo = "SI" if e.contratto_bastato else "NO"
        print(f"[{simbolo}] {e.file}\n     {e.nota}")
    print(f"\nTotale: {ok}/{len(esiti)} — contratto bastato senza modifiche")


if __name__ == "__main__":
    main()
