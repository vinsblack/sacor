"""Eval harness: esegue un extractor sul corpus e stampa il report per campo
e per documento (ADR-011). Extractor di default: TierZeroExtractor (ADR-032,
nessuna AI). Itera sulle istanze rilevate dalla segmentazione, non su quelle
dichiarate nell'oracle (ADR-033): misura la pipeline vera."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from sacor.cache import DEFAULT_CACHE_DIR, DEFAULT_TTL_SECONDI, CacheDisco, chiave_cache
from sacor.compare import uguali
from sacor.extractor import (
    DiagnosticaCampo,
    EsitoCampo,
    Extractor,
    TierZeroExtractor,
)
from sacor.invariants import valuta_tutte
from sacor.oracle import Oracle, OracleError, load_oracle
from sacor.providers.pricing import PrezziError
from sacor.providers.pricing import carica as carica_prezzi
from sacor.providers.prompt import costruisci_prompt
from sacor.providers.token_stima import TipoFormulaSconosciuto, stima_token_immagine
from sacor.schema import Campo, Schema, SchemaError, load
from sacor.segmentation import Istanza, segmenta
from sacor.triage import analizza, normalizza_testo

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "sacor" / "schemas" / "bolletta_luce_it.yaml"
ORACLE_PATH = REPO_ROOT / "corpus" / "attesi.json"
METADATA_PATH = REPO_ROOT / "corpus" / "metadata.json"
CORPUS_RAW = REPO_ROOT / "corpus" / "synth"

# T4.4: elenco dei modelli del bake-off (scripts/bakeoff.py legge questa
# stessa lista, non una copia). Nessun modello "scelto" nel codice — e' solo
# l'insieme su cui gira il confronto; la tabella prodotta dal bake-off
# decide, non questa lista (istruzione utente verbatim).
MODELLI_BAKEOFF: tuple[str, ...] = ("claude-haiku-4-5", "gpt-4o-mini", "claude-opus-5")

# T4.5, C1: stessa risoluzione usata da --dry-run per stimare e da
# scripts/bakeoff.py per chiamare davvero — la stima deve misurare quello
# che poi viene realmente inviato, non un'approssimazione indipendente.
RISOLUZIONE_RENDER_DPI = 150

# ADR-035 (provvisorio): nessun modello di produzione scelto per il flusso
# tier 1 normale (non bake-off, che disattiva sempre la cache — T4.4). Serve
# solo a dare un namespace stabile alla chiave di cache in --dry-run.
_MODELLO_CACHE_GENERICO = "tier1-generico"
_TOKEN_OUTPUT_STIMATI_PER_CAMPO = 8


@dataclass(frozen=True)
class RisultatoCampo:
    nome: str
    non_estratto: int
    non_normalizzabile: int
    normalizzato: int
    corretti: int
    totale: int

    @property
    def accuratezza(self) -> float:
        return self.corretti / self.totale if self.totale else 0.0


@dataclass(frozen=True)
class Report:
    documento: str
    n_documenti: int
    documenti_corretti: int
    campi: tuple[RisultatoCampo, ...]
    gate_pass: int
    gate_warning: int
    gate_reject: int
    valori_errati: int = 0  # T3.3: non-None ma sbagliato — l'estrattore "inventa"
    segmentazione_disallineata: int = 0  # T3.4: n. istanze rilevate != n. istanze oracle
    violazioni_invarianti: int = 0  # ADR-045: lo strato Arbitrate, ora eseguito davvero

    @property
    def accuratezza_documento(self) -> float:
        return self.documenti_corretti / self.n_documenti if self.n_documenti else 0.0


def _carica_metadata(path: Path) -> dict[str, Mapping[str, object]]:
    if not path.is_file():
        return {}
    dati = json.loads(path.read_text())
    if not isinstance(dati, dict):
        return {}
    # ADR-025: corpus/metadata.json porta un blocco "composizione" in testa;
    # le voci per istanza vivono sotto "documenti". Formato piatto (senza
    # wrapper) tollerato per compatibilita' con generazioni non composite.
    documenti = dati.get("documenti", dati)
    return documenti if isinstance(documenti, dict) else {}


def _raggruppa_per_file(
    oracle: Oracle, metadata: Mapping[str, Mapping[str, object]]
) -> dict[str, list[str]]:
    """file -> chiavi oracle che vi appartengono, nell'ordine di apparizione.

    Si parte dalle chiavi dell'ORACLE (cio' che serve valutare), non da
    quelle di metadata: un oracle scritto a mano (senza metadata.json) deve
    restare valutabile. Il file si risolve da metadata quando c'e'; altrimenti
    si assume che la chiave coincida col nome del file (ADR-014-bis: stesso
    fallback gia' usato altrove per un'istanza senza metadata)."""
    per_file: dict[str, list[str]] = {}
    for chiave in oracle.documenti:
        voce = metadata.get(chiave, {})
        nome_file = str(voce.get("file", f"{chiave}.pdf"))
        per_file.setdefault(nome_file, []).append(chiave)
    return per_file


@dataclass(frozen=True)
class ChiamataDaCompletare:
    """Un'istanza (ADR-033) per cui il tier 0 lascia almeno un campo None,
    coi campi mancanti da chiedere al tier 1. Calcolate in un solo posto:
    --dry-run e scripts/bakeoff.py (T4.4: 'stesse 5 chiamate') leggono
    esattamente questo elenco, non una rideterminazione indipendente."""

    istanza: Istanza
    chiave_oracle: str
    campi_mancanti: tuple[Campo, ...]


def istanze_da_completare(
    schema_path: Path = SCHEMA_PATH,
    oracle_path: Path = ORACLE_PATH,
    corpus_raw: Path = CORPUS_RAW,
    metadata_path: Path = METADATA_PATH,
) -> tuple[Schema, Oracle, list[ChiamataDaCompletare], int] | None:
    """None se il corpus non c'e' ancora. Altrimenti (schema, oracle,
    chiamate, file_disallineati): stesso criterio di esegui_eval per
    associare istanze rilevate a chiavi oracle (per ordine di pagina, MAI
    per id — ADR-014-bis), gli stessi file esclusi se il numero di istanze
    rilevate non combacia (ADR-033)."""
    schema = load(schema_path)
    if not oracle_path.is_file():
        return None
    oracle = load_oracle(oracle_path, schema)
    metadata = _carica_metadata(metadata_path)
    per_file = _raggruppa_per_file(oracle, metadata)

    tier0 = TierZeroExtractor()
    chiamate: list[ChiamataDaCompletare] = []
    file_disallineati = 0

    for nome_file, chiavi_oracle in per_file.items():
        pdf = corpus_raw / nome_file
        triage_result = analizza(pdf)
        with pdfplumber.open(pdf) as documento:
            testi_pagine = [normalizza_testo(p) for p in documento.pages]
        esito_segmentazione = segmenta(
            pdf, triage_result.pagine, testi_pagine, schema.segmentazione
        )

        if len(esito_segmentazione.istanze) != len(chiavi_oracle):
            file_disallineati += 1
            continue

        for istanza, chiave_oracle in zip(esito_segmentazione.istanze, chiavi_oracle, strict=True):
            estratti = tier0.extract(istanza, schema)
            campi_mancanti = tuple(c for c in schema.campi if estratti.get(c.nome) is None)
            if campi_mancanti:
                chiamate.append(ChiamataDaCompletare(istanza, chiave_oracle, campi_mancanti))

    return schema, oracle, chiamate, file_disallineati


def renderizza_pagine_istanza(istanza: Istanza) -> list[tuple[bytes, int, int]]:
    """PNG (bytes, larghezza_px, altezza_px) per ogni pagina dell'istanza,
    alla stessa risoluzione di scripts/bakeoff.py (T4.5, C1): le pagine del
    tier 1 sono SCANSIONE/IBRIDA, senza text layer — solo l'immagine
    renderizzata dice quanto costa davvero la chiamata."""
    with pdfplumber.open(istanza.file) as documento:
        pagine = documento.pages[istanza.pagina_da - 1 : istanza.pagina_a]
        risultato: list[tuple[bytes, int, int]] = []
        for pagina in pagine:
            immagine = pagina.to_image(resolution=RISOLUZIONE_RENDER_DPI).original
            buffer = io.BytesIO()
            immagine.save(buffer, format="PNG")
            larghezza, altezza = immagine.size
            risultato.append((buffer.getvalue(), larghezza, altezza))
        return risultato


def _diagnostica_per(
    extractor: Extractor, istanza: Istanza, schema: Schema
) -> dict[str, DiagnosticaCampo]:
    """T3.3: solo TierZeroExtractor sa distinguere non_estratto da
    non_normalizzabile (passa dentro Repair). Per un Extractor generico si
    puo' solo dedurre normalizzato/non_estratto dal valore finale."""
    if isinstance(extractor, TierZeroExtractor):
        return extractor.estrai_diagnostica(istanza, schema)

    estratti = extractor.extract(istanza, schema)
    return {
        nome: DiagnosticaCampo(
            EsitoCampo.NORMALIZZATO if valore is not None else EsitoCampo.NON_ESTRATTO,
            valore,
        )
        for nome, valore in estratti.items()
    }


