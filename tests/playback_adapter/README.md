# DRAFT-8 playback adapter — Software-owned, diagnostic only

Not product code and not verifier code. This is the mechanical adapter required by
[`tests/playback_draft8/ADAPTER.md`](../playback_draft8/ADAPTER.md), which is
Verification-owned and imported byte-for-byte. It lives outside that subtree so the
verifier package stays unmodified.

| File | Role |
|---|---|
| `playback_probe.c` | Drives the three scripted playback families through the **public** DRAFT-8 API and emits `observation.json` plus the three PCM files. |
| `Makefile` | Selects which candidate engine to link (`ENGINE_INC`, `ENGINE_LIB`). `compile` stops after `-c` so a compile gap and a link gap stay separable facts. |

## Design notes

It calls only public functions declared in the real product `tape.h`, supplied
mechanically via `-DTAPE_PUBLIC_HEADER` and `-I<engine>/include`. No engine
internals are observed, no product API is added, and all storage is caller-owned.

`adapter.kind` is hard-coded `product` and `adapter.id` is fixed; the runner and
`replay.py` both bind manifest identity to observation identity, so synthetic and
product evidence cannot be relabelled into one another.

**SHA-256 is implemented in this binary** rather than delegated to a script
wrapper. The contract requires the observation to bind `fixture_sha256`, and doing
it here means one process both performs the engine calls and computes the hash —
there is no intermediate step that could assemble an observation the engine never
produced.

Every block callback is recorded in order with its real `rc`, **unfiltered**,
including out-of-range requests. Reads are range-checked with widened arithmetic.
Playback is read-only, so `write` and `flush` callbacks are recorded and then
**refused**: if the engine ever attempts one during playback that is evidence, not
something to absorb silently. `tape_service` is driven at the oracle's required
budget of 1024 under a finite guard; nontermination fails rather than hangs.

## Current status: no engine implements playback

| Target | Compile | Link |
|---|---|---|
| Current product main | **fails** — main's public header predates the frozen DRAFT-8 API (`tape_mount` still takes `const void*, size_t` instead of `const tape_warm_start*`) | not reached |
| Held PR #20 `2e0e8a4b` | **clean** | **fails** — `tape_seek`, `tape_set_rate`, `tape_render`, `tape_service` are declared but defined nowhere |

Neither archive defines a single playback operation, so **no product playback
evidence can exist yet**, and none is claimed. Raw log:
[`docs/verification/runs/2026-09-12-r5/adapter-diagnostic.log`](../../docs/verification/runs/2026-09-12-r5/adapter-diagnostic.log).

Because no run is possible, this adapter's observation schema has **never been
exercised against a real engine**. It is written against the imported `ADAPTER.md`
and `oracle.py` by reading; the first product run is where it is actually tested.

## Usage once an engine implements playback

```sh
make ENGINE_INC=<engine>/include ENGINE_LIB=<build>/libtape.a

python3 ../playback_draft8/runner.py \
  --adapter-cmd "$PWD/build/playback_probe" \
  --adapter-kind product \
  --adapter-id software-lead-playback-public-api-probe-v1 \
  --adapter-source playback_probe.c \
  --adapter-build "<compiler, flags, engine archive identity>" \
  --source-commit <verifier commit> --source-tree <verifier tree> \
  --evidence-dir <fresh-or-empty-dir>

python3 ../playback_draft8/replay.py <evidence-dir>
```

A green run is raw observation for Verification to disposition. It is not
acceptance, the candidate PCM is not an accepted WP-11 golden, and nothing here
constitutes human listening.

## Second package: the P1-R6 complete tranche

`complete_probe.c` is the adapter for
[`tests/playback_complete_draft8`](../playback_complete_draft8/ADAPTER.md) and
schema `playback-complete-draft8-observation-v1`: ten families, seven PCM
outputs, invoked as `--fixture-dir DIR --out-dir DIR`.

`complete_adapter.sh` is a decompressing front-end. The package ships its
fixtures gzipped and the runner passes its own `fixtures/` directory straight
through, so something must inflate them; the wrapper builds a private temp tree
shaped like the package and does only that. **It is not trusted:** the probe
re-hashes every raw image against `fixture.json`'s own `raw_sha256` and refuses
on mismatch, so the wrapper cannot substitute fixture bytes, and it never touches
`observation.json` or any PCM. The probe stays the only producer of observations.

The WP-08 identity in the observation is **computed** from the package's own
`input/WP-08.md`, not hard-coded here, so a changed table is caught by the oracle
rather than papered over by a constant in my adapter.

**The play ring is deliberately larger than `TAPE_PLAY_RING_MIN`.** That constant
is a minimum and the caller owns the buffer (§4). A scrub row renders up to 22,050
frames after a single service sequence, and at 12.0× that spans 264,600 timeline
frames — far past 372 ms of ring — so this desktop harness supplies 8 MiB.
Firmware with a smaller ring simply services more often, which is the documented
interleaving case and yields identical bytes.

Build it separately, because it needs `tape_status`:

```sh
make complete ENGINE_INC=<engine>/include ENGINE_LIB=<build>/libtape.a
```
