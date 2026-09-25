# R29 format/duplicate identity + duplicate long-operation binding contract

This directory is an independent verifier-owned package. A later Software round may bind the exact publication tree to the Digital-Tape public API, but must not change fixtures, planner order/count/digest, durability semantics, expected bytes, parser, or oracle.

The product adapter is mechanical only. It may report raw bytes, opaque operation identifiers, numeric counters, callback traces, block-device events, and direct public/API state observations. It must not report verifier conclusions.

oracle.py recursively rejects derived verdict fields such as operation-running/work-advanced/restart judgments; unchanged-rate/position/ring judgments; audio-continues or source-faulted judgments; state-changed/recursed judgments; same-function/nonterminal/terminal summary judgments; and decoded final-identity verdicts. Verification derives those properties itself from the concrete observations below.

## Blindness boundary

This package was authored from frozen DRAFT-8 specifications only. Product implementation must not be used to alter the verifier package. A later binding may inspect product implementation only after importing the publication tree byte-for-byte.

## Streaming protocol

Run one adapter process. Its initial JSON handshake must contain format FMTDUP-ID-ADAPTER-1, adapter_kind product, a stable adapter_id, caseset_sha256 c493e77dff948df48d9c67c51ef4b68f0a61d2e02615b2d08760a594e79dc4e3, and raw_observation_only true.

The verifier streams every canonical case and expects one FMTDUP-ID-OBSERVATION-1 object per case. Production has no sampling, case-count, torn-length, durability-mode, or scenario override. EOF, timeout, malformed JSON, case drift, or process failure is failure.

## Raw crash observations

For scope=crash, return the verifier case index, injection_fired=true, verifier-format pre_snapshot and post_snapshot, target_baseline from the clean execution, actual_remount_result from a fresh product instance initialized from durable bytes only, and actual_selected_uuid when that mount succeeds.

A raw snapshot contains exact hex for primary superblock, mirror superblock, A0 block-0 header, and B0 block-0 header, each 512 bytes. Do not replace those bytes with decoded claims. The verifier independently checks magic/CRC, primary/mirror selection, version/state admission, UUID, sb_generation, A0/B0 identity, and final sequence numbers.

### Clean target baseline

For every operation/shape prove these four one-block superblock targets and bytes: step-1 partner; step-1 candidate/other copy; final identity mirror; final identity primary.

Each baseline entry reports only phase, copy, LBA, and SHA-256 of the exact target block. An extra, missing, reordered, or byte-different target fails before remount outcomes are considered.

All non-superblock writes required to prepare new indices/audio happen between the step-1 pair and the final identity pair as DRAFT-8 specifies. They are not additional superblock crash targets in this tranche. Before final identity begins, final A0/B0 headers must already be durable.

## Dual working/durable device

Maintain independent working and durable byte images. Reads observe working bytes. A successful write updates working bytes. In write_through a successful write also updates durable bytes immediately. In flush_required a successful write is not durable until a successful flush. A successful flush copies all preceding working writes to durable bytes. A fresh remount after injection uses durable bytes only; discard working state and all engine state.

For every targeted 512-byte superblock write, run before-write with 0 bytes landed, every torn prefix 1 through 511, after-write with the complete 512 bytes landed before its following flush, and a fault/power cut at the following target flush.

A torn prefix is copied into both working and durable media and then the write fails. after_write is not a 512-byte torn write: in flush_required the completed block remains non-durable at that cut.

## Mandatory destination shapes

Use the raw bytes from fixture.py, not product helpers: healthy byte-identical pair; structurally-valid mirror only; CRC-correct generation 0; only valid copy has version_major=2; equal-generation divergent CRC-correct pair; generation-exhausted candidate plus lower-generation partner; generation-exhausted equal-generation divergent pair.

The first five exercise the ordinary WIP-template path. The last two exercise the zeroing fallback. Equal-divergent geometry/capacity refusals are separate contract cases and must show no destination-superblock read/write before refusal.

## Raw WP-12a observation vocabulary

An in-progress duplicate observation uses an opaque operation snapshot with operation_token, progress_blocks, and destination_event_count. The token is not a verdict. Verification compares it across probes/continuations to detect restart. Likewise, the counters are facts; Verification decides whether work did or did not advance.