def esegui_eval(
    schema: Schema,
    oracle: Oracle,
    extractor: Extractor,
    corpus_raw: Path,
    metadata: Mapping[str, Mapping[str, object]] | None = None,
) -> Report:
    metadata = metadata or {}
    per_file = _raggruppa_per_file(oracle, metadata)

    non_estratto = {c.nome: 0 for c in schema.campi}
    non_normalizzabile = {c.nome: 0 for c in schema.campi}
    normalizzato = {c.nome: 0 for c in schema.campi}
    corretti = {c.nome: 0 for c in schema.campi}
    documenti_corretti = 0
    gate_reject = 0
    gate_warning = 0
    valori_errati = 0
    segmentazione_disallineata = 0
    violazioni_invarianti = 0

    for nome_file, chiavi_oracle in per_file.items():
        pdf = corpus_raw / nome_file
        triage_result = analizza(pdf)
        with pdfplumber.open(pdf) as documento:
            testi = [normalizza_testo(p) for p in documento.pages]
        esito_segmentazione = segmenta(pdf, triage_result.pagine, testi, schema.segmentazione)
        istanze_rilevate = esito_segmentazione.istanze

        if len(istanze_rilevate) != len(chiavi_oracle):
            # ADR-033: non si forza l'allineamento con l'oracle. Se la
            # segmentazione rilevata non ha lo stesso numero di istanze
            # dichiarate, non c'e' un modo onesto di attribuire i campi
            # estratti a una specifica istanza oracle: ogni istanza oracle
            # di questo file conta come non estratta e non corretta.
            segmentazione_disallineata += 1
            for _ in chiavi_oracle:
                for campo in schema.campi:
                    non_estratto[campo.nome] += 1
                if any(c.obbligatorio for c in schema.campi):
                    gate_reject += 1
            continue

        # Il conteggio combacia: si accoppiano per ordine di pagina, MAI per
        # id (ADR-014-bis: gli id oracle sono opachi, non si interpretano).
        for istanza, chiave_oracle in zip(istanze_rilevate, chiavi_oracle, strict=True):
            attesi = oracle.documenti[chiave_oracle]
            diagnostica = _diagnostica_per(extractor, istanza, schema)
            estratti = {nome: d.valore for nome, d in diagnostica.items()}

            tutti_corretti = True
            for campo in schema.campi:
                esito = diagnostica[campo.nome].esito
                if esito is EsitoCampo.NON_ESTRATTO:
                    non_estratto[campo.nome] += 1
                elif esito is EsitoCampo.NON_NORMALIZZABILE:
                    non_normalizzabile[campo.nome] += 1
                else:
                    normalizzato[campo.nome] += 1

                valore_estratto = estratti.get(campo.nome)
                if uguali(attesi.get(campo.nome), valore_estratto, campo.tipo):
                    corretti[campo.nome] += 1
                else:
                    tutti_corretti = False
                    if valore_estratto is not None:
                        valori_errati += 1

            if tutti_corretti:
                documenti_corretti += 1

            # ADR-045: lo strato Arbitrate, ora eseguito davvero — non solo
            # dichiarato. Una violazione 'reject' rigetta il documento anche
            # se tutti i campi obbligatori sono presenti; una 'warning' lo
            # sposta da pass a warning, mai a reject da sola.
            violazioni = valuta_tutte(schema, estratti)
            violazioni_invarianti += len(violazioni)
            ha_violazione_reject = any(v.severita == "reject" for v in violazioni)
            ha_violazione_warning = any(v.severita == "warning" for v in violazioni)

            campo_obbligatorio_mancante = any(
                c.obbligatorio and estratti.get(c.nome) is None for c in schema.campi
            )
            if campo_obbligatorio_mancante or ha_violazione_reject:
                gate_reject += 1
            elif ha_violazione_warning:
                gate_warning += 1

    n_documenti = len(oracle.documenti)
    campi_report = tuple(
        RisultatoCampo(
            nome=c.nome,
            non_estratto=non_estratto[c.nome],
            non_normalizzabile=non_normalizzabile[c.nome],
            normalizzato=normalizzato[c.nome],
            corretti=corretti[c.nome],
            totale=n_documenti,
        )
        for c in schema.campi
    )

    return Report(
        documento=schema.documento,
        n_documenti=n_documenti,
        documenti_corretti=documenti_corretti,
        campi=campi_report,
        gate_pass=n_documenti - gate_reject - gate_warning,
        gate_warning=gate_warning,
        gate_reject=gate_reject,
        valori_errati=valori_errati,
        segmentazione_disallineata=segmentazione_disallineata,
        violazioni_invarianti=violazioni_invarianti,
    )


