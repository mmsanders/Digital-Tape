# P1-R11-SW — the clean split candidate, run against the corrected package

> **SUPERSEDED — historical.** This run used the **once-per-row** scrub service
> cadence. The P1-R13 verifier correction rejects that schedule by name
> (`P1-R13-V01`): WP-08 requires a completed `tape_service` sequence before
> **every** render request, not once per rate row. The bytes here are unaffected
> — both schedules decode identically — but the observation does not exercise the
> specified cadence and must not be read as current product evidence. The current
> run is `docs/verification/runs/2026-09-14-r14/`. This packet is preserved
> unchanged.


Product run of the ten-family corrected complete playback package, plus the
independently landed 289-case mount package, against a **fresh integration slice
built from published main by file and symbol** — not by merging or cherry-picking
any held branch.

**Result: PASS.** Ten playback families with all seven PCM outputs byte-exact,
and 289/289 mount cases. **Not acceptance.** Independent Verification
dispositions this bundle at its exact boundary; PM routes it. The candidate is
draft and held.

## Identity

| Item | Value |
|---|---|
| Input product main (issue #75) | `6a8b2fb481cf43a8d84aad6c74336fc4a2a50d96` |
| **Pre-run code commit (built and run)** | **`86eb3b77756042c365e2d0353018b981c39c99e8`** |
| Independently accepted evidence commit / tree | `c18aa42579ef7c5ea92a4d70972d6a2daa6698bb` / `34bad4611b6849ed586c7ec701fa7ddafef0cb12` |
| Accepted code-under-test (source of the bytes) | `5f44b97fe9fb3342fce3b58236a75ea27b4898a6` |
| Held ancestors, untouched | PR #20 `2e0e8a4b…`, PR #64 `c18aa42…` |
| Verifier publication / package tree | `62b18deb8b4fbe6e797b00d792ee9f46ac0a8059` / `6dbb23bb4626238b0f22427031a551d2ece454fd` |
| `engine/src/play.c` sha256 | `d2a904d4f4b15595094d18f52ef3b4aeea30ce11320c2561e09b6ac82a7a49f1` |
| `engine/src/mount.c` sha256 | `324ba896a9f3f894f16e741b8e38b1307b88fcde9918a9c28db5cb204977a2f8` |
| `engine/src/chunks.c` sha256 | `82b5d16bdd3dc7e85d59b0ca8ba82ed0367a333668bd3319e2cd16a921d1391a` |
| libtape.a sha256 (as linked) | `ee75398163cbbe0d9e7674f1905b300773c317204d56b091207c6fcf17767cf9` |
| Adapter source / wrapper sha256 | `2349aa3a28fd3ce9821794c93143ccec85a8186e94b9fd2cd332d68267073b89` / `ebe108d0b960b389374b57848d14771af31d6154eadb2cb2049c1affe236051b` |
| Adapter binary sha256 | `599e544151f9d4c3ca57eb51d61417ce6a38e1d7d29ef6c19370c9ab5580e004` |
| Toolchain | cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; Python 3.11.15 |

Built from a clean `git archive` of the pre-run commit, which existed before the
run. The same identities appear in `product-evidence/manifest.json`'s
`adapter.build`, in this table and in `docs/REVIEW/returns/P1-R11-SW.md`.
`ar rcs` embeds member mtimes, so the archive hash identifies this build while
the sources are pinned by their own hashes and by the commit.

## The split

Every file in the slice is **byte-identical to the accepted candidate** — same
git blob ids, not a re-derivation:

| Path | Blob | Why it is in |
|---|---|---|
| `engine/include/tape.h` | `7d72fc13…` | the frozen DRAFT-8 public surface the accepted run used |
| `engine/include/tape_dev.h` | `57e59641…` | device contract for the same |
| `engine/src/mount.c` | `af4f826e…` | dispositioned mount behaviour; 289-case package |
| `engine/src/play.c` | `721735b1…` | the ten accepted playback families, `tape_status`, side-switch reset |
| `engine/src/tape_internal.h` | `59a99863…` | shared state for both |
| `engine/src/tapefs.c` | `babbae3d…` | superblock/index parsing both depend on |
| `tests/harness/media.h` | `bc0fcf49…` | harness dependency |
| `tests/harness/test_mount.c` | `0c568d5a…` | hard dependency: main's version cannot compile against the frozen header |
| `tests/harness/test_play.c` | `df1b07f4…` | playback scaffolding for the accepted slice |
| `tests/playback_adapter/complete_probe.c` | `f6e55779…` | hard dependency: main's version predates the P1-R7 fixture-parse fix the accepted run used |
| `tests/Makefile` | `9deb01f0…` | one include path `test_mount.c` needs |

Excluded, present in the accepted candidate: `engine/src/alloc.c`
(`267c9ec4…`) and `tests/harness/test_alloc.c` (`66e7afd1…`) — the VT8-001
allocator and its scaffolding, uncovered and unreferenced here. Also excluded:
all historical evidence bundles, which stay intact on the held PR #64 branch.

### The one new file, and the one judgment call

Linking the slice without `alloc.c` leaves **exactly one** undefined symbol, at
exactly one call site:

```
engine/src/mount.c:401: undefined reference to `tape_chunks_for_frames'
```

That site is TapeFS §9.3.3's promote-resume **row 3** shape check inside
`tape_mount`, and it is inside the independently landed mount package's own
coverage — `M-stage-row3` and `M-stage-row3-H-boundary`, which this run exercises
and passes. So the dispositioned mount behaviour cannot link without that symbol,
while `mount.c` stays unmodified accepted bytes.

`engine/src/chunks.c` therefore carries that function's accepted body **byte for
byte** and nothing else. The allocator proper — `tape_may_reference`,
`tape_may_allocate`, `tape_alloc_run` — has zero references from this slice and
stayed out. `tape_internal.h` keeps its accepted bytes and still declares all
four; a declaration binds no definition, and keeping it makes the boundary
visible rather than papering over it.

This is the round's only judgment call, and it is cheap to reverse: dropping
`chunks.c` makes `mount.c` unlinkable, and taking `alloc.c` whole imports the
uncovered allocator. If PM prefers either, say so and it changes in one commit.

## Result

```
PASS P1-R8 corrected playback evidence
REPLAY PASS docs/verification/runs/2026-09-13-r11/product-evidence
289 cases; 0 failed; seed=0xd8a607
```

| Family | Frames | PCM |
|---|---:|---|
| `empty_zero`, `empty_nonzero`, `nonempty_zero` | — | no PCM; call and state assertions hold |
| `one_intmax` | 1 | byte-exact |
| `reverse_zero` | 1 | byte-exact |
| `intmin` | 2 | byte-exact |
| `scrub_forward` | 88,200 | byte-exact |
| `scrub_reverse` | 88,200 | byte-exact |
| `side_playing` | 2 | byte-exact |
| `side_idle` | 1 | byte-exact |

The frame counts are the ones independently accepted at P1-R10: 1, 1, 2, 88,200,
88,200, 2, 1. Adapter exit `0`, empty stderr, `outcome: exited`,
`adapter.kind = product` in both manifest and observation, and replay enforces
that equality. `mount-289-cases.json` is the mount package's own run log.

Gates on this slice: allocation and `dev.h` funnel clean; stack **35 functions**
within 8,192 (three fewer than the accepted candidate — the excluded allocator);
RAM 156,472 / 204,800; `.rodata` 1,040 / 32,768; meta-gate 15/15; scaffolding
crc32 21, dev 37, mount 286, playback 114 — and no allocator suite, by design.

## What this does NOT establish

Not acceptance. No WP-11 golden, no human listening; candidate PCM is
verifier-derived and unlistened. No recording, crash/recovery, warm-start
descriptor negatives, long-operation or state-matrix work, performance, hardware
or card qualification, and no allocator: `tape_arm`, `tape_feed`, `tape_commit`,
`tape_abort`, `tape_promote`, `tape_respool`, `tape_dup`, `tape_format` and
`tape_reset_side_b` are not in this slice at all. `tape_status` reports
`recording_armed` and `frames_owed` false because §7 recording is not
implemented here. The candidate is draft and held; it must not merge.

## Reproduce

```sh
git checkout 86eb3b77756042c365e2d0353018b981c39c99e8
make -C engine BUILD=../build/engine
make -C tests/playback_adapter complete
export COMPLETE_PROBE=$PWD/tests/playback_adapter/build/complete_probe
python3 tests/playback_complete_draft8/runner.py \
  --adapter-cmd "$PWD/tests/playback_adapter/complete_adapter.sh" \
  --adapter-kind product \
  --adapter-id software-lead-complete-playback-public-api-probe-v1 \
  --adapter-source "$PWD/tests/playback_adapter/complete_probe.c" \
  --adapter-build '<compiler + engine source/archive + adapter + probe identity>' \
  --adapter-timeout-seconds 600 \
  --source-commit 62b18deb8b4fbe6e797b00d792ee9f46ac0a8059 \
  --source-tree 6dbb23bb4626238b0f22427031a551d2ece454fd \
  --evidence-dir <fresh-dir>
python3 tests/playback_complete_draft8/replay.py <fresh-dir>

make -C tests/mount_draft8 engine PUBLIC_HEADER=tape.h \
     CPPFLAGS="-I$PWD/engine/include" ENGINE_OBJECTS="$PWD/build/engine/libtape.a"
python3 tests/mount_draft8/run.py --adapter tests/mount_draft8/build/engine_probe \
     --log <fresh-log.json>
```

## Raw observation identity (WO-6)

`product-evidence/output/observation.json` is now cited by a committed
`observation.json.sha256` and `OBSERVATION-SOURCE.md` **at this run's root**, recording
its bytes, SHA-256 and original git blob. **The hash is the citation.**

Those pointers sit outside `product-evidence/` on purpose: the bundle's `manifest.json`
binds an exact file inventory, and adding anything inside it makes `replay.py` fail with
`unbound/missing evidence file`. The bundle is byte-for-byte unchanged and every command
above still behaves exactly as it did before this change. This superseded bundle does
not replay green against the corrected package (`REPLAY FAIL: assignment`), which is
pre-existing on main and is the `P1-R13-V01` control working, not a regression. See
`OBSERVATION-SOURCE.md` for the pending relocation to a release asset and why it does
not shrink a clone.
