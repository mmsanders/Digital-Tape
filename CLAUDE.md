# Digital Tape — working agreement

**Current agreement: 6 November 2026 PST.** Applies to every lead, regardless of model or app.
Spec revisions and hashes are in spec/VERSION.md; phase and gate state is in docs/STATUS.md.
A fresh context starts at [START-HERE](docs/START-HERE.md). Rationale is in docs/DECISIONS.md
and Git history.

## 1. Product guardrails

The product is a screenless music player for children. The tiebreaker is what a
seven-year-old can understand without instruction, not maximum capability.

| # | Constraint |
|---|---|
| 01 | Raw 44.1 kHz / 16-bit stereo PCM. No compressed audio storage format. |
| 02 | Scrub changes rate without anti-alias filtering, pitch preservation or smoothing crossfades. |
| 03 | No screen, lists, tracks, metadata browsing or music-library-management scope. |
| 04 | Warm wake-to-audio <100 ms target on hardware, timed by the firmware itself and judged by Michael (ADR-208). Retained warm buffers belong to the caller; do not resurrect the removed on-card preroll cache. |
| 05 | Side A ownership is structural. Ordinary Side-B allocations/writes stay at or above a_high_water; lawful references below it remain allowed. Privileged operations obey their exact spec exceptions. |
| 06 | Source-slot devices have a NULL write callback. Effective mount writability also includes the version barrier; runtime checks do not replace callback separation. |
| 07 | Every media update follows its specified durability protocol and permitted crash outcomes. Raw destructive operations have their own outcomes; no universal “old card unchanged” oracle. |
| 08 | No allocation or libc file I/O in the engine, including init. Caller owns storage. RAM (.data + .bss + instance) ≤200 KiB, stack ≤8 KiB, .rodata ≤32 KiB; gates print measured values. |
| 09 | Portable C99 engine, no board/OS knowledge, clock or timeout. Device coupling is read/write/flush; indirect calls follow the specified exemptions and dev.h funnel. |
| 10 | Whole C-60 copy <30 s on the target system. Bench function and PC card throughput are not proof of production end-to-end time. |
| 11 | 85 dB output cap on the headphones in use, enforced in the codec and reasserted at boot, unreachable from user controls. Checked with a phone sound-level app at ≤80 dB to allow for its error (ADR-208); never raised above the measured reading. |
| 12 | One engine shared by CLI, GUI and firmware; do not reimplement engine behaviour in a consumer. |
| 13 | Kid-resistant mechanical design is a first-order requirement. The assembled player and cartridge must tolerate foreseeable drops, shaking and rough handling without exposing or loosening the battery, creating sharp or hazardous detached parts, ejecting the cartridge, exposing live conductors, or silently losing the basic playback controls. Ruggedization is designed and tested before final enclosure CAD, not added afterward. |

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
| Verification Lead | Stream 2, independent review, tests and oracles, goldens, crash harness, package acceptance | Reports to PM, not Software. Does not inspect implementation before independently authoring tests for that behaviour. |
| Surge (Grok) | Bounded miscellaneous tasks primarily assigned directly by Michael | No standing lead, normative issuance, acceptance or merge authority. Return results to Michael; the responsible lead reviews integration. |

Model/app choice does not change authority. Preserve a separate independent
verification context and the standing cross-model separation from implementers;
Michael assigns the runtime. Size rounds to an outcome (ADR-195) and use capability appropriate to the
task. Michael controls available platforms and spending; do not assume service limits.
**Routing:** Michael starts each issue manually; PM posts issues only, with no kickoff
messages and no active listener. Details are in §7.

**Platforms:** the desktop tools target Windows 11 x64; macOS is deferred; Linux stays as CI.

## 3. Spec → independent tests → implementation

