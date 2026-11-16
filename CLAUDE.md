# Digital Tape — working agreement

**Current agreement: 16 November 2026 PST ([ADR-210](docs/DECISIONS.md#adr-210--light-process-outside-the-engine)).** Applies to every lead, regardless of model or app.
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
change goes to Michael before implementation. Every new gate needs a real negative
control: a gate that never goes red has not established what it detects.

## 2. Who does what

| Role | Owns | Boundary |
|---|---|---|
| Michael | Vision, taste, physical work, wallet, every bench verdict, final say on everything | Every purchase needs his approval. No routine code review is expected of him |
| Lead (Software or Hardware) | The task Michael gives it, end to end: code, its tests, docs, the PR | One lead per task. Hardware does not change `engine/`; nobody spends Michael's money |
| Verification | Independent tests and review **for the strict track** (§3), and any review Michael asks for | A separate context from the implementer. Does not read an implementation before writing tests for it |
| PM | Planning, spec revisions and arbitration, **when Michael asks for it** | Optional. Not a required step between Michael and a lead |
| Surge (Grok) | Small tasks from Michael | Returns results to Michael |

Model and app choice do not change authority. Michael assigns runtimes and controls spending;
do not assume service limits. No subworkers or automatic delegation unless Michael asks.
The desktop tools target Windows 11 x64; macOS is deferred; Linux is CI.

## 3. Two tracks

**The test for which track applies is the path, not the importance of the work.**

### Strict track: the engine and the format

`engine/`, the frozen product spec, the goldens and the imported verifier packages under
`tests/`. A bug here destroys a child's tape on every device, so:

- independent tests are published by Verification before the implementation lands
  (Structural Rule 1), and the implementer never edits them;
- Verification disposes the result, and CI enforces the import identity and ordering
  (`evidence-integrity.yml`, `verifier-publication.yml`, `tests/IMPORTS.json`);
- goldens are byte-exact and regenerated only with Michael's approval;
- any spec or guardrail change is Michael's decision before implementation.

The full procedure is [docs/ENGINE-CHANGES.md](docs/ENGINE-CHANGES.md). The engine is pinned
at `d96b4245` and the format is frozen, so expect to need it rarely. **Do not start
strict-track work without Michael saying so in as many words.**

### Light track: everything else

Firmware, the desktop tools, hardware, tooling, CI and docs.

1. **One lead, one session, one PR.** The lead that writes the code writes its tests and
   docs. No interface-declaration round, no separate binding round, no per-round PM issue.
2. **Tests are proportionate.** Test the outcome, and show once that the test can fail.
   Prefer a host-side test that runs in CI. Do not build a checker for evidence a person
   will read.
3. **Bench results are Michael's.** The firmware prints its numbers and its build id; Michael
   tries it and adds a row to [MICHAEL-CHECKS](docs/MICHAEL-CHECKS.md). That row is the
   record. No schema, no capture bundle, no hash linkage (ADR-208).
4. **Merge.** Open a PR. Merge it when CI is green, unless it touches a Michael-owned path
   (CODEOWNERS), a guardrail or a safety limit: those wait for Michael.
5. **Review is opt-in.** Michael may ask for an independent review of anything. A lead
   should suggest one for code that writes to a cartridge, sets an output cap or touches
   disk selection in the desktop tools.

Light does not mean careless. These still bind every track:

- the guardrails in §1;
- the output caps, the CLOSED fabrication and charging gate, and purchase approval (§5);
- firmware calls the engine and never reimplements it (§6);
- one block per card write call until Michael lifts the batching hold;
- the desktop tools' disk-safety rules (WP-14): never write a disk the user did not pick.

## 4. How work runs

**Starting.** Michael starts every piece of work, either by saying so in a session or by
opening an issue. What he asks for is the assignment. Read `AGENTS.md`, this file and
`docs/STATUS.md`, then the task. Read anything else only for the sections the task touches,
through [the decisions index](docs/archive/DECISIONS-INDEX-ADR-001-209.md) and
[spec/NAVIGATION.md](spec/NAVIGATION.md). Not reading a document the task does not touch is
correct. A stale notification, closed issue or old review does not authorize work.

**Finishing.** Say what you did, what you did not do, and what Michael needs to do next.
Then update `docs/STATUS.md` if the state changed. Use an issue only when work spans
sessions or needs Michael's hands; see [the issue workflow](docs/ISSUE-WORKFLOW.md).

**Writing for Michael.** Plain English, shortest thing that is complete. Link the PR and
let it carry the detail. **Do not recite commit hashes, tree hashes, run ids or check
counts** in reports, issues or status; give one short commit id only when identity is the
point. No disclaimers listing what a result does not authorize. If parts, money or
Michael's hands are the real blocker, say that first.

**Decisions.** Record a decision in `docs/DECISIONS.md` only when it changes a guardrail,
the spec, this agreement or something expensive to reverse. Routine engineering choices
live in the code and the PR.

**Escalate to Michael:** a guardrail that is in the way, any engine or format change, an
added physical control, a target missed by more than 20%, and anything that costs money.
Give the evidence, a recommendation and a safe default. No default overrides a safety hold.

**Size budgets.** `docs/STATUS.md` is capped at **120 lines** and
`docs/VERIFICATION-INTEGRATION.md` at **150 lines**: current state, not history. Older
content moves under `docs/archive/` in the same commit. Raw evidence over 1 MiB goes to a
release asset with its SHA-256 committed beside the run. History is never rewritten.
`.github/workflows/repo-hygiene.yml` enforces this.

## 5. Hardware boundary

Hardware specs are versioned, not frozen with the byte format. Board interface
changes come with a change list for Software. Safety limits live in spec/acceptance.md
and change only with Michael's approval. Michael witnesses measurements. Physical and timing criteria use the hands-on method of ADR-208:
firmware self-measurement plus Michael's recorded verdict in docs/MICHAEL-CHECKS.md, about
$30 of instruments, no calibrated-instrument audit. Estimates are not measurements; a firmware timer reading is one.

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