def carica_report(
    schema_path: Path = SCHEMA_PATH,
    oracle_path: Path = ORACLE_PATH,
    corpus_raw: Path = CORPUS_RAW,
    metadata_path: Path = METADATA_PATH,
    extractor: Extractor | None = None,
) -> Report | None:
    """Ritorna il report, o None se il corpus (oracle) non e' ancora presente."""
    schema = load(schema_path)
    if not oracle_path.is_file():
        return None
    oracle = load_oracle(oracle_path, schema)
    metadata = _carica_metadata(metadata_path)
    return esegui_eval(schema, oracle, extractor or TierZeroExtractor(), corpus_raw, metadata)


def _cella(n: int, totale: int) -> str:
    return f"{n}/{totale}"


def formatta_report(report: Report) -> str:
    righe = [
        f"sacor eval — {report.documento} — {report.n_documenti} documenti",
        "",
        f"ACCURATEZZA PER DOCUMENTO: {report.accuratezza_documento * 100:.1f}%  "
        f"({report.documenti_corretti}/{report.n_documenti})",
        "",
        f"{'Campo':<16}{'non estratto':>14}{'non normaliz.':>15}"
        f"{'normalizzato':>14}{'corretto':>10}",
    ]

    tot_non_estratto = tot_non_normalizzabile = tot_normalizzato = tot_corretti = 0
    for c in report.campi:
        righe.append(
            f"{c.nome:<16}"
            f"{_cella(c.non_estratto, c.totale):>14}"
            f"{_cella(c.non_normalizzabile, c.totale):>15}"
            f"{_cella(c.normalizzato, c.totale):>14}"
            f"{_cella(c.corretti, c.totale):>10}"
        )
        tot_non_estratto += c.non_estratto
        tot_non_normalizzabile += c.non_normalizzabile
        tot_normalizzato += c.normalizzato
        tot_corretti += c.corretti

    totale_slot = report.n_documenti * len(report.campi)
    righe.append("---")
    righe.append(
        f"{'TOTALE CAMPI':<16}"
        f"{_cella(tot_non_estratto, totale_slot):>14}"
        f"{_cella(tot_non_normalizzabile, totale_slot):>15}"
        f"{_cella(tot_normalizzato, totale_slot):>14}"
        f"{_cella(tot_corretti, totale_slot):>10}"
    )
    righe.append("")
    righe.append(
        f"Gate: pass {report.gate_pass} | warning {report.gate_warning} | "
        f"reject {report.gate_reject}"
    )
    righe.append("Escalation: n/d (nessun extractor a due tier)")
    righe.append(f"Campi con valore NON-None ma errato: {report.valori_errati}")
    righe.append(
        f"File con segmentazione disallineata dall'oracle: {report.segmentazione_disallineata}"
    )
    righe.append(f"Violazioni invarianti (ADR-045, Arbitrate): {report.violazioni_invarianti}")
    return "\n".join(righe)