1. **Structural Rule 1:** corresponding independent tests land before new engine
   implementation. Public branches do not waive verifier blindness. A narrow tranche
   licenses only its documented coverage boundary.

   **They land in history, not necessarily in a separate merge.** A tranche is one
   branch carrying two commits: an import commit byte-identical to a verifier
   publication whose hash predates it, then the implementation commit. The protocol is
   Verification publishes → Software returns that branch → CI proves it → Verification
   disposes blind → PM disposes. What disappears is a round whose only product was a
   separate merge commit; what does not disappear is blindness.

   Review-discovered regressions on a held branch preserve the original reviewed
   lineage (ADR-206). A new, immutable review package may follow the reviewed
   implementation only under the independently tested provenance/order contract:
   full reviewed-ancestor identity, independent publication attestation, import
   before the corresponding corrective implementation, no prior imported-tree
   edits and no combined import/fix commit. This does not claim retrospective
   tests-first coverage or waive the rule for unrelated new behavior. The gate
   correction is independently disposed and integrated through PR665/ADR-209.
   The current gate authenticates that narrow route; all other ordering stays strict.

   The guarantee moved into CI, it was not dropped.
   `.github/workflows/evidence-integrity.yml` proves the imported subtree is
   byte-identical to the declared publication (`tests/IMPORTS.json`), that ordinary
   verifier-tree changes precede `engine/`/`firmware/` changes, that late review imports
   satisfy the independently attested exception, and that no commit does both.
   Package self-tests/offline replay are green, and spec bytes in evidence trees
   match `spec/VERSION.md`.
   `tools/ci/verify-structural-rule-1.py` proves that ordering check goes red.
   The implementer still cannot tune an assertion: the tree it imported is fixed by a
   hash Verification published first, and `tests/IMPORTS.json` is Michael-owned in
   CODEOWNERS, so declaring a different tree is not a lead's to do quietly.
   `.github/workflows/verifier-publication.yml` adds the cross-repository half (ADR-157):
   every cited `source_commit` must be on `digital-tape-verification/main` with its
   declared tree. A PR head is not a publication; Verification merges its own.
2. Integration is mechanical only if it cannot change whether correct code passes:
   include/link paths and equivalent symbol/type plumbing. Assertions, values,
   tolerances, ordering, ranges, skips and case deletion are not mechanical.
   Return these to Verification/PM; never relax tests to fit code.
Private or unpublished scaffolding is not an exception to a task's tests-first rule.
Declare interfaces before code where needed; publish the independent expectations
before implementing covered behavior.

3. Spec/test disagreement is a PM decision, not bargaining with the implementer.
   An API absent from the spec is a finding; do not invent it to compile a test.
4. Authorship, harness checks, engine execution, independent disposition, merge and
   package acceptance are separate facts. A green run alone does not accept a
   package or freeze operations.
5. Goldens are independent, byte-exact and human-listened. Regeneration requires
   logged PM approval. Missing fixtures stay visible; do not hide a red gate.
6. **Proportional evidence (ADR-195).** A criterion is proved by a test of the outcome it
   names plus a negative control that shows the test can fail. Mechanism forensics (kernel
   traces, PID/handle attribution) are required only where a criterion names them. A method is
   qualified by its own controls in the tranche that uses it, not in a separate round.

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
**Required reading is exactly four documents plus the issue:** `AGENTS.md`, `CLAUDE.md`,
`docs/STATUS.md` and the lead's own charter, with the live issue body and its scope
updates. Everything else — `docs/DECISIONS.md`, `docs/VERIFICATION-INTEGRATION.md`,
`docs/PACKAGES/README.md`, `docs/PHASE0-FREEZE.md` and the frozen specs — is **read on demand, for the sections the tranche touches**, entered
through [the decisions index](docs/DECISIONS-INDEX.md) and
[spec/NAVIGATION.md](spec/NAVIGATION.md). Not reading a document the tranche does not
touch is compliance, not a skipped step.
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

