# P1-R17-SW — held implementation + evidence candidate, **BLOCKED**

**Issue:** [#95](https://github.com/mmsanders/Digital-Tape/issues/95) ·
**Input product main:** `a277ee7d52b26a5cf100b6d3bd69e2b6f6638802` ·
**Branch:** `claude/bold-hypatia-zhrrzf-r17` ·
**Pre-run code commit:** `00008d9a44e6ed6ef8ae003609989dee2958a688`

Returning **Blocked** at the issue's own stop condition: *"any verifier semantic
byte must change."* The two VT8-001 fixtures cannot mount on a DRAFT-8-conforming
engine, and the only fix is inside `tests/ops_draft8/`, which this round is
expressly not licensed to touch.

The implementation is complete and is submitted held for PM authentication and a
new independent Verification disposition. It is **not** accepted by anything here.

## The blocker, in one paragraph

`tests/ops_draft8/oracle.py`'s `sb()` writes `nominal_length_s = 60` alongside
`total_chunks = 16` and an 18 433-block device. TapeFS DRAFT-8 §2 derives
`total_chunks` from the superblock's own `nominal_length_s`, and 60 s derives 21.
The fixture therefore fails §4.1 phase 2 step 5 twice over — §2.1 GEOMETRY_OK
line 3 (`2048 + 21*1024 = 23552 > 18432`) and the bolded stored-equals-derived
line (`16 != 21`). Mount returns `TAPE_ERR_GEOMETRY` with zero writes, so neither
case reaches the operation it exists to test. The independently landed mount
package derives the same way (`tests/mount_draft8/cases.py:27,115`) and carries a
negative control for precisely this mismatch (`:120`), and its 286 records pass
against this same engine build.

## Is the engine right?

With that one fixture field corrected and **nothing else** changed — every
assertion, expected value, oracle, hardening layer and runner the package's own —
both cases pass:

```
VT8-001-RB-ALLSLOT: PASS
VT8-001-REC-ALLOCSEQ: PASS
```

That run is a **Software-owned diagnostic with no coverage value**, retained at
`docs/verification/runs/2026-09-19-r17/diagnostic/`. Its own replay correctly
refuses it, because `replay.py` regenerates the fixture independently.

## Second finding — `replay.py` cannot close over a failing run

`replay.py` compares `hardened.check(...)` for exact equality against the saved
verdict, but `runner.py` also records `adapter returned {rc}`. The divergence is
exactly that one string in both cases; input media, every hash binding and the
DRAFT-8 spec authentication all verify. Issue #95's "prove unmodified offline
replay" is structurally unavailable for a failing run. No evidence byte was
edited to make it agree.

## What landed on the branch

| File | Change |
|---|---|
| `engine/src/chunks.c` | WP-07 allocation: `tape_may_allocate`, `tape_alloc_run`. |
| `engine/src/commit.c` | **new** — §8 index commit, §4.5 headroom, §8/§4.6 stage clearing. |
| `engine/src/record.c` | **new** — §7 `tape_arm`/`tape_feed`/`tape_commit`, splice algebra, service drain. |
| `engine/src/ops.c` | **new** — tapefs §9.2 `tape_reset_side_b`. |
| `engine/src/tapefs.c` | Little-endian writers and the index byte producers. |
| `engine/src/play.c` | `tape_service` drains owed frames; `tape_status` reports real state; seek/set_rate refuse while armed. |
| — | `tape_feed` narrows `rec_ring_len` the way `play_capacity()` narrows the play ring: a caller-supplied ring of 2^32 frames or more would otherwise truncate below `rec_buf_frames`, underflow `ring_free`, and let `tape_feed` accept past the end of the caller's buffer. |
| `engine/src/mount.c` | unmount/set_side refuse while armed; mount resets record state. |
| `engine/include/tape.h` | Implementation-status block brought up to date. |
| `tests/ops_adapter/vt8_ops_probe.c` | **one mechanical fix** — see below. |

`tests/ops_draft8/` is byte-identical: `4a862fa69ccb2fc4c9afe59c9c9161c3470f9263`.

## The one adapter edit

The adapter reserved 65 536 bytes per caller-owned instance against an engine
`tape_instance_size()` of 156 528, so **no engine could run the probe at all** —
it failed at `tape_init` before any script step. The buffers are now sized from
guardrail 08's 200 KiB RAM ceiling, which is sufficient for any conforming engine
by construction; the existing runtime check still fails loudly if that stops
being true. No fixture, expected value, observation, callback classification,
ordering, range or assertion is touched.

## Judgment calls PM should dispose of

1. **`tape_arm` accepts `TAPE_REC_SPLICE` only.** `TAPE_REC_OVERWRITE` and
   `TAPE_REC_OVERDUB` have no landed independent tests and are explicit VT8-001
   exclusions, so they are not implemented; arm refuses them with
   `TAPE_ERR_INVALID_ARG` and zero writes. **This is a divergence from
   engine-api §7** and is a statement about this engine, not the format.
2. **Stage clearing landed unexercised.** Both fixtures are `promote_stage == 0`,
   so `tape_clear_promote_stage` never ran. It is here because tapefs §8 states
   the rule as a requirement *on* `tape_arm` and `tape_reset_side_b`; omitting it
   would make both silently violate §8 on stage-1 media. Zero coverage, no claim.
3. **Unexercised branches inside exercised functions** — interior splice and
   splice at an entry boundary, partial-block record drain, multi-chunk
   allocation, `CARTRIDGE_FULL` short accept, every §10 refusal, and every §7.2
   fault path. Written from spec, run by nothing.

## Gates at the pre-run code commit

| Gate | Result |
|---|---|
| build | PASS — `-Werror -Wconversion`, no warnings |
| spec bundle | PASS — three frozen DRAFT-8 hashes unchanged |
| allocation / libc file I/O | PASS |
| indirect-call funnel | PASS — all `tape_dev` access through `engine/src/dev.h` |
| stack depth | PASS — 1 536 / 8 192 bytes (18.8%), 54 functions |
| memory budgets | PASS — RAM 156 528 / 204 800 (76%), .rodata 1 040 / 32 768 (3%) |
| meta-gate | PASS — 15/15, every gate demonstrably goes red |
| unit / scaffolding | PASS — crc32 21, dev 37, **mount 286**, **playback 114**, crash harness |
| golden suite | **FAIL, visible, unrequired** — WP-11 fixtures absent, hold preserved |
| `ops_draft8` self-test | PASS — 2 conforming + 12 oracle controls + spec/evidence/replay controls |
| `playback_draft8`, `playback_complete_draft8` self-tests | PASS |
| `mount_draft8/test_package.py` | PASS — 10 tests |

## Holds preserved

Structural Rule 1; PR #20 and PR #64 not ancestors and nothing imported from
either; `engine/src/alloc.c` and `tests/harness/test_alloc.c` still absent;
frozen DRAFT-8 and WP-08 bytes unchanged; all four verifier package trees
unchanged; WP-11 golden failure red and visible; no self-acceptance, no package
acceptance, no merge; hardware fabrication/charging gate untouched; no purchases.
