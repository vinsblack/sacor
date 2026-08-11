"""Ispezione di singole istanze (T4.6): salva esattamente cosa viene inviato
al provider e cosa risponde, PRIMA di ogni parsing. Diagnosi, non correzione
(C3): nessun cambio di DPI, prompt o parsing qui — solo dump.

Chiama gli SDK direttamente, non AnthropicProvider/OpenAIProvider: quei due
gia' normalizzano la risposta internamente (sacor.providers.parsing), e qui
serve vedere il testo grezzo prima che succeda."""

from __future__ import annotations

import base64
import os
import stat
import sys
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.run import (  # noqa: E402
    MODELLI_BAKEOFF,
    RISOLUZIONE_RENDER_DPI,
    ChiamataDaCompletare,
    istanze_da_completare,
    renderizza_pagine_istanza,
)
from sacor.providers.errors import ErroreProvider  # noqa: E402
from sacor.providers.prompt import costruisci_prompt  # noqa: E402

OUTPUT_ROOT = Path("/tmp/ispezione")

# T4.6, C1: scansione pulita, multi-fattura scansionato, ibrida.
FILE_DA_ISPEZIONARE = ("S005.pdf", "S011.pdf", "S009.pdf")


def _chiamate_per_file(
    chiamate: list[ChiamataDaCompletare], nome_file: str
) -> list[ChiamataDaCompletare]:
    return [c for c in chiamate if c.istanza.file.name == nome_file]


def _chiamata_raw_anthropic(modello: str, pagine: list[bytes], prompt: str) -> str:
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
        model=modello,
        max_tokens=4096,
        messages=[{"role": "user", "content": contenuto}],  # type: ignore[typeddict-item]
    )
    return "".join(b.text for b in risposta.content if b.type == "text")


def _chiamata_raw_openai(modello: str, pagine: list[bytes], prompt: str) -> str:
    import openai

    chiave = os.environ.get("OPENAI_API_KEY")
    if not chiave:
        raise ErroreProvider("OPENAI_API_KEY non impostata")
    client = openai.OpenAI(api_key=chiave, timeout=60.0, max_retries=5)
    contenuto: list[dict[str, object]] = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64.standard_b64encode(p).decode('ascii')}"
            },
        }
        for p in pagine
    ]
    contenuto.append({"type": "text", "text": prompt})
    risposta = client.chat.completions.create(
        model=modello,
        max_tokens=4096,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": contenuto}],  # type: ignore[call-overload]
    )
    messaggio = risposta.choices[0].message.content
    return messaggio if isinstance(messaggio, str) else ""


def _crea_dir_privata(percorso: Path) -> None:
    percorso.mkdir(parents=True, exist_ok=True)
    os.chmod(percorso, stat.S_IRWXU)  # 0o700


def _scrivi_privato(percorso: Path, contenuto: str | bytes) -> None:
    # T4.13 (security review): puo' contenere immagini e valori di
    # documenti REALI (non solo del corpus sintetico) sotto un path fisso
    # in /tmp, condiviso da tutti gli utenti locali — permessi ristretti,
    # non l'umask di default del processo.
    if isinstance(contenuto, bytes):
        percorso.write_bytes(contenuto)
    else:
        percorso.write_text(contenuto)
    os.chmod(percorso, stat.S_IRUSR | stat.S_IWUSR)  # 0o600


def _chiamata_raw(modello: str, pagine: list[bytes], prompt: str) -> str:
    if modello.startswith("claude-"):
        return _chiamata_raw_anthropic(modello, pagine, prompt)
    if modello.startswith("gpt-"):
        return _chiamata_raw_openai(modello, pagine, prompt)
    raise ErroreProvider(f"nessun provider noto per '{modello}'")


def ispeziona_chiamata(
    chiamata: ChiamataDaCompletare, indice: int, atteso: Mapping[str, str | None]
) -> None:
    cartella = OUTPUT_ROOT / f"{chiamata.istanza.file.stem}_istanza{indice}"
    _crea_dir_privata(cartella)

    render = renderizza_pagine_istanza(chiamata.istanza)
    prompt = costruisci_prompt(chiamata.campi_mancanti)
    _scrivi_privato(cartella / "prompt.txt", prompt)

    nomi_campi = [c.nome for c in chiamata.campi_mancanti]
    righe_oracle = [f"{nome}: {atteso.get(nome)!r}" for nome in nomi_campi]
    _scrivi_privato(cartella / "oracle_atteso.txt", "\n".join(righe_oracle))

    print(
        f"\n=== {chiamata.istanza.file.name} istanza {indice} "
        f"(pagine {chiamata.istanza.pagina_da}-{chiamata.istanza.pagina_a}) ==="
    )
    print(f"campi mancanti: {nomi_campi}")
    print(f"DPI usato: {RISOLUZIONE_RENDER_DPI}")
    print(f"cartella: {cartella}")

    pagine_bytes: list[bytes] = []
    for i, (png, larghezza, altezza) in enumerate(render):
        percorso = cartella / f"pagina_{i}.png"
        _scrivi_privato(percorso, png)
        pagine_bytes.append(png)
        print(f"  pagina {i}: {larghezza}x{altezza}px, {len(png)} byte -> {percorso.name}")

    for modello in MODELLI_BAKEOFF:
        try:
            testo = _chiamata_raw(modello, pagine_bytes, prompt)
        except ErroreProvider as exc:
            testo = f"[CHIAMATA FALLITA] {exc}"
        percorso = cartella / f"risposta_{modello}.txt"
        _scrivi_privato(percorso, testo)
        print(f"  risposta {modello} -> {percorso.name}")


def main() -> int:
    esito = istanze_da_completare()
    if esito is None:
        print("corpus non ancora presente: manca corpus/attesi.json", file=sys.stderr)
        return 1
    _schema, oracle, chiamate, _file_disallineati = esito

    _crea_dir_privata(OUTPUT_ROOT)

    for nome_file in FILE_DA_ISPEZIONARE:
        trovate = _chiamate_per_file(chiamate, nome_file)
        if not trovate:
            print(
                f"\n{nome_file}: nessuna chiamata tier 1 necessaria "
                "(tier 0 completo su questo file, o file fuori dalle 5)."
            )
            continue
        for i, chiamata in enumerate(trovate):
            atteso = oracle.documenti[chiamata.chiave_oracle]
            ispeziona_chiamata(chiamata, i, atteso)

    return 0


if __name__ == "__main__":
    sys.exit(main())
