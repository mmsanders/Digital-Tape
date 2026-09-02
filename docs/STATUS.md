# STATUS

**Updated:** 2026-09-02 · **Phase:** 1 (engine), held · **Updated by:** Software Lead
**Charter Rev C · specs DRAFT-3, NOT FROZEN, four blockers open · CI 7/8 green**

---

## What changed since last time

**PR #17 merged**, with both of Decisions 004's conditions met. `main` now carries DRAFT-3
rather than my stale WP-02 draft — which is the more important half of the merge, because until
now anyone reading `main` was reading the wrong spec.

**Both DRAFT-3 blockers confirmed against this code**, not taken on trust:

- **V3-001** — `last_chunk_id` wraps to **0** on the spec's own repro values, where the true
  value is 32768. Zero is the most permissive result available: it passes the `last < first`
  guard *and* every bound including `a_high_water`. A CRC-correct index claiming a
  4-billion-frame run validates as one chunk at position 0. On Side A that defeats immutability.
- **V3-004** — the geometry check accepts a chunk store whose last block *is* the mirror
  superblock. Confirmed numerically.

Neither is fixed. The spec is upstream of the code; DRAFT-4 owns the rules. Both are marked
PROVISIONAL at the head of `tapefs.c` and `mount.c` and at each affected check.

**One fault injector, not two** (#16 closed). `dev_sim` lost its durability model. The reasoning
is ADR-025 and it generalises: a simulator where every completed write is durable is
*structurally incapable* of failing any test that depends on a flush having happened — and the
verifier found exactly that defect in DRAFT-1 by reading.

**Every gate is now proven able to go red.** `tools/ci/verify-gates.sh`, 11/11, in CI.

## In flight

| Work | Owner | State |
|---|---|---|
| DRAFT-4 | PM | **The critical path.** 4 blockers + 11 majors; days, not hours |
| WP-06 validity/mount rules | Software Lead | **Held** by Decisions 004 §5 until DRAFT-4 |
| WP-06 commit path | Software Lead | **Held** by structural Rule 1 |
| WP-10 crash harness | Verification | Infrastructure in CI; adapters need DRAFT-4 |
| WP-11 golden suite | Verification | Runner proven; fixtures owed |

## Blocked

Nothing is blocked in the sense of idle. Everything downstream of the format rules is **held by
instruction**, which is different and correct: five findings land on the read path, and building
further on rules that are about to change would be work done twice.

## Acceptance criteria flipped to passing

**None**, and one moved backwards. WP-06's criterion says every §4.1 and §5.2 mount rule has a
refusal test — 60 checks do that, but §5.2 and §4.1 are two of the sections DRAFT-4 is expected
to change materially, so those tests encode rules that are provisional. Nothing has the
Verification Lead's independent confirmation.

## What will hurt in three weeks

- **The format has four open blockers and Q-001 has moved out again.** That is the right call —
  freezing a format the verifier has shown to be broken means reflashing cartridges later for
  something we knew today — but the Phase 0 gate is now the longest-standing open item in the
  project, and everything in Streams 1, 3, 4 and 5 sits behind it.
- **Two rounds, two silent-desync failures.** The unversioned charter, then a stale spec on
  `main` that three streams would have read as truth. Both were caught by someone noticing, not
  by a mechanism. The charter now carries a revision and the specs now carry a status banner;
  there is still nothing that *detects* the next instance.
- **V3-005 is the one I would watch.** DRAFT-3 has no index-slot selection algorithm at all, so
  what `pick_live_index` does was invented by analogy. It is reasonable and it is not normative,
  and two conforming implementations could mount different generations after the same crash —
  which is precisely the thing a crash oracle cannot tolerate.
- **RAM is at 72 % before the commit and record paths add their state.** Two index arrays
  dominate at 48 KiB each. If it tightens, the honest lever is `TAPE_MAX_ENTRIES` — an engine
  memory constraint, not a media one — not the budget.