@dataclass(frozen=True)
class StimaCostoModello:
    token_input_stimati: int
    token_output_stimati: int
    costo_stimato: float


@dataclass(frozen=True)
class StimaDryRun:
    chiamate_necessarie: int
    gia_in_cache: int
    file_disallineati: int
    costo_per_modello: dict[str, StimaCostoModello]  # vuoto se i prezzi non si caricano
    # T4.13: senza formula token_immagine per una pagina, mai stimati per difetto.
    modelli_esclusi: tuple[str, ...] = ()


def esegui_dry_run(
    schema_path: Path = SCHEMA_PATH,
    oracle_path: Path = ORACLE_PATH,
    corpus_raw: Path = CORPUS_RAW,
    metadata_path: Path = METADATA_PATH,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    ttl_secondi: int = DEFAULT_TTL_SECONDI,
    modelli: Sequence[str] = MODELLI_BAKEOFF,
) -> StimaDryRun | None:
    """ADR-034: stima quante chiamate servirebbero, senza chiamare nulla.
    ADR-035: una chiamata serve solo per istanze dove tier 0 ha lasciato
    almeno un campo None — un valore deterministico non si sovrascrive mai.

    T4.5, C1: le pagine coinvolte sono SCANSIONE/IBRIDA, senza text layer —
    i token si stimano dall'immagine renderizzata (stessa risoluzione di
    scripts/bakeoff.py), con la formula del provider dichiarata in
    config/prezzi_modelli.yaml, non dalla lunghezza del testo."""
    esito = istanze_da_completare(schema_path, oracle_path, corpus_raw, metadata_path)
    if esito is None:
        return None
    schema, _oracle, chiamate, file_disallineati = esito
    return stima_costo_chiamate(
        schema, chiamate, file_disallineati, cache_dir, ttl_secondi, modelli
    )


