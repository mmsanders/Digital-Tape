# P1-R6-SW return — Software Lead

**Issue:** [#63](https://github.com/mmsanders/Digital-Tape/issues/63). **Returned:** 13 September 2026 UTC.
**Next owner:** PM. Independent Verification must disposition the product observation before any implementation merge.

## Phase A — PR #60 reviewed, updated, merged

**Merge SHA: `4517db7efba0d1a0933fc0dda1a607c5441197b7`.** Head reviewed and merged: `9c657b5f359d3dad267fefd1c48c4dadfb8a3a0d`.

Main had advanced five commits since #60 branched at `fd2b73f` — dashboard PR #62, its PR-time CI job, the roadmap bar, the WP-08 scrub table plus P1-R6 disposition, and the assignment links. Brought up to `d8b7adc` by **merging main in, additively**:

- The only conflict was `.github/workflows/ci.yml`, where PM's `dashboard` job and this branch's `playback-package` job were inserted at the same anchor. **Both belong; both kept.**
- Verified no PM line was lost: every non-blank line of main's `docs/VERIFICATION-INTEGRATION.md` is still present, and my playback section is the only addition. `docs/PACKAGES/WP-08.md` is byte-identical to main at `ff519e960ed3db6e401baebd12f33d5527f83f0e4dfec12484f498470198a96a`.
- `tests/playback_draft8/` still hashes exactly `ff810814dbc8079c6903e6f85ed7ee312abd3076`; no file inside it was touched.
- Empty diff against `engine/` and `firmware/` — no engine implementation in Phase A.
- Retained: synthetic/product distinction in both package job names, hard-coded `product` adapter identity, bounded execution, unfiltered callback/result records, and the exact compile/link diagnosis. WP-11 golden red left visible and unrequired.

Checks: playback package self-test, mount 10/10, ops 2+12, dashboard behaviour, `tools/ci/all.sh` green, `golden` red as expected. PR CI: 20 checks, only the two `golden suite` runs red.

## Phase B — held implementation candidate and real evidence

**Branch `claude/bold-hypatia-zhrrzf-playback`, head `c108356c640e971967fb3a00d87e3f6003a129db`. Draft, and it must not merge this round.**

Provenance: branched from held #20 head `2e0e8a4b7bff42797ac37901196e5ea348b2e392` and merged post-Phase-A main `4517db7` to bring in the exact tests. **#20's own ref is untouched** — verified against the remote, still `2e0e8a4b`. Nothing was rebased or force-pushed.

### What was implemented

One new file, `engine/src/play.c`, implementing the four operations from the frozen normative text for the **whole valid input domain**, not narrowed to the package's ±1.0× examples:

- **`tape_seek`** — beyond end clamps and returns `TAPE_OK`; clears both endpoint flags (§6).
- **`tape_set_rate`** — signed 16.16, instantaneous only; clears both flags.
- **`tape_service`** — the only thing that touches the device; at most `block_budget` blocks per call; `*more_work` while its window is unfilled; `block_budget == 0` is `TAPE_ERR_INVALID_ARG`.
- **`tape_render`** — §6.3 verbatim, **fetch → emit → advance**, the §6.2 advance with each direction clearing the other's flag and `at_start` set only when the playhead was *already* at 0, the V5-005 **on-grid** snap to `(total−1) << 32`, §8 interpolation with both operands cast before subtracting and no `>>` on a negative value, and `TAPE_ERR_UNDERRUN` only when the ring was the cause.

The play ring is treated as a **window over timeline frames** (`play_base`, `play_frames`). That is what makes §6.3's cross-target contract hold: render reads only the window, so "service to completion then render" and "interleave them" cannot differ.

### Minimum plumbing, and one representation change worth flagging

`struct tape` gained `play_base`, `play_frames` and `resume_whole_frame`. `tape_set_side` now also clears the window (invariant 31: no frame from the previous side is ever rendered after a switch).

**`position_frame` now holds §6.1's 32.32 fixed-point position** rather than whole frames — playback needs the fraction and the spec defines `max_pos = total_frames << 32`. Four small edits in `mount.c`: mount stores `clamped << 32`, warm-start validation compares the retained whole-frame value, and `tape_tell`/`tape_unmount` truncate with `>> 32`. **Observable behaviour is unchanged**, and that is measured, not assumed: **the 289 independent mount cases still pass 289/289** against this candidate (seed `0xd8a607`).

Not implemented, as instructed: `tape_set_side` behaviour beyond the window reset, warm descriptors, recording, crash/recovery, `tape_status`, or any other held operation. No stubs. No verifier assertion, fixture or candidate PCM was touched.

### The real product run

`product-evidence/` in [the packet](../../verification/runs/2026-09-13-r6/README.md) is the complete v2 bundle, copied verbatim and **re-replayed in place: REPLAY PASS**.

| Family | Bytes | Differing samples | Peak delta |
|---|---|---|---|
| `forward_1x` | 60 | 0 | 0 |
| `seek_boundaries` | 32 | 0 | 0 |
| `reverse_neg1x` | 60 | 0 | 0 |

`adapter.kind = product` in both manifest and observation — replay enforces that equality, so this is not a relabelled synthetic bundle. Callbacks occur **only** during `tape_mount` and `tape_service`, all `rc = 0`; **zero block I/O during seek, set_rate or render**, asserted by the oracle independently of my own claim.

It passed on the first run, and no adapter defect surfaced — so there is no failing diagnostic to retain for that clause.

### Because a first-try pass on three families proves little, I tested the domain it misses

The package uses one 15-frame fixture at exactly ±1.0×, where **every interpolation has `f == 0`** and no clamp is approached. An implementation narrowed to those examples would pass it. So `tests/harness/test_play.c` (Software scaffolding, **not acceptance**) adds **114 checks** over what the package cannot reach, with expected interpolation computed by a deliberately different formulation than the engine's:

fetch-before-advance at all eight seek targets · **zero device reads across a full render** · fractional +0.5× where `f = 0x80000000` and the output is provably between the endpoints · negative fractional rate flooring toward −∞ · full reverse-from-end run checked over **all** frames, which is what distinguishes the on-grid snap from DRAFT-5's `max_pos−1` · `rate == 0` rendering nothing · `INT32_MAX` clamping without the V4-009 wrap · `INT32_MIN` landing on frame 0 · seek beyond end · fractional position truncating in `tape_tell` · a run that **jumps chunks** mid-timeline · render before service returning `TAPE_ERR_UNDERRUN` rather than silence · `block_budget == 0`.

### Gates on the candidate

| Gate | Result |
|---|---|
| build `-Werror` C99 | clean |
| allocation / libc file I/O in engine | **PASS** — none |
| indirect calls funnel through `dev.h` | **PASS** |
| stack depth | **PASS** — 1536 / 8192 bytes (18.8%), 37 functions |
| RAM | **PASS** — 156,472 / 204,800 bytes (76%) |
| `.rodata` | **PASS** — 1,040 / 32,768 (3%) |
| meta-gate | **PASS** — every gate still goes red on demand |
| independent mount tranche | **289 / 289** |
| scaffolding suites | allocator 46, crc32 21, dev 37, mount 286, **playback 114** |
| golden suite | **RED** — missing WP-11 manifest, left visible |

## Dependency map

| Need | Status |
|---|---|
| Playback tests on main | **done**, Phase A `4517db7` |
| `tape_seek`, `tape_set_rate`, `tape_service`, `tape_render` | implemented on the held candidate only |
| §6.1 32.32 position | `mount.c` 4 edits, mount-observationally neutral (289/289) |
| Play-ring window state | `play_base`, `play_frames` in `struct tape` |
| `tape_status` | **still undefined** — out of scope here; my scaffolding asserts `at_end` behaviourally rather than depending on it |
| Independent disposition of this product observation | **required before any merge** |
| Verification #7's broader package | must be imported first |

## Holds

PR #20 held, not rewritten, not merged — ref verified unchanged. **The implementation must not merge this round**, and this return does not ask for it. No header-only main upgrade, no verifier change, no test weakening, no synthetic relabel, no golden or listening acceptance, no repository-setting change, no frozen-spec edit, no hardware/card/purchase work. WP-11 red visible. A passing product run is raw observation, not acceptance, and I do not accept my own work.
