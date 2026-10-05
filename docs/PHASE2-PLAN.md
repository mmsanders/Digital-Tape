# Phase 2 plan — desktop tooling

**Issued by PM, 4 October 2026 (ADR-161). Status: ADOPTED 5 October 2026 (ADR-162).** Michael
answered D1–D8 and PM declared D9; answers are in §2. Round-1 issues wait for Michael's go to assign. Nothing in this file assigns work. Work is assigned in role-labeled
issues ([issue workflow](ISSUE-WORKFLOW.md)), each citing the section of this plan it carries out.
Package detail and acceptance criteria are in [WP-14](PACKAGES/WP-14.md),
[WP-15](PACKAGES/WP-15.md) and [WP-16](PACKAGES/WP-16.md). Current state is in [STATUS](STATUS.md).

## 1. What Phase 2 delivers

**Goal:** a person who is not Michael drops a folder of music onto a computer program, types a
label, and gets a microSD cartridge that the Phase 1 engine plays. The cartridge plays the music
in order, at a consistent level, with no clicks at the joins.

| Package | Delivers | Owner |
|---|---|---|
| [WP-14](PACKAGES/WP-14.md) `tapectl` on real cards | Provision a real microSD (MBR, FAT32 README partition, TAPEFS partition), load, verify, dump, promote, all on removable media, safely and durably | Software builds · Verification accepts |
| [WP-16](PACKAGES/WP-16.md) Ingest | A folder of mixed-source music becomes one 44.1 kHz / 16-bit stereo stream: decoded, resampled, gain-normalised, joined gaplessly | Software builds · Verification accepts |
| [WP-15](PACKAGES/WP-15.md) Drag-and-drop app | One window over WP-14 and WP-16: drop a folder, type a label, pick the card, press one button | Software builds · Verification accepts · Michael runs the unaided test |
| ~~WP-38~~ Phone test harness | **Not taken (D7).** No explicit development; Phase 2 design must not exclude a later WebAssembly build | — |

**Milestone:** someone who is not Michael makes a playable cartridge from a folder, unaided.
On a laptop the "playable" check is `tapectl verify` plus `tapectl dump`, because no device exists yet.

**Phase 2 exit gate**, all of:
1. WP-14, WP-15 and WP-16 independently accepted against their package criteria.
2. The unaided test (WP-15 G2) passed and witnessed by Michael.
3. Phase 1 goldens and every Phase 1 replay still green on main. Nothing in Phase 2 changes the engine.
4. Copy-throughput question Q-P2-1 (§5) decided and recorded before Phase 3 firmware starts.
5. Host scope frozen: *it loads cartridges*. It is not a music manager, tag editor, library or player.

**Not in Phase 2:** hardware (parked through Phase 2, ADR-160), firmware, engine behaviour changes,
card-to-card `dup` on the desktop (the device copies cartridges), warm start, metadata of any kind
on the cartridge beyond the superblock `label`, and printed label art.

## 2. Kickoff decisions

Each has a recommended default. "Go with the defaults" is a complete answer.

