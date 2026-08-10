"""Genera docs/03-current-state.md. Mai scritto a mano (vedi AGENTS.md)."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.run import carica_report  # noqa: E402
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


def genera() -> str:
    acc_campo, acc_documento = _accuratezza()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return f"""# 03 — Stato corrente

> **File generato da `scripts/state.py`. Non modificare a mano.**

| | |
|---|---|
| Commit | {_git_sha()} |
| Test | {_riepilogo_pytest()} |
| Accuratezza (per campo) | {acc_campo} |
| Accuratezza (per documento) | {acc_documento} |
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
