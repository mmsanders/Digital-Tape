# P1-R7-SW return — complete playback tranche: import, candidate, product evidence

Issue [#66](https://github.com/mmsanders/Digital-Tape/issues/66) under PM round
[#65](https://github.com/mmsanders/Digital-Tape/issues/65).

**Status: BLOCKED at item 7.** Phase A is merged. Phase B is implemented, built
and run from an immutable commit, and the complete ten-family product bundle
exists — but the package disagrees with the frozen DRAFT-8 contract in three
places, all reverse-direction. Item 7 says to stop Blocked with the exact case
rather than modify the verifier subtree or relax an oracle, so that is what this
return does. The engine was not changed to match the package; the package was
not changed to match the engine.

## Identity

| Item | Value |
|---|---|
| Input product main (issue #66) | `c497f21fc3ab71defd509bbb3eedc9413457e8e9` |
| Phase-A merge on main (PR #67) | `14a5931` |
| Complete verifier subtree on main | tree `863b3a49c421bda1bebcf1a9760149bec7051048` (reproduced; unedited) |
| Retained synthetic evidence subtree | tree `c67ea8fa128e06393839f968ae3cc949d84e5f2a` |
| Preserved first playback package | tree `ff810814dbc8079c6903e6f85ed7ee312abd3076` |
| Verifier publication | `mmsanders/digital-tape-verification@121f5f7ab03c9ce08c38329e518c49a1ca9b65a5` |
| Verifier source commit / tree | `54789cc6e6bbfd942857374e2e0b3305d05d2f2c` / `5527547b72b3e5c6d6fb91d41f3aa3bfa86fab7d` |
| PR #64 head before this round | `3dc5abb85e5b30200cf1553b9a06a83bc83c6d36` |
| Held ancestor (PR #20 head, unmodified) | `2e0e8a4b7bff42797ac37901196e5ea348b2e392` |
| **Phase-B tested-code commit** | **`43d2dbaa6434942df37e165b25edc6d45135fee2`** |
| `engine/src/play.c` sha256 | `d2a904d4f4b15595094d18f52ef3b4aeea30ce11320c2561e09b6ac82a7a49f1` |
| libtape.a sha256 (as linked) | `1a91c0eab8d8a6c5d486c2f3ec7622328178046db843f53da7f4332c29114458` |
| Adapter source sha256 (`complete_probe.c`) | `2349aa3a28fd3ce9821794c93143ccec85a8186e94b9fd2cd332d68267073b89` |
| Adapter wrapper sha256 (`complete_adapter.sh`) | `ebe108d0b960b389374b57848d14771af31d6154eadb2cb2049c1affe236051b` |
| Adapter binary sha256 | `f1606b844a836c495ca4873c3d1b820a7d6987d57973c107653928fb82bcb9a6` |
| Complete evidence | `docs/verification/runs/2026-09-13-r7/` |
| Superseded three-family evidence | `docs/verification/runs/2026-09-13-r6/` (immutable, not rewritten) |

The same libtape.a, adapter-source, adapter-binary and wrapper hashes appear in
the bundle manifest's `adapter.build` string, in the packet README and in this
table. That is item 8's single build identity; the earlier round's split
identity (`41eb993f...` in the packet against `fdacb6d2...` in the manifest,
with no implementation commit named) is not rewritten and is superseded here.

## Findings — the package against the frozen contract

All three are reverse-direction. In each the product engine transcribes the
frozen normative text, another already-landed independent package agrees with
the engine, and the newly published complete package expects the behaviour the
frozen text rejects by name.

### F-1 — `intmin` expects frame 0 to be dropped on rewind

`oracle.py` requires, for rate `INT32_MIN` after `tape_seek(1)` on the
1,100,000-frame fixture, `tape_render(requested=2) -> rendered 1` with one
output frame, `tape_tell = 0` and `at_start = true`.

Engine: `rendered = 2`, output `frame(1)` then `frame(0)`, `tape_tell = 0`,
`at_start = true`. Reaching that requires frame 0 to be emitted after the step
lands on it, which is what the frozen §6.2 says in its normative code:

> `else if (position <= s) position = 0;   /* land ON frame 0; it is emitted next pass */`

and in the note directly under it:

> **`at_start` is set only when the playhead was *already* at 0, never on the
> step that lands there.** DRAFT-6's first cut set it on the landing step, and
> because §6.3 tests the flag *before* emitting, **frame 0 was never rendered.**
> [...] the first frame of every tape silently dropped on every rewind, and
> `acceptance.md` WP-08's own reverse golden unachievable against the normative
> algorithm.

The oracle's expectation is exactly DRAFT-6's rejected first cut. It is not an
`INT32_MIN` special case either: the same expectation fails for `-1.0x` from
frame 1.

Corroboration from the landed, already-run package: `tests/playback_draft8`'s
`reverse_neg1x` family seeks to `total_frames`, plays at `-1.0x` and expects
**all 15 frames including frame 0** (`reversed(fr)` in its `expected_outputs`).
The product engine satisfies that family byte-exactly. The two independent
packages cannot both be right.

### F-2 — the reverse scrub candidate PCM is the DRAFT-5 off-grid snap

`generate_fixture.py`'s reference renderer starts the reverse case at
`pos = maxpos - 1`:

```python
if rates[0]<0 and pos>=maxpos: pos=maxpos-1
```

`candidate/scrub-reverse.pcm` is generated from that, and `oracle.py` compares
the product output against it. §6.3's snap rule is
`position = ((uint64_t)(total_frames - 1)) << 32`, and V5-005 addresses
`max_pos - 1` by name:

> DRAFT-5 snapped to `max_pos − 1`, which is the last frame with
> `f = 0xFFFFFFFF` — one fixed-point unit short of the grid. The first emitted
> sample was right, and **every sample after it was wrong.** [...] a golden
> fixture taken from DRAFT-5 would have **frozen the defect as the reference.**

Measured on this bundle, reproducing both formulations independently in Python
against the package's own fixture generator:

| Comparison | Result |
|---|---|
| `candidate/scrub-reverse.pcm` == render from `max_pos - 1` | **byte-equal** |
| `candidate/scrub-reverse.pcm` == render from `(total-1) << 32` | not equal |
| product `output/scrub-reverse.pcm` == render from `(total-1) << 32` | **byte-equal** |
| product output vs candidate | 88,199 of 88,200 frames differ; first difference at frame **1** |

Frame 0 agrees and every later frame differs, which is precisely the signature
V5-005 describes. `scrub_forward` — same generator, no snap involved — is
byte-exact against its candidate, so this is the snap alone and not a
disagreement about rates, interpolation, cadence or the table.

Corroboration from the landed package: `tests/playback_draft8/oracle.py` defines
`draft5_bad_reverse` with `pos=(len(fr)<<32)-1` and `selftest.py` uses it as a
**negative control the oracle must reject**. The complete package's candidate is
generated the way the earlier package's negative control is.

### F-3 — expected `tape_render` result code after `tape_set_side`

Both side families expect `tape_render(requested=1) -> result 6, rendered 0`
before the post-switch service. §5's table is satisfied — the ring is
invalidated and the render is short with `TAPE_ERR_UNDERRUN` — but in the frozen
§2 enum `TAPE_ERR_UNDERRUN` is **18**; **6** is `TAPE_ERR_GEOMETRY`. The engine
returns 18.

Corroboration: `tests/mount_draft8/candidate_api.h`, the other independent
package's own transcription of the same frozen enum, numbers
`TAPE_ERR_UNDERRUN` 18, and that package is green against this engine at
289/289.

### How much of the package the engine satisfies

With exactly those three expectations set aside in a scratch copy of the oracle
held **outside** the repository (`docs/verification/runs/2026-09-13-r7/isolation/`
records the diff and the verdict), the package passes: 1,625 checked calls, and
five byte-exact PCM families — `one_intmax`, `reverse_zero`, `scrub_forward`,
`side_playing`, `side_idle`. Every call-order, callback-legality, service
sequence, `tape_tell`/`tape_status`/`tape_get_info`, clamp and rate-retention
assertion holds. The disagreement is three points, not a broken candidate.

That isolation is a diagnostic. The real oracle ran unmodified, the retained
verdict is `FAIL` with `tape_render.rendered`, and it stays visible.

## Recommendation to PM, with a safe default

These are spec-versus-test disagreements, which §3.3 of the working agreement
makes a PM decision. My recommendation, on the evidence above, is that the
frozen contract stands in all three cases and the complete package needs a
corrected tranche from Verification:

* F-1: drop the landing-step `at_start` expectation; `intmin` should expect
  `rendered = 2` with `frame(1)`, `frame(0)`.
* F-2: regenerate `candidate/scrub-reverse.pcm` from the §6.3 grid snap. This is
  a golden-adjacent regeneration and needs logged PM approval per §3.5.
* F-3: expect 18 for `TAPE_ERR_UNDERRUN`.

**Safe default if PM prefers no change this round:** leave everything as it is.
The tranche stays unaccepted, the engine stays held, WP-11 stays open, and no
golden is frozen from a candidate that F-2 says encodes a rejected draft. The
risk of the alternative is concrete and one-directional: accepting F-2's
candidate as a WP-11 golden would freeze the DRAFT-5 off-grid reverse defect as
the product reference, and the frozen spec says so in as many words.

I am not asking to change the engine. If PM decides the package is right and the
frozen §6.2/§6.3/§2 text is wrong, that is a spec change and goes through the
freeze, not through me editing `play.c` to match a test.

## Phase A (merged)

Merged as PR #67 → `14a5931`, tests/adapter/CI only, empty engine/firmware
delta. The complete published subtree reproduces tree `863b3a49...` byte, mode
and path identical, including its retained synthetic evidence tree
`c67ea8fa...`; `tests/playback_draft8/` (`ff810814...`) is untouched. CI gained
`playback-complete-package`, which runs deterministic generation, the package
self-test, the saved synthetic replay and the compile-only adapter gate. The
WP-11 missing-golden job stays red and unrequired.

## Phase B (implemented, held)

`tape_status` (`engine/src/play.c`) and the `tape_set_side` playback-state reset
are the only public behaviour added, both covered by the landed package.
`recording_armed` and `frames_owed` are reported false because §7 recording is
not implemented in this candidate — no path arms, so that is the correct answer
for every state this engine can reach rather than a stub. No warm-descriptor
negatives, recording, crash/recovery, long-operation or state-matrix work was
added.

One adapter defect of my own was found by the first real run and is retained as
a diagnostic rather than discarded: `complete_probe.c`'s array JSON parser was
reused for a scalar key and returned the first element of the next array, so
`long_side_a_frames` read 262144 instead of 1100000 and two families ran at the
wrong positions. Fixed in `43d2dba` with a strict scalar parser plus a stdout
echo of the parsed fixture parameters, so the positions a run used are visible in
the evidence. Details and the per-row table are in
`docs/verification/runs/2026-09-13-r7/first-run-diagnostic/DIAGNOSIS.md`. The
engine's behaviour in that bundle was correct for the positions it was given.

## Commands

See `docs/verification/runs/2026-09-13-r7/README.md` for the exact build, run and
replay commands, including in-place replay of the committed bundle.

## Dependency map

| Waiting on | For |
|---|---|
| PM | F-1, F-2, F-3 arbitration; a corrected complete tranche from Verification, or a recorded decision that the frozen text changes |
| Independent Verification | disposition of this product bundle; it is not accepted by having been produced or by this issue closing |
| PM + Michael | WP-11 goldens: independent regeneration with logged approval (F-2) and then human listening |
| PM | PR #20 and PR #64 remain draft and held; no implementation merge this round |

## Holds observed

No verifier-subtree edit, no fixture/assertion/oracle change, no test weakening,
no synthetic relabel (`adapter.kind = product` in both manifest and observation,
and replay enforces the equality), no golden or listening acceptance, no
frozen-spec edit, no repository-setting change, no card/purchase/qualification or
hardware/fabrication/charging work, no rewrite of PR #20 or of PR #64's history,
and the expected WP-11 failure stays visible. The final PR #64 head for this
round is recorded in the issue #66 return comment.