def stima_costo_chiamate(
    schema: Schema,
    chiamate: list[ChiamataDaCompletare],
    file_disallineati: int,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    ttl_secondi: int = DEFAULT_TTL_SECONDI,
    modelli: Sequence[str] = MODELLI_BAKEOFF,
) -> StimaDryRun:
    """Stima di costo a partire da un elenco di chiamate GIA' calcolato
    (T4.13, BASSA, trovato in review): separata da esegui_dry_run perche' chi
    ha gia' triage/segmentazione/rendering in mano (scripts/bakeoff.py, che
    calcola le stesse chiamate per farle davvero) non deve rifare da capo lo
    stesso lavoro — triage, segmentazione e rendering PNG di ogni pagina di
    ogni file — solo per ottenere la stima di costo. esegui_dry_run resta
    l'entry point quando le chiamate non sono ancora note."""
    cache = CacheDisco(cache_dir=cache_dir, ttl_secondi=ttl_secondi)
    gia_in_cache = 0
    # Renderizzata una sola volta per chiamata, riusata per ogni modello:
    # il rendering non dipende dal modello, solo la formula di conteggio.
    chiamate_da_stimare: list[tuple[ChiamataDaCompletare, str, list[tuple[bytes, int, int]]]] = []

    for chiamata in chiamate:
        prompt = costruisci_prompt(chiamata.campi_mancanti)
        render = renderizza_pagine_istanza(chiamata.istanza)
        pagine_bytes = [png for png, _larghezza, _altezza in render]

        chiave = chiave_cache(pagine_bytes, prompt, _MODELLO_CACHE_GENERICO, schema.schema_version)
        if cache.contiene(chiave):
            gia_in_cache += 1
            continue
        chiamate_da_stimare.append((chiamata, prompt, render))

    costo_per_modello: dict[str, StimaCostoModello] = {}
    try:
        prezzi = carica_prezzi()
    except PrezziError:
        prezzi = None

    modelli_esclusi: list[str] = []
    if prezzi is not None:
        for modello in modelli:
            try:
                prezzo = prezzi.prezzo(modello)
            except PrezziError:
                continue

            token_input = token_output = 0
            formula_mancante = False
            for chiamata, prompt, render in chiamate_da_stimare:
                token_input += len(prompt) // 4  # solo il testo del prompt: stima approssimata
                for _png, larghezza, altezza in render:
                    try:
                        token_input += stima_token_immagine(prezzo, larghezza, altezza)
                    except TipoFormulaSconosciuto:
                        # T4.13: nessuna formula token_immagine per questo
                        # modello -> il modello va escluso DAL TUTTO, non
                        # sommato con un pezzo mancante. Una stima che conta
                        # solo il testo del prompt e salta ogni immagine e'
                        # sottostimata di un ordine di grandezza e peggio
                        # di nessuna stima (vedi token_stima.py: "una stima
                        # che sbaglia per difetto no" — istruzione verbatim).
                        formula_mancante = True
                        break
                if formula_mancante:
                    break
                token_output += len(chiamata.campi_mancanti) * _TOKEN_OUTPUT_STIMATI_PER_CAMPO

            if formula_mancante:
                modelli_esclusi.append(modello)
                continue

            costo_per_modello[modello] = StimaCostoModello(
                token_input_stimati=token_input,
                token_output_stimati=token_output,
                costo_stimato=prezzo.costo(token_input, token_output),
            )

    return StimaDryRun(
        chiamate_necessarie=len(chiamate),
        gia_in_cache=gia_in_cache,
        modelli_esclusi=tuple(modelli_esclusi),
        file_disallineati=file_disallineati,
        costo_per_modello=costo_per_modello,
    )


