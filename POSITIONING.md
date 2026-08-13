# POSITIONING

One page. The reference for README, site, HN, Reddit, talks — answer the
same question the same way every time.

## Why SACOR exists

**What happens if the extracted number is wrong?**

Most document extraction engines are built to answer a different
question: how many document types can I read, how many fields can I
pull out. Accuracy is reported as one aggregate number, and every
returned value looks equally trustworthy — right or wrong, both just
print.

SACOR starts from the failure mode instead of the happy path: in
workflows where extracted data drives automated decisions, wrong data
is often more expensive than missing data. A bill total that's silently
wrong by €40 costs more than a bill total that's honestly `null` and
gets a human's attention.

## The problem

Confidence scores, when extractors have them, are usually a number
someone tuned to feel right. They're opaque — you can't tell why a
field got 0.87 instead of 0.94, and you can't act on the difference.
Downstream systems either trust every value the same amount, or trust
none of them and route everything to manual review anyway. Either way
the extractor's "confidence" isn't doing any work.

## Our thesis

**AI should know when it doesn't know.**

Not as a slogan — as a technical property you can check. If a system
can't tell you *why* a value should be trusted, it doesn't actually
know whether the value is right.

## Principles

- Evidence before confidence — confidence is computed from evidence,
  never assigned independently.
- Null over guesses — a field SACOR can't verify is `null`, not a
  plausible-looking guess.
- Deterministic before AI — regex/rules read what they reliably can;
  an optional AI layer only touches what's left.
- Every value must explain itself — `origin`, `repair`, `derivation`,
  `invariants` travel with the value, not in a separate log.
- Validation is part of extraction — arithmetic/cross-field checks
  (`invariants`) run before a value is called trusted, not after.

## What SACOR is

- An extraction engine where every field carries **evidence**
  (`origin`/`status`/`repair`/`derivation`/`invariants`), and `gate`
  (accept/reject) is a pure function of that evidence — not a
  hand-picked threshold.
- Schema-driven: a new document type is a new YAML file
  (`src/sacor/schemas/*.yaml`), not new code or a new sprint.
- Deterministic-first, with an optional AI (tier1) layer for the
  fields rules can't reliably read.
- Honest about its own accuracy: real, measured numbers in the
  README, not a cherry-picked demo.

## What SACOR is not

- Not a general-purpose document parser. It does not aim to read
  arbitrary PDFs, invoices from any country, or unstructured free
  text as well as tools built for that.
- Not an AI-first pipeline. The AI layer is optional and scoped to
  specific fields, not the default extraction path.
- Not a black box. There is no confidence number without an evidence
  trail behind it.

## Non-goals

- SACOR is **not** trying to replace general-purpose document
  extraction frameworks (Docling, Unstructured, LlamaParse). Different
  bet, different users.
- SACOR is **not** optimizing for the largest number of supported
  document types. Coverage grows by schema, deliberately, not by
  chasing breadth.
- SACOR is **not** trying to maximize extraction accuracy at any
  cost. A wrong `null` is an acceptable failure; a wrong value that
  looks right is not.

## Why not Docling / Unstructured / LlamaParse

These are strong, general-purpose tools — layout parsing, chunking
for RAG, LLM-based reading of arbitrary documents. That's a real and
different job: get text and structure out of *any* document, then let
a downstream system decide what to trust.

SACOR doesn't compete on that breadth. It has no field-level evidence
contract, no `gate`, no arithmetic invariant layer — because that's
not what those tools optimize for. If the job is "read this arbitrary
PDF into text/chunks," they're the right choice. If the job is "this
specific number feeds an automated decision and a silent wrong value
is a real cost," that's the gap SACOR fills.

## Who should use SACOR

- Teams extracting data from Italian utility bills (electricity,
  gas) or CTE pre-contractual offer sheets today, or a narrow,
  well-defined document type via a new schema tomorrow.
- Workflows where extracted values feed automated decisions
  (billing, reconciliation, compliance checks) without a human
  reading every source document.
- Anyone who'd rather get `null` and a reason than a wrong number
  with no way to tell it apart from a right one.

## Who should not use SACOR

- Anyone needing broad document-type coverage out of the box —
  today's schemas are Italian utility bills and CTE only; everything
  else needs a new YAML schema written and validated first.
- Anyone who wants a single aggregate accuracy number and doesn't
  need to know which specific fields to trust.
- Anyone whose documents aren't the kind SACOR's evidence rules
  (regex origin, arithmetic invariants, Italian decimal-comma repair)
  were built around — a new domain needs a new schema and its own
  measured accuracy, not an assumption it'll just work.

## Long-term vision

Evidence-first extraction as the trust layer between raw documents
and the systems (ERP, billing, compliance) that act on their numbers
— schema by schema, each one measured honestly before it's called
done.
