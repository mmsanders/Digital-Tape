# STATUS

**Updated:** 2026-09-04 · **Phase:** 1 (engine) · **Updated by:** Software Lead
**Charter Rev C · spec bundle DRAFT-5, §§1–8 freeze candidate · CI 8/9 green**

---

## What changed since last time

**The DRAFT-5 bundle is landed** — `tapefs-v1.md`, `engine-api.md`, `acceptance.md` and the new
`spec/VERSION.md`, all four `cmp`-verified against the PM's copies. The three files hash exactly
to the manifest. The status banner was already inside the hashed content; I added nothing.

**The manifest gate is wired and proven red-able.** `tools/ci/verify-spec-bundle.sh` is the PM's
script, extracted from the fenced block in `VERSION.md` rather than retyped. It is its own CI job
and runs on **every** PR, not only PRs touching `spec/` — the drift it exists to catch was already
sitting on `main`, where no path filter would have looked (ADR-028).

**The meta-gate needed three probes for it, not one, and the reason is the point** (ADR-029). The
obvious probe — edit the revision string — also breaks that file's hash, so the hash check fires,
the gate goes red, the probe passes, and the revision check is never executed. It compares two
`sed` extractions, and two empty strings compare equal: a typo in either pattern leaves it
unconditionally green with the aggregate probe still showing red. So the revision probe re-hashes
`VERSION.md` to keep the hash check green, and asserts the gate says *`is DRAFT-3, bundle is
DRAFT-5`*. A third probe empties the manifest — `awk` matches nothing, `sha256sum -c` gets an
empty list — because a gate with nothing to check must not report success. All three go red.
**15/15**, up from 11.

**The correction to my last report.** I wrote "DRAFT-4 landed". It landed on a *branch*; `main`
was still publishing DRAFT-3/DRAFT-3/DRAFT-1 this morning, which is what the PM found. Read
against `main` — which is what the PM has — that line was wrong, and this gate is now the thing
that would have said so.

**Spec now travels on its own branches, ahead of code** (ADR-030). The bundle had been queued
behind the WP-06/WP-07 engine work on one branch, and that branch cannot merge: structural Rule 1
holds engine implementation off `main` until Stream 2's tests land there. So the document three
streams read as truth was gated on the slowest-moving thing in the repository. It landed alone
instead, with no `engine/` or `tests/` diff, and spec changes go this way from here.

**`spec/README.md` stops restating revisions.** It listed them in a table beside the same claim
`VERSION.md` now makes with hashes — a second place to drift, in the round whose whole subject is
drift. It points at the manifest instead.

## In flight

| Work | Owner | State |
|---|---|---|
| DRAFT-5 bundle + manifest gate | Software Lead | **On `main`** — the canonical publication point |
| Read path reconciliation to DRAFT-5 | Software Lead | **Not started.** Engine is DRAFT-4-era |
| WP-06 sub-criteria 06a–06f | Software Lead | Not started |
| WP-07 allocator | Software Lead | Done against DRAFT-4; needs the Rule 3 re-read |
| WP-06/07 commit paths | Software Lead | **Held** by structural Rule 1 |
| WP-06/07 read+alloc paths | Software Lead | On `claude/new-project-setup-fooeic`, PR #20 — also held, and no longer holding anything up |
| WP-10 crash injection | Verification | Infrastructure in CI; adapters owed |
| WP-11 golden suite | Verification | Runner proven; fixtures owed. **The only red gate** |

## Blocked

Nothing. The commit path is held by instruction, not blocked.

## Acceptance criteria flipped to passing

**None.** 118 self-test checks on `main`, 206 counting the engine branch — and all of them are the
Software Lead's claims about its own code. `acceptance.md` requires the Verification Lead's
independent confirmation. Nothing has had it, so nothing has flipped.

## What will hurt in three weeks

- **The engine is a revision behind the spec it is measured against.** Seven rules moved between
  DRAFT-3 and DRAFT-5 and the superblock grew two fields at offsets 124 and 128. The 102 mount
  checks currently assert DRAFT-4 behaviour — green, and green against the wrong document until
  next round's reconciliation. This is the same class of failure the manifest gate was built for,
  one layer up: nothing yet checks that *code* matches the bundle it claims to implement.
- **Two of the seven changes invalidate work rather than extend it.** Fetch-emit-advance means a
  renderer that seeks to *N* and emits *N+1* is now wrong rather than provisional, and the
  interpolation's signed right-shift was implementation-defined — desktop and firmware could
  legitimately have disagreed. Both are pre-fixture, which is the cheap time to find them.
- **RAM was 72 % before the disjointness sort, the commit path and the record path.** WP-13's gate
  will report the measured `tape_instance_size()` from next round, per Decisions 007 §7. The
  answer if it tightens is escalation, not a smaller `TAPE_MAX_ENTRIES` — 4 096 entries is a
  product number.
- **Not a hurt any more: #19 is resolved.** DRAFT-5 §5.1 deletes the "Equivalently:" scalar test
  outright (V4-002), on both grounds I filed — not equivalent, and circular via `free_next`. The
  pairwise interval check already implemented on the engine branch is now the normative rule, so
  no code change follows. Issue closed.
