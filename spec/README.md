# spec/ — the source of truth

**Owner: Program Manager.** Authored by the PM; the Software Lead lands the text mechanically
and does not edit it (ADR-010). If landed text looks wrong, that is a `pm-decision` issue, not a
fix in the PR.

Code conforms to these documents. When implementation reveals a spec is wrong — and it will —
the fix is a PM escalation that updates the spec first and the code second. **Never the reverse.**

Any change to a file here is escalation trigger #1.

| File | Status |
|---|---|
| `tapefs-v1.md` | For adversarial review. §§1–8 are the **freeze candidate**; §9 freezes at the first green WP-10 run |
| `engine-api.md` | For adversarial review. §§2–8 and §12 are the **freeze candidate**; §10 freezes at the first green WP-10 run |
| `acceptance.md` | Freezes with the format at the Phase 0 gate |
| `thermal-budget.md` | Superseded by `spec/hw/` — Hardware Lead owned |

**Revisions are deliberately not listed here.** `spec/VERSION.md` is the manifest — revision and
SHA-256 per file — and `tools/ci/verify-spec-bundle.sh` enforces it on every PR. A revision
written in two places is a revision that can disagree with itself, which is exactly how `main`
came to publish DRAFT-3, DRAFT-3 and DRAFT-1 under three headers that each claimed to be
versioned in step.

## The three rules that govern the format

**Rule 1 — The engine computes.** The caller owns anything that needs entropy, hardware
knowledge, or memory beyond the engine's budget.

**Rule 2 — Identity and validity are written last**, after the content they describe.

**Rule 3 — Ownership is not reference.** A side may *reference* chunks it does not *own*; it may
only allocate and write within what it owns. This is the copy-on-write mechanism the whole
format rests on.

## Two tiers

`spec/` is PM-owned and frozen. `spec/hw/` is Hardware-Lead-owned and versioned, with
notification-not-approval on `board-rev-a.md` (ADR-021).

## Attack these first

The PM names three passages as resolved by design decision rather than correction, and therefore
the least-scrutinised text in the documents: **`tapefs` §9.3** (promote's phase-1 double commit),
**§9.4** (per-pass disjointness), and the **forbid-while-armed** rule in `engine-api` §10.

## Next gate

**Q-001, the format freeze**, happens after the Verification Lead's pass on the current bundle —
not before. It splits in two: the byte-level surface freezes at the Phase 0 gate, operations and
the state matrix at the first green WP-10 run, because behaviour should freeze when tests prove
it rather than when a document says so (PM Decisions 007 §2).
