# STATUS

**Updated:** 2026-09-05 · **Phase:** 1 (engine) · **Updated by:** Software Lead
**Charter Rev C · spec bundle DRAFT-7 on `main` · CI 8/9 green**

---

## What changed since last time

**DRAFT-7 is on `main`**, plus the PM's rewrite of `docs/FOR-MICHAEL.md`. All five files
`cmp`-verified; the three hashes checked against the manifest before anything was copied and again
after. The banner is inside the hashed content, so nothing was added or edited.

**The manifest-driven probe survived its first bundle change** — which is what it was rebuilt for.
The revision probe named `DRAFT-5` and its hash until ADR-031 made it read `spec/VERSION.md` at run
time; this is the first bundle to land since, and the meta-gate went 15/15 with **no edit to any
gate**. A hardcoded probe would have gone quiet today exactly as it did on the DRAFT-6 landing.

**Issue #23 closes with this bundle**, per the PM. `acceptance.md` DRAFT-7 carries the independent
audit language that Decisions 008 §4 announced and DRAFT-6 did not contain.

## In flight

| Work | Owner | State |
|---|---|---|
| DRAFT-7 bundle | Software Lead | **On `main`**, gate green |
| WP-06 read path | Software Lead | Done against **DRAFT-6**, 260 checks. PR #20, **parked by the PM** |
| WP-06/07 reconciliation to DRAFT-7 | Software Lead | **Not started** — three items, below |
| WP-07 allocator | Software Lead | Done. `tapefs` §7 unchanged through DRAFT-7 |
| WP-06/07 commit paths | Software Lead | **Held** by structural Rule 1 |
| WP-10 crash injection | Verification | Infrastructure in CI. DRAFT-7 widens its scope again |
| WP-11 golden suite | Verification | Runner proven; fixtures owed. **The only red gate** |

## Blocked

Nothing. The commit path is held by instruction, not blocked.

## Acceptance criteria flipped to passing

**None.** 364 self-test checks are the Software Lead's claims about its own code. `acceptance.md`
requires the Verification Lead's independent confirmation and nothing has had it.

## What will hurt in three weeks

- **`cartridge_sequence` (`tapefs` §5.5) is new and my read path does not compute it.** It is the
  max over every **structurally valid** slot of all four — a *weaker* predicate than §5.2 validity,
  deliberately, and my `load_slot` collapses the two. Every commit's base depends on it, and the
  defect it fixes is ordinary: Side A live at `sequence = 10` and Side B at `500` is what a
  cartridge looks like after a few recordings, and a side-local reading writes 11, loses selection
  to B's old slot at 500, and gets the cartridge rejected by the stage oracle.
- **Degraded-B has a second cause I do not implement** (V6-001). Both B slots valid at *equal*
  `sequence` is now degraded-B, and a mount **requesting** Side B must return that side's own §5.3
  error — `TAPE_ERR_INCONSISTENT` in that case, not `TAPE_ERR_NO_VALID_INDEX`. My
  `select_indices` flattens both causes to `NO_VALID_INDEX`. The `set_side` refusal stays
  `NO_VALID_INDEX` in both, so the two paths genuinely differ.
- **`tape_set_side` is now permitted while Playing** (V6-005), and the degraded-B row overrides the
  Playing row. Neither is reachable in my code yet — there is no render path — but WP-08's
  `set_side` criterion is written against the Playing case and could not be executed before this
  change.
- **The PM's calibration note is now three rounds old and still holds.** Both blockers this round
  were in text written to fix the previous round's findings. My own `select_side` defect last round
  was the same shape. *A fix is the only text in a document nobody but its author has ever read* —
  and the same is true of a patch.
