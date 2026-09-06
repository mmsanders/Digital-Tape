# Surge support — 6 Sep 2026

Newest first. Proposed DRAFT-8 bundle for PM issue. Not a lead packet.

## What this branch is

`surge/draft-8-freeze-candidate` against `mmsanders/Digital-Tape` `main` at DRAFT-7.

**Do not merge without the PM.** Spec authorship is the PM's. The three hashed files plus `spec/VERSION.md` are a proposal the PM can `cmp`-land. The banner inside the hash still says **NOT FROZEN**.

## Dispositions submitted for adversarial review

| ID | Severity in DRAFT-7 | Disposition | Why |
|---|---|---|---|
| **V7-001** | blocker, in candidate | `tapefs` §4.6 partner-first write order on every *ordinary* logical superblock update; phase 4 also repairs a *stale* lower-generation partner; WP-10 two-interruption closure | Mirror-first plus "repair only if exactly one valid copy" is how two permitted power losses leave a water line that rejects both live A indices. Partner-first is the rule format/dup step 1 already used. Requiring mutators to wait for two current copies would stall a child on a flaky card. |
| **V7-002** | major, in candidate | Headroom formula consults a counter only when that counter's `needed != 0` | `FFFFFFFF + 0 <= FFFFFFD` is false and contradicts the zero-write rows. FE/FF stay legal on crafted media; they are never written. |
| **V7-003** | major, §9 | Accept foreign-major cards. Step 1 writes a specified **v1 WIP template** so remount is `INCOMPLETE` not `VERSION`. Equal-generation-divergent copies have no candidate — zero both *after* refusal preconditions, continue as blank. | Refuse looked clean and fought §4.3 (work slot reclaims any household card). Classification is a plan, not a write, so a card that is both inconsistent and too small is refused, not erased. |
| **V7-004** | major, §9 | Destination `label` is a byte copy of the source `label` | Michael: the copy is the same album. |
| **V7-005** | question, §10 | `tape_service` allowed in every mounted row except Faulted | Table, §7.2 and WP-12a already agreed. The prose sentence did not. |

## Adversarial self-review that changed this draft (second pass, 6 Sep afternoon)

Treated as a fresh verifier against the first-cut DRAFT-8 text, not against DRAFT-7. Findings that landed:

1. **§4.6 claimed "the new `sb_generation` is strictly greater than the candidate's" and also claimed to cover "any write that produces a new `sb_generation`."** Format/dup identity-assignment commits write generation 1 after step 1 may have left a higher-generation WIP copy. Applying partner-first there would make the strictly-greater sentence false and would rename crash-table rows that already say "mirror" / "primary". **Fix:** §4.6 covers ordinary logical updates (stage clearing, promote 4 / 5-decline / 9) plus format/dup *step 1*. Identity-assignment commits stay mirror-then-primary and are named as excluded.
2. **Raw classification wrote during the precondition list.** Equal-generation-divergent zeroing in item 3 would destroy a destination that also failed geometry or capacity. That fights "all before any write" and invariant 18. **Fix:** classification is a plan. Zero-both and the v1 template are step 1, after refusals 1/2/4/5 pass.
3. **§9.5 step 1 still said "write it"** (field-edit) after item 3 specified a v1 template. Two implementations could still disagree on `version_major` of the barrier. **Fix:** step 1 writes the template, on both dup and format.
4. **Step 1 tie-break said "§4.1 phase 1 names no candidate" for a healthy identical pair.** That sentence describes the *divergent* equal-generation case. Healthy identical copies *are* a candidate plus a partner under §4.6 (primary / mirror). **Fix:** tie-break cites §4.6.
5. **Phase 1 did not record `needs_repair` for a stale lower-generation partner**, only for an invalid one, while phase 4 now repairs both. **Fix:** both bullets record it; `tape_info.needs_repair` comment matches.
6. **Newest-text paragraph still said "raw-destination refusals"** after the disposition stopped refusing foreign-major cards. **Fix:** it now says classification.

Proposed hashes after the merge-safe banner trim (dropped "Proposed bundle… Not issued by the PM." from each hashed header so a merge would not publish that sentence on `main`):

```
0007b3ef076c271f49e2c4c3414d797772ab219f62c086d8e640f8b5635b55e5  spec/tapefs-v1.md
4b2b1e0354c940ea42c8749b92a3827cc172e1e3db45a159bfa547ea9f1f30c9  spec/engine-api.md
42123be21b471c72f28b36a3f0a51f98b2a94893a8808f327d3f988f032abd75  spec/acceptance.md
```

Bundle gate: green, forced red with a one-byte flip on `acceptance.md`, restored green.


## Simulated verifier pass (third pass, 6 Sep evening)

Directed the way the DRAFT-7 review was directed: newest text first (§4.6, phase 4 stale repair, §4.5 zero-needed, §9.5/§9.6 classification), then the promote step bodies and crash tables, then invariants. What that pass would have filed against the second-cut DRAFT-8, and what changed:

| Would-have-been | Severity | Claim | Fix now in the files |
|---|---|---|---|
| **S8-001** | blocker-shaped consistency | §9.3.1 step 4 and §9.3.2 steps 5-decline and 9 still said *mirror, flush, primary, flush* after §4.6 and §9.3.4 required partner-first. The document already names this class: an implementer reading the steps literally ships the old order. | Step bodies now cite §4.6. |
| **S8-002** | major, crash oracle | Equal-generation-divergent zero-both had no mid-write row. After the mirror is zeroed the primary — one of the two previously unorderable copies — is the sole valid superblock. Remount is that old cartridge; re-run takes the template path. An exhaustive runner had no permitted outcome. | Row added to both format and duplicate tables. |
| **S8-003** | question | V7-001's other fix (refuse mutators until two current copies exist) was not explicitly rejected, so a reviewer could file it as an open alternative. | §4.6 now rejects it: stalls a child on a flaky partner write. WP-10 two-interruption closure is the test. |
| **S8-004** | doc, candidate | §4.3 still said "no mirror repair"; phase 4 now repairs a stale partner too. Invariant 7 / WP-10 "repair advanced neither" named only the invalid-copy shape. | Wording aligned. Fallback parenthetical no longer pretends the increment path sees equal-generation-divergent copies. |

Traces that survived and were *not* turned into findings:

- V7-001's two-interruption promote: after a torn partner-first first-write the candidate is untouched; after a durable first-write the new generation wins even if the candidate then tears; phase-4 repair of the leftover stale partner does not increment `sb_generation`. Mutators with `needs_repair` still cannot roll selection backwards.
- Zero-needed: `sequence_needed == 0` / `generation_needed == 1` (RESUME-at-step-5 decline) still consults generation and still refuses at `sb_generation ≥ 0xFFFFFFFD`. Only the unused counter is skipped.
- Classification-as-plan: a destination that is both divergent and too small is refused, not erased.
- Format/dup identity commits remain mirror-then-primary; their tables still work because generation goes backwards on purpose.

Still not a freeze recommendation. This pass is surge pretending to be the lead. The lead has not signed.

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

1. `docs/REVIEW/` should become the round brief so Michael stops pasting directions. Leads read `main`.
2. No 64 GB cards. Smallest current V30 microSDHC. Micro is fine.
3. Question queue first every round. This file and `docs/FOR-MICHAEL.md` start that way this round.
4. `CLAUDE.md` header on `main` still cited DRAFT-3 / DRAFT-1. Fixed on this branch.