Block-device traces contain chronological raw callback events. Reads/writes include LBA/count; callbacks include their raw return code where relevant.

## Duplicate in-progress 15-column row

Exercise all fifteen Engine API state-matrix columns against a duplicate already in progress: seek, set_rate, render, service, status/info/tell, arm, feed, commit, abort, set_side, reset_b, promote, respool, dup, unmount.

For every row provide the operation snapshot immediately before and immediately after the probe plus the exact probe call/result and its block-event trace.

For the eleven BUSY columns additionally provide an ordinary matching duplicate continuation after the probe, with raw before/after operation snapshots and its public return/more_work. Verification derives that BUSY did no media work, token/progress/event count did not change during BUSY, and the next duplicate call advances the same token rather than starting a new operation.

For matching dup, report the continuation result/more_work, block trace, and raw before/after operation snapshots. Verification derives that it advanced.

For render, report public result, rendered-frame count, raw output bytes, and block trace. The seeded fixture is non-silent. Verification derives that rendering remained usable and touched no media.

For service, report result and complete block trace. Verification verifies the duplicate operation token/progress itself did not advance through service.

For the grouped status/info/tell cell, report all three public calls/results, tell position, and the block trace.

## Zero budget

For initiation and continuation separately emit the operation snapshot before and after, with operation_token null for the pre-initiation state; the exact tape_dup call with block_budget=0; public result and more_work; and complete block trace.

Verification derives no state/work change and, for a continuation, survival of the existing operation.

## Continuation argument stability

Emit both initiating and attempted continuation values for the fixed arguments destination context identity, new_uuid, epoch, destination nominal length, and for the mutable arguments block_budget, callback token, and user token.

Each planner case changes exactly one fixed argument, or changes only mutable arguments. Also emit raw operation snapshots before/after and call result/trace. Verification itself checks which fields changed and derives rejection/no-work versus permitted progress.

## Callback re-entry

From inside a duplicate progress callback, exercise the same fifteen columns. Emit the raw operation snapshot before/after nested call; numeric callback-entry count before/after; numeric maximum callback recursion depth before/after; exact nested public call result and block trace; for render/status-info-tell their same raw observations described above; and the next ordinary duplicate continuation with raw before/after operation snapshots and result/more_work.

Verification derives that callback entry count/depth did not increase, nested BUSY calls did no work, and the next ordinary continuation advanced the same operation token.

## Destination failure while Playing

Use a known non-silent Playing fixture. Before the failing duplicate call emit raw source facts: transport state enum/name, exact rate_q16_16, exact position, and a ring descriptor containing read index, write index, valid-frame count, and a stable SHA-256 of retained ring bytes.

After failing a destination dev_write, emit the same source facts again, plus the duplicate public result and more_work, complete destination callback trace including the non-zero failing write return, complete source callback trace, and a subsequent tape_render result/rendered count/raw output bytes/block trace.

Verification derives that source transport stayed Playing, rate/position/ring are byte/state identical, source media was not written/flushed, and non-silent audio still renders. Do not emit booleans like source_faulted, rate_unchanged, ring_unchanged, or audio_continues.

## Small-budget completion

Emit the actual ordered duplicate call sequence. Every element contains function identity, budget, public result, more_work, operation token, progress before/after, and destination event count before/after.

Also emit the terminal raw media snapshot, not a decoded identity object. Verification derives same-function continuation, at least one nonterminal call, one terminal call, token continuity/no restart, forward progress, and final sb_generation=1 / A0=1 / B0=2 identity from raw media.

## Already-FAULTED source

Emit the direct raw/public source state enum/name FAULTED, duplicate call/result, and complete zero-length block-event trace. Verification checks TAPE_ERR_FAULTED and zero block operations. Do not emit a precomputed source_faulted boolean.

## Failure retention

On first failure retain failure-reproducer.json. Crash reproductions contain exact pre/post primary and mirror blocks, exact case/injection parameters, actual fresh-remount result, and the verifier independently parsed result.

Success evidence retains canonical census/digest, adapter/build/source provenance, package hashes, and stderr. A Software green is evidence, never self-acceptance.
