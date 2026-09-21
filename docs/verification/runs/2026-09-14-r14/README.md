# P1-R14-SW — corrected per-render scrub cadence, product run

Product run of the ten-family **cadence-corrected** complete playback package
against the held clean candidate, with the Software-owned probe corrected to
service before every render as WP-08 specifies. **PASS**, all seven PCM families
byte-exact, and **698 renders / 698 immediately preceding completed services in
each scrub direction**.

**Not acceptance.** Independent Verification dispositions this bundle; PM routes
it. A green run accepts no product behaviour, source, PCM, golden or listening
result, and the candidate stays draft and held.

**This supersedes the P1-R12 cadence evidence in
`docs/verification/runs/2026-09-13-r11/`, which is historical.** That run used
the once-per-row scrub service schedule the corrected package now rejects by name
(`P1-R13-V01`). It is preserved unchanged and must not be read as current.

## Identity

| Item | Value |
|---|---|
| Input product main (issue #83) | `a87263aa4f006233d1b855a9736c41995b8343ce` |
| Phase-A merge on main (PR #85) | `888f4dafcddcc4d7b96e8ec8e250dd5bb4062b63` |
| Imported package tree | `467a34bb0a84672c5bdef9059f2dd326d6435eb6` |
| Ancestry-sync commit | `5b8d62938a0ed5010fac658235de110ffadfbd0c` |
| **Pre-run code commit (built and run)** | **`b94ee2e33fd7fb8f6691e76a83d2392b6717e8a7`** |
| Pre-run tree | `9a801f8b7e61f498e4a0459a640bc1aacf706c66` |
| Evidence commit / tree | `9204512b7f3f06ce6ce202db9f1e2a92e56e8d0b` / `78ecbe71ec38d854f77989408bd3f0b8a15fe623` |
| PR #77 head before this round | `f100937aed1437401218003db3edbb07d8e4f543` |
| Existing clean code commit | `86eb3b77756042c365e2d0353018b981c39c99e8` |
| Verifier publication / evidence commit | `e3a25bf3b9eda6581b5de524e5bd5fa2c032e0da` / `05e193209542d204669b32f485dad21007a084ee` |
| `engine/src/play.c` sha256 | `d2a904d4f4b15595094d18f52ef3b4aeea30ce11320c2561e09b6ac82a7a49f1` |
| `engine/src/mount.c` sha256 | `324ba896a9f3f894f16e741b8e38b1307b88fcde9918a9c28db5cb204977a2f8` |
| `engine/src/chunks.c` sha256 | `82b5d16bdd3dc7e85d59b0ca8ba82ed0367a333668bd3319e2cd16a921d1391a` |
| libtape.a sha256 (as linked) | `e49cd1b599752a06f71c6d5440623acf42faeb3ad1d2ca925d4f0096036d5323` |
| Adapter source sha256 | `da64522cce7e623161ea3c5d8d27ac46d027873b79a7a8830ec1b8dc4bc2786d` |
| Adapter wrapper sha256 | `ebe108d0b960b389374b57848d14771af31d6154eadb2cb2049c1affe236051b` |
| Adapter binary sha256 | `7ee49c67ebbf6c949c5f0ccfed65ed2ae779df02a8383bd41ff569f7cda6dee2` |
| Toolchain | cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; Python 3.11.15 |

Built from a clean `git archive` of the pre-run commit, which existed before the
run. The same identities appear in `product-evidence/manifest.json`'s
`adapter.build`, here, and in `docs/REVIEW/returns/P1-R14-SW.md`.

## What changed, and what did not

The whole product delta against PR #77's previous head is **one file**:

| Path | Before | After |
|---|---|---|
| `tests/playback_adapter/complete_probe.c` | `f6e557793087e980e7f3758a1bacf8ed006c131e` | `a3c79aef0911e21fd88e04207c49116e8f598d1a` |

`site/lead-queue/index.html` also differs against that head; it arrived with
main through the ancestry sync and is PM's, not mine.

Unchanged and verified blob-for-blob against `f100937`: `tape.h`, `tape_dev.h`,
`mount.c`, `play.c`, `tape_internal.h`, `tapefs.c`, **`chunks.c`**, `crc32.c`,
`dev.h`, `media.h`, `test_mount.c`, `test_play.c`, `tests/Makefile`,
`complete_adapter.sh` and the adapter `Makefile`. `engine/src/alloc.c` and
`tests/harness/test_alloc.c` remain absent. No verifier-owned file changed after
the Phase A import.

### The correction, in two parts

1. **Cadence.** `service_to_idle` moved from above the render loop to inside it,
   so every render request in all 16 rows and both directions is immediately
   preceded by a completed `tape_service(block_budget == 1024)` sequence under
   the same finite guard. Once per row was the defect.

2. **Ring size.** `PLAY_RING_BYTES` is now `TAPE_PLAY_RING_MIN` rather than
   8 MiB. The large ring existed only to let a whole row render after one
   service sequence. Under the specified schedule it is actively wrong here:
   `tape_service` restarts its window whenever the playhead moves, so a forward
   scrub re-reads the rest of the timeline before every render. Measured across
   the 16 rows, same engine, same driver, only the ring differing:

   | Ring | Direction | Renders | Services | Block reads |
   |---|---|---:|---:|---:|
   | 8 MiB | forward | 698 | 4,516 | 4,260,912 |
   | 8 MiB | reverse | 698 | 706 | 8,608 |
   | 64 KiB | forward | 698 | **698** | 90,003 |
   | 64 KiB | reverse | 698 | **698** | 90,056 |

   The 8 MiB run also overflowed the probe's own call trace, which is how it
   surfaced. This is caller-owned storage (guardrail 08); no engine byte changed
   with it, and identical PCM across both rings is the cross-target contract
   working — the ring is a window over timeline frames, so its size cannot change
   what a loaded frame decodes to.

## Result

```
PASS P1-R13 corrected playback evidence
REPLAY PASS docs/verification/runs/2026-09-14-r14/product-evidence
289 cases; 0 failed; seed=0xd8a607
```

| Family | Frames | PCM sha256 | Match |
|---|---:|---|---|
| `one_intmax` | 1 | `911beffad40098d1dc520cbe58946c7179d7f8d9334f9813aabb223bf11ccc47` | yes |
| `reverse_zero` | 1 | `911beffad40098d1dc520cbe58946c7179d7f8d9334f9813aabb223bf11ccc47` | yes |
| `intmin` | 2 | `d844e1554b5c802b4cc27c59d7503f3117296f7928d3d24dc87679a3e32a27dd` | yes |
| `scrub_forward` | 88,200 | `41e882e74e3c64d929fcc76ad47b52f72ce9ed1541e971497b3c9a04fb46006b` | yes |
| `scrub_reverse` | 88,200 | `5f1794e8dcd7c1b3e2c390a1aef33039f5b88b20f682c56c4aa6f94051bd8fa1` | yes |
| `side_playing` | 2 | `8cde253ff03900ec30ecc695b700913a442ede54fd8b45a1dd06a6fe6e0206e1` | yes |
| `side_idle` | 1 | `3f9f540229960d11ed73b7ff1fae0b6f26f723ea5c80d238976fc4c902cea28b` | yes |

**All seven PCM outputs are unlistened and are not WP-11 goldens.** They are
verifier-derived candidate bytes; human listening remains held.

`empty_zero`, `empty_nonzero` and `nonempty_zero` emit no PCM; their call and
state assertions hold.

### Cadence counts (`cadence-counts.txt`, recomputed from the observation)

| | scrub_forward | scrub_reverse |
|---|---:|---:|
| `tape_render` calls | 698 | 698 |
| `tape_service` calls | 698 | 698 |
| renders immediately preceded by a completed `tape_service(1024, more_work=false, result=0)` | **698** | **698** |
| exceptions | none | none |
| `tape_set_rate` calls | 16 | 16 |
| frames rendered | 88,200 | 88,200 |
| short renders | 0 | 0 |
| device callbacks, all `read` with `rc = 0` | 90,003 | 90,056 |

## Mount regression (provenance, not new acceptance)

Re-ran the independent 289-case mount package against this pre-run commit:
**289 cases, 0 failed**, seed `0xd8a607`. All 289 **case records are
byte-identical** to the P1-R12 run's log (`mount-289-cases.json` in
`2026-09-13-r11/`), compared line-by-line after the provenance header.

**The executable identity is *not* bit-identical, and that is expected here:**
the probe binary hashes `c0e98c56…` this round against `57b8274e…` last round.
The engine *sources* are byte-identical (`play.c d2a904d4…`, `mount.c
324ba896…`, `chunks.c 82b5d16b…`, `tapefs.c`, `crc32.c` all unchanged), but the
engine Makefile compiles with `-g` from an absolute source path and archives
with `ar rcs`, so object, archive and linked-binary hashes depend on the build
directory and on mtimes. Two builds of this same commit in two directories give
`play.o` hashes `70a54fbb…` and `c2f30a23…`. Binary identity across runs is
therefore not reproducible by construction in this repository; source identity
is, and the manifest binds both the sources and this build's own binaries.

This mount run is regression and provenance evidence. It is not new independent
acceptance, and the narrow P1-R12 mount disposition does not transfer to this
commit.

## Exclusions

Not acceptance. No WP-11 golden, no listening. No allocator, recording,
crash/recovery, warm-start descriptor negatives, state-matrix or operations
work, performance, hardware or card behaviour: `tape_arm`, `tape_feed`,
`tape_commit`, `tape_abort`, `tape_promote`, `tape_respool`, `tape_dup`,
`tape_format` and `tape_reset_side_b` are absent from this slice entirely.
`tape_status` reports `recording_armed` and `frames_owed` false because §7
recording is not implemented here. PR #77 stays draft and unmerged; PR #20 and
PR #64 stay held.

## Reproduce

```sh
git checkout b94ee2e33fd7fb8f6691e76a83d2392b6717e8a7
make -C engine BUILD=../build/engine
make -C tests/playback_adapter complete
export COMPLETE_PROBE=$PWD/tests/playback_adapter/build/complete_probe
python3 tests/playback_complete_draft8/runner.py \
  --adapter-cmd "$PWD/tests/playback_adapter/complete_adapter.sh" \
  --adapter-kind product \
  --adapter-id software-lead-complete-playback-public-api-probe-v1 \
  --adapter-source "$PWD/tests/playback_adapter/complete_probe.c" \
  --adapter-build '<compiler + engine source/archive + adapter + probe identity>' \
  --adapter-timeout-seconds 900 \
  --source-commit 05e193209542d204669b32f485dad21007a084ee \
  --source-tree 467a34bb0a84672c5bdef9059f2dd326d6435eb6 \
  --evidence-dir <fresh-dir>
python3 tests/playback_complete_draft8/replay.py <fresh-dir>
python3 tests/playback_complete_draft8/replay.py \
  docs/verification/runs/2026-09-14-r14/product-evidence

make -C tests/mount_draft8 engine PUBLIC_HEADER=tape.h \
     CPPFLAGS="-I$PWD/engine/include" ENGINE_OBJECTS="$PWD/build/engine/libtape.a"
python3 tests/mount_draft8/run.py --adapter tests/mount_draft8/build/engine_probe \
     --log <fresh-log.json>
```

## Raw observation (WO-6)

`product-evidence/output/observation.json` is **not in the working tree**. It is a
release asset, cited by the committed `observation.json.sha256` and
`OBSERVATION-SOURCE.md` at this run's root. **The hash is the citation.**

Before running any command above that reads the bundle:

```sh
tools/fetch-evidence.sh 2026-09-14-r14
```

That verifies the asset against the committed hash and refuses to install a mismatch.
The bundle is otherwise byte-for-byte unchanged, and CI fetches automatically.
