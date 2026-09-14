# P1-R14-SW return — corrected cadence package imported, probe corrected, fresh evidence

Issue [#83](https://github.com/mmsanders/Digital-Tape/issues/83). Verifier return:
[P1-R13 cadence correction](https://github.com/mmsanders/digital-tape-verification/blob/e3a25bf3b9eda6581b5de524e5bd5fa2c032e0da/findings/p1-r13-per-render-scrub-service-correction-2026-09-14.md).

**Status: Ready for PM review.** Phase A merged as an import-only PR. Phase B
corrected my own probe's scrub cadence, and the corrected unmodified package now
passes all ten families with **698 renders and 698 immediately preceding
completed services in each direction**. PR #77 is **not merged** and stays draft.
Nothing here is acceptance.

**P1-R13-V01 was my defect, not the engine's.** WP-08 says "Before every render
request, call `tape_service` with `block_budget == 1024` until
`more_work == false`, under a finite guard." My scrub driver serviced once per
row. It produced the right bytes — the play ring is a window over timeline
frames, so the two schedules decode identically, which is the cross-target
contract working — but it is not the specified schedule, and firmware interleaves
service with every buffer rather than once per rate change. No engine byte
changed in this round.

## Identity

| Item | Value |
|---|---|
| Input product main | `a87263aa4f006233d1b855a9736c41995b8343ce` |
| **Phase-A PR / merge commit** | **[#85](https://github.com/mmsanders/Digital-Tape/pull/85) / `888f4dafcddcc4d7b96e8ec8e250dd5bb4062b63`** |
| Phase-A branch head | `1e391dc2146ffa798ffc07e5f9b68db42f761104` |
| Imported package tree | `467a34bb0a84672c5bdef9059f2dd326d6435eb6` |
| Retained synthetic evidence tree | `3323542c187f4121beddb3c8960ed2e35992e586` |
| Verifier publication / evidence commit | `e3a25bf3b9eda6581b5de524e5bd5fa2c032e0da` / `05e193209542d204669b32f485dad21007a084ee` |
| Verifier source commit / tree | `1f7fe3f79d326c4a6e37f8c301c97c110d481619` / `fe79113bfe600268585b382fab218e2bbf687a7e` |
| Ancestry-sync commit (merge) | `5b8d62938a0ed5010fac658235de110ffadfbd0c` |
| **Phase-B pre-run code commit** | **`b94ee2e33fd7fb8f6691e76a83d2392b6717e8a7`** |
| PR #77 head before this round | `f100937aed1437401218003db3edbb07d8e4f543` |
| Existing clean code commit | `86eb3b77756042c365e2d0353018b981c39c99e8` |
| Evidence path | `docs/verification/runs/2026-09-14-r14/` |
| libtape.a / adapter source / adapter binary sha256 | `e49cd1b5…` / `da64522c…` / `7ee49c67…` |

## Phase A — exact verifier import, merged

Fresh branch from the exact input main; `tests/playback_complete_draft8/`
replaced **by tree object** (`git read-tree --prefix=…` from the fetched
evidence commit), so path, mode and byte identity is a hash fact, not an
inspection claim. Nothing imported was edited, normalized or regenerated.

All eight corrected source blobs match the verifier return exactly, each mode
`100644`: `COVERAGE.md 7cf313b5`, `README.md b874d6c7`,
`_synthetic_adapter.py eda53cff`, `oracle.py 86aa77f8`, `package.json 111fa007`,
`replay.py 5000076a`, `runner.py 4f54f675`, `selftest.py 1f55dcc0`. Frozen
hashes verified in the imported package: TapeFS `3bffa0ec…`, Engine API
`537eadc4…`, acceptance `7f78fba7…`, WP-08 `ff519e96…`.

No product probe or engine byte exists anywhere in that branch's history: the
`engine`, `firmware`, `tests/playback_adapter` and `tests/harness` deltas
against input main are empty, and remain empty on merged main.

| Check | Result |
|---|---|
| deterministic generation | PASS, every generated input unchanged |
| corrected self-test | PASS — 10 families, 22 controls, retained 18-control P1-R4 package |
| **`P1-R13-V01 old once-per-row cadence forward`** | **CAUGHT** |
| **`P1-R13-V01 old once-per-row cadence reverse`** | **CAUGHT** |
| saved P1-R13 synthetic replay | `REPLAY PASS` |
| three-family / mount / VT8-001 packages | PASS / PASS / PASS |
| frozen spec bundle · dashboard | OK · PASS |
| guardrail gates · meta-gate · scaffolding | clean · 15/15 · PASS |
| Actions on `1e391dc` | 10 of 10 required green; `golden suite` red and unrequired |

Merged only after all ten required checks passed. That merge accepts no product
behaviour, source, PCM, golden, listening result or package.

## Phase B — minimal probe correction and fresh evidence

Post-Phase-A main brought into PR #77's branch by a `--no-ff` merge: no
force-push, no rebase, no rewritten commit, both held histories intact.

**Changed-path map against PR #77's previous head `f100937`:**

| Path | Before | After | Author |
|---|---|---|---|
| `tests/playback_adapter/complete_probe.c` | `f6e557793087e980e7f3758a1bacf8ed006c131e` | `a3c79aef0911e21fd88e04207c49116e8f598d1a` | mine |
| `site/lead-queue/index.html` | — | — | PM's, arrived with main |

Nothing else. Verified unchanged blob-for-blob: `tape.h`, `tape_dev.h`,
`mount.c`, `play.c`, `tape_internal.h`, `tapefs.c`, **`chunks.c`**, `crc32.c`,
`dev.h`, `media.h`, `test_mount.c`, `test_play.c`, `tests/Makefile`,
`complete_adapter.sh`, adapter `Makefile`. `engine/src/alloc.c` and
`tests/harness/test_alloc.c` remain absent. No verifier-owned file changed after
the import.

The probe correction is two parts of one thing:

1. `service_to_idle` moved from above the render loop into it, so every render
   in all 16 rows and both directions is immediately preceded by a completed
   `tape_service(1024)` sequence under the same finite guard.
2. `PLAY_RING_BYTES` changed from 8 MiB to `TAPE_PLAY_RING_MIN`. The large ring
   existed only to let a whole row render after one service sequence. Under the
   specified schedule it is actively wrong here — `tape_service` restarts its
   window whenever the playhead moves, so a forward scrub re-reads the rest of
   the timeline before every render:

   | Ring | Direction | Renders | Services | Block reads |
   |---|---|---:|---:|---:|
   | 8 MiB | forward | 698 | 4,516 | 4,260,912 |
   | 8 MiB | reverse | 698 | 706 | 8,608 |
   | 64 KiB | forward | 698 | **698** | 90,003 |
   | 64 KiB | reverse | 698 | **698** | 90,056 |

   The 8 MiB run also overflowed the probe's own call trace, which is how it
   surfaced. Caller-owned storage (guardrail 08); no engine byte changed, and
   identical PCM across both rings is the window-over-timeline-frames property
   doing its job.

### Results

```
PASS P1-R13 corrected playback evidence
REPLAY PASS docs/verification/runs/2026-09-14-r14/product-evidence
289 cases; 0 failed; seed=0xd8a607
```

All seven PCM families byte-exact: `one_intmax` 1, `reverse_zero` 1, `intmin` 2,
`scrub_forward` 88,200, `scrub_reverse` 88,200, `side_playing` 2, `side_idle` 1
frames, with the hashes listed in the packet README. **All seven are unlistened
and are not WP-11 goldens.**

Cadence, recomputed from the observation and retained as `cadence-counts.txt`:
**698 renders, 698 services, and 698 renders immediately preceded by a completed
`tape_service(1024, more_work=false, result=0)` in each direction, zero
exceptions**, 16 `tape_set_rate` calls, 88,200 frames, no short renders, and
every device callback a `read` with `rc = 0` (90,003 forward, 90,056 reverse).

### Mount regression — and one thing that is *not* exact

289 cases, 0 failed, seed `0xd8a607`. All 289 **case records are byte-identical**
to the P1-R12 log, compared after the provenance header.

The **executable identity is not bit-identical** and I am not going to paper over
it: the probe binary hashes `c0e98c56…` now against `57b8274e…` last round. The
engine sources are byte-identical. The engine Makefile compiles with `-g` from an
absolute source path and archives with `ar rcs`, so object, archive and binary
hashes depend on the build directory and on mtimes — two builds of this same
commit in two directories give `play.o` hashes `70a54fbb…` and `c2f30a23…`.
Binary identity across runs is not reproducible by construction in this
repository; source identity is. Worth a PM decision someday (`-ffile-prefix-map`
and `ar rcsD` would fix it); it changes nothing about this round's evidence,
which binds both the sources and this build's own binaries.

This mount run is regression and provenance evidence only. The narrow P1-R12
mount disposition does not transfer to this commit.

## Superseded evidence

`docs/verification/runs/2026-09-13-r11/` is **historical**: it used the
once-per-row cadence the corrected package now rejects by name. It is preserved
unchanged, and both its README and PR #77's body now say so. `2026-09-13-r6/`,
`-r7/` and `-r9/` remain untouched on the PR #64 branch.

## Exclusions and holds

Not acceptance — not by this run, not by this issue closing. No WP-11 golden and
no listening. No allocator, recording, crash/recovery, warm-start descriptor
negatives, state/operations, performance, hardware or card behaviour, purchases,
qualification, fabrication, charging or Michael-reserved approvals. PR #77 stays
draft and unmerged; PR #20 and PR #64 stay draft and held. Structural Rule 1,
independent Verification and the frozen hashes are preserved.
