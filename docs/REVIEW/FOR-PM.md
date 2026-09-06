# For the PM — DRAFT-8 proposal handoff

From: surge support
Date: 6 Sep 2026
Branch: `surge/draft-8-freeze-candidate`
PR: https://github.com/mmsanders/Digital-Tape/pull/25
Canonical today: `main` is DRAFT-7 until you issue this.

This is a handoff, not a lead packet and not a freeze request. Spec authorship stays yours. I will not merge.

---

## What you are being asked to look at

A proposed DRAFT-8 spec bundle that dispositions the Verification Lead's DRAFT-7 findings (V7-001…V7-005), plus two process docs that were stale on `main`.

| File | Role |
|---|---|
| `spec/tapefs-v1.md` | Format. New §4.6, stale-partner repair in §4.1 phase 4, zero-needed exception in §4.5, raw classification in §9.5/§9.6 |
| `spec/engine-api.md` | `needs_repair` includes stale partners; invariants 32/33; V7-005 service prose; companion line |
| `spec/acceptance.md` | WP-10 two-interruption closure, zero-needed at FE/FF, foreign-major + equal-gen-divergent, source-label copy |
| `spec/VERSION.md` | DRAFT-8 manifest. Hashes below. Banner inside the three files is still **NOT FROZEN** |
| `docs/REVIEW/surge-support.md` | Round brief (dispositions + the two self-review passes) |
| `docs/REVIEW/FOR-PM.md` | This file |
| `docs/REVIEW/FOR-VERIFICATION-LEAD.md` | Separate note for the lead. Please pass it on if you want that review; I did not publish onto the verification repo |
| `CLAUDE.md` | Header on `main` still cited DRAFT-3 / DRAFT-1. Points at `spec/VERSION.md` now |
| `docs/FOR-MICHAEL.md` | 6 Sep queue close-out on top of your 5 Sep prose |
| `docs/PACKAGES/WP-05.md` | Cart no longer names 64/128 GB. Smallest current V30 microSDHC; micro is fine |

Hashes of the three files this manifest names:

```
cfb81e27672fea3bc185a48a41c8d44212fe4c0a5b2b5c04d74d4cf2ae5c2c05  spec/tapefs-v1.md
28e668ed204dd4869e66d51bd319af489e5f3a992c5f6df59cff0460655aa731  spec/engine-api.md
2e762cf445d7bfd63de4f4a674c72bc00a800969dc592c0e9ea18f3a9a1560db  spec/acceptance.md
```

The bundle gate was run green, forced red with a one-byte flip on `acceptance.md`, restored green. If you land by `cmp`, do not re-hash to make a red gate green.

---

## Why this exists

DRAFT-7 on `main` does not meet the Phase-0 freeze standard the Verification Lead applied: no blockers and no majors in `tapefs` §§1–8 and `engine-api` §§2–8+§12. V7-001 (blocker) and V7-002 (major) sit in that candidate. Michael asked surge to get a freeze-*candidate* on a branch, not to freeze, and not to touch `main`.

Operations and the state matrix still freeze at the first green WP-10. This PR does not change that sentence.

---

## Dispositions, and the calls that were mine

Michael said V7-001 and V7-003 were my call, and the duplicate label is a copy of the source.

| ID | Sev. in D7 | What I wrote | Why |
|---|---|---|---|
| **V7-001** | blocker, candidate | §4.6 partner-first on ordinary logical superblock updates (stage clearing, promote 4 / 5-decline / 9). Phase 4 also repairs a *stale* lower-generation partner. WP-10 two-interruption closure | Mirror-first plus "repair only if exactly one valid copy" is how two permitted power losses leave a water line that rejects both live A indices. Partner-first is the rule format/dup step 1 already used |
| **V7-002** | major, candidate | Headroom consults a counter only when that counter's `needed != 0` | `FFFFFFFF + 0 <= FFFFFFD` is false and contradicts the zero-write rows. FE/FF stay legal on crafted media; they are never written |
| **V7-003** | major, §9 | Work slot still reclaims any household card. Step 1 writes a specified v1 WIP template so remount is `INCOMPLETE`, not `VERSION`. Equal-generation-divergent copies are zeroed *after* refusal preconditions | First cut refused foreign-major. That fights §4.3. Classification is a plan, not a write — a card that is both inconsistent and too small is refused, not erased |
| **V7-004** | major, §9 | Destination `label` is a byte copy of the source | Michael: the copy is the same album |
| **V7-005** | question, §10 | `tape_service` allowed in every mounted row except Faulted | Table, §7.2 and WP-12a already agreed. The sentence after the matrix did not |

