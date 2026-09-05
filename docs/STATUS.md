# STATUS

**Updated:** 2026-09-04 · **Phase:** 1 (engine) · **Updated by:** Software Lead
**Charter Rev C · spec bundle DRAFT-6 on `main` · CI 8/9 green**

---

## What changed since last time

**DRAFT-6 is on `main`**, the second bundle to land today. All four files `cmp`-verified against
the PM's copies; the three hashes were checked against the manifest before anything was copied
and again after. The banner is inside the hashed content, so nothing was added or edited.
`docs/FOR-MICHAEL.md` is the PM's rewrite, landed the same way.

**The gate held across a bundle change** — which is the first evidence it does anything. It went
green on DRAFT-6 without an edit, and `verify-spec-bundle.sh` is still byte-identical to the
fenced block in `VERSION.md`.

**The meta-gate's revision probe did not, and is fixed** (ADR-031). It named `DRAFT-5` and the
DRAFT-5 hash in two `sed` commands, so from today it would have planted nothing — the gate would
stay green and the probe would report BROKEN. That is the right failure direction and the wrong
maintenance burden on a document that has moved four times in three days. It now reads the
current revision and hash out of `VERSION.md` and plants `DRAFT-0`, a value no bundle will ever
carry, and refuses to run at all if either derived value is empty. 15/15.

**`spec/README.md` stopped restating revisions** (ADR-032). Its own table said DRAFT-4 while
`main` published DRAFT-3 — a fourth copy of the same claim, drifting, inside the round about
drift. Status and freeze scope only now; revisions live in the manifest that has a gate behind it.

## In flight

| Work | Owner | State |
|---|---|---|
| DRAFT-6 bundle | Software Lead | **On `main`**, gate green |
| Read-path reconciliation to DRAFT-6 | Software Lead | **Not started, and the delta grew** — see below |
| WP-06 sub-criteria 06a–06h | Software Lead | Not started. **Eight now, not six** |
| WP-06/07 read+alloc paths | Software Lead | PR #20, built against DRAFT-4. Held by structural Rule 1 |
| WP-06/07 commit paths | Software Lead | **Held** by structural Rule 1 |
| WP-10 crash injection | Verification | Infrastructure in CI. DRAFT-6 adds two durability modes and counter boundaries to its scope |
| WP-11 golden suite | Verification | Runner proven; fixtures owed. **The only red gate** |

## Blocked

Nothing. The commit path is held by instruction, not blocked.

## Acceptance criteria flipped to passing

**None.** 118 self-test checks on `main`, 206 counting PR #20 — all of them the Software Lead's
claims about its own code. `acceptance.md` requires the Verification Lead's independent
confirmation. Nothing has had it, so nothing has flipped.

## What will hurt in three weeks

- **The engine is now two revisions behind, and the gap is structural rather than cosmetic.**
  `tape_mount` gains a **fourth phase, with repair last** (V5-003) — my implementation splits
  repair out of selection but still runs it before index validation, so invariant 26 is false in
  my code today for every index failure. That is a reordering of the function this round's whole
  read path is built around, not a parameter change.
- **A new engine state exists that I have no code for.** `TAPE_ERR_FAULTED` (§7.2) quarantines an
  instance after any indeterminate write or flush, overrides every other row of the state matrix,
  and permits exactly four calls. It closes a path where a recoverable I/O error followed by an
  ordinary permitted call destroys audio. It is not a code, it is a state machine.
- **One ABI change landed inside the freeze candidate.** `tape_tell` is now
  `tape_result tape_tell(const tape *, uint64_t *)`. The old bare-`uint64_t` signature could not
  return `TAPE_ERR_NOT_MOUNTED`, so the document contradicted itself. Cheap now, expensive after
  three consumers link against it — which is the argument for finding it here.
- **Two arithmetic fixes invalidate any renderer prototype**, and would have been frozen into the
  goldens: reverse-from-end snaps to `(total_frames − 1) << 32` rather than `max_pos − 1`, and
  `at_start` is set only when the playhead was *already* at 0 — DRAFT-6's own first cut set it on
  the landing step, which never rendered frame 0 at all. Both are pre-fixture, which is the cheap
  time.
- **RAM was 72 % before the disjointness scratch, the commit path and the record path.** WP-13
  now requires the gate to **print** the measured `tape_instance_size()`, not just assert the
  ceiling, and the memory audit does not yet include it at all. Owed with the reconciliation. If
  the sum crosses 200 KiB the answer is escalation, not a smaller `TAPE_MAX_ENTRIES` — 4 096
  entries is roughly two thousand splices, a child's editing budget and therefore a product
  number.
- **The PM's own note is the one worth acting on.** Of the 37 defects found in DRAFT-6's first
  cut, two were introduced by the fixes for the verifier's DRAFT-5 findings. The most dangerous
  text on this project is whatever was written last, in a hurry, to close a hole someone just
  found. That applies to my patches as squarely as to the PM's drafts, and it is the argument for
  reconciling the read path deliberately rather than fast.