| # | Decision | Owner | Recommended default |
|---|---|---|---|
| D1 | Start Phase 2 | Michael | Go |
| D2 | Which computers the tools must run on | Michael | The computer(s) the family will actually use, plus Linux in CI. Everything is built portable; only the named platforms are tested and accepted |
| D3 | Which source files ingest accepts | Michael | WAV, AIFF, FLAC, MP3, AAC/M4A (non-DRM). DRM-protected files are refused with a plain message |
| D4 | Loudness | Michael | Gain only, no compression or limiting. Each song is set to −16 LUFS integrated (EBU R128). If that gain would push a peak above −1 dBTP, use less gain instead, so that song plays quieter rather than distorted |
| D5 | Order and gaps | Michael | Natural filename order within the dropped folder (1, 2 … 10). No gap inside one folder. Dropping several folders inserts 2 s of silence between them |
| D6 | Who runs the unaided test | Michael | A family member who has not seen the app, with Michael watching and not helping |
| D7 | Take WP-38 (phone harness, from #341) in Phase 2 | Michael | Yes, after WP-14, as a separate lane that does not block the exit gate |
| D8 | Required-check ruleset (R2) | Michael (repository setting) | Change it after R1 lands (§4), to the stable aggregate contexts R1 produces |
| D9 | Declare the operations/state freeze | PM | Declare at kickoff. Its condition (complete green WP-10) is met |

**Answers, 5 October 2026 (Michael's words verbatim on #381; ADR-162).**

| # | Answer |
|---|---|
| D1 | Go |
| D2 | **Windows 10** and **current macOS** (up to date; Software records the exact version tested), plus Linux in CI |
| D3, D4, D5, D8 | Defaults |
| D6 | Michael's wife, if she agrees. Fallback: the default (a family member who has not seen the app) |
| D7 | **No WP-38 in Phase 2.** No explicit development, but Software keeps it possible: nothing in WP-14/15/16 may make a later WebAssembly build of the engine and ingest path impossible. Recorded under WP-38 in the roadmap |
| D9 | Operations/state freeze **declared** (ADR-162) |

## 3. How the work is organised

Lead format, authorities and the issue workflow are unchanged from Phase 1 (CLAUDE.md §2 and §7).
Phase 2 adopts these from the retrospective (#372, [roadmap R1–R9](PACKAGES/README.md#phase-2-kickoff-prep)):

- **Pre-routed rounds (R5, ADR-158).** PM issues a contract. Software builds against it while
  Verification writes the acceptance tests from the same contract, without reading Software's code.
  Verification then disposes Software's exact head. The original assignment authorises integrating
  that exact head once it passes, with no separate "merge" round. PM enters for scope and the final
  disposition.
- **Contracts first.** Each package gets a PM-issued contract before code, as WP-11 did with
  [`WP11-CLI-CONTRACT.md`](WP11-CLI-CONTRACT.md). Changing a contract after issue is a PM decision
  recorded in the contract and both issues.
- **Thin end-to-end path first (R6).** Round 1 proves the whole path on one real card: format,
  load, verify, dump. Ingest and the app build onto a path that already works.
- **Contract preflight (R3).** Before publishing a large test package, Verification checks its
  fixtures against the contract itself. That catches the "test that no correct program can pass"
  class Phase 1 kept rediscovering.
- **Independence for host tools.** Structural Rule 1 governs engine code. Host tools follow the
  WP-11 pattern instead: tests are authored from the contract in parallel and disposed blind
  against an exact head. Phase 2 makes no engine change. If one turns out to be needed, it goes
  back to PM and Structural Rule 1 applies in full.
- **Where the code lives.** Recommended, for Software to confirm in its round-1 return:
  - `tapectl` stays C over the engine and its ports.
  - Ingest is a separate command-line tool that writes a canonical WAV, which `tapectl load`
    consumes. It may be Rust (decoding, resampling and loudness libraries are mature there); ingest
    is not format logic.
  - The app (Tauri) runs those two tools and never writes the card itself. "Never reimplement format
    logic in Rust" becomes a checkable rule: no Rust code opens a block device for writing.

## 4. Rounds

Round numbers are planning labels. Each round's issues name their exact inputs and stop conditions.

### P2-R0 — kickoff (Michael and PM)
- Michael answers D1–D8. PM declares the operations freeze (D9) and records all of it in an ADR.
- PM issues the round-1 issues below.

### P2-R1 — the real-card path and cheaper CI
- **Software, first (small): R1 CI lanes.**
  - Docs-only merges to main stop running the full suite.
  - Jobs are grouped into three stable required contexts:
    - **cheap:** docs, spec, build and guardrails;
    - **regression:** current-engine replays, goldens and changed packages;
    - **qualification:** full campaigns, mutation, historical replay. These run on a schedule and at phase gates.
  - Job names and the ruleset must change in one coordinated step. GitHub matches required checks by name, so renaming a job before the ruleset changes blocks every PR. Software ships the CI side; Michael switches the ruleset (D8) the same day.
- **PM: issue `docs/WP14-CLI-CONTRACT.md`** from [WP-14](PACKAGES/WP-14.md). It covers device naming, the refusal rules, exit codes, `provision`, `verify`, and `load`/`dump`/`promote` on a device.
- **Software: WP-14 build** against that contract:
  - a partition-view port over a raw device;
  - a durable flush;
  - 64-bit offsets;
  - the disk-safety guard;
  - MBR and FAT32 provisioning;
  - read-only `verify`.
- **Verification, in parallel:**
  - the WP-14 acceptance package, built on disk images and loop devices, including negative controls for every refusal rule;
  - the R3 preflight on that package;
  - Q-P2-1(a), §5.
- **Michael: witnessed real-card run** on one of his PNY 64 GB cards, following the script in the
  Verification package: provision, load, eject, reinsert, verify, dump, and ten deliberate pulls mid-load.
- **Stop:** Verification PASS on an exact WP-14 head, integrated; the real-card run recorded.

### P2-R2 — ingest
- PM issues the WP-16 contract, using D3–D5.
- Software builds the tool. Verification builds the fixtures and acceptance tests in parallel. Fixtures are generated tones and public-domain or CC0 recordings only, like the WP-11 goldens.
- PM rules on Q-P2-1(b), §5.
- **Stop:** Verification PASS on an exact WP-16 head, integrated.

### P2-R3 — the app and the unaided test
- PM issues the WP-15 contract (screens, wording, refusal messages).
- Software builds. Verification checks the "no list, no direct device write" rules and the error paths.
- Michael runs the unaided test (D6) and records it in the issue.
- **Stop:** Verification PASS; unaided test passed; host scope frozen.

### WP-38 lane (if D7 is yes)
**Not taken: D7 was no (ADR-162).** Kept as the record of what the lane would be if Michael takes it later.
- Starts after P2-R1. It runs alongside R2/R3 and does not block the exit gate.
- PM issues a short contract. Acceptance: the ten WP-11 goldens are bit-identical through the WASM build, and Michael plays and records a test cartridge image on his phone.
- It makes no claim about the product codec, the 85 dB cap or wake latency.

## 5. Q-P2-1 — copy throughput and the one-block call shape (from #379)

`tape_dup`, `tape_promote`, `tape_respool`, record and play all move chunk data **one 512-byte block
per device call** (for example `engine/src/raw_ops.c`, the `tape_dup` copy loop). On a desktop the operating system's
cache hides this. On the device's SD port it does not. Unbatched single-block writes each wait out the
card's program time. #379 estimates about two minutes for one C-60 copy at any bus speed, against
guardrail 10's 30 s. That makes this the largest known risk to the copy-time requirement, and it is
cheaper to settle now, on paper, than after firmware exists.

- **(a) Verification, P2-R1.** `tapefs` §8.1 says the absence of a flush implies nothing. A port may
  therefore persist any subset of unflushed writes, in any order, before the next flush. That is what
  a desktop OS cache does, and what an SD port batching writes into multi-block commands would do. The WP-10 crash
  model runs two modes, flush-required and write-through. Verification determines whether those two
  modes cover "any subset of the writes since the last flush". If they do not, Verification states
  what a third mode would need.
- **(b) PM, P2-R2.** Input: (a), plus a Software count of device calls per C-60 operation on
  `dev_sim`. No hardware is needed. PM rules between two options, and records the ruling in an ADR before Phase 3:
  - **Port-level batching.** The engine is unchanged; the firmware port batches and reads ahead.
  - **A spec change.** Multi-block device calls in the engine. That is engine behaviour, so it means a spec revision, Michael's approval and Structural Rule 1.

## 6. Out of scope, recorded for later phases

From #379 (Michael, 4 Oct: "make SDR50 the primary path"). Hardware is parked, so this is recorded,
not scheduled. It is in [the roadmap](PACKAGES/README.md) under WP-05, WP-26 and WP-28:
- SDR50 at 1.8 V as the primary card bus, with High Speed 4-bit at 3.3 V as the fallback.
- Fit the 1.8 V parts on rev A. The footprints already exist.
- A thermal recheck at SDR50.
- A Software change list for the board interface (CLAUDE.md §5). PM approval is needed only if a guardrail moves; as filed, none does.
- The A-6 atomicity test must use the write command and bus mode the firmware will actually use.
- The cold instant-on and commit-latency criteria are measured in the shipping bus mode.
- Check whether the Teensy 4.1's built-in slot can run SDR50 at all.

## 7. What Phase 2 measures

The pilot targets from #372, tracked weekly in STATUS while Phase 2 runs:
- docs/site PRs finish in about 2 minutes;
- ordinary code feedback in about 5 minutes;
- summed CI job-minutes for unchanged-code work at least halved;
- no round whose only purpose is to merge an accepted head;
- correction cycles per accepted package;
- no repeat of a settled contract defect.

After two corrections of the same kind, the shared mechanism gets fixed rather than patched a third time.