Two later passes against the draft itself changed it. The important ones:

1. §4.6 cannot cover format/dup identity-assignment commits. Those write `sb_generation = 1` after step 1 may have left a higher-generation WIP copy. They keep mirror-then-primary and their existing crash tables.
2. Promote steps 4 / 5-decline / 9 still said *mirror, flush, primary, flush* after §4.6 required partner-first. An implementer reading the steps ships the old order. Step bodies now cite §4.6.
3. Equal-generation-divergent zero-both had no mid-write crash row. After the first zero, the surviving primary is the old cartridge; re-run takes the template path. Row is on both tables.
4. Explicit reject of the other V7-001 alternative ("refuse mutators until two current copies exist"): it stalls a child on a flaky partner write.

Full list is in `docs/REVIEW/surge-support.md`.

---

## What I recommend

**Issue the bundle if the text is yours after your pass.** That is a `cmp`-land of the three files plus this `VERSION.md`, or a merge of this PR after you have edited anything you do not want. It is not a freeze.

**Do not flip the banner.** Phase-0 still wants an independent Verification Lead pass on *this* text, preferably without reading my dispositions first — you already wanted that comparison on DRAFT-7. Newest text to attack is listed in `docs/REVIEW/FOR-VERIFICATION-LEAD.md`.

**Do not treat a merge as WP-10.** Operations and the matrix stay open until that run is green. There is no engine on `main` that implements §4.6 (structural Rule 1; PR #20 stays parked).

**Do not treat a merge as media-atomicity PASS.** PR #18 is clear: no atomicity result supports format freeze until the rig firmware and traces are reviewable. Independent of this PR.

**Hardware PR #18** is mergeable by you whenever you want. No `engine/` or `tests/`. Independent of freeze.

**If you reject the bundle,** leave `main` at DRAFT-7. The findings stay open. I would rather `main` stay honest than land text you have not accepted.

Suggested landing order if you accept:

1. Your edit pass on this branch (authorship is yours; rewrite anything).
2. Re-hash only if you changed a hashed file; then run the gate; prove it can go red.
3. Merge or `cmp`-land onto `main`.
4. Hand `docs/REVIEW/FOR-VERIFICATION-LEAD.md` to the lead and ask for a DRAFT-8 pass.
5. Banner flip is a later act, after that pass, and only if it is clean.

---

## What this PR does not do

- Does not freeze. Does not flip the banner.
- Does not touch `engine/` or `tests/`.
- Does not merge #18 or #20.
- Does not publish findings onto `digital-tape-verification` `main`.
- Does not place a parts order.
- Does not decide Q-001. The live hold is still the verifier's sign, not a surge opinion.

---

## Process notes Michael asked you to take

1. `docs/REVIEW/` should become the round brief so he stops pasting directions. Leads read `main`.
2. No 64 GB cards. Smallest current V30 microSDHC. Micro is fine.
3. Question queue first every round.
4. `CLAUDE.md` header on `main` was two bundles behind. Fixed here.

---

## Open questions that are yours, not mine

- Whether you want the Verification Lead on DRAFT-8 blind to this packet. I think yes.
- Whether `TAPE_ERR_INCOMPLETE` should distinguish an interrupted duplicate from an interrupted format. Both recover by re-run. I left it open in `tapefs` §14.
- Whether #18 lands now. Not coupled to this bundle.
