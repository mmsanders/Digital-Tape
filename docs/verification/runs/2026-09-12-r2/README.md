# P1-R2-SW raw evidence packet — 12 September 2026 UTC

Produced by the **Software Lead** working
[issue #50](https://github.com/mmsanders/Digital-Tape/issues/50). Raw
software-run observations and build diagnostics. **Nothing here is independent
acceptance.** Independent disposition belongs to Verification.

## Provenance

| Input | Exact value |
|---|---|
| Product main at pickup | `7fe9942a847c6decfa40ea75aa08d16ea730bb39` (the SHA the issue names) |
| Hardware merge landed first | PR #47 merged as `8d9e8bd`, head `ebde2f9` |
| Hardened verifier source | `mmsanders/digital-tape-verification` `dcc4d7cdb357cf0b082071390c762c25b650f617` |
| Hardened `tests/ops_draft8` tree | `4a862fa69ccb2fc4c9afe59c9c9161c3470f9263` — matches the issue exactly |
| Superseded baseline tree | `c8a43df69a6be8e2c34bf79a1d79933abf48286a`, provenance only |
| Held engine input | PR #20 head `2e0e8a4b7bff42797ac37901196e5ea348b2e392` |
| DRAFT-8 hashes | unchanged; bundle gate green |
| Toolchain | `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`; Python 3.11.15 |

## Files

| Path | What it is |
|---|---|
| `synthetic-evidence/` | A complete hash-bound evidence bundle produced by the hardened `runner.py` against the verifier's **synthetic** stand-in adapter: manifest, run log, authenticated DRAFT-8 spec copies, and per-case input/output VO08 (gzipped), stdout, stderr, observation and result. 2/2 PASS. |
| `hardened-selftest.log` | The hardened package self-test: 2 conforming + 12 oracle controls + tampered-spec + missing-evidence + tampered-evidence replay controls. |
| `offline-replay.log` | `replay.py` recomputing every verdict offline from the bundle above, with no engine or adapter execution. |
| `pr20-link-diagnostic.log` | The revised adapter compiled and linked against held #20: compile clean, link fails on the same six undefined public operations. |

**`adapter_kind` in the bundle is `synthetic`.** No engine was built, linked or
executed for any PASS recorded here.

## Why there is still no product media

No engine defines `tape_seek`, `tape_arm`, `tape_feed`, `tape_service`,
`tape_commit` or `tape_reset_side_b`, so the product adapter cannot link, the
runner cannot invoke it, and no product VO08 media exists. The runner now retains
media automatically, so the first run that links will produce a real bundle without
any extra wrapper.

A consequence worth stating plainly: because no product run is possible, **the
product adapter's observation schema has never been exercised against a real
engine.** It was written against the imported `ADAPTER.md` and `hardened.py`.

## Reproduce

```sh
python3 tests/ops_draft8/selftest.py

python3 tests/ops_draft8/runner.py --adapter tests/ops_draft8/_synthetic_adapter.py \
        --adapter-kind synthetic --evidence-dir /tmp/vt8-evidence \
        --adapter-source '<verifier blob id>' --adapter-build 'python3, no compilation' \
        --verifier-source 'dcc4d7cdb357cf0b082071390c762c25b650f617 tree 4a862fa6...'
python3 tests/ops_draft8/replay.py /tmp/vt8-evidence

git archive 2e0e8a4b7bff42797ac37901196e5ea348b2e392 | tar -x -C /tmp/pr20
make -C /tmp/pr20/engine all
make -C tests/ops_adapter compile ENGINE_INC=/tmp/pr20/engine/include   # clean
make -C tests/ops_adapter        ENGINE_INC=/tmp/pr20/engine/include \
     ENGINE_LIB=/tmp/pr20/build/engine/libtape.a                        # six undefined symbols
```
