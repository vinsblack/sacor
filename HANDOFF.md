# Handoff — 2026-08-13

For whoever (human or agent) picks this up next. Not a status report
for stakeholders — a "what you need to know before touching anything"
doc. Source of truth is always the repo/git; this is a snapshot, not
a mirror to maintain forever (delete or rewrite it once stale).

## Where things stand

- **G1 reached** (ADR-062): `pip install sacor` works, repo public,
  Evidence Model shipped.
- **`POSITIONING.md`** — the project's thesis is written and pushed.
  Explicit instruction: **don't touch it** unless real users
  systematically misunderstand something specific. Not a living doc
  to iterate on speculatively.
- **Adoption Report v1** (`docs/adoption-report-v1.md`) — first
  simulated first-time-user pass. Found product bugs, not code bugs.
  P0 (blocked adoption) fixed and verified; P1/P2/P3 open, see the
  report for the full list and severities.
- **Community Foundations sprint closed** — Discussions, issue
  templates, labels, 3 seed issues, project board, milestones. All
  done directly via `gh`/GraphQL, live on GitHub, mostly no commits
  (see "How things were done" below for the two steps that need a
  human).
- **`docs/adoption-metrics.md`** — weekly tracking file, one baseline
  entry so far (13-08). Success criteria defined there: first
  external issue/discussion/PR/fork/usage report, not stars.

## What's next (proposed, not started)

**Sprint 3 — "Real World Validation"**: stop adding governance/
features, get 5 real external developers to actually use sacor.
Watch where they get stuck. The KPIs that matter from here are
external signals (`docs/adoption-metrics.md`), not internal backlog
size.

## Open findings not yet fixed (from Adoption Report v1)

- P1: README JSON example doesn't match real CLI output shape.
- P1: PyPI `Summary` metadata still says "The Open Document Extraction
  Engine", not "Evidence-first Document Extraction".
- P2: CLI is 100% Italian (`--help`, error messages) — README is
  English-first, first command a non-Italian dev runs breaks that.
- P2: `gate` doesn't exist as a JSON key — real key is `esito`
  (Italian). POSITIONING.md documents "gate" as an architectural
  property; the wording and the code disagree.
- P2: `--schema` available values (gas/CTE) undocumented in `--help`.

## Things that surprised me this session (worth knowing before you act)

- **GitHub API cannot manage Discussion categories or pin
  discussions.** No GraphQL mutation exists for either (checked via
  introspection, not assumption). Both were done manually by the user
  in the browser. Don't waste time looking for a CLI way — there
  isn't one yet.
- **`gh project field-edit` doesn't exist** — to change a single-select
  field's options (e.g. the Status column names), you delete+recreate
  isn't allowed on the built-in `Status` field either (`Only custom
  fields can be deleted`). The way that worked: GraphQL
  `updateProjectV2Field` with a full `singleSelectOptions` replace.
- **`gh auth` token needs `project` scope** to touch Projects v2 at
  all — not included by default, requires an interactive device-flow
  authorization the user has to complete in a browser.
- **`sacor[providers]` extra already existed** in `pyproject.toml`
  before this session (`anthropic`+`openai`) — it just wasn't
  documented anywhere or handled gracefully in code. The fix wasn't
  "add an extra", it was "catch the ModuleNotFoundError and point at
  the extra that was already there."

## Ground rules that held all session (keep following them)

- One task → verify → commit → push → stop. Don't batch multiple
  sprint items into one push.
- TDD for code changes: failing test reproducing the real bug first,
  then the minimal fix, verify green, re-verify in a clean environment
  (not just unit tests) before calling it done.
- Root-cause fixes at the single shared function, not scattered
  per-caller patches.
- No real PDFs of third parties in the repo, ever, without documented
  consent — synthetic (`corpus/synth/`) or consented (`corpus/cte/`,
  `corpus/reale/`) only.
- Measure before claiming (CONTRIBUTING.md) — this is also why
  Adoption Report v1 exists: the same discipline applied to UX, not
  just accuracy numbers.
