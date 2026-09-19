# P1-R9-SW Phase B — the unchanged candidate against the corrected package

Product run of the ten-family **corrected** complete playback package against the
held candidate, with **no engine, firmware or public-behaviour change in this
assignment**. `engine/src/play.c` still hashes
`d2a904d4f4b15595094d18f52ef3b4aeea30ce11320c2561e09b6ac82a7a49f1` — the same
bytes that produced the P1-R7 failing run. What changed is the package, not the
engine.

**Result: PASS. Every family matches byte-exactly.** That is not acceptance.
Independent Verification dispositions this bundle; PM routes it. Closing the
assignment issue is not acceptance either, and a green run does not accept a
package, a PCM, a golden or a listening step.

## Identity

| Item | Value |
|---|---|
| Input product main (issue #70) | `d208614dc11eee9935f1575c0a545cc8714def6b` |
| Phase-A merge on main (PR #71) | `d52730ffb4c9d8e634eded9caca208dcacb0d046` |
| **Code-under-test commit (built and run)** | **`5f44b97fe9fb3342fce3b58236a75ea27b4898a6`** |
| PR #64 head before this round | `bc53076448112ec3015de40e71c229e17d225c2f` |
| Held ancestor (PR #20 head, unmodified) | `2e0e8a4b7bff42797ac37901196e5ea348b2e392` |
| Verifier publication | `mmsanders/digital-tape-verification@62b18deb8b4fbe6e797b00d792ee9f46ac0a8059` |
| Corrected package tree (on main and here) | `6dbb23bb4626238b0f22427031a551d2ece454fd` |
| Corrected pre-evidence source commit / tree | `1c1489a5b1c10f2baa8425557fd7bdfde3225575` / `43ca6f6bbc1990d5ced6de3b2ce0d04f00aa7519` |
| `engine/src/play.c` sha256 | `d2a904d4f4b15595094d18f52ef3b4aeea30ce11320c2561e09b6ac82a7a49f1` |
| libtape.a sha256 (as linked) | `403d736290035909792c053ba10c0e2ca67a3d06e40d80a3064eb5b5286edf91` |
| Adapter source sha256 (`complete_probe.c`) | `2349aa3a28fd3ce9821794c93143ccec85a8186e94b9fd2cd332d68267073b89` |
| Adapter wrapper sha256 (`complete_adapter.sh`) | `ebe108d0b960b389374b57848d14771af31d6154eadb2cb2049c1affe236051b` |
| Adapter binary sha256 | `a566f3f891bb0451cf53b3a2b3d57410c55a24b6b584cebdc40d2f3cfb1abe22` |
| Toolchain | cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; Python 3.11.15 |

Every artefact above was built from a clean `git archive` checkout of the
code-under-test commit, which existed before the run. The same hashes appear in
`product-evidence/manifest.json`'s `adapter.build` string, in this table and in
`docs/REVIEW/returns/P1-R9-SW.md`: one build identity for this round. `ar rcs`
embeds member mtimes, so the archive hash identifies *this* build while the
engine source is pinned by the commit and by the `play.c` hash — which is
byte-identical to the P1-R7 round's.

`manifest.json`'s `assignment: P1-R8-V` is the verifier runner's own constant,
not a claim by me.

## Result

```
PASS P1-R8 corrected playback evidence
REPLAY PASS docs/verification/runs/2026-09-13-r9/product-evidence
```

Replayed in place with the package's unmodified `replay.py` after being copied
into the repository, so the committed bytes are what passed.

| Family | Frames | PCM |
|---|---:|---|
| `empty_zero`, `empty_nonzero`, `nonempty_zero` | — | no PCM; call/state assertions hold |
| `one_intmax` | 1 | byte-exact |
| `reverse_zero` | 1 | byte-exact |
| `intmin` | 2 | byte-exact — `frame(1)` then `frame(0)`, per §6.2's "land ON frame 0; it is emitted next pass" |
| `scrub_forward` | 88,200 | byte-exact |
| `scrub_reverse` | 88,200 | byte-exact against the corrected `5f1794e8…` candidate, the §6.3 grid snap |
| `side_playing` | 2 | byte-exact |
| `side_idle` | 1 | byte-exact |

The three P1-R8 findings are closed by this run without a line of engine change:
F-1 `intmin` now renders 2; F-2 the reverse scrub candidate is the grid snap the
engine already produced; F-3 the side families expect `TAPE_ERR_UNDERRUN = 18`,
which is what the engine already returned. `adapter.kind` is `product` in both
the manifest and the observation, and replay enforces that equality, so this is
not a relabelled synthetic bundle.

## What this does NOT establish

Not acceptance. No WP-11 golden and no human listening: the candidate PCM is
verifier-derived and remains unlistened. No recording, crash/recovery,
warm-start descriptor negatives, state-matrix completion, performance, hardware
or card qualification. `tape_status` reports `recording_armed` and `frames_owed`
as false because §7 recording is not implemented in this candidate. The
implementation remains held: PR #64 must not merge.

Prior bundles are untouched and remain immutable: `2026-09-13-r6/` (three
families) and `2026-09-13-r7/` (the failing run against the pre-correction
package, with its retained first-run diagnostic).

## Reproduce

```sh
git checkout 5f44b97fe9fb3342fce3b58236a75ea27b4898a6
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
python3 tests/playback_complete_draft8/replay.py \
  docs/verification/runs/2026-09-13-r9/product-evidence
```

The bundle is 11 MB, nearly all of it `output/observation.json`: the package's
call schedule services the whole timeline once per scrub row, so the observation
carries about 1.5 million individual read-callback records, retained unfiltered
because callback legality is one of the things the oracle checks.
