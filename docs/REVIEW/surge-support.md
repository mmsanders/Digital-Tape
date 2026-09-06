# Surge support — 6 Sep 2026

Newest first. Proposed DRAFT-8 bundle for PM issue. Not a lead packet.

## What this branch is

`surge/draft-8-freeze-candidate` against `mmsanders/Digital-Tape` `main` at DRAFT-7.

**Do not merge without the PM.** Spec authorship is the PM's. The three hashed files plus `spec/VERSION.md` are a proposal the PM can `cmp`-land. The banner inside the hash still says **NOT FROZEN**.

## Dispositions submitted for adversarial review

| ID | Severity in DRAFT-7 | Disposition | Why |
|---|---|---|---|
| **V7-001** | blocker, in candidate | `tapefs` §4.6 partner-first write order on every logical superblock update; phase 4 also repairs a *stale* lower-generation partner; WP-10 two-interruption closure | Mirror-first plus "repair only if exactly one valid copy" is how two permitted power losses leave a water line that rejects both live A indices. Partner-first is the rule format/dup step 1 already used. Requiring mutators to wait for two current copies would stall a child on a flaky card. |
| **V7-002** | major, in candidate | Headroom formula consults a counter only when that counter's `needed != 0` | `FFFFFFFF + 0 <= FFFFFFD` is false and contradicts the zero-write rows. FE/FF stay legal on crafted media; they are never written. |
| **V7-003** | major, §9 | First cut refused foreign-major cards. Self-review threw that out: it contradicts §4.3 (work slot reclaims any household card). Now: accept; step 1 writes a specified **v1 WIP template** so remount is `INCOMPLETE` not `VERSION`. Equal-generation-divergent copies have no candidate — zero both, continue as blank. | Refuse looked clean and fought a product rule. Canonicalising the barrier fields is the verifier's other fix and keeps the crash tables true. |
| **V7-004** | major, §9 | Destination `label` is a byte copy of the source `label` | Michael: the copy is the same album. |
| **V7-005** | question, §10 | `tape_service` allowed in every mounted row except Faulted | Table, §7.2 and WP-12a already agreed. The prose sentence did not. |

## Self-review that changed the draft

1. Section order: §4.6 had been inserted above §4.5. Moved.
2. V7-003 refusal of `version_major ≠ 1` vs §4.3 reclaim. Changed as above.
3. Invariant 18 / "five preconditions" had to be walked back when classification stopped being a refusal.
4. Spec-bundle gate run green, forced red with a one-byte flip, restored green.

## What this branch does not do

- Does not freeze. Does not flip the banner.
- Does not touch `engine/` implementation. PR #20 stays parked (structural Rule 1; three drafts behind).
- Does not merge hardware PR #18. Mergeable by the PM; contains the live WP-04 card.
- Does not publish findings onto `digital-tape-verification` `main`.
- Does not place a parts order.

## Branch inventory, for Michael's "land what we can" note

| Ref | Land on `main`? |
|---|---|
| This branch, spec files | Only when the PM issues the bundle |
| This branch, `CLAUDE.md` header / `FOR-MICHAEL.md` / `WP-05.md` | Yes, separately, if the PM wants process docs current while the bundle is still in review |
| PR #18 hardware | PM call. No `engine/` or `tests/`. Independent of freeze. |
| PR #20 engine | No. Rule 1. |

## Process notes Michael asked the PM to take

1. `docs/REVIEW/` should become the round brief so Michael stops pasting directions. Leads read `main`. Surge cannot give Claude Cowork a GitHub connection.
2. No 64 GB cards. Smallest current V30 microSDHC. Micro is fine.
3. Question queue first every round. This file and `docs/FOR-MICHAEL.md` start that way this round.
4. `CLAUDE.md` header on `main` still cited DRAFT-3 / DRAFT-1. Fixed on this branch.
