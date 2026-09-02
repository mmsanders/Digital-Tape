# spec/ — the source of truth

**Owner: Program Manager.** Authored by the PM; the Software Lead lands the text mechanically
and does not edit it (ADR-010). If landed text looks wrong, that is a `pm-decision` issue, not a
fix in the PR.

Code conforms to these documents. When implementation reveals a spec is wrong — and it will —
the fix is a PM escalation that updates the spec first and the code second. **Never the reverse.**

Any change to a file here is escalation trigger #1.

| File | Revision | Status |
|---|---|---|
| `tapefs-v1.md` | **DRAFT-3** (2 Sep) | For adversarial review; **not frozen** |
| `engine-api.md` | **DRAFT-3** (2 Sep) | For adversarial review; **not frozen** |
| `acceptance.md` | **DRAFT-1** (2 Sep) | Freezes with the format at the Phase 0 gate |
| `thermal-budget.md` | — | Superseded by `spec/hw/` — Hardware Lead owned |

DRAFT-3 incorporates verification findings V-001…V-022, issues #2/#3/#4/#13/#14, the round-1
review packet, and Michael's answers to Q-002/003/004.

## The two rules that govern the format

**Rule 1 — The engine computes.** The caller owns anything that needs entropy, hardware
knowledge, or memory beyond the engine's budget.

**Rule 2 — Identity and validity are written last**, after the content they describe.

## Two tiers

`spec/` is PM-owned and frozen. `spec/hw/` is Hardware-Lead-owned and versioned, with
notification-not-approval on `board-rev-a.md` (ADR-021).

## Next gate

**Q-001, the format freeze**, happens after the Verification Lead's DRAFT-3 pass — not before.
