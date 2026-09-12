# P1-R1-SW raw run packet — 12 September 2026 UTC

Produced by the **Software Lead** while working
[issue #41](https://github.com/mmsanders/Digital-Tape/issues/41). These are raw
software-run observations and build diagnostics. **Nothing here is independent
acceptance**, and no file in this directory grants coverage: independent
disposition belongs to Verification.

## Provenance

| Input | Exact value |
|---|---|
| Product main at pickup | `40507bf` (parent `d9bc6ebd10983711acade6d148895e78fd1a17e3`, the SHA named by the issue) |
| Issue | #41, label `software-lead`, updated `2026-09-12T05:27:09Z` |
| Verifier package source | `mmsanders/digital-tape-verification` commit `a91138667673fcf19dc9e83c9034322b982b1771`, path `tests/ops_draft8/` |
| Verifier package tree | `c8a43df69a6be8e2c34bf79a1d79933abf48286a` (matches the tree the issue specifies) |
| Held engine input | PR #20 head `2e0e8a4b7bff42797ac37901196e5ea348b2e392` |
| TapeFS / Engine API / Acceptance | `3bffa0ec…47cbb` / `537eadc4…7e3a1` / `7f78fba7…56bbb`, gate green |
| Toolchain | `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`; Python 3.11.15 |
| Build state | clean checkouts; the held engine was built from a pristine `git archive` extraction of `2e0e8a4b`, never from a dirty tree |

## Files

| File | What it is |
|---|---|
| `ops-selftest-synthetic.log` | Verifier oracle self-test + synthetic runner, reproduced. **SYNTHETIC**: no engine executed. Byte-identical to the package's own `evidence/selftest.log`. |
| `synthetic-runner.jsonl` | Raw synthetic runner log, 2/2 PASS against the verifier's `_synthetic_adapter.py`. Runner plumbing evidence only. |
| `pr20-link-diagnostic.log` | The one diagnostic build attempt against held #20: compile stage, link stage, enumerated undefined symbols, and the public symbols #20 actually defines. |
| `mount-split-289.jsonl` | The 289 landed mount cases re-run against a four-object split archive built from `2e0e8a4b` (`crc32.o mount.o tapefs.o alloc.o`), seed `0xd8a607`, 0 failed. Dependency evidence for the split matrix, **not** a new acceptance. |

## Missing media, stated plainly

There are **no VO08 input/output envelopes in this packet**, because the
diagnostic build never produced a linkable adapter executable, so the runner was
never able to invoke one and no media was ever written. The evidence wrapper
(`tests/ops_adapter/preserve.sh`) exists and is ready to capture both envelopes
on the first run that links; it has not yet preserved anything. This is an
absent run, not a lost artifact.

## Reproduce

```sh
# verifier package self-test and synthetic runner (no engine)
python3 tests/ops_draft8/selftest.py
python3 tests/ops_draft8/runner.py --adapter tests/ops_draft8/_synthetic_adapter.py \
        --log /tmp/vt8-synthetic.jsonl

# held-engine diagnostic (expected: compile clean, link fails on six symbols)
git archive 2e0e8a4b7bff42797ac37901196e5ea348b2e392 | tar -x -C /tmp/pr20
make -C /tmp/pr20/engine all
make -C tests/ops_adapter compile ENGINE_INC=/tmp/pr20/engine/include
make -C tests/ops_adapter        ENGINE_INC=/tmp/pr20/engine/include \
     ENGINE_LIB=/tmp/pr20/build/engine/libtape.a

# split dependency experiment
cc -std=c99 -Wall -Wextra -Werror -pedantic -I/tmp/pr20/engine/include \
   -DTAPE_PUBLIC_HEADER='"tape.h"' tests/mount_draft8/mount_probe.c \
   /tmp/pr20/build/engine/src/{crc32,mount,tapefs}.o -o /tmp/noalloc   # fails: tape_chunks_for_frames
```
