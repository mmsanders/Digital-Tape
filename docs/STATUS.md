# STATUS

**Updated:** 2026-09-06 · **Phase:** 1 (engine) · **Updated by:** Software Lead
**Charter Rev C · spec bundle DRAFT-7 on `main` · CI 8/9 green**

---

## What changed since last time

**DRAFT-7 is on `main`** (#24), and the manifest-driven probe survived its first bundle change:
15/15 with no edit to any gate. The hardcoded version would have gone quiet today exactly as it did
on the DRAFT-6 landing. Issue #23 closed with the bundle.

**PR #20 is rebased onto DRAFT-7 and reconciled, not extended** — the PM's instruction. It is no
longer behind: `main` and the branch are both DRAFT-7, and the debt the PM warned would compound is
paid off rather than carried.

**`cartridge_sequence` is implemented** (`tapefs` §5.5), and implementing it required splitting one
function into two (ADR-036). The base is the maximum over every **structurally** valid slot — magic,
`entry_count ≤ MAX`, CRC — which is deliberately *not* §5.2 validity, because §5.2 validity is not
stable across an operation and a base computed over it can be outranked later by a slot that becomes
valid. `tape_index_parse` and `tape_index_validate` are now separate.

**Degraded-B's second cause is implemented** (ADR-037). Both B slots valid at equal `sequence` is
degraded-B, and a mount *requesting* Side B now returns `TAPE_ERR_INCONSISTENT` there rather than
`TAPE_ERR_NO_VALID_INDEX`. The `tape_set_side(B)` refusal stays `NO_VALID_INDEX` in both causes —
a real divergence between the two paths, not a rename that missed a caller.

**Each new test was proven to catch its own defect** before being kept, the way the meta-gate proves
a gate: reverting V6-001 reddens the mount-error test; computing the base over §5.2-valid slots
reddens the structural test; making the base side-local — the V6-003 defect itself — reddens four.
286 checks on the mount path, up from 260.

**`tape_instance_size()` is unchanged at 156 456 bytes, 76 %.** `cartridge_sequence` fit in existing
padding. Stack 1 536 / 8 192; `.rodata` 1 040 / 32 768.

## In flight

| Work | Owner | State |
|---|---|---|
| DRAFT-7 bundle | Software Lead | **On `main`** (#24), gate green |
| WP-06 read path at DRAFT-7 | Software Lead | **Done**, unconfirmed. PR #20, still a draft |
| WP-06 sub-criteria 06a–06h | Software Lead | Exercised; 06e and 06f partial — see below |
| WP-07 allocator | Software Lead | Done. `tapefs` §7 unchanged through DRAFT-7 |
| WP-06/07 commit paths | Software Lead | **Held** by structural Rule 1 |
| WP-10 crash injection | Verification | Infrastructure in CI. DRAFT-7 widens its scope again |
| WP-11 golden suite | Verification | Runner proven; fixtures owed. **The only red gate** |

## Blocked

Nothing. The commit path is held by instruction, not blocked.

## Acceptance criteria flipped to passing

**None.** 390 self-test checks are the Software Lead's claims about its own code. `acceptance.md`
requires the Verification Lead's independent confirmation and nothing has had it.

## What will hurt in three weeks

- **Three sub-criteria are half-testable and will stay that way until the commit path lands.**
  06e needs `tape_arm` to prove stage clearing happens after preconditions; 06f's new
  remount-after-`reset_b` assertion needs `tape_reset_side_b`; WP-12a's forty-five cells need the
  long operations. The mount halves are done. What is *not* covered is exactly the half that
  writes, which is the half structural Rule 1 holds — so the hold and the coverage gap are the same
  fact, and neither is a surprise.
- **`cartridge_sequence` is derived and has no consumer yet.** It is correct, tested, and read by
  nothing, because every site that will use it is a commit site. That is the shape most likely to
  rot between now and then: a value nobody reads is a value nobody notices going wrong. The three
  probes above are the mitigation.
- **`FAULTED` still has no producer**, for the same reason — the read path's only write is phase-4
  repair, which §4.1 excludes by design.
- **The PM's calibration note is four rounds old and has not stopped being true.** Both blockers
  this round were again in text written to fix the round's findings. My own `select_side` defect
  last round was the same shape. *A fix is the only text nobody but its author has read* — which is
  why every fix in this round's diff has a probe that reddens it.