def formatta_dry_run(stima: StimaDryRun) -> str:
    righe = [
        "sacor eval --dry-run",
        "",
        f"Chiamate tier 1 necessarie (solo campi None dopo tier 0, ADR-035): "
        f"{stima.chiamate_necessarie}",
        f"Gia' in cache: {stima.gia_in_cache}",
        f"Da chiamare: {stima.chiamate_necessarie - stima.gia_in_cache}",
    ]
    if stima.file_disallineati:
        righe.append(
            "File con segmentazione disallineata dall'oracle (esclusi dalla stima): "
            f"{stima.file_disallineati}"
        )
    righe.append("")
    if stima.costo_per_modello:
        righe.append(
            "Stima per modello (token immagine da pagina renderizzata, C1/T4.5 — "
            "formula per provider in config/prezzi_modelli.yaml):"
        )
        for modello, s in stima.costo_per_modello.items():
            righe.append(
                f"  {modello:<20} {s.token_input_stimati:>7} tok input, "
                f"{s.token_output_stimati:>5} tok output  ->  ${s.costo_stimato:.4f}"
            )
    else:
        righe.append("Tabella prezzi non disponibile: nessuna stima di costo per modello.")
    if stima.modelli_esclusi:
        righe.append("")
        righe.append(
            "ATTENZIONE — esclusi dalla stima (nessuna formula 'token_immagine' in "
            "config/prezzi_modelli.yaml, una stima senza i token immagine sarebbe "
            f"sottostimata): {', '.join(stima.modelli_esclusi)}"
        )
    righe.append("")
    righe.append("Nessuna chiamata effettuata.")
    return "\n".join(righe)


def main() -> int:
    if "--dry-run" in sys.argv[1:]:
        try:
            stima = esegui_dry_run()
        except SchemaError as exc:
            print(f"errore schema: {exc}", file=sys.stderr)
            return 1
        except OracleError as exc:
            print(f"errore oracle: {exc}", file=sys.stderr)
            return 1

        if stima is None:
            print("corpus non ancora presente: manca corpus/attesi.json")
            return 0

        print(formatta_dry_run(stima))
        return 0

    try:
        report = carica_report()
    except SchemaError as exc:
        print(f"errore schema: {exc}", file=sys.stderr)
        return 1
    except OracleError as exc:
        print(f"errore oracle: {exc}", file=sys.stderr)
        return 1

    if report is None:
        print("corpus non ancora presente: manca corpus/attesi.json")
        return 0

    print(formatta_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
