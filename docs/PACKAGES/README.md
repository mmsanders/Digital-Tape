# Work packages

One file per WP: interface, acceptance criteria, status. `WP-NN.md`.

A package file is written when the package is picked up, not before. The index preserves all 37 packages from Plan Rev B (received 2026-08-31).
Current status below is updated 3 October 2026 UTC (Phase 1 close-out, ADR-160). Historical phase durations are
planning estimates, not fresh commitments. This repo is the restart authority; no
external Plan or Charter is required. Read [STATUS](../STATUS.md) and the
[scoped freeze record](../PHASE0-FREEZE.md) before treating a phase as complete.
New information about a future phase is appended to that phase's package entry here and
waits there; see [intake](../INTAKE.md). Recording a fact is not scheduling it.

Owner column preserves historical categories: **Agent** means the assigned lead's
own chat-based work, not an unattended worker pool · **You** needs Michael's hands or
judgement · **Either** has both a DIY and a service-bureau path. Streams: 1 engine,
2 independent verification, 3 desktop tooling, 4 prototype firmware, 5 production firmware.

## Phase 0 — foundations and spikes · 2 weeks, fully parallel

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-01 | Repo, agent docs, decision log | Agent | — | Repo and restart agreement published; no independent package acceptance claimed |
| WP-02 | TAPEFS v1 specification | **PM** | spec | Scoped freeze signed by Michael 8 September 2026 (DRAFT-8, #25); amended through DRAFT-9 (#247) and DRAFT-10 (#352). Current revision in `spec/VERSION.md` |
| WP-03 | Engine API specification | **PM** | spec | Scoped contract freeze signed (DRAFT-8, #25); amended through DRAFT-10 (#352). Operations/state freeze **declared** at Phase 2 kickoff (ADR-162) |
| WP-04 | Transport spike: Route A vs Route B | You | hardware | **Parked through Phase 2** (#309, ADR-160). Michael owns an A1 Mini (nominal 180 × 180 × 180 mm), the default printer for all new print work; the library-printer route is retired. Michael reports filament on hand (3 Oct) and that clasps from his own sizing prints appear to work; that is owner observation, not qualification. Held PRs #120 (A1 Mini filament advice + A1MINI-01 coupon method), #197 and #198 (latch test-frame fixes) were closed unmerged; see the [parked hardware PR record](#parked-hardware-pr-record), including the latch root cause the next revision must start from. Safe wallet default remains: no purchase without Michael's approval. Resume at Phase 3 or on an explicit request |
| WP-05 | Parts order #1 | You | hardware | **Parked through Phase 2** (#309, ADR-160). Three PNY 64 GB V30 cards are bought. Five stored-rate vectors are independently arithmetically reproduced, but Verification rejected the measurement method (`P1-R23-V01`), so no card is characterised to A-2. PR #87 (schema-2 sustained-write path) was closed unmerged and is restorable; see the [parked hardware PR record](#parked-hardware-pr-record). A-2, exact identity, attribution, atomicity and end-to-end acceptance remain open and are a Verification review on resume. #379: the A-6 atomicity test must use the write command and bus mode the firmware will ship (likely multi-block CMD25 at SDR50); check whether a Teensy 4.1 built-in slot can run SDR50 before the rig depends on it |
| WP-34 | Thermal and safety budget | Hardware | hardware | Current version in spec/hw/VERSION.md; estimates, open safety acceptances and HC221 qualification hold |
| WP-35 | Repo access and agent push setup | You | — | Effectively satisfied — see note |

**Gate:** Michael signs off the TAPEFS spec. After this, format changes cost real rework.

## Phase 1 — audio engine, on a laptop · 4–6 weeks, no hardware

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-06 | Block device layer, superblock, index commit | Agent | 1 | **COMPLETE.** Verification #138's DRAFT-10 ledger closes WP-06: 40 rows independently accepted and integrated (mount, writability, NOT_MOUNTED, #297 sequential, #326 closure gaps), 2 WP-06e rows unreachable by spec (V10-002), none open |
| WP-07 | Chunk allocator, copy-on-write Side B | Agent | 1 | **COMPLETE / independently accepted.** Verification PR #67 accepted the frozen 10,000-sequence allocator/COW package. Product PR #215 mechanically carried the accepted bytes onto post-WP13 main and integrated them unchanged |
| WP-08 | Playback, seek, variable-rate scrub | Agent | 1 | **COMPLETE.** Every behaviour row is covered. L01/L14 close on the WP-11 goldens approved by Michael (#367). Verification #143 PASS on exact #369 |
| WP-09 | Record: overwrite, overdub, splice | Agent | 1 | **COMPLETE.** Every behaviour row is covered (#346). L01 closes on the WP-11 goldens approved by Michael (#367). Verification #143 PASS on exact #369 |
| WP-10 | Crash-injection harness | Verification | 2 | **COMPLETE.** Verification #141 passed exact Product #362 (V10-001) and closed the DRAFT-10 WP-10 ledger: 63 rows, zero open; earlier bounded tranches carried within their exact boundaries |
| WP-11 | CLI harness and golden-file regression suite | Verification | 2 | **COMPLETE.** `tapectl` per `docs/WP11-CLI-CONTRACT.md`; ten golden references from public-domain Grieg plus a CC0 voice, approved by Michael (#367) and bit-identical in CI; the §8 differential on three configurations; mutation 7/7. Verification #143 PASS on exact #369, merged at `d93ca4e` |
| WP-12 | Re-spool / defragment pass | Agent | 1 | **COMPLETE.** WP-12/12a ledger: 36 rows, zero open (`wp11_ledgers_r63`; Verification #143) |
| WP-13 | Embedded-readiness audit | Agent | 1 | **COMPLETE / independently accepted.** Verification PR #66 independently reproduced all six frozen gates from raw evidence and accepted exact product PR #206; integrated on main |
| WP-36 | Slot capability model | Agent | 1 | **COMPLETE / independently accepted.** Verification PR #57 accepted the frozen package after the deterministic 5/5 precursor plus the exact 100,000-sequence / 1,997,914-operation literal-NULL source-slot campaign. Product PR #200 integrated the exact accepted tree unchanged at main `e4a3565...` |

**Milestone:** splice your own voice into the middle of a song on a laptop and hear it. **Met 3 Oct 2026** (WP-11 `splice` golden, approved by ear on #367; `tapectl record --mode splice` lets anyone repeat it with their own voice).

## Phase 2 — desktop tooling · 2–3 weeks · [plan](../PHASE2-PLAN.md)

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-14 | `tapectl`: format, load, dump, verify, promote — [on real cards](WP-14.md) | Agent | 3 | **P2-R1; not accepted.** Playback #419 independently accepted/integrated (ADR-175), immutable A8 engine `d96b4245` recorded. Existing #392/#146 final WP14 qualification resumes with complete authored verifier package `56e25cc1`. Native C60/exact-head disposition, physical macOS/Windows 10 and release evidence remain; #390 merge Michael-reserved. Criteria A1–A9 in package file |
| WP-15 | [Drag-and-drop app (Tauri)](WP-15.md) | Agent | 3 | **Planned, P2-R3.** One window over WP-14 and WP-16; never writes the card itself; no lists (guardrail 03). Milestone test: someone who is not Michael makes a cartridge unaided |
| WP-16 | [Ingest: gapless join, loudness normalisation](WP-16.md) | Agent | 3 | **Planned, P2-R2.** Folder of mixed sources → one canonical WAV; gain-only loudness; exact gapless joins. D3–D5 settled (ADR-162); follows the WP-14 real-card path |
| WP-38 | Phone / web-app test harness (engine built to WebAssembly) | Agent | 3 | **Not taken in Phase 2 (D7, ADR-162).** Michael: no explicit development, but Software keeps the possibility open; Phase 2 host work must not make a later WASM build of the engine and ingest path impossible. Resume: Michael's `REQUEST:`. Lane outline kept in [the plan](../PHASE2-PLAN.md#wp-38-lane-if-d7-is-yes). Feasibility (PM, #341): the C99 engine compiles to WASM unchanged (guardrail 12); phone audio is not the product codec, so it gives no 85 dB-cap or wake-latency evidence, and golden identity must hold on the WASM build |

**Milestone:** someone who is not Michael makes a playable cartridge from a folder, unaided. The detailed plan, rounds and kickoff decisions are in [docs/PHASE2-PLAN.md](../PHASE2-PLAN.md).

## Phase 3 — bench prototype · 3–4 weeks, gated on parts

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-17 | Teensy firmware skeleton, engine integration | Agent | 4 | Blocked. ADR-167 [energy review](../PERFORMANCE-REVIEW.md): on resume, measure burst service / I²S DMA scheduling, CPU idle waits and clock choices; preserve warm wake and exact audio. Scrub at 12× gives only ~31 ms in 64 KiB. Record energy and worst latency; no current-phase activation |
| WP-18 | Dual card, hot-swap detect, copy with LED row | Either | 4 | Blocked. ADR-167: copy-time planning must add read and write time unless transfers truly overlap; 635 MB at 25 MB/s each is at least 50.8 s sequential. ADR-168 rejects relaxing <30 s; [framework](../PERFORMANCE-PLAN.md) plans bounded read/write overlap with two owned buffers, completion/error handling and safe fallback. Target implementation/measurement remains parked |
| WP-19 | Line-in, mic, gain staging, output limit | Either | 4 | Blocked |
| WP-20 | Button matrix, solenoid driver, interlock | You | 4 | Blocked on WP-04 |
| WP-21 | Bench acceptance demo | Either | 4 | Blocked |

**Milestone:** a working, hideous device.

Hardware is parked through Phase 2 (#309, ADR-160); Phase 3 is where it resumes.

## Phase 4 — transport mechanism and enclosure · 6–10 weeks · the long pole

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-22 | Transport mechanism, production design | You | hardware | Blocked on WP-04 |
| WP-23 | Enclosure CAD | Either | hardware | Not started. Michael ran an informal sizing study with Hardware (PR #296: WM-2 and layout-A hand mockups, 3 A1 Mini plates); it was closed unmerged on 3 Oct at Michael's direction, and Hardware will provide a write-up later. The PR stays restorable; see the [parked hardware PR record](#parked-hardware-pr-record) |
| WP-24 | Cartridge shell and carrier PCB | Either | hardware | **Phase 4; parked in Phase 1.** Michael's 21 Sep SURGE-OML-01 handling result withdraws 86 × 54 × 12 mm as the owner taste target: both printed media dummies were too large and the intended reference class is memory-card-like, with the microSD hidden/edge-slotted rather than cassette-planform media. No replacement dimensions are issued and no reprint/redesign is scheduled. Resume only on an explicit WP-24 request; then Hardware must start from the smaller reference class rather than silently inheriting 86 × 54 × 12 |
| WP-25 | Abuse testing | You | hardware | **Phase 4; parked as Phase 1 activity.** Guardrail 13 remains binding and still requires ruggedization designed and tested before final enclosure CAD — the guardrail is not parked, only the shock/load-path matrix, failure-mode matrix, drop/shake protocol and staged physical trials are. PR #92 (ruggedization method rev 0.3) was closed unmerged on 3 Oct and is restorable; it needs independent Verification method review when hardware resumes (see the [parked hardware PR record](#parked-hardware-pr-record)); no independent method or physical acceptance is claimed and the fabrication/safety gate remains closed. Resume when Phase 4 opens, when enclosure CAD approaches finalization, on an explicit request, or in an authorized hardware round. Retrospective intake #130 is filed/closed; this package entry plus Guardrail 13 are the durable record |

**Milestone:** a Teensy-based unit in a finished printed case. A reasonable place to stop.

## Phase 5 — production PCB · 8–12 weeks, 2–3 board spins

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-26 | Schematic capture and review | Agent | hardware | No schematic yet; codec architecture recorded in board-rev-a.md; fabrication/charging safety gate remains CLOSED. **#379 (Michael, 4 Oct): SDR50 at 1.8 V becomes the primary card bus, High Speed 4-bit at 3.3 V the fallback.** On resume, Hardware revises `board-rev-a.md` (fit the 1.8 V parts, whose footprints exist; SDR50 becomes the primary gate, superseding ADR-113's gate order), rechecks the thermal budget at SDR50 (including playback during copy, which the current thermal model excludes but engine-api §10 supports), and sends Software a change list (CLAUDE.md §5). Parked with hardware |
| WP-27 | Layout, DFM, assembly BOM | Agent | hardware | Not started — results format now fixed by ADR-118 |
| WP-28 | Firmware port and UHS-I bring-up | Agent | 5 | Blocked. #379 firmware-port work: drive the 1.8 V rail and CMD11 voltage switch, power ordering (`+3V3` before `+1V8`), re-initialise signalling after a slot power cycle, and automatic fallback to High Speed if CMD11 or tuning fails; all in the port (`engine/port/dev_sd.c`), none in the engine. Copy throughput depends on Q-P2-1 ([plan §5](../PHASE2-PLAN.md#5-q-p2-1--copy-throughput-and-the-one-block-call-shape-from-379)). Measure cold instant-on and commit latency in the shipping bus mode. ADR-167: audit USDHC DMA completion/CPU idle waits, DMA-accessible memory/cache ownership, rate-aware refill deadlines and checkpoint flash wear; measure playback energy/hour and copy energy/C60. Preserve <200 ms commit unless formally revised; details in the [performance review](../PERFORMANCE-REVIEW.md) |
| WP-29 | Bring-up and rev B | Either | 5 | Blocked |
| WP-30 | Power budget and runtime validation | Either | 5 | Blocked |
| WP-37 | Thermal validation and abuse | Either | 5 | Blocked — results format now fixed by ADR-118 |

## Phase 6 — family rollout · 3 weeks

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-31 | Build the units | You | — | Blocked |
| WP-32 | Starter cartridge library | Either | 3 | Blocked |
| WP-33 | Field trial | You | — | Blocked |

## Phase 2 kickoff prep

Recorded at the Phase 1 close-out (3 October 2026, ADR-160). Phase 1 exit criteria are met
(ADR-159). Nothing below is scheduled until Michael gives the Phase 2 go. **The kickoff
decisions (D1–D9), rounds and package criteria are now in [the Phase 2 plan](../PHASE2-PLAN.md)
(ADR-161)**, which schedules the R-items below; this section keeps their rationale.
**Answered 5 October 2026 (ADR-162):** go; Windows 10 + current macOS; defaults for D3–D5/D8;
D6 Michael's wife; WP-38 not taken; operations freeze declared. The list below is historical.

**Decisions to make at kickoff**

1. **Michael's go** for Phase 2 (WP-14, WP-15, WP-16, and whether to take WP-38).
2. **Operations/state freeze.** Its condition is met (WP-10 complete, #141). PM declares it.
3. **WP-38 vs WP-15** (intake #341): phone/web-app testing before a desktop-only GUI design.
4. **Hardware park through Phase 2** is decided (#309, ADR-160); it resumes at Phase 3 or on
   Michael's request, starting with a Verification review of PRs #87 and #92.

**Process and tooling candidates** from the Phase 1 retrospective (intake #372; full text
and evidence in that issue). The retrospective's stopping rule applies: after two
corrections of the same class, repair the shared mechanism; once the cheap path and the
main handoffs work, go back to product work.

| # | Candidate | Owner | Note |
|---|---|---|---|
| R1 | CI execution lanes: cheap checks / current regression / full qualification | PM ruling, Software builds | **Integrated #387 at `47575af`; D8 live seven-context strict ruleset verified (ADR-164).** First make unchanged-code docs **main merges** cheap; today every main push runs the whole suite (~165 job-minutes for a docs merge). Inventory the 48 job definitions by purpose and cost before moving anything; fail toward a full run when unsure |
| R2 | Required-check policy | **Michael** (ruleset 22084355 is a setting) | The ruleset requires 14 contexts that omit the golden suite, verifier publication, portability and mutation. Prefer a few stable aggregate contexts. Verification's ruleset has no required checks |
| R3 | Contract preflight inside authoring assignments | Verification | Derive fixture geometry and branch reachability from the spec; settled-regression library (reverse frame zero, multi-block callbacks, real mount/service reads, budget 1); a deliberately different conforming trace |
| R4 | Descriptor-driven package plumbing | Software (transport), Verification (expectations) | One package descriptor/runner interface built on `tests/IMPORTS.json`, for **new** Phase 2 work first; migrate old adapters only when touched |
| R5 | Pre-routed rounds with conditional integration (ADR-158) | PM | One coherent scope runs publication → implementation → exact-head disposition → integration; no activation solely to merge an unchanged accepted head. Keep stage and next owner explicit, and close an issue only at its final stop |
| R6 | Thin end-to-end path first | PM scoping | input audio → cartridge image → verify/export → listen, on the landed `tapectl`/engine; add GUI and ingest in slices against that path |
| R7 | Site test before merge | Software | `site/**` is docs-only, so the dashboard test runs only after merge in Pages; run it on site PRs |
| R8 | One current-state record | PM | STATUS is the state table; other docs link to it rather than keep their own current tables |
| R9 | CODEOWNERS ↔ IMPORTS consistency check | Software, with a negative control | CODEOWNERS and `.gitattributes` now list every IMPORTS-declared tree, by hand; a gate would stop the next import drifting out of ownership |

Pilot targets, not acceptance requirements: docs/site PRs finish in about two minutes; ordinary
code feedback in about five; summed job-minutes for unchanged-code work at least halved.

**Documentation debt left after the close-out cleanup** (from intake #374; the rest was fixed in
the close-out PRs):

- **Library-printer premise in hardware generators and packets** (`hardware/Makefile`
  `packet-wp04`, `hardware/cad/**`, `hardware/mech/clasp.py`, `hardware/packets/wp04-01/`,
  `spec/hw/cartridge-shell.md`, `spec/hw/thermal-budget.md`, `spec/hw/board-rev-a.md`).
  `hardware/README.md` flags them, including `plate-map.md`'s wrong A1 Mini size claim. These
  are generated or hash-tracked (`mech-check`, `spec-check`), so the fix is Hardware's
  generator-first sweep and revision bump on resume, not a hand edit.
- **"PM Decisions 00N" citations** in `hardware/**`, `spec/hw/*`, `engine/port/dev_sim.h`,
  `engine/src/crc32.c` and the workflows point at documents outside the repo. Cite ADR numbers
  as each file is next touched.
- **Revision labels restated in source headers and CI job names** (ADR-032). Drop them as
  each file is next touched; package job names that genuinely are DRAFT-8 stay.

## Parked hardware PR record

Closed unmerged on 3 October 2026 at Michael's direction (ADR-160). Closing accepts and rejects
nothing. Every head stays fetchable from GitHub's PR ref even after its branch is deleted:
`git fetch origin pull/<N>/head:restore-<N>`.

| PR | Package | What it held | State at close | Head |
|---|---|---|---|---|
| #87 | WP-05 | Schema-2 sustained-write measurement path (`write_fully`, full-precision windows, fill accounting) and `audit_sustained_write.py` | Method rejected by Verification `P1-R23-V01` (eleven adjacent cases); repair `e294d51` never re-audited | `8d26ecb9ad36dd39a06bcab532fee66eb4682caf` |
| #92 | WP-25 (Guardrail 13) | `spec/hw/ruggedization.md` rev 0.3: B01–B06 resolved, sharp point/edge screens bound to 16 CFR 1500.48/.49 in `hardware/rugged/sharp.py`, rev-6 split print packet | No independent method audit; no trial, no compliance claim | `0943571e83126795797c33a0aa92706247dbaa65` |
| #120 | WP-04 | A1 Mini filament advice (buy nothing now; PETG HF later; TPU only for a real part) and the A1MINI-01 fit-ladder / coupon plate | Verification #20 closed without a finding. Filament advice is moot: Michael has filament | `a6437c0c54d75324dc79910d822a790a5c77ba6c` |
| #197 | WP-04 | Latch test-frame entry keyway and bar alignment | Superseded by the root cause below | `98bc27caba14da63c66ce26c0cbedc1ed4dd3612` |
| #198 | WP-04 | Alternative latch test-frame geometry fix | Michael's A1 Mini print, 23 Sep: still not a functional latch | `ef21367969b27c47e62ed24104ff3011a3157166` |
| #296 | WP-23/24 | Sizing study (layouts A/B against TPS-L2, WM-2, WM-F5) and SIZE-01 hand mockups | Michael's informal study; Hardware to write it up later | `d4f65096a33971ae2a3cbd9e3bbd8f73a39e4357` |

**Latch root cause (WP-04, from Michael's 23 Sep physical check on #198).** The carrier barb is
vertically reversed for a push-down / spring-return latch: its slope is above the tip and its
undercut shelf below. The insertion ramp must be the lower, leading face and the retention
shoulder must sit above the hook, so that spring return drives the shoulder into the underside
of the fixed bar. The next revision redesigns carrier hook orientation and frame/bar height
together and adds a positive retention / motion-path check: non-intersection regressions proved
clearance, not engagement. The existing long bar is probably reusable; the carrier set is not
validated.

---

## Note on WP-35

The historic plan requested a fine-grained token; current configured access permits
repository work, so no new credential request is made. Ruleset 22084355 is active on
the default branch: pull request, conversation-resolution, no-deletion, no-force-push
and ten all-PR required-check rules apply, with strict latest-main testing and no bypass
actor. Michael removed the hardware-path-only packet context after it blocked ordinary
PRs; PM PR #73 then merged normally. PM made no setting change or bypass. The expired
combined-lead mandate is not current authority.

## Per-file template

```markdown
# WP-NN — title

**Stream:** · **Owner:** · **Status:** not started | in flight | in review | accepted
**Depends on:** · **Blocks:**

## Interface
What this package exposes to other streams. The contract, not the implementation.

## Acceptance criteria
From `spec/acceptance.md` and the current package definition; cite exact criteria. Measurable and independently checkable.

## Independent sign-off
Verification Lead only. Date and what was run.
```
