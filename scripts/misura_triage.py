"""Misura densita_testo e copertura_immagine su un corpus generato ad-hoc con
tutti i casi rilevanti (digitale per layout con logo/QR, scansione pulita,
scansione sporca, pagina ibrida), per decidere le soglie di sacor.triage con
dati reali (ADR-018, ADR-019, ADR-020, ADR-021, ADR-022).

Non modifica le soglie. Non aggiunge test che le validano. Solo numeri.
Il caso "ibrida" e' escluso dal calcolo dei margini di banda: e' il caso che
la banda ibrida (ADR-022) esiste apposta per catturare, non un confine.
"""

from __future__ import annotations

import random
import statistics
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sacor.triage import (  # noqa: E402
    SOGLIA_COPERTURA_DIGITALE,
    SOGLIA_COPERTURA_SCANSIONE,
    PaginaInfo,
    analizza,
)
from scripts.genera_corpus import LAYOUTS, Flags, genera_documento  # noqa: E402

_SEED = 42

Caso = tuple[str, str, tuple[PaginaInfo, ...]]  # (nome, gruppo, pagine)


def _genera_casi(tmp_dir: Path) -> list[Caso]:
    casi: list[Caso] = []

    for i, layout in enumerate(LAYOUTS):
        nome = f"digitale_{layout.split()[0].lower()}"
        pdf_bytes, _, _ = genera_documento(random.Random(_SEED + i), nome, layout, Flags())
        path = tmp_dir / f"{nome}.pdf"
        path.write_bytes(pdf_bytes)
        casi.append((nome, "digitale", analizza(path).pagine))

    pdf_bytes, _, _ = genera_documento(
        random.Random(_SEED + 100), "scansione_pulita", LAYOUTS[0], Flags(scansione=True)
    )
    path = tmp_dir / "scansione_pulita.pdf"
    path.write_bytes(pdf_bytes)
    casi.append(("scansione_pulita", "scansione_pulita", analizza(path).pagine))

    pdf_bytes, _, _ = genera_documento(
        random.Random(_SEED + 200),
        "scansione_sporca",
        LAYOUTS[0],
        Flags(scansione_sporca=True),
    )
    path = tmp_dir / "scansione_sporca.pdf"
    path.write_bytes(pdf_bytes)
    casi.append(("scansione_sporca", "scansione_sporca", analizza(path).pagine))

    pdf_bytes, _, _ = genera_documento(
        random.Random(_SEED + 300), "pagina_ibrida", LAYOUTS[0], Flags(pagina_ibrida=True)
    )
    path = tmp_dir / "pagina_ibrida.pdf"
    path.write_bytes(pdf_bytes)
    casi.append(("pagina_ibrida", "ibrida", analizza(path).pagine))

    return casi


def _stampa_tabella(casi: list[Caso]) -> None:
    intestazione = (
        f"{'caso':<20}{'pagina':>7}{'tipo':>12}{'densita_testo':>16}"
        f"{'copertura_img':>16}{'ha_text_layer':>15}"
    )
    print(intestazione)
    for nome, _, pagine in casi:
        for p in pagine:
            print(
                f"{nome:<20}{p.numero:>7}{p.tipo.value:>12}{p.densita_testo:>16.2e}"
                f"{p.copertura_immagine:>16.2f}{str(p.ha_text_layer):>15}"
            )


def _valori_per_gruppo(casi: list[Caso], estrai: object) -> dict[str, list[float]]:
    gruppi: dict[str, list[float]] = {}
    for _, gruppo, pagine in casi:
        gruppi.setdefault(gruppo, []).extend(estrai(p) for p in pagine)  # type: ignore[operator]
    return gruppi


def _stampa_statistiche(casi: list[Caso]) -> None:
    features: tuple[tuple[str, object], ...] = (
        ("densita_testo", lambda p: p.densita_testo),
        ("copertura_immagine", lambda p: p.copertura_immagine),
    )

    for nome_feature, estrai in features:
        print(f"\n--- {nome_feature} ---")
        per_gruppo = _valori_per_gruppo(casi, estrai)
        for gruppo, valori in per_gruppo.items():
            print(
                f"{gruppo:<20} min={min(valori):.2e}  max={max(valori):.2e}  "
                f"mediana={statistics.median(valori):.2e}"
            )

        dig = per_gruppo.get("digitale")
        scan = [
            v
            for gruppo, valori in per_gruppo.items()
            if gruppo not in ("digitale", "ibrida")
            for v in valori
        ]
        if not dig or not scan:
            continue

        if nome_feature == "copertura_immagine":
            # Due confini di banda (ADR-022), non una soglia unica: il
            # margine si misura separatamente ai due bordi.
            dig_peggiore = max(dig)
            scan_peggiore = min(scan)
            margine_digitale = (
                SOGLIA_COPERTURA_DIGITALE / dig_peggiore if dig_peggiore else float("inf")
            )
            margine_scansione = scan_peggiore / SOGLIA_COPERTURA_SCANSIONE
            print(
                f"margine banda digitale = {margine_digitale:.2f}x "
                f"(soglia={SOGLIA_COPERTURA_DIGITALE:.2f} / "
                f"digitale_peggiore={dig_peggiore:.2e})"
            )
            print(
                f"margine banda scansione = {margine_scansione:.2f}x "
                f"(scansione_peggiore={scan_peggiore:.2e} / "
                f"soglia={SOGLIA_COPERTURA_SCANSIONE:.2f})"
            )
            continue

        # densita_testo: segnale secondario, soglia unica informativa.
        critico_digitale, critico_scansione = min(dig), max(scan)
        alto, basso = max(critico_digitale, critico_scansione), min(
            critico_digitale, critico_scansione
        )
        lato_alto = "digitale" if critico_digitale >= critico_scansione else "scansione"
        margine = alto / basso if basso else float("inf")
        print(
            f"margine di separazione = {margine:.2f}x "
            f"(lato piu' alto: {lato_alto}={alto:.2e}, piu' basso={basso:.2e})"
        )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        casi = _genera_casi(Path(tmp))
        _stampa_tabella(casi)
        _stampa_statistiche(casi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
