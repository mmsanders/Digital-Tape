# spec/ — the source of truth

**Owner: Program Manager. Frozen at the Phase 0 gate.**

Code conforms to these documents. When implementation reveals a spec is wrong — and it will,
two or three times — the fix is a PM escalation that updates the spec first and the code
second. **Never the reverse.** A spec that drifts to describe whatever got built is not a
specification, it is a changelog, and three streams are reading it as truth.

Any change to a file in this directory is escalation trigger #1. No exceptions, including
typos that look load-bearing and typos that do not.

## Two tiers

Established by **PM Decisions 001 §3**. This directory is frozen; `spec/hw/` is not.

| Path | Owner | Status | Contents |
|---|---|---|---|
| `spec/` | PM | **Frozen** at the Phase 0 gate. Changes are escalation trigger #1. | `tapefs-v1.md`, `engine-api.md`, `acceptance.md` |
| `spec/hw/` | **Hardware Lead** | **Versioned, not frozen.** No PM gate. | `board-rev-a.md`, `thermal-budget.md` |

The cut is at the *consumer*, not the document. `board-rev-a.md` carries a notification
obligation to the Software Lead instead of a PM gate; see `spec/hw/README.md`. **Limits stay
here**: the numbers a unit must not exceed are PM-owned even when the measurement against them
is not.

| File | Fills in | Status |
|---|---|---|
| `tapefs-v1.md` | WP-02 | Written |
| `engine-api.md` | WP-03 | Written |
| `acceptance.md` | WP-02/03, then per package | Not written — **7 hardware limits proposed**, `spec/hw/thermal-budget.md` §8 |
| `hw/thermal-budget.md` | WP-34, Hardware Lead | Rev 0.1 — estimates, no measurements yet |
| `hw/board-rev-a.md` | WP-26 onward, Hardware Lead | Rev 0.1 — skeleton, nothing `FROZEN` |
