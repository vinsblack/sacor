"""Diagnosi puntuale (T4.16): dump della risposta GREZZA del modello, prima
del parsing, confrontata campo per campo con l'oracle — su un sottoinsieme
piccolo del corpus reale, solo claude-haiku-4-5 (economico). Serve a capire
COSA succede, non solo QUANTO va male (i bake-off ADR-042/043 danno solo
percentuali aggregate, mai una risposta vera letta).

Chiama l'SDK direttamente (come scripts/ispeziona.py), non AnthropicProvider:
serve il testo grezzo prima che sacor.providers.parsing lo normalizzi."""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.run import SCHEMA_PATH, istanze_da_completare, renderizza_pagine_istanza  # noqa: E402
from sacor.providers.errors import ErroreProvider  # noqa: E402
from sacor.providers.prompt import costruisci_prompt  # noqa: E402

ORACLE_PATH = REPO_ROOT / "corpus" / "reale" / "attesi.json"
CORPUS_RAW = REPO_ROOT / "corpus" / "reale" / "raw"
METADATA_PATH = REPO_ROOT / "corpus" / "reale" / "metadata.json"

# T4.16: 2 casi "puliti" (nessuna anomalia nota) + 2 casi "difficili"
# (business/IVA22, pagine estranee escluse) — se anche i puliti falliscono,
# il problema non e' nei casi limite.
DOC_DA_ISPEZIONARE = ("R001", "R010", "R002", "R013")
MODELLO = "claude-haiku-4-5"


def _chiamata_raw_anthropic(pagine: list[bytes], prompt: str) -> str:
    import anthropic

    chiave = os.environ.get("ANTHROPIC_API_KEY")
    if not chiave:
        raise ErroreProvider("ANTHROPIC_API_KEY non impostata")
    client = anthropic.Anthropic(api_key=chiave, timeout=60.0, max_retries=5)
    contenuto: list[dict[str, object]] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.standard_b64encode(p).decode("ascii"),
            },
        }
        for p in pagine
    ]
    contenuto.append({"type": "text", "text": prompt})
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=4096,
        messages=[{"role": "user", "content": contenuto}],  # type: ignore[typeddict-item]
    )
    testo = "".join(b.text for b in risposta.content if b.type == "text")
    return f"[stop_reason={risposta.stop_reason}]\n{testo}"


def main() -> int:
    if not CORPUS_RAW.is_dir():
        print("PDF reali non presenti in locale")
        return 0

    esito = istanze_da_completare(SCHEMA_PATH, ORACLE_PATH, CORPUS_RAW, METADATA_PATH)
    if esito is None:
        print("corpus reale non presente")
        return 0
    _schema, oracle, chiamate, _disallineati = esito
    per_doc = {c.chiave_oracle: c for c in chiamate}

    for doc_id in DOC_DA_ISPEZIONARE:
        chiamata = per_doc.get(doc_id)
        if chiamata is None:
            print(f"\n=== {doc_id}: nessuna chiamata tier1 necessaria o non trovato ===")
            continue

        render = renderizza_pagine_istanza(chiamata.istanza)
        pagine = [png for png, _l, _a in render]
        prompt = costruisci_prompt(chiamata.campi_mancanti)

        print(
            f"\n{'=' * 70}\n{doc_id} — {len(pagine)} pagine, "
            f"{len(chiamata.campi_mancanti)} campi chiesti"
        )
        try:
            testo = _chiamata_raw_anthropic(pagine, prompt)
        except ErroreProvider as exc:
            print(f"CHIAMATA FALLITA: {exc}")
            continue

        print(f"--- risposta grezza ---\n{testo}\n--- fine risposta ---")

        atteso = oracle.documenti[doc_id]
        print("--- atteso (per confronto manuale) ---")
        for campo in chiamata.campi_mancanti:
            print(f"  {campo.nome}: atteso={atteso.get(campo.nome)!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
