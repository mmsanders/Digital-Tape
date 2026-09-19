# P1-R21-SW — clean split for the two accepted VT8-001 observations

**Issue:** [#110](https://github.com/mmsanders/Digital-Tape/issues/110) ·
**Date:** 19 September 2026 UTC ·
**Both cases PASS. Offline replay PASSES.**

Raw observation, not acceptance. Nothing here accepts source, WP-07, the verifier
package, PCM or goldens, and nothing here makes any PR mergeable.

## Provenance

| Object | Identity |
|---|---|
| Product main (branch root) | `86a1ba0874812ef4ca052a4dbc6baad2b16addb6` |
| **Pre-run code commit** | `20505f4254b36c2100b9b1ec8f78aff8e95e252c`, tree `305525d207ba60750f45229838c20599fd6fc4be` |
| Candidate `engine/` tree | `65a72f78572223364c51e265fd68bffdda2b6518` |
| `tests/ops_adapter/` tree | `6f6df812ae346933dff91aebb739feb0e2f0a113` |
| `tests/ops_draft8/` tree | `3667a2830ba80dbcedad03b97870d1127001ab59` — untouched |
| Verifier acceptance | `e77b61fe420e48444cf0791c74fc7e296ef0ccf6` |
| Toolchain | `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`, `python3 3.11.15` |

**Clean ancestry.** Exactly one commit above main. Held heads `2e0e8a4b…` (#20),
`c18aa42…` (#64), `b26ffa02…` and `088226a3…` (#96) are **none of them ancestors**.
No held PR is modified or superseded.

## Results

| Case | Adapter outcome | Exit | Verdict | Errors |
|---|---|---|---|---|
| `VT8-001-RB-ALLSLOT` | `exited` | 0 | **PASS** | none |
| `VT8-001-REC-ALLOCSEQ` | `exited` | 0 | **PASS** | none |

`manifest.json` SHA-256 `e0af6d607d21579309ad97abcb89f69be6721e3d63c9226ee9af36799c565f44`
`run.jsonl` SHA-256 `e61a5ddfbb6bd3ead1400812fd683617ed1819936e6d80eacb7dcc3bb1bea03f`

Offline replay: **PASS** — complete, hash-bound, DRAFT-8 authenticated, verdicts
recomputed without invoking the engine or adapter.

Traces reproduce the accepted orderings exactly:

```
RB-ALLSLOT   reset_b write 265 ×1 | flush | write 264 ×1 | flush
             no superblock write, no chunk write

REC-ALLOCSEQ service write 5120 ×1 | flush | read 2048 ×1
             commit  write 393  ×1 | flush | write 392  ×1 | flush
             seek/arm/feed/unmount issue no block I/O; commit performs no read
```

## What is narrower than the held P1-R17 candidate

**§8 stage clearing and its §4.6 partner-first superblock writer are gone.** Both
accepted fixtures are `promote_stage == 0`, so neither case depends on them, and
this round excludes behaviour the two observations do not cover. **Nothing in this
split writes a superblock at all.** The stack gate counts 50 engine functions here
against 54 in the held candidate.

`tape_arm` and `tape_reset_side_b` therefore **refuse on stage-1 media with zero
writes** rather than commit an index onto media §8 forbids committing onto.

## Two invented refusals — PM's to dispose of, neither a spec claim

1. **`tape_arm` accepts `TAPE_REC_SPLICE` only.** `TAPE_REC_OVERWRITE` and
   `TAPE_REC_OVERDUB` get `TAPE_ERR_INVALID_ARG` and zero writes. §7 defines all
   three modes; this engine implements one.
2. **`promote_stage == 1` → `TAPE_ERR_BUSY`, zero writes**, from both `tape_arm`
   and `tape_reset_side_b`. §8 requires clearing, not refusing. `TAPE_ERR_BUSY` is
   the closest §2 code and is a narrowing, not the format's rule.

Nothing in this candidate can *set* `promote_stage`: `tape_promote`, `tape_format`
and `tape_dup` are all undefined. Stage-1 media can only arrive pre-existing.

## Branches that exist but are NOT exercised by the two observations

Written from spec because the enclosing function is unavoidable, run by nothing here:

- `splice_insert` interior-split and entry-boundary-insert rows (only the
  append-at-exact-end row runs);
- the partial-final-block path in the record drain (the case feeds exactly one
  full block);
- multi-chunk allocation in `tape_feed` (the case allocates one chunk);
- `TAPE_ERR_CARTRIDGE_FULL` short accept, and the §5.4 timeline-cap clamp;
- every §10 refusal — armed `seek`/`set_rate`/`set_side`/`unmount`/`arm`,
  unarmed `feed`/`commit`, `Playing` → `reset_b`, `TAPE_ERR_INDEX_FULL`,
  `TAPE_ERR_READ_ONLY`, `TAPE_ERR_SEQUENCE_EXHAUSTED`;
- every §7.2 fault path (no injected write or flush failure);
- the zero-accepted-frames commit no-op;
- the non-degraded-B `reset_b` destination (the accepted case is degraded-B).

## Exclusions — what this packet does NOT establish

Other arm modes; splice boundaries; partial or multi-chunk behaviour; short
accepts; I/O faults; warm start; `tape_abort`; zero-frame commit; crash injection
or recovery; FAULTED quarantine; promote, re-spool, duplicate or format; further
allocation cases; mount or playback expansion; performance; media atomicity; PCM;
goldens; listening; complete WP-07. No source, helper, package or format
acceptance. **The PR carrying this is held and must not be merged.**
