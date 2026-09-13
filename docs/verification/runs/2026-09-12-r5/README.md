# P1-R5-SW raw evidence packet — 12 September 2026 UTC

Software Lead work on [issue #59](https://github.com/mmsanders/Digital-Tape/issues/59).
Raw software-run reproduction and build diagnostics. **Nothing here is acceptance.**
Independent disposition belongs to Verification, through a separate issue.

## Provenance

| Input | Exact value |
|---|---|
| Product input named by the issue | `b7f92dbb5ef4e59d9dd4ae268937ebbac31225ca` |
| Product main actually worked against | `fd2b73f` (`b7f92dbb` is its ancestor; two PM doc commits since) |
| Verifier publication | `mmsanders/digital-tape-verification@7a22cbb4447c40c51b7c8b2282a685ed30a46ba6` |
| Corrected source / tree | `d565403907ecea331a5dcf63efbd1c08d8bd732e` / `aaa6dde86c9a0bdffa2b375361049ac670e26467` |
| Published subtree imported | `ff810814dbc8079c6903e6f85ed7ee312abd3076` — reproduced exactly, 57 files |
| Held comparison engine | PR #20 head `2e0e8a4b7bff42797ac37901196e5ea348b2e392` |
| DRAFT-8 hashes | unchanged; bundle gate green |
| Toolchain | `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`; Python 3.11.15 |

## Files

| File | What it is |
|---|---|
| `playback-synthetic.log` | Deterministic fixture/candidate-PCM regeneration, the package self-test (3 families + 18 controls), offline replay of the retained **P1-R4** synthetic bundle, and confirmation that the historical **P1-R2 v1** bundle is refused rather than silently upgraded. **All synthetic — no engine executed.** |
| `adapter-diagnostic.log` | The product adapter compiled and linked against both engines that exist: current main and held #20. Lossless compiler and linker output. |

## There is no product evidence directory, and why

Item 5 of the assignment is conditional on a real engine run being obtainable
without implementation changes. **It is not.** No engine in the repository or on the
held branch defines `tape_seek`, `tape_set_rate`, `tape_render` or `tape_service` —
the four operations every playback family needs:

```
  tape_seek:     main=0 pr20=0      (0 = undefined)
  tape_set_rate: main=0 pr20=0
  tape_render:   main=0 pr20=0
  tape_service:  main=0 pr20=0
```

So the runner was never invoked, no `v2` evidence directory was created, and no
VO08/PCM/observation/manifest product bundle exists. That is an absent run, not
lost or withheld evidence. No stub, fake or uncovered implementation was added to
manufacture one.

Against **current main** the adapter does not even compile: main's public header
still declares `tape_mount(tape*, tape_side, uint64_t, const void*, size_t)` where
the frozen DRAFT-8 API has `const tape_warm_start *warm`.

A consequence worth stating: because no product run is possible, **the product
adapter's observation schema has never been exercised against a real engine.**

## Reproduce

```sh
make -C tests/playback_draft8 check          # regeneration + selftest, synthetic
python3 tests/playback_draft8/replay.py tests/playback_draft8/evidence/p1-r4-synthetic
python3 tests/playback_draft8/replay.py tests/playback_draft8/evidence/p1-r2-synthetic  # expected: wrong schema

make -C tests/playback_adapter compile ENGINE_INC=../../engine/include        # fails: tape_mount arity
git archive 2e0e8a4b7bff42797ac37901196e5ea348b2e392 | tar -x -C /tmp/pr20
make -C /tmp/pr20/engine all
make -C tests/playback_adapter compile ENGINE_INC=/tmp/pr20/engine/include    # clean
make -C tests/playback_adapter ENGINE_INC=/tmp/pr20/engine/include \
     ENGINE_LIB=/tmp/pr20/build/engine/libtape.a                              # four undefined symbols
```
