# Adoption Report v1 — First-Time User Simulation

**Date:** 2026-08-13
**Method:** Clean venv, `pip install sacor` from real PyPI, only the
public README followed — no repo knowledge assumed. No fixes applied
during the simulation itself; findings recorded first, fixed after.

This is not a code review. Every issue below is a **product** friction
point — the code worked; the *experience* of a stranger arriving with
nothing but `pip install sacor` did not.

## Metrics

| Metric | Target | Actual (before fix) | Actual (after fix) |
|---|---:|---:|---:|
| Time to first successful extraction | < 60s | blocked — never succeeded on the documented path | ~15s (`pip install` + `curl` + `extract`) |
| Commands executed | — | 8 | 3 |
| Unexpected errors | 0 | 2 (raw Python traceback on `--tier1`; `file non trovato` on undocumented Quick Start command) | 0 |
| Documentation searches required | 0 | 1 (had to find a sample PDF inside `corpus/synth/`, not linked from README) | 0 |

## Findings

### 🔴 P0 — blocks adoption

**1. `--tier1` crashed with a raw traceback, not a sacor error.**
The `providers` extra (`anthropic`, `openai` — declared in
`pyproject.toml`) already existed but was never surfaced: not
mentioned in the README, not in `--help`, and not caught anywhere in
the code. `sacor extract file.pdf --tier1` on a plain `pip install
sacor` hit `ModuleNotFoundError: No module named 'anthropic'` as an
unhandled exception — the second command shown in the README's Quick
Start could not finish without a Python stack trace.

**2. Quick Start not runnable as written.**
`sacor extract bolletta.pdf` — no `bolletta.pdf` ships with the pip
package or is linked from the README. A new user had nothing to run
the tool on until manually finding (undocumented) `corpus/synth/*.pdf`
inside the repo.

### 🟠 P1

**3. README JSON example ≠ real CLI output shape.**
README showed a flat `{"total": {...}}` snippet; real output is an
array of per-instance objects (`istanza_id`/`documento`/`campi`/
`esito`) with Italian field names (`campi`, `fornitore`) nested
inside. A trust problem, not just a docs gap — output not matching
docs reads as "wrong version."

**4. PyPI Summary metadata contradicted the just-established identity.**
`pip show sacor` → *"The Open Document Extraction Engine"*, not
"Evidence-first Document Extraction" (README/`POSITIONING.md`).

### 🟡 P2

**5. CLI entirely in Italian**, including internal jargon (`ADR-048`,
`ADR-053`) in `--help` text and error messages (`errore: file non
trovato`). README is English-first OSS; the first command a
non-Italian-speaking developer runs breaks that.

**6. `gate` doesn't exist as a JSON key.** POSITIONING.md documents it
as an architectural property (`pass`/`warning`/`reject`); the real key
is `esito` (Italian). `grep gate output.json` finds nothing.

**7. Available `--schema` values undocumented** — `--help` only shows
the default, not the gas/CTE schema names.

### 🟢 P3

**8. No `examples/` directory** with input + expected output for
side-by-side comparison.

## What already worked well

Tier0 alone: 0.3s, zero config, zero API key, valid JSON, exit 0. The
"quick" in Quick Start was real *once a file existed to point it at*.

## Fixes applied (this pass)

Scope: **P0 only**, per explicit instruction — architecture,
extraction logic, and the Evidence Model untouched.

- **P0#1** — `sacor/pipeline.py::_provider_tier1_default`: the
  `anthropic` import now raises `ErroreProvider` (the same exception
  every other tier1 failure already routes through — API key missing,
  network error) instead of letting `ModuleNotFoundError` escape
  uncaught. Message points to `pip install "sacor[providers]"`. Result
  is the same graceful shape as any other tier1 failure: `tier1_errore`
  populated in the JSON, exit code unaffected, no traceback. Covered by
  `tests/test_pipeline.py::test_tier1_senza_anthropic_installato_non_esplode_con_traceback`
  (RED confirmed reproducing the real crash before the fix, GREEN
  after).
- **P0#2** — `examples/sample.pdf` (synthetic, same source as
  `corpus/synth/S001.pdf`, no real data) + `examples/sample-output.json`
  + `examples/README.md` added. README Quick Start rewritten to a
  runnable 3-command sequence (`pip install` → `curl` the sample →
  `extract`), `--tier1` example updated to show the now-required
  `pip install "sacor[providers]"` step.

## Not fixed (deferred, tracked above)

P1 (#3, #4), P2 (#5, #6, #7), P3 (#8) — out of scope for this pass by
explicit instruction. Re-run this simulation after each is addressed;
this file is the baseline to diff against.

## Next simulation

Re-run the exact clean-venv steps above after P1 items land. Update
the metrics table with a new "Actual" column rather than overwriting
this one — the point of this report is to see the trend, not just the
current state.
