# Work packages

One file per WP: interface, acceptance criteria, status. `WP-NN.md`.

A package file is written when the package is picked up, not before. The index below is the
authority until then, taken from **Plan Rev B §09** (received 2026-08-31).

Owner column is the plan's: **Agent** runs unattended · **You** needs Michael's hands or
judgement · **Either** has both a DIY and a service-bureau path. Stream column maps to
Charter §04.

## Phase 0 — foundations and spikes · 2 weeks, fully parallel

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-01 | Repo, agent docs, decision log | Agent | — | **Done**, unconfirmed |
| WP-02 | TAPEFS v1 specification | **PM** | spec | **Delivered** — DRAFT-6 bundle on `main` 4 Sep, under `verify-spec-bundle.sh` |
| WP-03 | Engine API specification | **PM** | spec | **Delivered** — DRAFT-6 bundle on `main` 4 Sep, under `verify-spec-bundle.sh` |
| WP-04 | Transport spike: Route A vs Route B | You | hardware | **Packet WP04-01 built** — Q-006 answered, ready to send |
| WP-05 | Parts order #1 | You | hardware | **Carts drafted** — every order goes to Michael (Decisions 002 §4) |
| WP-34 | Thermal and safety budget | Hardware | hardware | **Rev 0.2** — estimates; three review findings closing |
| WP-35 | Repo access and agent push setup | You | — | Effectively satisfied — see note |

**Gate:** Michael signs off the TAPEFS spec. After this, format changes cost real rework.

## Phase 1 — audio engine, on a laptop · 4–6 weeks, no hardware

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-06 | Block device layer, superblock, index commit | Agent | 1 | **Read path complete against DRAFT-6** — four-phase mount, both sides, degraded-B, stage oracle. 260 checks, sub-criteria 06a–06h exercised. PR #20. Commit path held by structural Rule 1 |
| WP-07 | Chunk allocator, copy-on-write Side B | Agent | 1 | **Allocator done against DRAFT-6** — 46 checks on Rule 3; `tapefs` §7 unchanged since DRAFT-4, re-read, no code follows. Reset-B's commit held by structural Rule 1 |
| WP-08 | Playback, seek, variable-rate scrub | Agent | 1 | Blocked on WP-02/03 |
| WP-09 | Record: overwrite, overdub, splice | Agent | 1 | Blocked on WP-02/03 |
| WP-10 | Crash-injection harness | Verification | 2 | **Infrastructure landed and running in CI**; DRAFT-6 adds both durability modes and the counter boundaries to its scope |
| WP-11 | CLI harness and golden-file regression suite | Verification | 2 | **Runner built and proven** (manifest, byte-exact, audible diff). Fixtures + manifest are theirs |
| WP-12 | Re-spool / defragment pass | Agent | 1 | Blocked on WP-02/03 |
| WP-13 | Embedded-readiness audit | Agent | 1 | **Green, with numbers**: `tape_instance_size()` 156 456 B (76 % of 200 KiB), stack 1 536 / 8 192, `.rodata` 1 040 / 32 768. Funnel and allocator gates green |
| WP-36 | Slot capability model | Agent | 1 | Blocked on WP-02/03 |

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
| WP-24 | Cartridge shell and carrier PCB | Either | hardware | Not started — captive card per issue #6 |
| WP-25 | Abuse testing | You | hardware | Blocked |

**Milestone:** a Teensy-based unit in a finished printed case. A reasonable place to stop.

## Phase 5 — production PCB · 8–12 weeks, 2–3 board spins

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-26 | Schematic capture and review | Agent | hardware | Not started — codec question first |
| WP-27 | Layout, DFM, assembly BOM | Agent | hardware | Not started |
| WP-28 | Firmware port and UHS-I bring-up | Agent | 5 | Blocked |
| WP-29 | Bring-up and rev B | Either | 5 | Blocked |
| WP-30 | Power budget and runtime validation | Either | 5 | Blocked |
| WP-37 | Thermal validation and abuse | Either | 5 | Blocked |

## Phase 6 — family rollout · 3 weeks

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-31 | Build the units | You | — | Blocked |
| WP-32 | Starter cartridge library | Either | 3 | Blocked |
| WP-33 | Field trial | You | — | Blocked |

---

## Note on WP-35

The plan asks Michael for a fine-grained token. The Software Lead already has push access and
has opened a PR, so the access half is satisfied. **The `main` branch protection half is not
verified** — the plan's repo decision says "nothing merges to main without your review".
Flagged in STATUS.md; changing repository settings is not the Software Lead's call.

## Per-file template

```markdown
# WP-NN — title

**Stream:** · **Owner:** · **Status:** not started | in flight | in review | accepted
**Depends on:** · **Blocks:**

## Interface
What this package exposes to other streams. The contract, not the implementation.

## Acceptance criteria
From `spec/acceptance.md` and Plan Rev B §09. Measurable and independently checkable.

## Independent sign-off
Verification Lead only. Date and what was run.
```
