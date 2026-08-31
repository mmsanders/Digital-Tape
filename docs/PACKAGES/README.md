# Work packages

One file per WP: interface, acceptance criteria, status. `WP-NN.md`.

A package file is written when the package is picked up, not before — the charter's stream
definitions in §04 are the authority until then.

## Index — from Software Charter §04

Package numbering and full definitions come from the plan document (Rev B), which has not yet
reached this repo. The mapping below is what the charter names directly.

| Stream | Surface | Packages |
|---|---|---|
| 1 — Tape engine | `engine/` | WP-06, 07, 08, 09, 12, 13, 36 |
| 2 — Verification | `tests/` | WP-10, WP-11 |
| 3 — Host tooling | `host/` | WP-14, 15, 16 |
| 4 — Bench firmware | `firmware/bench/` | WP-17, 18, 19, 20, 21 |
| 5 — Production firmware | `firmware/prod/` | WP-28; firmware support for WP-29, 30, 37 |

Also referenced in the charter, stream not stated: WP-01 (scaffold), WP-02 (`tapefs-v1.md`),
WP-03 (`engine-api.md`), WP-04 (transport spike), WP-05 (bench hardware).

Unaccounted for: WP-22 – WP-27, WP-31 – WP-35. Presumed hardware and integration; awaiting
the plan document.

## Per-file template

```markdown
# WP-NN — title

**Stream:** · **Owner:** · **Status:** not started | in flight | in review | accepted
**Depends on:** · **Blocks:**

## Interface
What this package exposes to other streams. The contract, not the implementation.

## Acceptance criteria
From `spec/acceptance.md`. Each criterion measurable and independently checkable.

## Independent sign-off
Verification Lead only. Date and what was run.
```
