# Retained failing first run — P1-R7-SW Phase B

This is the **first** real product run of the complete playback tranche, kept
because issue #66 item 8 requires a failing bundle to be retained rather than
discarded. It failed on a defect in **my own adapter**, not in the engine and
not in the verifier package.

## Identity

| Item | Value |
|---|---|
| Tested-code commit | `32ced9e11f4df5b05fe3f9c5008e3434f56aebd1` |
| libtape.a sha256 (as linked) | `debacad3e62e9be4472041f40e7ffc38f09ae0eb249448898ed8def7e44b4dff` |
| Probe source sha256 | `85c71e2dc66ba174f32370aee726c4f13b9765f026cab97a0ca88865ad3985f6` |
| Probe binary sha256 | `795ed072c00f0b3b6153f5da401fb6fe0dd449828d3088ebb92aa89ff9f82a25` |
| Runner verdict | `FAIL`, `result.json` error `tape_render.rendered` |
| Adapter exit | `0`, empty stderr |
| `output/observation.json` sha256 | `82468e1e3921dde5a0794acde740a63063d41c3f968541f99e5fd186241e169e` |

## Why `observation.json` is not stored here

It is 9,289,887 bytes and byte-reproducible: the probe binary above run against
the package's own fixtures regenerates it exactly (verified identical during
diagnosis). Storing a second 9 MB copy of a superseded observation next to the
11 MB bundle that supersedes it is not worth the repository weight, so this
directory keeps the manifest, the verdict, the adapter's streams and every PCM
output, and binds the observation by hash instead.

```sh
git checkout 32ced9e11f4df5b05fe3f9c5008e3434f56aebd1
make -C engine BUILD=../build/engine
make -C tests/playback_adapter complete
# decompress tests/playback_complete_draft8/fixtures/*.vo08.gz into <tmp>/fixtures,
# copy input/WP-08.md to <tmp>/input, then:
tests/playback_adapter/build/complete_probe --fixture-dir <tmp>/fixtures --out-dir <dir>
sha256sum <dir>/observation.json   # 82468e1e...e169e
```

## Root cause

`json_int_array` in `complete_probe.c` skipped forward to the next `[` before
parsing, so on a **scalar** key it returned the first element of the next array
in the document. `fixtures/fixture.json` is sorted, so

    "long_side_a_frames": 1100000        <- what the script needed
    "rates_q16_16": [262144, ...]        <- what it actually read

resolved `long_side_a_frames` to `262144`. Two families used that value:

* `scrub_reverse` seeked to frame 262,144 instead of 1,100,000 and walked into
  the start of the tape after nine rows;
* `side_playing` seeked to 262,143 instead of 1,099,999, so its first Side-A
  frame was the wrong frame of the fixture waveform.

The engine's behaviour in the bundle is **correct for the positions it was
given**: reverse playback from frame 262,144 reaches frame 0 during row 9, and
from there `tape_render` returns `TAPE_OK` with `*rendered = 0` because
`at_start` is set — §6.3's "a shortfall caused by `at_end`, `at_start` or
`rate == 0` returns `TAPE_OK`". Nothing in this bundle is evidence about the
engine; that is what made it worth keeping as a worked example of an adapter
defect that looks like an engine defect.

## Observed reverse scrub, first run

| Row | Reverse rate Q16.16 | tape_service calls | Frames rendered | Expected |
|---:|---:|---:|---:|---:|
| 0 | -262144 | 3 | 4410 | 4410 |
| 1 | -297097 | 1 | 4410 | 4410 |
| 2 | -332049 | 1 | 4410 | 4410 |
| 3 | -367002 | 1 | 4410 | 4410 |
| 4 | -401954 | 1 | 4410 | 4410 |
| 5 | -436907 | 1 | 4410 | 4410 |
| 6 | -471859 | 1 | 4410 | 4410 |
| 7 | -506812 | 1 | 4410 | 4410 |
| 8 | -541764 | 1 | 4410 | 4410 |
| 9 | -576717 | 1 | 2128 | 4410 |
| 10 | -611669 | 1 | 1 | 4410 |
| 11 | -646622 | 1 | 1 | 4410 |
| 12 | -681574 | 1 | 1 | 4410 |
| 13 | -716527 | 1 | 1 | 4410 |
| 14 | -751479 | 1 | 1 | 4410 |
| 15 | -786432 | 1 | 1 | 22050 |
| **total** | | | **41824** | **88200** |

Row 0 needed three `tape_service` calls because the reverse window under a
262,146-frame playhead is 262,146 frames wide (2,049 block reads at
`block_budget == 1024`); rows 1-15 needed one each because the window already
held everything below the playhead. Under the corrected seek the first row
services nine times for the full 1,100,000-frame window, which is the first
thing that gave the defect away.

## Fix

`43d2dbaa6434942df37e165b25edc6d45135fee2` adds a strict scalar parser and
echoes the parsed fixture parameters to stdout, so the positions a run actually
used are visible in the evidence. The oracle pins every family's call list
exactly, so the adapter cannot add a recorded cross-check call, and it must not
make unrecorded engine calls — printing is the honest option. No engine source,
verifier file, fixture, oracle or assertion was touched.
