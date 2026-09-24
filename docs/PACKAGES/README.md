# Work packages

One file per WP: interface, acceptance criteria, status. `WP-NN.md`.

A package file is written when the package is picked up, not before. The index preserves all 37 packages from Plan Rev B (received 2026-08-31).
Current status below is updated 24 September 2026 UTC. Historical phase durations are
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
| WP-02 | TAPEFS v1 specification | **PM** | spec | Exact independently paper-reviewed DRAFT-8 issued via #25; scoped freeze signed by Michael 8 September 2026 |
| WP-03 | Engine API specification | **PM** | spec | Exact independently paper-reviewed DRAFT-8 issued via #25; scoped contract freeze signed; operations/state remain unfrozen |
| WP-04 | Transport spike: Route A vs Route B | You | hardware | **Parked outside Phase 1.** Michael owns an A1 Mini; its nominal advertised envelope is 180 × 180 × 180 mm, ordinary household tools are available, and current material stock is white Bambu PLA Basic. Existing library print work stays on its library route; new print work defaults to the A1 Mini, with the library retained for oversized PLA. Held PR #120 A1MINI-01 still awaits independent no-print method audit; material/process and every physical result remain unproved. Safe wallet default remains **buy nothing**; PETG/TPU are unqualified hypotheses, not approved purchases. Resume only on an explicit request, when transport/enclosure work reaches the critical path, or in an authorized hardware round. Retrospective intake #129 is filed/closed; these facts are the durable record |
| WP-05 | Parts order #1 | You | hardware | Five stored-rate vectors are independently arithmetically reproduced. Verification rejects PR #87 repaired head `e520c2c...` on `P1-R23-V01`'s eleven adjacent forms; new acquisition stays blocked. A-2, exact identity, attribution, atomicity and end-to-end acceptance remain open |
| WP-34 | Thermal and safety budget | Hardware | hardware | Current version in spec/hw/VERSION.md; estimates, open safety acceptances and HC221 qualification hold |
| WP-35 | Repo access and agent push setup | You | — | Effectively satisfied — see note |

**Gate:** Michael signs off the TAPEFS spec. After this, format changes cost real rework.

## Phase 1 — audio engine, on a laptop · 4–6 weeks, no hardware

| ID | Package | Owner | Stream | Status |
|---|---|---|---|---|
| WP-06 | Block device layer, superblock, index commit | Agent | 1 | Exact 289/289 mount plus 8/8 writability and 34/34 NOT_MOUNTED product observations are independently accepted and integrated. Source/helper design and complete-package acceptance remain held |
| WP-07 | Chunk allocator, copy-on-write Side B | Agent | 1 | PR #112 is integrated at main `be7f8f2...` with exact independently observed history intact. Acceptance remains only the two recorded observations; invented refusals, excluded behavior, source and complete-package acceptance remain held |
| WP-08 | Playback, seek, variable-rate scrub | Agent | 1 | Exact ten corrected-cadence observations plus 16/16 set-side/warm-start product evidence are independently accepted and integrated via #171. Source, complete package and listening/goldens remain separate |
| WP-09 | Record: overwrite, overdub, splice | Agent | 1 | Exact 26/26 product observations are independently accepted and integrated via corrected verifier-first PR #167. The package's explicit history/crash/golden and other excluded coverage remains outstanding |
| WP-10 | Crash-injection harness | Verification | 2 | Crash infrastructure and narrow independent mount package landed; complete crash/operation/state run not yet green |
| WP-11 | CLI harness and golden-file regression suite | Verification | 2 | Seven exact product PCM outputs independently match verifier candidates byte-for-byte, but remain unlistened and are not accepted goldens; golden CI remains red |
| WP-12 | Re-spool / defragment pass | Agent | 1 | Exact 8/8 product evidence is independently accepted and integrated through the #180 chain. WP-12a continuation/BUSY/re-entry/FAULTED coverage and complete acceptance remain outstanding |
| WP-13 | Embedded-readiness audit | Agent | 1 | Held #20 measurements: instance 156456 B, stack 1536/8192, rodata 1040/32768; allocator/funnel gates green. Implementer evidence, not package acceptance |
| WP-36 | Slot capability model | Agent | 1 | **COMPLETE / independently accepted.** Verification PR #57 accepted the frozen package after the deterministic 5/5 precursor plus the exact 100,000-sequence / 1,997,914-operation literal-NULL source-slot campaign. Product PR #200 integrated the exact accepted tree unchanged at main `e4a3565...` |

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
| WP-24 | Cartridge shell and carrier PCB | Either | hardware | **Phase 4; parked in Phase 1.** Michael's 21 Sep SURGE-OML-01 handling result withdraws 86 × 54 × 12 mm as the owner taste target: both printed media dummies were too large and the intended reference class is memory-card-like, with the microSD hidden/edge-slotted rather than cassette-planform media. No replacement dimensions are issued and no reprint/redesign is scheduled. Resume only on an explicit WP-24 request; then Hardware must start from the smaller reference class rather than silently inheriting 86 × 54 × 12 |
| WP-25 | Abuse testing | You | hardware | **Phase 4; parked as Phase 1 activity.** Guardrail 13 remains binding and still requires ruggedization designed and tested before final enclosure CAD — the guardrail is not parked, only the shock/load-path matrix, failure-mode matrix, drop/shake protocol and staged physical trials are. Held PR #92 remains historical/held evidence; no independent method or physical acceptance is claimed and the fabrication/safety gate remains closed. Resume when Phase 4 opens, when enclosure CAD approaches finalization, on an explicit request, or in an authorized hardware round. Retrospective intake #130 is filed/closed; this package entry plus Guardrail 13 are the durable record |

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
