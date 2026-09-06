# For the PM — DRAFT-8 proposal handoff

From: surge support
Date: 6 Sep 2026
Branch: `surge/draft-8-freeze-candidate`
PR: https://github.com/mmsanders/Digital-Tape/pull/25
Canonical today: `main` is DRAFT-7 until you issue this.

This is a handoff, not a lead packet and not a freeze request. Spec authorship stays yours. I will not merge.

The branch is shaped so that **if you accept the text**, a merge or a `cmp`-land is a clean issue of DRAFT-8. It is still not a freeze.

---

## What you are being asked to look at

A proposed DRAFT-8 spec bundle that dispositions the Verification Lead's DRAFT-7 findings (V7-001…V7-005), plus the process docs that were stale on `main`.

| File | Role |
|---|---|
| `spec/tapefs-v1.md` | Format. New §4.6, stale-partner repair in §4.1 phase 4, zero-needed exception in §4.5, raw classification in §9.5/§9.6 |
| `spec/engine-api.md` | `needs_repair` includes stale partners; invariants 32/33; V7-005 service prose; companion line |
| `spec/acceptance.md` | WP-10 two-interruption closure, zero-needed at FE/FF, foreign-major + equal-gen-divergent, source-label copy |
| `spec/VERSION.md` | DRAFT-8 manifest. Hashes below. Banner inside the three files is still **NOT FROZEN** |
| `docs/REVIEW/surge-support.md` | Round brief (dispositions + the self-review passes) |
| `docs/REVIEW/FOR-PM.md` | This file |
| `docs/REVIEW/FOR-VERIFICATION-LEAD.md` | Separate note for the lead. Pass it on if you want that review; I did not publish onto the verification repo |
| `CLAUDE.md` | Header on `main` still cited DRAFT-3 / DRAFT-1. Now points at `spec/VERSION.md` |
| `docs/FOR-MICHAEL.md` | 6 Sep queue close-out on top of your 5 Sep prose |
| `docs/PACKAGES/WP-05.md` | Cart no longer names 64/128 GB. Smallest current V30 microSDHC; micro is fine |

Hashes of the three files this manifest names. These are the files on this branch. Earlier PR comments cited other hashes while the specs were still DRAFT-7 on the tree; ignore those.

```
a769c772ba9efd867badeaa6dbc4dd731913a31b01a5c296336686463093e792  spec/tapefs-v1.md
d19c8f2453c258c582622c3447a792215debd3ec68df81c306d47ae5b57da836  spec/engine-api.md
d2cf1f620f582df46bbcd736eed589aefe04512ca7953f15601850210d51ca81  spec/acceptance.md
```

The bundle gate was run green on this tree, forced red with a one-byte flip on `acceptance.md`, restored green. If you land by `cmp`, do not re-hash to make a red gate green.

The hashed banner is **DRAFT-8. NOT FROZEN.** No "not issued" sentence lives inside the hash, so a merge does not publish a lie.

---

## Why this exists

DRAFT-7 on `main` does not meet the Phase-0 freeze standard the Verification Lead applied: no blockers and no majors in `tapefs` §§1–8 and `engine-api` §§2–8+§12. V7-001 (blocker) and V7-002 (major) sit in that candidate. Michael asked surge to get a freeze-*candidate* on a branch, not to freeze, and not to touch `main`.

Operations and the state matrix still freeze at the first green WP-10. This PR does not change that sentence.

---

## What I did, and why

1. **Wrote proposed dispositions into the three hashed files** rather than into a review note. A note the implementer has to interpret is how V7-001 happened: the crash table said one order and the step bodies said another.
2. **Kept the work on this branch.** `main` is still an honest DRAFT-7. I will not merge.
3. **Ran two adversarial passes against my own draft**, then a third pass that pretended to be the verifier and pre-empted four defects (S8-001…S8-004). Those fixes are in the hashed files. That is surge pretending to be the lead. It is not a sign-off.
4. **Landed the hashed files together with `spec/VERSION.md`.** An earlier cut of this PR updated the manifest while the three files were still DRAFT-7, which would have made the gate red on merge. Restored, then landed as one unit.
5. **Fixed three process docs Michael already answered in conversation** (`CLAUDE.md` header, 6 Sep queue on `FOR-MICHAEL.md`, WP-05 cart). Those are independent of freeze and are safe to keep even if you reject the bundle.

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

Later passes against the draft itself changed it. The ones that would have been findings if they had shipped:

1. §4.6 cannot cover format/dup identity-assignment commits. Those write `sb_generation = 1` after step 1 may have left a higher-generation WIP copy. They keep mirror-then-primary and their existing crash tables.
2. Promote steps 4 / 5-decline / 9 still said *mirror, flush, primary, flush* after §4.6 required partner-first. An implementer reading the steps ships the old order. Step bodies now cite §4.6.
3. Equal-generation-divergent zero-both had no mid-write crash row. After the first zero, the surviving primary is the old cartridge; re-run takes the template path. Row is on both tables.
4. Explicit reject of the other V7-001 alternative ("refuse mutators until two current copies exist"): it stalls a child on a flaky partner write.

Full list is in `docs/REVIEW/surge-support.md`.

---

## What I recommend

**Issue the bundle if the text is yours after your pass.** Merge this PR, or `cmp`-land the three files plus `spec/VERSION.md`. That issues DRAFT-8. It is not a freeze.

**Do not flip the banner.** Phase-0 still wants an independent Verification Lead pass on *this* text, preferably without reading my dispositions first — you already wanted that comparison on DRAFT-7. Newest text to attack is listed in `docs/REVIEW/FOR-VERIFICATION-LEAD.md`.

**Do not treat a merge as WP-10.** Operations and the matrix stay open until that run is green. There is no engine on `main` that implements §4.6 (structural Rule 1; PR #20 stays parked).

**Do not treat a merge as media-atomicity PASS.** PR #18 is clear: no atomicity result supports format freeze until the rig firmware and traces are reviewable. Independent of this PR.

**Hardware PR #18** is mergeable by you whenever you want. No `engine/` or `tests/`. Independent of freeze.

**If you reject the bundle,** leave `main` at DRAFT-7. The findings stay open. I would rather `main` stay honest than land text you have not accepted.

Suggested landing order if you accept:

1. Your edit pass on this branch (authorship is yours; rewrite anything).
2. Re-hash only if you changed a hashed file; then run `tools/ci/verify-spec-bundle.sh`; prove it can go red with a one-byte flip, then restore.
3. Merge or `cmp`-land onto `main`.
4. Hand `docs/REVIEW/FOR-VERIFICATION-LEAD.md` to the lead and ask for a DRAFT-8 pass.
5. Banner flip is a later act, after that pass, and only if it is clean.

If you change even one sentence in a hashed file and skip the re-hash, the gate on `main` goes red and stays red until someone breaks the "do not adjust hashes to match the files" rule. Better to catch that on the branch.

If you want the process docs without the bundle: take `CLAUDE.md`, `docs/FOR-MICHAEL.md`, and `docs/PACKAGES/WP-05.md` only. They do not depend on DRAFT-8.

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

---

## Note I would like the Verification Lead to hear

That text is in `docs/REVIEW/FOR-VERIFICATION-LEAD.md`, not here, so you can forward one file. Short version: attack §4.6, the promote step bodies, stale-partner repair, zero-needed, and classification-as-plan first. Do not treat my self-review as a disposition record. WP-10 has not been run.
