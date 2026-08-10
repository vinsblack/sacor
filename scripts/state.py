"""Genera docs/03-current-state.md. Mai scritto a mano (vedi AGENTS.md)."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.run import carica_report  # noqa: E402
from eval.triage import METADATA_PATH as TRIAGE_METADATA_PATH  # noqa: E402
from eval.triage import motivo_copertura_rotazione_bassa  # noqa: E402
from eval.triage import valuta as valuta_triage  # noqa: E402
from sacor.oracle import OracleError  # noqa: E402
from sacor.schema import SchemaError  # noqa: E402

OUTPUT = REPO_ROOT / "docs" / "03-current-state.md"


def _git_sha() -> str:
    esito = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return esito.stdout.strip() if esito.returncode == 0 else "n/d"


def _riepilogo_pytest() -> str:
    esito = subprocess.run(
        ["pytest", "--tb=no", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    righe = [r for r in esito.stdout.strip().splitlines() if r.strip()]
    return righe[-1] if righe else "n/d"


def _accuratezza() -> tuple[str, str]:
    try:
        report = carica_report()
    except (SchemaError, OracleError):
        return "n/d", "n/d"
    if report is None:
        return "n/d", "n/d"

    totale_corretti = sum(c.corretti for c in report.campi)
    totale_slot = sum(c.totale for c in report.campi)
    acc_campo = totale_corretti / totale_slot if totale_slot else 0.0
    return f"{acc_campo * 100:.1f}%", f"{report.accuratezza_documento * 100:.1f}%"


@dataclass(frozen=True)
class AccuratezzaTriage:
    numero_istanze: str
    intervalli_pagine: str
    tipo_pagina: str
    rotazione_copertura: str
    rotazione_motivo: str
    rotazione_accuratezza: str
    peggiore: str


_TRIAGE_ND = AccuratezzaTriage("n/d", "n/d", "n/d", "n/d", "n/d", "n/d", "n/d")


def _accuratezza_triage() -> AccuratezzaTriage:
    # ADR-026: mai una media aggregata come dato principale. Gli attributi si
    # riportano separati, piu' il peggiore in evidenza — una media nasconde
    # quale attributo sta fallendo.
    # ADR-027: rotazione puo' essere non determinabile. Copertura e
    # accuratezza separate — il peggiore si calcola sull'accuratezza, mai
    # sulla copertura (la copertura misura l'ambiente, non il codice).
    if not TRIAGE_METADATA_PATH.is_file():
        return _TRIAGE_ND
    try:
        report = valuta_triage()
    except (SchemaError, OSError, ValueError):
        return _TRIAGE_ND

    accuratezze = {
        "numero istanze": report.numero_istanze.accuratezza,
        "intervalli pagine": report.intervalli_pagine.accuratezza,
        "tipo pagina": report.tipo_pagina.accuratezza,
        "rotazione": report.rotazione.accuratezza,
    }
    nome_peggiore = min(accuratezze, key=lambda nome: accuratezze[nome])

    rotazione_motivo = "—"
    if report.rotazione.copertura < 100.0:
        rotazione_motivo = motivo_copertura_rotazione_bassa() or "motivo non determinato"

    return AccuratezzaTriage(
        numero_istanze=f"{accuratezze['numero istanze']:.1f}%",
        intervalli_pagine=f"{accuratezze['intervalli pagine']:.1f}%",
        tipo_pagina=f"{accuratezze['tipo pagina']:.1f}%",
        rotazione_copertura=f"{report.rotazione.copertura:.1f}%",
        rotazione_motivo=rotazione_motivo,
        rotazione_accuratezza=f"{accuratezze['rotazione']:.1f}%",
        peggiore=f"{nome_peggiore}, {accuratezze[nome_peggiore]:.1f}%",
    )


def genera() -> str:
    acc_campo, acc_documento = _accuratezza()
    triage = _accuratezza_triage()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return f"""# 03 — Stato corrente

> **File generato da `scripts/state.py`. Non modificare a mano.**

| | |
|---|---|
| Commit | {_git_sha()} |
| Test | {_riepilogo_pytest()} |
| Accuratezza (per campo) | {acc_campo} |
| Accuratezza (per documento) | {acc_documento} |
| Triage — numero istanze | {triage.numero_istanze} |
| Triage — intervalli pagine | {triage.intervalli_pagine} |
| Triage — tipo pagina | {triage.tipo_pagina} |
| Triage — rotazione (copertura) | {triage.rotazione_copertura} |
| Triage — rotazione (motivo copertura bassa) | {triage.rotazione_motivo} |
| Triage — rotazione (accuratezza) | {triage.rotazione_accuratezza} |
| Triage — attributo peggiore (per accuratezza) | {triage.peggiore} |
| Tasso di escalation | n/d |
| Generato il | {timestamp} |

## Blocco corrente

Blocco 1 — Il metro. Vedi `docs/04-roadmap.md`.
"""


def main() -> int:
    OUTPUT.write_text(genera())
    print(f"scritto {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
