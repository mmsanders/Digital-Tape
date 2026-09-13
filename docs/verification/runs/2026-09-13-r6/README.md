# P1-R6-SW Phase B — real product playback evidence

First real product run of the independent playback package against an engine
that implements the four DRAFT-8 transport operations. **Not acceptance.**
Independent Verification must disposition this; PM routes it through a fresh issue.

## Identity

| Item | Value |
|---|---|
| Phase-A merge (tests on main) | `4517db7efba0d1a0933fc0dda1a607c5441197b7` |
| Candidate base (held #20 head, unmodified) | `2e0e8a4b7bff42797ac37901196e5ea348b2e392` |
| Candidate head | `c108356c640e971967fb3a00d87e3f6003a129db` |
| Verifier publication / tree | `7a22cbb4447c40c51b7c8b2282a685ed30a46ba6` / `ff810814dbc8079c6903e6f85ed7ee312abd3076` |
| engine/src/play.c sha256 | `9f96eadab7e0816fc24306d470416f22f844aa0ded3ae48539a2eef48fc87bf1` |
| libtape.a sha256 | `41eb993f65d780a254f9eb95a642fde91595bf654ed7b2d402ca51052403256d` |
| adapter source sha256 | `4bdcefea3aa2c106701fc1749e323f12acd8248ac38c0fb4e098da87150dff02` |
| adapter binary sha256 | `edfbc838d638ea2efe2d90b3b375b45cc7e7728060e70cdc9912c54771508eee` |
| Toolchain | cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; Python 3.11.15 |

## Result

`product-evidence/` is the complete v2 bundle the runner produced, copied
verbatim and re-replayed in place: **REPLAY PASS**, all three families, zero
differing samples and zero peak delta on each.

| Family | Bytes | Differing samples | Peak delta |
|---|---|---|---|
| forward_1x | 60 | 0 | 0 |
| seek_boundaries | 32 | 0 | 0 |
| reverse_neg1x | 60 | 0 | 0 |

The manifest records `adapter.kind = product`, not synthetic, and the
observation agrees — replay enforces that equality, so this cannot be a
relabelled synthetic bundle. Its `assignment: P1-R4-V` field is the
verifier runner's own constant, not a claim by me.

Callback traces occur **only** during `tape_mount` and `tape_service`, with
every `rc = 0`: 14 callbacks for forward, 28 across the eight seeks, 14 for
reverse. Zero block I/O during seek, set_rate or render, which is contract 2
and §6.3 and is asserted independently by the oracle.

## What this does NOT establish

Three families on one 15-frame fixture at exactly +/-1.0x. No human listening;
the candidate PCM is verifier-derived oracle bytes, not accepted WP-11 goldens.
No rate ramps, non-integral or extreme rates, `tape_set_side`, warm start,
recording, crash/recovery, state matrix or performance. WP-08 and WP-11 remain
open, and the implementation is held: it must not merge this round.

## Reproduce

```sh
make -C engine all
make -C tests/playback_adapter ENGINE_INC=../../engine/include \
     ENGINE_LIB=../../build/engine/libtape.a
python3 tests/playback_draft8/runner.py \
  --adapter-cmd "$PWD/tests/playback_adapter/build/playback_probe" \
  --adapter-kind product --adapter-id software-lead-playback-public-api-probe-v1 \
  --adapter-source tests/playback_adapter/playback_probe.c \
  --adapter-build '<compiler + engine archive identity>' \
  --source-commit 7a22cbb4447c40c51b7c8b2282a685ed30a46ba6 \
  --source-tree ff810814dbc8079c6903e6f85ed7ee312abd3076 \
  --evidence-dir <fresh-dir>
python3 tests/playback_draft8/replay.py <fresh-dir>
```
