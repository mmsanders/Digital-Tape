# VT8-001 mechanical adapter — Software-owned, diagnostic only

This directory is **not** product code and **not** verifier code. It holds the
mechanical adapter required by
[`tests/ops_draft8/ADAPTER.md`](../ops_draft8/ADAPTER.md), which is
Verification-owned and imported byte-for-byte. Keeping the adapter here keeps it
out of the verifier oracle's directory, as PM directed.

| File | Role |
|---|---|
| `vt8_ops_probe.c` | Drives the two scripted VT8-001 case sequences through the **public** API and emits the harness-owned block-callback trace as JSON. |
| `Makefile` | Selects which candidate engine to link (`ENGINE_INC`, `ENGINE_LIB`). `compile` stops after `-c` so a compile gap and a link gap stay separable facts. |
| `preserve.sh` | External evidence wrapper. The verifier runner builds fixtures in a `TemporaryDirectory` and deletes them on exit; this copies both VO08 envelopes out before that happens. It does not touch the runner, the oracle, any fixture or any assertion. |

## What the adapter may and may not do

It calls only public functions declared in the real product `tape.h`, which is
supplied mechanically through `-DTAPE_PUBLIC_HEADER` and `-I<engine>/include`.
It observes no engine internals, reads no allocator counter or private index
structure, and adds no product API. All storage is caller-owned. The 128-frame
sample values are deterministic and arbitrary: this tranche does not compare PCM.

The audio region is a genuinely sparse block map — a chunk is backed only once
written — so unmapped audio reads stay deterministic poison, and every callback
batch is range-checked with widened arithmetic before any copy. `tape_service`
is driven under a finite guard (`SERVICE_GUARD`) and nontermination fails the
case rather than hanging.

Anything that would change a fixture, an expected sequence, an operation
argument, an accepted result or a callback classification is **not** a permitted
integration edit and goes back to Verification/PM.

## Current status: no engine can link this

Against held PR #20 (`2e0e8a4b7bff42797ac37901196e5ea348b2e392`) the adapter
**compiles clean** and then fails to link on exactly six public symbols that the
header declares but no translation unit defines: `tape_seek`, `tape_arm`,
`tape_feed`, `tape_service`, `tape_commit`, `tape_reset_side_b`. That is the
loud failure #20's own header documents as intended, and it is an integration
finding, not something to patch here. Raw log:
[`docs/verification/runs/2026-09-12/pr20-link-diagnostic.log`](../../docs/verification/runs/2026-09-12/pr20-link-diagnostic.log).

Against **current main** the adapter does not even compile, because main's public
header is older than the frozen DRAFT-8 API (see the return document for the
exact signature deltas). Main is not a valid target for this adapter.

## Usage once an engine defines the operations

```sh
make ENGINE_INC=<engine>/include ENGINE_LIB=<build>/libtape.a

VT8_PROBE="$PWD/build/vt8_ops_probe" \
VT8_PRESERVE_DIR=<evidence-dir> \
  python3 ../ops_draft8/runner.py --adapter "$PWD/preserve.sh" --log <evidence-dir>/product.jsonl
```

A green run is raw observation for Verification to disposition. It is not
acceptance, and it covers only the two VT8-001 case IDs.
