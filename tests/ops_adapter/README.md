# VT8-001 mechanical adapter — Software-owned, diagnostic only

This directory is **not** product code and **not** verifier code. It holds the
mechanical adapter required by
[`tests/ops_draft8/ADAPTER.md`](../ops_draft8/ADAPTER.md), which is
Verification-owned and imported byte-for-byte. Keeping the adapter here keeps it
out of the verifier oracle's directory, as PM directed.

| File | Role |
|---|---|
| `vt8_ops_probe.c` | Drives the two scripted VT8-001 case sequences through the **public** API and emits one `VT8-OPS-OBSERVATION-1` object: ordered public-call results plus the harness-owned block-callback trace. |
| `Makefile` | Selects which candidate engine to link (`ENGINE_INC`, `ENGINE_LIB`). `compile` stops after `-c` so a compile gap and a link gap stay separable facts. |

## What the adapter may and may not do

It calls only public functions declared in the real product `tape.h`, supplied
mechanically through `-DTAPE_PUBLIC_HEADER` and `-I<engine>/include`. It observes
no engine internals, reads no allocator counter or private index structure, and
adds no product API. All storage is caller-owned. The 128-frame sample values are
deterministic and arbitrary: this tranche does not compare PCM.

`adapter_kind` is hard-coded `product`; the verifier's own stand-in reports
`synthetic`, and the runner rejects a mismatch against its `--adapter-kind`.

Every callback is recorded in call order — **including unexpected callbacks and
nonzero returns**. Observations are never filtered to make a verdict pass; a
nonzero callback return is evidence that fails these conforming cases. Batches are
range-checked with widened 64-bit arithmetic before any copy, and the audio region
is a genuinely sparse block map, so unmapped audio reads stay deterministic poison.
`tape_service` runs at a fixed positive block budget under a finite guard
(`SERVICE_GUARD`); nontermination fails the case rather than hanging.

`tape_instance_size` and `tape_init` are harness setup, not script steps: the
contract's call sequence starts at `tape_mount`, so they are not recorded as calls.
The phase before the first public call is deliberately named `init`, which is
outside the contract's allowed phase set — so block I/O during `tape_init` surfaces
as a schema violation instead of being quietly attributed to the mount that follows.

Anything that would change a fixture, an expected sequence, an operation argument,
an accepted result, a callback classification, an ordering or a range is **not** a
permitted integration edit and goes back to Verification/PM.

## Evidence retention is the runner's job

The hardened `runner.py` retains the input and final VO08 media (gzipped and
hash-bound), stdout, stderr, the observation, a per-case result and a manifest,
and `replay.py` recomputes every verdict offline from that bundle. The external
`preserve.sh` wrapper this directory used to carry was for the older runner, which
deleted its temporary media; it is obsolete and has been removed.

## Current status: no engine can link this

Against held PR #20 (`2e0e8a4b7bff42797ac37901196e5ea348b2e392`) the adapter
**compiles clean** and then fails to link on exactly six public symbols that the
header declares but no translation unit defines: `tape_seek`, `tape_arm`,
`tape_feed`, `tape_service`, `tape_commit`, `tape_reset_side_b`. That is the loud
failure #20's own header documents as intended, and it is an integration finding,
not something to patch here.

Against **current main** the adapter does not compile, because main's public header
is older than the frozen DRAFT-8 API. Main is not a valid target for this adapter.

**Because no engine links, the observation schema below has never been exercised
against a real engine.** It is written against `ADAPTER.md` and `hardened.py` by
reading, and only the verifier's synthetic path currently exercises the oracle.
The first product run is where that schema is actually tested.

## Usage once an engine defines the operations

```sh
make ENGINE_INC=<engine>/include ENGINE_LIB=<build>/libtape.a

python3 ../ops_draft8/runner.py \
  --adapter "$PWD/build/vt8_ops_probe" --adapter-kind product \
  --evidence-dir <evidence-dir> \
  --adapter-source '<commit/tree/blob of vt8_ops_probe.c>' \
  --adapter-build  '<compiler, flags, engine archive identity>' \
  --verifier-source '<verifier commit and ops_draft8 tree>'

python3 ../ops_draft8/replay.py <evidence-dir>
```

A green run is raw observation for Verification to disposition. It is not
acceptance, and it covers only the two VT8-001 case IDs.
