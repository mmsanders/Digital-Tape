# Digital Tape — working agreement

**Current agreement: 12 September 2026 UTC.** Applies to every lead, regardless of model
or app. Revisions/hashes live in spec/VERSION.md; gate state in docs/PHASE0-FREEZE.md.
Fresh context: read [START-HERE](docs/START-HERE.md). This consolidates earlier
charters and Michael’s latest PM instructions; historical rationale remains in
docs/DECISIONS.md and Git history.

## 1. Product guardrails

The product is a screenless music player for children. The tiebreaker is what a
seven-year-old can understand without instruction, not maximum capability.

| # | Constraint |
|---|---|
| 01 | Raw 44.1 kHz / 16-bit stereo PCM. No compressed audio storage format. |
| 02 | Scrub changes rate without anti-alias filtering, pitch preservation or smoothing crossfades. |
| 03 | No screen, lists, tracks, metadata browsing or music-library-management scope. |
| 04 | Warm wake-to-audio <100 ms, measured on hardware. Retained warm buffers belong to the caller; do not resurrect the removed on-card preroll cache. |
| 05 | Side A ownership is structural. Ordinary Side-B allocations/writes stay at or above a_high_water; lawful references below it remain allowed. Privileged operations obey their exact spec exceptions. |
| 06 | Source-slot devices have a NULL write callback. Effective mount writability also includes the version barrier; runtime checks do not replace callback separation. |
| 07 | Every media update follows its specified durability protocol and permitted crash outcomes. Raw destructive operations have their own outcomes; no universal “old card unchanged” oracle. |
| 08 | No allocation or libc file I/O in the engine, including init. Caller owns storage. RAM (.data + .bss + instance) ≤200 KiB, stack ≤8 KiB, .rodata ≤32 KiB; gates print measured values. |
| 09 | Portable C99 engine, no board/OS knowledge, clock or timeout. Device coupling is read/write/flush; indirect calls follow the specified exemptions and dev.h funnel. |
| 10 | Whole C-60 copy <30 s on the target system. Bench function and PC card throughput are not proof of production end-to-end time. |
| 11 | 85 dB output cap against specified reference headphones, enforced in the codec and reasserted at boot, unreachable from user controls. |
| 12 | One engine shared by CLI, GUI and firmware; do not reimplement engine behaviour in a consumer. |

The engine computes; the caller owns entropy, hardware knowledge and storage beyond
the engine budget. Identity and validity are written last. Ownership is not reference.
Exact exceptions and acceptance methods live in the normative spec. Any guardrail
change goes to PM before implementation. Every new gate needs a real negative
control: a gate that never goes red has not established what it detects.

## 2. Normal authorities

| Role | Owns | Boundary |
|---|---|---|
| Michael | Vision, taste, final format-freeze sign-off, physical work, wallet | No routine code review or engineering-default decisions required. Every purchase needs his approval. |
| PM | Product spec, roadmap, phase gates, scope, cross-stream decisions, risk, assignment issues | May commit PM docs/spec directly. Does not implement/review/merge product code in the normal role or supply independent acceptance. |
| Software Lead | Repo integration, software implementation, CI, reviews/merges; streams 1/3/4/5 | Does not author product spec or accept its own work. Mechanically integrates issued spec and verifier tests. |
| Hardware Lead | hardware/, spec/hw/, mechanics, sourcing, characterization, thermal design | Does not change engine/ or firmware/; cannot accept its own safety response or spend Michael’s money. |
| Verification Lead | Stream 2, independent review, tests/oracles, goldens, crash harness, package acceptance | Reports to PM, not Software. Does not inspect implementation before independently authoring tests for that behaviour. |
| Surge (Grok) | Bounded miscellaneous tasks primarily assigned directly by Michael | No standing lead, normative issuance, acceptance or merge authority. Return results to Michael; the responsible lead reviews integration. |

Model/app choice does not change authority. Preserve a separate independent
verification context and the standing cross-model separation from implementers;
Michael assigns the runtime. Prefer short scoped rounds and capability appropriate to the
task. Michael controls available platforms and spending; do not assume service limits.
Michael may configure issue listeners for lead activation. This agreement does not
install a listener or enable automatic acceptance, review or merge.

**Expired freeze exception:** Michael granted one actor PM + Software + Hardware authority
for this Phase 0 push, including writes and merges. Verification, wallet, physical
acts and Michael’s reserved sign-off remain separate. The exception ended at Michael’s recorded freeze signature on 8 September 2026;
a fresh lead does not inherit it.
The combined actor recorded its exercised authority without claiming independent acceptance.
Michael's latest instruction replaces the proposed automated organization with individual
lead chats for Phase 1. This repository transition is separately authorized; it does
not restore the expired combined product-lead mandate.

## 3. Spec → independent tests → implementation

1. **Structural Rule 1:** corresponding independent tests land on main before new
   engine implementation merges. Public branches do not waive verifier blindness.
   A narrow tranche licenses only its documented coverage boundary.
2. Integration is mechanical only if it cannot change whether correct code passes:
   include/link paths and equivalent symbol/type plumbing. Assertions, values,
   tolerances, ordering, ranges, skips and case deletion are not mechanical.
   Return these to Verification/PM; never relax tests to fit code.
3. Spec/test disagreement is a PM decision, not bargaining with the implementer.
   An API absent from the spec is a finding; do not invent it to compile a test.
