# P1-R9-SW return — corrected package import, and the unchanged candidate rerun

Issue [#70](https://github.com/mmsanders/Digital-Tape/issues/70) under PM round
[#69](https://github.com/mmsanders/Digital-Tape/issues/69), authenticated by the
[P1-R9 PM disposition](../P1-R9-PM-DISPOSITION.md).

**Status: Ready for PM review.** Phase A is merged. Phase B ran the **existing,
unchanged** candidate against the corrected independent package and **passed
every family byte-exactly**, and the bundle replays from the repository. This is
not acceptance: independent Verification dispositions the bundle, PM routes it,
and a green run accepts no package, PCM, golden or listening step.

## The candidate implementation was unchanged in this assignment

Stated plainly because it is the point of the round: **no engine, firmware or
public-behaviour change was made in P1-R9.** `engine/src/play.c` hashes
`d2a904d4f4b15595094d18f52ef3b4aeea30ce11320c2561e09b6ac82a7a49f1`, byte-identical
to the P1-R7 round that failed against the pre-correction package. `git diff
bc53076 5f44b97 -- engine firmware tests/playback_adapter tests/harness` is
empty. The delta between the failing run and this passing one is entirely inside
the verifier package.

## Identity

| Item | Value |
|---|---|
| Input product main (issue #70) | `d208614dc11eee9935f1575c0a545cc8714def6b` |
| **Phase-A PR / merge commit** | **[#71](https://github.com/mmsanders/Digital-Tape/pull/71) / `d52730ffb4c9d8e634eded9caca208dcacb0d046`** |
| Phase-A branch head | `42719e4eee76dea5d991a0bafddd745079441812` |
| Imported package tree (on main) | `6dbb23bb4626238b0f22427031a551d2ece454fd` |
| Retained P1-R8 synthetic evidence tree | `d867fc68c80a2217508868c4b339d160b55ec2cc` |
| Retained P1-R6 synthetic evidence tree | `c67ea8fa128e06393839f968ae3cc949d84e5f2a` |
| Preserved earlier playback subtree | `ff810814dbc8079c6903e6f85ed7ee312abd3076` |
| Verifier publication | `mmsanders/digital-tape-verification@62b18deb8b4fbe6e797b00d792ee9f46ac0a8059` |
| Corrected pre-evidence source commit / tree | `1c1489a5b1c10f2baa8425557fd7bdfde3225575` / `43ca6f6bbc1990d5ced6de3b2ce0d04f00aa7519` |
| **Phase-B pre-run code commit** | **`5f44b97fe9fb3342fce3b58236a75ea27b4898a6`** |
| PR #64 head before this round | `bc53076448112ec3015de40e71c229e17d225c2f` |
| Held ancestor (PR #20 head) | `2e0e8a4b7bff42797ac37901196e5ea348b2e392` — verified still an ancestor |
| `engine/src/play.c` sha256 | `d2a904d4f4b15595094d18f52ef3b4aeea30ce11320c2561e09b6ac82a7a49f1` |
| libtape.a sha256 (as linked) | `403d736290035909792c053ba10c0e2ca67a3d06e40d80a3064eb5b5286edf91` |
| Adapter source / wrapper sha256 | `2349aa3a28fd3ce9821794c93143ccec85a8186e94b9fd2cd332d68267073b89` / `ebe108d0b960b389374b57848d14771af31d6154eadb2cb2049c1affe236051b` |
| Adapter binary sha256 | `a566f3f891bb0451cf53b3a2b3d57410c55a24b6b584cebdc40d2f3cfb1abe22` |
| Compiler | cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 |
| Immutable evidence | `docs/verification/runs/2026-09-13-r9/product-evidence/` |

One build identity, repeated without variation in the manifest's `adapter.build`,
the packet README and this return. `ar rcs` embeds member mtimes, so the archive
hash identifies this build while the engine source is pinned by the commit and by
the `play.c` hash.

## Phase A — exact test-first replacement

Fresh branch from the exact input main, then `tests/playback_complete_draft8/`
replaced **by tree object** (`git read-tree --prefix=…` from the fetched
publication) rather than by copying files, so path, mode and byte identity is a
hash fact rather than an inspection claim. The product tree equals
`6dbb23bb4626238b0f22427031a551d2ece454fd`. The **publication** was imported, not
only the pre-evidence source tree, so the retained P1-R8 evidence is present and
replays.

Nothing outside the verifier subtree changed at all — no adapter or CI adjustment
turned out to be needed, so the question of whether one would have been
"strictly mechanical" never arose. Nothing inside the subtree was edited. The
engine/firmware delta against input main is empty, and remains empty on merged
main.

| Check | Result |
|---|---|
| deterministic generation | PASS; reverse candidate `5f1794e8dcd7c1b3e2c390a1aef33039f5b88b20f682c56c4aa6f94051bd8fa1`, all four fixtures and forward scrub unchanged |
| corrected package self-test | PASS — 10 families, 20 behavioral controls including the F-1/F-2/F-3 negatives, retained 18-control P1-R4 suite |
| saved P1-R8 replay | `REPLAY PASS` |
| earlier three-family package self-test | PASS |
| mount package self-test | PASS |
| VT8-001 package self-test | PASS — 2 conforming + 12 oracle controls |
| frozen spec bundle | OK on all three DRAFT-8 hashes |
| dashboard behaviour | PASS |
| guardrail gates | allocation clean; `dev.h` funnel clean; stack 1,536 / 8,192; RAM and `.rodata` within budget |
| meta-gate | 15/15 — every gate still demonstrably goes red |
| scaffolding suite | PASS |
| Actions on `42719e4` | all green except `golden suite (awaiting WP-11 fixtures)`, which stays **red and unrequired** |

Merged with an empty engine/firmware delta. That merge accepts no package,
engine behaviour, PCM or golden.

## Phase B — rerun, not rework

Merged the new main into the PR #64 branch with `--no-ff` and no rebase, squash
or force-push; both held histories are intact and PR #20's head is still an
ancestor. That merge commit, `5f44b97`, is the pre-run code commit: imported
package plus unchanged code under test, created before the run. Engine, adapter
and probe were built from a clean `git archive` of it.

```
PASS P1-R8 corrected playback evidence
REPLAY PASS docs/verification/runs/2026-09-13-r9/product-evidence
```

| Family | Frames | PCM |
|---|---:|---|
| `empty_zero`, `empty_nonzero`, `nonempty_zero` | — | no PCM; call/state assertions hold |
| `one_intmax` | 1 | byte-exact |
| `reverse_zero` | 1 | byte-exact |
| `intmin` | 2 | byte-exact |
| `scrub_forward` | 88,200 | byte-exact |
| `scrub_reverse` | 88,200 | byte-exact |
| `side_playing` | 2 | byte-exact |
| `side_idle` | 1 | byte-exact |

Adapter exit `0`, empty stderr, `outcome: exited`. `adapter.kind` is `product` in
both manifest and observation, and replay enforces the equality. The run retains
the full raw input package copy, all seven PCM outputs, the observation with
every unfiltered callback and public-call record, exit/stdout/stderr,
`result.json`, `manifest.json`, and replays offline from the committed bytes.

The three P1-R8 findings close with no engine change: F-1 `intmin` renders 2
frames (`frame(1)` then `frame(0)`); F-2 the reverse scrub candidate is now the
§6.3 grid snap the engine already produced; F-3 the side families expect
`TAPE_ERR_UNDERRUN = 18`, which the engine already returned.

## Commands

Build, run and replay commands are in
`docs/verification/runs/2026-09-13-r9/README.md`, including in-place replay of
the committed bundle.

## Exclusions

No acceptance of anything. No WP-11 golden and no human listening; candidate PCM
is verifier-derived and remains unlistened. No recording, crash/recovery,
warm-start descriptor negatives, long-operation or state-matrix work,
performance, hardware or card qualification. `tape_status` reports
`recording_armed` and `frames_owed` false because §7 recording is not implemented
in this candidate. VT8-001 allocator/running-sequence and the warm-start,
state and operation exclusions remain uncovered.

## Holds observed

PR #20 and PR #64 remain draft and held, and PR #64 was not merged. No
implementation merge, no behaviour change, no verifier-subtree edit, no fixture,
assertion or oracle change, no scratch oracle this round, no test weakening, no
synthetic relabel, no frozen-spec edit, no candidate/golden/listening acceptance,
no card purchase or qualification, no fabrication or charging, no
repository-setting change. Prior bundles `2026-09-13-r6/` and `2026-09-13-r7/`
are untouched. The WP-11 missing-golden failure stays visible and unrequired. The
final PR #64 head for this round is recorded in the issue #70 return comment.
