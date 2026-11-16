# Phase 3 ledger — every exit criterion, one row each

Opened 2 November 2026. Plan: [PHASE3-PLAN](PHASE3-PLAN.md). Updated 16 November for
[ADR-210](DECISIONS.md#adr-210--light-process-outside-the-engine).

**States:** PASSED · READY (written, waiting for hardware) · TO DO · BLOCKED (says on what).
The [dashboard](../site/lead-queue/index.html) mirrors this table and its test fails if they differ.

**How a row closes.** Counted facts (bytes equal, zero underruns, zero torn blocks) are
checked by a test or a log. Timing and feel are firmware-timed and judged by Michael in
[MICHAEL-CHECKS](MICHAEL-CHECKS.md) (ADR-208). Output caps are checked with a phone app,
5 dB under the limit.

## Entry items

| Item | State | Next |
|---|---|---|
| First parts order | BLOCKED | Michael orders group 1 of [the parts list](../hardware/sourcing/PHASE3-BENCH.md), about $62 |
| DRAFT-11 spec revision ([proposal](SPEC-DRAFT-11-PROPOSAL.md)) | BLOCKED | Waiting on Michael: approve the speaker limit (80 dB(A) at 50 cm proposed), then PM finishes the text for his sign-off |
| Crash coverage before write batching (Q-P2-1) | BLOCKED | 365 of 365 deferred load faults pass. Six long cuts could not be run on the fixture. **Write batching stays off.** Revisit only if one-block writes prove too slow on the bench |

## WP-05 — cards and bench parts

| # | State | Next |
|---|---|---|
| A-1 Card identity | PASSED | [evidence/cards](evidence/cards/README.md): three PNY Elite-X 64 GB microSDXC U3 V30 A1, photos kept. Retail part number unknown (packaging gone) |
| A-2 Sustained write on 80%-filled media | TO DO | On the bench, with the Teensy and the existing reader |
| A-3 Against the C-60 copy requirement | TO DO | After A-2 |
| A-4 Reader not the bottleneck | TO DO | With A-2 |
| A-5 Bench parts in hand | BLOCKED | Blocked on the order. Group 1 first; groups 2 and 3 when their work starts |
| A-6 Power-cut test: 1,000 or more qualifying cuts per card model, zero torn | TO DO | After playback works. Needs group 3 parts. The host-side judge and its planted-tear tests exist in `hardware/characterisation/`; the Teensy cut firmware does not. A torn block is a format blocker |

## WP-17 — firmware skeleton ([FW-1](WP17-FIRMWARE-CONTRACT.md))

| # | State | Next |
|---|---|---|
| F1 Goldens byte-identical on target | READY | Passes off-target (portable render path against all seven 1.0× goldens, with controls). Run `golden_serial.py` on the Teensy |
| F2 RAM, stack and .rodata budgets | READY | Static sizes pass in CI (RAM 191,600 of 204,800 bytes; engine .rodata 1,040 of 32,768). Stack high-water needs the board: `info` prints it |
| F3 Warm wake under 100 ms | READY | Implemented and tested off-target (16 Nov). On the bench: `sleep`, Play, read `WAKE us`, run `wake150`; Michael's verdict |
| F4 Commit latency under 200 ms | TO DO | With recording (WP-19). Zero underruns is strict |
| F5 Play, Stop and card removal | READY | Implemented. Bench: pull the card mid-play, then `tapectl verify` |
| F6 Engine unchanged | PASSED | CI checks the engine tree against `d96b4245` on every firmware PR |

## WP-18 to WP-21

Not started. Each begins when the one before it works on the bench:
- WP-18: second slot, copy correctness, progress from the callback.
- WP-19: recording, audio paths, the two output caps, speaker mute, record source.
- WP-20: key reading, depth-sensitive scrub, LED status, record light.
- WP-21: the bench demo, end to end, with Michael.