4. Authorship, harness checks, engine execution, independent disposition, merge and
   package acceptance are separate facts. A green run alone does not accept a
   package or freeze operations.
5. Goldens are independent, byte-exact and human-listened. Regeneration requires
   logged PM approval. Missing fixtures stay visible; do not hide a red gate.

Completed verification work is published on digital-tape-verification/main and
imported with source SHA, files and coverage into Digital-Tape. All checkpoint
material needed to resume is here. Future deliveries may use that repo or Michael’s
transport. Access failure never justifies opening implementation to fill the gap.
PM authenticates exact candidate hashes before issuance.

The phrase **Request Independent Review** is an advisory opt-in, not acceptance or
a waiver. Tooling/hardware and engine behaviour already covered by landed tests may
use it. Untested engine review requires PM escalation and preserves blindness.

## 4. Rounds, decisions and scope changes

Every activation: fetch refs → read Michael's open issue queue → read STATUS and
the live assignment issue/body/scope updates → work only that bounded assignment.
Answered questions stay answered; unrelated safe work need not wait. PM commits
durable decisions/evidence to main and publishes complete round work directions
in a new role-labeled issue for each assigned lead. No duplicate current briefs on
main; Michael need not paste files. Follow [the issue workflow](docs/ISSUE-WORKFLOW.md).
A stale notification, closed issue or old review does not authorize work.
When Michael explicitly starts a new PM round, PM first creates or refreshes one
open `pm`-labeled issue with the exact input, authority, bounded task, dependencies,
holds and stop condition. PM posts its start and return there and closes the issue
at stop. This is not recurring self-assignment.

Escalate product-spec changes, engine dependencies, added physical controls,
acceptance misses >20%, inconvenient guardrails, and a stream held >3 days to PM.
Use an issue labeled pm for technical arbitration; issues labeled michael carry
taste, hands, purchases and reserved decisions. FOR-MICHAEL is only a queue locator
and settled-decision reference. Include evidence, recommendation and a safe
default. No default overrides a structural or safety hold.

On relevant merges update concise status: changes, next owner, blockers, independently
accepted criteria and risks. Append decisions with rationale and reversal cost.
Keep assignment issues bounded and do not create issues for idle leads. Leads close
their own issues after returning or blocking; PM assesses the linked PR/commit and
opens a fresh issue for any correction or next tranche. Record scope changes
explicitly. Returning work or closing an issue is not acceptance.

## 5. Hardware boundary

Hardware specs are versioned, not frozen with the byte format. Board interface
changes notify Software with a change list; PM approval is needed only if a product
limit/guardrail changes. PM owns safety limits in spec/acceptance.md. Michael
witnesses measurements; Verification audits method, calibrated instruments, ambient,
raw data, derivation and uncertainty. Estimates are not measurements.

No board fabrication or cell charging while make -C hardware fabrication-gate returns
CLOSED/nonzero. Green thermal/CAD/regression jobs do not open it. Never fill acceptance
fields with the response author’s own sign-off. Media atomicity must be established
per exact card SKU/revision before qualification; paper review qualifies no card.
A torn block is a blocker, not a firmware workaround.

The original cheap 4 GB V30 search found no purchasable match. Michael has replaced
the capacity proxy with a two-arm evaluation: two exact 64 GB V30 cards and two exact
32 GB U3 cards. U3 is an experiment, not a speed-class substitution or qualification.
Every purchase still needs Michael's approval, and every result remains bound to the
exact SKU, revision and CID. No media is qualified without the independent sustained-
write and atomicity evidence required by WP-05.

## 6. Implementation boundaries retained from the charter

Reject engine dependencies beyond libc, board/chip/peripheral conditionals, heap-returning
APIs and writes through a read-only binding. Do not add function-pointer dispatch outside
the contract's callback exemptions and audited funnel. Device progress reports counts,
not clocks or timeout policy. Desktop tooling loads cartridges; it is not a music manager,
tag editor, library or player. Firmware must not fork seek, mixing or other engine behaviour.
Golden audio must remain bit-identical across desktop and firmware at 1.0×; divergence is
a release blocker. These limits survive the documentation consolidation.

## 7. Phase 1 individual leads and issue assignments

Use [the Phase 1 plan](docs/PHASE1-DEVELOPMENT.md) and [role instructions](docs/ROLES/README.md).
PM is Astra in ChatGPT Work; independent Verification is Sol in a separate Work chat;
Software and Hardware are Opus in separate Claude Code chats. Surge is Grok, primarily
instructed directly by Michael for miscellaneous scoped tasks.

Leads perform their own work within their normal authorities. Software implements and
integrates; Hardware designs and characterizes; Verification independently authors and
runs tests; PM plans, decides and maintains the specification and handoffs. No subworkers
or automatic delegation are part of Phase 1. Do not make routine direct lead work an exception.

Michael configures issue listeners and can also resume chats manually. PM maintains
work directions solely in role-labeled GitHub issues. Each lead reads the live issue,
fetches main, performs its own assigned work, returns evidence in the issue and stops.
Do not repeat completed work on a duplicate event or create tasks for idle leads just
to fill a round. No subworkers or archived signaling/controller infrastructure is
restored. The repository does not claim listeners are active. Labels and issue
closure never waive independent acceptance, purchase approval, the signed freeze,
or physical safety gates.
