# P1-R5-SW return — Software Lead

**Issue:** [#59](https://github.com/mmsanders/Digital-Tape/issues/59) (`software-lead`, updated `2026-09-12T22:59:15Z`).
**Returned:** 12 September 2026 UTC. **Next owner:** PM. Verification receives any product observation only through a fresh separate issue — and there is none to send.

Mechanical test integration, adapter plumbing and diagnostic execution only. No engine
operation implemented, no stub added, no verifier assertion/fixture/PCM touched, no
golden accepted, no engine merged.

## Inputs

| Input | Value |
|---|---|
| Product input named by the issue | `b7f92dbb5ef4e59d9dd4ae268937ebbac31225ca` |
| Product main worked against | `fd2b73f` — `b7f92dbb` is its ancestor; the two commits since are PM-only docs, left untouched |
| Verifier publication | `7a22cbb4447c40c51b7c8b2282a685ed30a46ba6` |
| Corrected source / tree | `d565403907ecea331a5dcf63efbd1c08d8bd732e` / `aaa6dde86c9a0bdffa2b375361049ac670e26467` |
| Published subtree | `ff810814dbc8079c6903e6f85ed7ee312abd3076` |
| Held comparison | PR #20 head `2e0e8a4b7bff42797ac37901196e5ea348b2e392` |
| Raw evidence | [`docs/verification/runs/2026-09-12-r5/`](../../verification/runs/2026-09-12-r5/README.md) |

## 1. Import — exact, with retained evidence intact

`tests/playback_draft8/` imported from the publication with `git archive`, so no byte
or mode passed through a copy. **The product subtree hash reproduces
`ff810814dbc8079c6903e6f85ed7ee312abd3076`**, and a full three-column comparison of
mode + blob + path against the verifier tree is identical for all **57 files**. Six
executables preserved: `_synthetic_adapter.py`, `generate_fixture.py`, `oracle.py`,
`replay.py`, `runner.py`, `selftest.py`.

I imported from the **publication** `7a22cbb…`, not the corrected source `d565403…`,
because the two differ: the publication adds the 18-file
`evidence/p1-r4-synthetic/` bundle on top of the corrected source tree
`aaa6dde8…`. Importing the source tree would have silently omitted the retained
synthetic evidence the assignment says not to omit. Both named hashes were
authenticated before import; nothing inside the subtree was edited.

## 2. Reproduced — all synthetic

| Check | Result |
|---|---|
| `generate_fixture.py` | **PASS** — checked-in fixture and all three candidate PCM files equal deterministic regeneration; raw VO08 `c2ef07b3…`, 3,146,248 bytes |
| `selftest.py` | **PASS** — 3 families + **18 controls**: seek/boundary/grid mutations, callback I/O during render, wrong seek target, altered fixture and PCM bytes, tampered spec, manifest-only kind relabel, manifest-only ID mismatch, missing source/build provenance, missing/tampered evidence, tampered verifier identity, missing/nonzero/timed-out adapter exit, nonempty-destination rejection with bytes retained |
| `replay.py evidence/p1-r4-synthetic` | **REPLAY PASS**, all three families |
| `replay.py evidence/p1-r2-synthetic` | **REPLAY FAIL: wrong evidence schema** — correct: the v1 bundle is historical and must not be silently upgraded to v2 |
| `make -C tests/mount_draft8 check` | 10/10 |
| `tests/ops_draft8/selftest.py` | PASS, 2 + 12 controls |
| `tools/ci/verify-spec-bundle.sh` | green, frozen hashes unchanged |
| `tools/ci/all.sh` | build, allocation, indirect funnel, stack, memory, **meta-gate 15/15**, scaffolding — green |
| `tools/ci/run-golden.sh` | **RED** on `no tests/golden/MANIFEST` — expected WP-11, left visible |

The verifier package was not modified. **Every PASS above is synthetic plumbing.**

## 3. Product adapter

`tests/playback_adapter/` — outside the verifier subtree. Public API only, through the
real `tape.h` via `-DTAPE_PUBLIC_HEADER`; caller-owned storage; the three scripted
families exactly as `ADAPTER.md` specifies, including `tape_service` at the oracle's
required budget of **1024** driven to `more_work == false` under a finite guard.

Identity is hard-coded, not per-run: `kind = product`,
`id = software-lead-playback-public-api-probe-v1`. Runner and replay both bind
manifest identity to observation identity, so synthetic and product evidence cannot be
relabelled into one another.

Two deliberate choices worth recording:

- **SHA-256 is implemented inside the probe** rather than delegated to a script
  wrapper. The schema requires the observation to bind `fixture_sha256`; doing it in
  the same binary means one process both performs the engine calls and computes the
  hash, with no intermediate step that could assemble an observation the engine never
  produced.
- **Write and flush callbacks are recorded and then refused.** Playback is read-only,
  so if an engine ever attempts one, that is evidence — not something to absorb. Every
  callback is recorded in order with its real `rc`, unfiltered, including
  out-of-range requests, which are range-checked with widened arithmetic.

## 4. Diagnostic against the engines that exist — clean failure

| Target | Compile | Link |
|---|---|---|
| Current product main (`fd2b73f`) | **fails** | not reached |
| Held PR #20 (`2e0e8a4b`) | **clean** | **fails** |

Against #20 the link fails on exactly four declared-but-undefined public symbols, and
**neither** archive defines any of them:

```
  tape_seek:     main=0  pr20=0     (0 = undefined)
  tape_set_rate: main=0  pr20=0
  tape_render:   main=0  pr20=0
  tape_service:  main=0  pr20=0
```

Against current main the adapter does not compile at all: main's header still declares
`tape_mount(tape*, tape_side, uint64_t, const void*, size_t)` where frozen DRAFT-8 has
`const tape_warm_start *warm`. This is the same pre-DRAFT-8 header debt recorded in
P1-R1/P1-R2 and left alone under PM decision 3.

No stub, fake or uncovered implementation was added to obtain a run. Per item 4 this
clean failure **is** the valid diagnostic return.

While fixing my own adapter I hit and corrected a defect of mine, not the engine's:
compressed `if` statements tripped `-Wmisleading-indentation` under `-Werror`. Noted so
the compile diagnostics above are attributable purely to the header divergence.

## 5. Product evidence — none, and that is the honest state

Item 5 is conditional on a run being obtainable without implementation changes. It is
not. The runner was never invoked, **no v2 evidence directory exists**, and there is no
product VO08/PCM/observation/exit/manifest bundle. An absent run, not withheld
evidence.

Consequence: **the product adapter's observation schema has never been exercised
against a real engine.** It was written against the imported `ADAPTER.md` and
`oracle.py` by reading. The first product run is where it is actually tested, and a
reasonable place to expect schema mismatches.

No PCM was compared by listening and no PCM is called accepted. The
`tests/playback_draft8/golden/` files are verifier-derived candidate oracle bytes, not
frozen WP-11 goldens.

## 6. Dependency and split map — proposal only

### Which public symbols prevent the first run

Four, all required by all three families, defined nowhere:
`tape_seek`, `tape_set_rate`, `tape_render`, `tape_service`.

Ranked by what unblocks the most: `tape_service` and `tape_render` are needed by
**every** family; `tape_set_rate` by every family; `tape_seek` by `seek_boundaries` and
`reverse_neg1x`. There is no subset that yields a partial run — the link is
all-or-nothing, so no family can be observed until all four exist.

A fifth, distinct blocker applies to main only: the `tape_mount` signature. That is a
header-compatibility blocker, not a missing operation, and no header-only change is
proposed here.

### Which existing files mix covered playback behaviour with uncovered behaviour

**None mix implementation**, because no playback implementation exists anywhere:
`grep` over `engine/`, `firmware/`, `host/` and `tests/harness/` finds these four
symbols only in headers and a device-level test. That is unusually clean — the split
problem here is state, not code:

| Location | Playback-relevant content | Status |
|---|---|---|
| `engine/src/tape_internal.h` (`struct tape`) | `play_ring`/`play_ring_len`, `position_frame`, `rate_q16_16`, and on #20 additionally `at_end`/`at_start`, `play_ring_valid` | Derived at mount, consumed only by the unimplemented operations. Lands with any mount split, unobserved. |
| `engine/src/mount.c` | sets `position_frame` from `resume_frame`, clears `at_end`/`at_start`, validates both indices | Covered for mount by the 289-case tranche; its playback-facing outputs are not observable through `tape_info` |
| `engine/src/tapefs.c` | index/entry parsing that defines the physical run layout the timeline is read from | Covered for mount; the timeline-to-physical mapping playback needs is not separately observed |
| `engine/include/tape.h` (#20) | declares all four operations | Declarations only — calling one is a link error, which is the intended loud failure |

### Smallest future implementation slice, reviewable only after this package is on main

A single `engine/src/play.c` (plus the minimum `struct tape` additions) implementing
exactly: `tape_set_rate` restricted to ±65536; `tape_seek` with §6.3 fetch-before-advance
positioning on the 32.32 grid including reverse-from-end snap-to-last-frame;
`tape_service` filling the caller's play ring from the live Side-A index at a block
budget, reporting `more_work` by count; and `tape_render` emitting frames with §8's
portable signed-floor interpolation, grid-aligned at integral ±1.0×.

Bounded by what this package actually observes, that slice **excludes** rate ramps,
non-integral rates, zero/one-frame and extreme-rate boundaries, `tape_set_side`, warm
descriptors, recording, crash/recovery, long operations and the state matrix — all
explicitly excluded by `COVERAGE.md` and none of them licensed by these three families.

**This is a proposal, not merge authority.** It is reviewable only after this exact
package is on main, and even then a green product run is raw observation for
Verification, not acceptance.

## Residual holds

PR #20 draft and held; no wholesale engine merge; no public-header-only upgrade; no
test weakening, fixture or golden rewrite; no synthetic-to-product relabel; no
destructive evidence overwrite; no human-listening claim; no WP-08/WP-11 acceptance;
frozen DRAFT-8 hashes unchanged; WP-11 golden CI red and visible; VT8-001 allocator and
all-slot running-sequence still unobserved; hardware fabrication/charging CLOSED and no
card or purchase work. Independent Verification owns oracle expectations and disposition.
