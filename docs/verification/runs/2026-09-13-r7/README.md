# P1-R7-SW Phase B — real product run of the complete playback tranche

First real product run of the ten-family complete playback package
(`tests/playback_complete_draft8/`) against the engine that implements
`tape_seek`, `tape_set_rate`, `tape_service`, `tape_render`, `tape_set_side` and
`tape_status`. **Not acceptance.** Independent Verification dispositions this;
PM routes it through a fresh issue. Closure of the assignment issue is not
acceptance either.

## Identity

| Item | Value |
|---|---|
| Input product main (issue #66) | `c497f21fc3ab71defd509bbb3eedc9413457e8e9` |
| Phase-A merge (tests on main) | `14a5931` (PR #67) |
| Tested-code commit (built and run) | `43d2dbaa6434942df37e165b25edc6d45135fee2` |
| PR #64 head before this round | `3dc5abb85e5b30200cf1553b9a06a83bc83c6d36` |
| Held candidate base (PR #20 head, unmodified) | `2e0e8a4b7bff42797ac37901196e5ea348b2e392` |
| Verifier publication | `mmsanders/digital-tape-verification@121f5f7ab03c9ce08c38329e518c49a1ca9b65a5` |
| Verifier source commit / tree | `54789cc6e6bbfd942857374e2e0b3305d05d2f2c` / `5527547b72b3e5c6d6fb91d41f3aa3bfa86fab7d` |
| Complete published subtree (reproduced on main) | `863b3a49c421bda1bebcf1a9760149bec7051048` |
| `engine/src/play.c` sha256 | `d2a904d4f4b15595094d18f52ef3b4aeea30ce11320c2561e09b6ac82a7a49f1` |
| libtape.a sha256 (as linked) | `1a91c0eab8d8a6c5d486c2f3ec7622328178046db843f53da7f4332c29114458` |
| Adapter source sha256 (`complete_probe.c`) | `2349aa3a28fd3ce9821794c93143ccec85a8186e94b9fd2cd332d68267073b89` |
| Adapter wrapper sha256 (`complete_adapter.sh`) | `ebe108d0b960b389374b57848d14771af31d6154eadb2cb2049c1affe236051b` |
| Adapter binary sha256 | `f1606b844a836c495ca4873c3d1b820a7d6987d57973c107653928fb82bcb9a6` |
| Toolchain | cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; Python 3.11.15 |

Every engine and adapter artefact above was built from a clean `git archive`
checkout of the tested-code commit, after that commit existed — the code was
committed first, then built, then run. The same libtape.a and probe-binary
hashes appear in `product-evidence/manifest.json`'s `adapter.build` string, in
this table and in the return document; there is one build identity for this
round. `ar rcs` embeds member mtimes, so the archive hash identifies *this*
build while the engine source is pinned by the commit and by the `play.c` hash.

## Result

`product-evidence/` is the complete bundle the verifier's own runner produced,
copied verbatim and re-replayed in place with the package's unmodified
`replay.py`:

```
REPLAY FAIL: tape_render.rendered
```

Every hash binding in the manifest verified — replay reached the oracle, which
is what proves the bundle self-consistent — and the oracle then rejected the
observation at its first disagreement. The verdict is **FAIL and it stays
visible**: no assertion, fixture, oracle, candidate PCM or verifier file was
modified, and nothing here is relabelled.

`result.json` names one error because the oracle raises at the first
disagreement. There are three, all reverse-direction, and all of them are
points where **the package disagrees with the frozen DRAFT-8 contract**, not
places where the engine disagrees with the package. They are set out with
citations in `docs/REVIEW/returns/P1-R7-SW.md` and escalated to PM; the engine
was not changed to match them and the package was not relaxed to match the
engine.

| Family | PCM | Verdict |
|---|---|---|
| `empty_zero`, `empty_nonzero`, `nonempty_zero` | none | call/state assertions hold |
| `one_intmax` | 1 frame | byte-exact |
| `reverse_zero` | 1 frame | byte-exact |
| `intmin` | 2 frames | **F-1**: package expects 1 |
| `scrub_forward` | 88,200 frames | byte-exact against the candidate |
| `scrub_reverse` | 88,200 frames | **F-2**: candidate is the DRAFT-5 off-grid snap |
| `side_playing` | 2 frames | byte-exact |
| `side_idle` | 1 frame | byte-exact |
| `side_playing`, `side_idle` post-switch render | — | **F-3**: package expects result 6, frozen enum says 18 |

`isolation/` measures how much of the package the engine satisfies with exactly
those three expectations set aside in a scratch copy held outside the
repository: 1,625 checked calls, all pass, five byte-exact PCM families. That is
a diagnostic, not a verdict.

`first-run-diagnostic/` retains the earlier failing run, which failed on a
defect in my own adapter (a scalar fixture value parsed as the first element of
the next array). It is kept per issue #66 item 8 and is evidence about the
adapter only.

## What this does NOT establish

No acceptance, no WP-11 golden, no human listening: the candidate PCM is
verifier-derived, and two of the three findings are about that candidate and its
oracle. No recording, crash/recovery, warm-start descriptor negatives, state
matrix completion, performance, hardware or card qualification. `tape_status`
reports `recording_armed` and `frames_owed` as false because §7 recording is not
implemented in this candidate. The implementation remains held: it must not
merge this round.

## Reproduce

```sh
git checkout 43d2dbaa6434942df37e165b25edc6d45135fee2
make -C engine BUILD=../build/engine
make -C tests/playback_adapter complete
export COMPLETE_PROBE=$PWD/tests/playback_adapter/build/complete_probe
python3 tests/playback_complete_draft8/runner.py \
  --adapter-cmd "$PWD/tests/playback_adapter/complete_adapter.sh" \
  --adapter-kind product \
  --adapter-id software-lead-complete-playback-public-api-probe-v1 \
  --adapter-source "$PWD/tests/playback_adapter/complete_probe.c" \
  --adapter-build '<compiler + engine archive + probe binary identity>' \
  --adapter-timeout-seconds 600 \
  --source-commit 121f5f7ab03c9ce08c38329e518c49a1ca9b65a5 \
  --source-tree 863b3a49c421bda1bebcf1a9760149bec7051048 \
  --evidence-dir <fresh-dir>
python3 tests/playback_complete_draft8/replay.py <fresh-dir>
python3 tests/playback_complete_draft8/replay.py \
  docs/verification/runs/2026-09-13-r7/product-evidence
```

The bundle is 11 MB, nearly all of it `output/observation.json`: the package's
call schedule services the whole timeline once per scrub row, so the observation
carries about 1.5 million individual read-callback records. They are retained
unfiltered because callback legality is one of the things the oracle checks.