**Standing size budget.** `docs/STATUS.md` is capped at **120 lines** and
`docs/VERIFICATION-INTEGRATION.md` at **150 lines**. Both are state tables, not
chronicles: current boundary, current coverage, current owner. When an update would
exceed the budget, the oldest content moves under `docs/archive/` **in the same commit**,
with a pointer and the relocated file's recorded SHA-256. Nothing is summarised away,
nothing a disposition cites is deleted, and every hash stays reachable. A lead that
cannot state the current position in 120 lines does not yet know it.

**Raw evidence over 1 MiB goes to a release asset, not the tree.** Commit the
SHA-256 beside the run and cite the hash; the hash is the citation, not the bytes.
Relocation never deletes — the blob stays in history because dispositions cite it,
and Guardrail 3 forbids rewriting history. A relocation that breaks offline replay
of a retained bundle is not done: the fetch-and-verify step ships with it.
`.github/workflows/repo-hygiene.yml` enforces the budgets and the 1 MiB limit, and
`tools/ci/verify-docs-hygiene-gate.sh` proves that gate can go red.

## 5. Hardware boundary

Hardware specs are versioned, not frozen with the byte format. Board interface
changes notify Software with a change list; PM approval is needed only if a product
limit/guardrail changes. PM owns safety limits in spec/acceptance.md. Michael
witnesses measurements. Physical and timing criteria use the hands-on method of ADR-208:
firmware self-measurement plus Michael's recorded verdict in docs/MICHAEL-CHECKS.md, about
$30 of instruments, no calibrated-instrument audit. Verification checks that the record and
logs match the candidate. Estimates are not measurements; a firmware timer reading is one.

No board fabrication or cell charging while make -C hardware fabrication-gate returns
CLOSED/nonzero. Green thermal/CAD/regression jobs do not open it. Never fill acceptance
fields with the response author’s own sign-off. Media atomicity must be established
per card model (brand, part number, capacity) before qualification, by the Teensy
self-run power-cut test (ADR-208); paper review qualifies no card.
A torn block is a blocker, not a firmware workaround.

Michael owns three PNY 64 GB V30 cards. Card identity is brand, part number and capacity
from the card and package, plus a photo. The CID is logged by the firmware over native SD
when available and gates nothing; no reader is bought for it (ADR-208). No media is
qualified without the sustained-write and atomicity evidence required by WP-05.

## 6. Implementation boundaries

Reject engine dependencies beyond libc, board/chip/peripheral conditionals, heap-returning
APIs and writes through a read-only binding. Do not add function-pointer dispatch outside
the contract's callback exemptions and audited funnel. Device progress reports counts,
not clocks or timeout policy. Desktop tooling loads cartridges; it is not a music manager,
tag editor, library or player. Firmware must not fork seek, mixing or other engine behaviour.
Golden audio must remain bit-identical across desktop and firmware at 1.0×; divergence is
a release blocker.

## 7. Individual leads and issue assignments

Each phase runs with individual leads routed by role-labeled GitHub issues. The current
phase plan is [the Phase 3 plan](docs/PHASE3-PLAN.md); closed phases are in docs/archive/.
Role charters are in [docs/ROLES](docs/ROLES/README.md).

PM has no fixed model; Michael assigns the runtime. Software is Claude Code on Michael's
local Windows machine, model chosen by Michael, one active context per task. Verification
is a separate, independent context. Hardware is a separate context. Surge (Grok) takes
miscellaneous tasks directly from Michael.

Leads do their own work within their authorities, with no subworkers or automatic
delegation. Michael starts each issue manually. PM posts issues and sends no kickoff
messages; no listener is active. A lead reads the live issue, fetches main, does the work,
returns evidence in the issue and stops; it may continue into the next named stage of the
same issue when that stage's input has already arrived. Do not repeat completed work on a
duplicate event or create tasks for idle leads. Labels and issue closure never waive
independent acceptance, purchase approval, the signed freeze or physical safety gates.
