# Work packages

One file per WP: interface, acceptance criteria, status. `WP-NN.md`.

A package file is written when the package is picked up, not before. The index preserves all 37 packages from Plan Rev B (received 2026-08-31).
Current status below is updated 12 September 2026 UTC. Historical phase durations are
planning estimates, not fresh commitments. This repo is the restart authority; no
external Plan or Charter is required. Read [STATUS](../STATUS.md) and the
[scoped freeze record](../PHASE0-FREEZE.md) before treating a phase as complete.

Owner column preserves historical categories: **Agent** means the assigned lead's
own chat-based work, not an unattended worker pool · **You** needs Michael's hands or
judgement · **Either** has both a DIY and a service-bureau path. Streams: 1 engine,
2 independent verification, 3 desktop tooling, 4 prototype firmware, 5 production firmware.

## Phase 0 — foundations and spikes · 2 weeks, fully parallel

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-01 | Repo, agent docs, decision log | Agent | — | Repo and restart agreement published; no independent package acceptance claimed |
| WP-02 | TAPEFS v1 specification | **PM** | spec | Exact independently paper-reviewed DRAFT-8 issued via #25; scoped freeze signed by Michael 8 September 2026 |
| WP-03 | Engine API specification | **PM** | spec | Exact independently paper-reviewed DRAFT-8 issued via #25; scoped contract freeze signed; operations/state remain unfrozen |
| WP-04 | Transport spike: Route A vs Route B | You | hardware | **Packet WP04-01 rev 5 built and sendable** — carries WP-24's sweep too |
| WP-05 | Parts order #1 | You | hardware | Michael selected a 2 × 64 GB V30 vs 2 × 32 GB U3 evaluation; no purchase or card qualification yet; exact SKU/revision/CID and independent evidence remain required |
| WP-34 | Thermal and safety budget | Hardware | hardware | Current version in spec/hw/VERSION.md; estimates, open safety acceptances and HC221 qualification hold |
| WP-35 | Repo access and agent push setup | You | — | Effectively satisfied — see note |

**Gate:** Michael signs off the TAPEFS spec. After this, format changes cost real rework.

## Phase 1 — audio engine, on a laptop · 4–6 weeks, no hardware

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-06 | Block device layer, superblock, index commit | Agent | 1 | 289/289 recorded mount assertions independently dispositioned; full package and uncovered #20 behavior remain held; active work is assigned in issues |
| WP-07 | Chunk allocator, copy-on-write Side B | Agent | 1 | Exact hardened VT8 tree integrated; synthetic self-tests only. Six operations remain undefined, no product run exists and full acceptance remains held; see current issues for assignments |
| WP-08 | Playback, seek, variable-rate scrub | Agent | 1 | First corrected three-family verifier package authenticated for exact import; no product run or acceptance. Remaining boundary/ramp/side-switch coverage is independently assigned before implementation |
| WP-09 | Record: overwrite, overdub, splice | Agent | 1 | Contract issued; corresponding independent tests must land before implementation |
| WP-10 | Crash-injection harness | Verification | 2 | Crash infrastructure and narrow independent mount package landed; complete crash/operation/state run not yet green |
| WP-11 | CLI harness and golden-file regression suite | Verification | 2 | First candidate PCM/evidence tranche is corrected and authenticated but remains synthetic-only and unlistened; exact import/product evidence and Michael listening are outstanding, so golden CI remains red |
| WP-12 | Re-spool / defragment pass | Agent | 1 | Contract issued; independent WP-12a coverage and acceptance outstanding |
| WP-13 | Embedded-readiness audit | Agent | 1 | Held #20 measurements: instance 156456 B, stack 1536/8192, rodata 1040/32768; allocator/funnel gates green. Implementer evidence, not package acceptance |
| WP-36 | Slot capability model | Agent | 1 | Contract issued; corresponding independent tests must land before implementation |

**Milestone:** splice your own voice into the middle of a song on a laptop and hear it.

## Phase 2 — desktop tooling · 2–3 weeks

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-14 | `tapectl`: format, load, dump, verify, promote | Agent | 3 | Blocked on Stream 1 |
| WP-15 | Drag-and-drop GUI (Tauri) | Agent | 3 | Blocked on Stream 1 |
| WP-16 | Ingest: gapless concat, loudness normalisation | Agent | 3 | Blocked on Stream 1 |

## Phase 3 — bench prototype · 3–4 weeks, gated on parts

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-17 | Teensy firmware skeleton, engine integration | Agent | 4 | Blocked |
| WP-18 | Dual card, hot-swap detect, copy with LED row | Either | 4 | Blocked |
| WP-19 | Line-in, mic, gain staging, output limit | Either | 4 | Blocked |
| WP-20 | Button matrix, solenoid driver, interlock | You | 4 | Blocked on WP-04 |
| WP-21 | Bench acceptance demo | Either | 4 | Blocked |

**Milestone:** a working, hideous device.

## Phase 4 — transport mechanism and enclosure · 6–10 weeks · the long pole

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-22 | Transport mechanism, production design | You | hardware | Blocked on WP-04 |
| WP-23 | Enclosure CAD | Either | hardware | Not started |
| WP-24 | Cartridge shell and carrier PCB | Either | hardware | **In flight** — clasp assessment delivered (ADR-117); variants share the WP04-01 plate |
| WP-25 | Abuse testing | You | hardware | Blocked |

**Milestone:** a Teensy-based unit in a finished printed case. A reasonable place to stop.

## Phase 5 — production PCB · 8–12 weeks, 2–3 board spins

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-26 | Schematic capture and review | Agent | hardware | No schematic yet; codec architecture recorded in board-rev-a.md; fabrication/charging safety gate remains CLOSED |
| WP-27 | Layout, DFM, assembly BOM | Agent | hardware | Not started — results format now fixed by ADR-118 |
| WP-28 | Firmware port and UHS-I bring-up | Agent | 5 | Blocked |
| WP-29 | Bring-up and rev B | Either | 5 | Blocked |
| WP-30 | Power budget and runtime validation | Either | 5 | Blocked |
| WP-37 | Thermal validation and abuse | Either | 5 | Blocked — results format now fixed by ADR-118 |

## Phase 6 — family rollout · 3 weeks

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-31 | Build the units | You | — | Blocked |
| WP-32 | Starter cartridge library | Either | 3 | Blocked |
| WP-33 | Field trial | You | — | Blocked |

---

## Note on WP-35

The historic plan requested a fine-grained token; current configured access permits
repository work, so no new credential request is made. The P1-R1 read-only check
confirms `main` is unprotected and ruleset 22084355 is disabled (VR-P1-001).
Software proposes a configuration consistent with normal roles, including PM's
direct document authority; Michael must direct any settings change. No change or
bypass was made. The expired combined-lead mandate is not current authority.

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
