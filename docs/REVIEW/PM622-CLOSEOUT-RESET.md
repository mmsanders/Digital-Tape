# PM622 — Phase 2 closeout review and reset

**28 October 2026 PDT. New PM runtime, started explicitly by Michael ([#622](https://github.com/mmsanders/Digital-Tape/issues/622)).**
Inputs: Product main `4f5810b6672d8fb07d3648bb6c36e740fd4c50a3`, Verification main
`5512a2d0d7bd8135f4a10016d9469c612340737a`. Decisions are recorded in
[ADR-195](../DECISIONS.md#adr-195--phase-2-closeout-proportional-evidence-and-the-make-path).
The plan is in [the Phase 2 plan §8](../PHASE2-PLAN.md#8-closeout-plan-adr-195), and the
criterion-by-criterion state is in [the Phase 2 ledger](../PHASE2-LEDGER.md).

Michael asked for a fresh look: where are we, how do we close Phase 2 in three to five
rounds, and why has progress been slower than expected.

## 1. Where we actually are

In plain terms:

- **`tapectl` works on a real card on Windows 11.** On 13–14 October Michael provisioned a
  64 GB PNY card, loaded a full C-60, pulled the card out ten times mid-load, reinserted it,
  verified it and dumped both sides byte-identically. Verification passed all of that. The
  README byte check passed too. **Every WP-14 criterion except A6 was independently passed by
  14 October.**
- **A6 (large media) is held on a tracing technicality, not a failure.** On 19 October Michael
  ran `verify` on that 64 GB card under a kernel trace. `verify` returned OK, and the trace shows
  two successful 512-byte reads of the card's last sector, at byte 62,537,072,128, far above
  4 GiB. The trace checker still says FAIL because of four records from *other* file streams
  after the process exited, which it could not attribute. Two weeks of method work since then
  (route designs, ETW schema decoders, a missing `SplitIo32` schema) have not changed that.
- **Ingest (WP-16) is built and integrated.** Verification cleared the exact source and it is
  on main. Every I1–I8 criterion has independent evidence, including Windows 11 byte-identity
  runs. What holds the last rung is a Windows "own-host" requirement: kernel-level proof that
  ingest never even attempts to open a block device, including failed attempts.
- **The app (WP-15) runs, but it cannot make a cartridge.** The window, drag-and-drop, ingest
  on drop, label editing, card discovery, messages and packaging are built, independently
  tested as components and integrated. **The Make button is hard-wired off.** `tapectl make`
  does not exist in the shipping binary. An internal, test-only composition core exists in
  `host/internal_make` and has independent tests, and the S3 test package
  (`tests/wp15_cards_make_r1`) has been on main since 18 October. The production path is
  held behind a requirement to prove, before writing code, how the device handle is bound to
  the safety check.
- **Q-P2-1(b)**, the copy-throughput architecture ruling, has been undecided since the plan
  was written. It needs only a PM decision.

So the Phase 2 milestone, "someone who is not Michael makes a playable cartridge from a
folder", has never been attempted end to end, because the one button that does it has never
been built.

## 2. Why progress slowed

Phase 2 has used about 240 Product issue and PR numbers (#381 → #622), about 210 Verification
numbers, 33 ADRs (162–194) and 63 review documents in 23 days. Rungs went from 3/12 on
13 October to 6/12 on 17 October, then to 7/12 on 27 October. The last rung came from
integrating source that had already been cleared. The work was real and careful. Most of it
was not aimed at the exit gate. There are five causes.

### 2.1 The evidence demanded grew past what the criteria ask

The criteria are about outcomes. A6 says "all commands work on a 64 GB card, at addresses past
4 GiB". Over time the required proof turned into mechanism forensics:

- kernel ETW traces joined by `IrpPtr` and `FileObject` lifetimes (six method corrections,
  WP14-NATIVE-CAPTURE §3);
- "process-attributed detection of actual device-open attempts, including failed, transient
  and zero-access opens" for G1 (APP-1A §6);
- "binding before authorized write-mode access" for S3, with "no weaker guarantee adopted"
  (APP-1A §7);
- parent PID, OS start time and child-receipt lineage for a window that opens and closes.

Each of these needs a method. The method needs controls. The controls need a qualified
environment. When a Windows script policy refused a control script (#359), a whole round
(#361) went into qualifying the controls in CI so that one later session could run. That
session (#618) proved that the app's background card poller ran `tapectl cards` twice with
no card present and got `offered 0`. No criterion moved.

These obligations were never written into the WP-14/15/16 criteria. They came in one ADR at a
time, and each was recorded as "no weaker guarantee is adopted", so none could be removed.

### 2.2 Work went to what could be proved, not what was missing

When the S3 make path was held, the queue moved to app work that could advance without it:
poller receipts, console-window behaviour, diagnostics, build-count exceptions, a
"one-session budget". All of it was useful, and none of it was on the critical path. The
critical path, Make, has had no implementation issue since S3 was held around 18 October.

### 2.3 Tranches got smaller and meta-rounds multiplied

Recent round titles include "run unchanged C01/C02 once in Claude Terminal", "close the
build-count exception", "qualify held612 session method in Windows CI" and "admit and dispose
one corrected612 native poller receipt session". Under manual activation (ADR-192), each round
costs Michael three context starts and a PM review. The Phase 1 retrospective already found
the fixed cost of a round exceeds its variable cost. Phase 2 rounds got smaller anyway.

### 2.4 The rung measure hid progress and the gap

WP-15 sat at 1/4 the whole time, because rung 2 needs complete coverage, including native and
S3. Weeks of real app progress showed no movement. More importantly, the measure never
showed the single fact that matters: the app cannot make a cartridge. There was no
criterion-by-criterion ledger saying which of A1–A9, I1–I8 and G1–G5 are passed, have
evidence awaiting disposition, or are not started.

### 2.5 The documents stopped being readable

Current status lines read like
"616 integrated090551e,116SUCCESS/1guardedBUILDskip". Each line meets its line budget, but no
one can read the state at a glance, including a fresh lead. Every assignment is mostly a list
of prohibitions. That makes it hard for anyone, Michael included, to see what is next.

## 3. What changes (ADR-195)

1. **Proportional evidence.** A criterion is proved by a test of the outcome it names, plus a
   negative control showing that test can fail. Mechanism proofs (kernel traces, PID lineage,
   handle forensics, attribution of failed opens) are required only where a criterion names
   them. Where the operating system already enforces a property, that enforcement is the
   proof. For example, an unelevated Windows process cannot open a physical disk at all.
2. **No meta-rounds.** A test method is qualified by its own controls in the same tranche that
   uses it. No separate round to qualify a method, admit a session, grant a session budget or
   approve a build count. Rebuilding a candidate is free. Its identity is recorded, not
   rationed.
3. **Witnessed human runs count as evidence.** Michael's witnessed record (screenshots, logs,
   his statement) is reviewed for consistency with the criterion, as G2 always was. It is not
   held to chain-of-custody forensics.
4. **Outcome-sized rounds.** Each lead issue carries its work to the next natural handoff,
   across stages, with Verification disposing Software's exact head directly (ADR-158). PM
   enters at round end. Each round must close named ledger rows.
5. **Build the Make path now.** `make` reuses the accepted WP-14 provision open and safety
   sequence and keeps that handle for load and verify. It is implemented now against the S3
   tests already on main, and disposed with its method description in one round.

What does not change: guardrails 01–13, the frozen engine and format (A8 pin `d96b4245`),
Structural Rule 1 for engine code, Verification's blindness and independence, WP-14 A4 disk
safety outranking everything else, and Make never shipping without independent disposition.
No criterion in WP-14/15/16 is weakened. Only the added proof obligations are withdrawn.

## 4. The roadmap

| Round | Software | Verification | Michael | Closes |
|---|---|---|---|---|
| **C1 (now)** | Build `tapectl make`, UAC elevation and the app's Make button; one Windows candidate | Re-dispose WP-14 and WP-16 under ADR-195; A6 negative control; author the WP-15 acceptance package and the C2 checklist; then dispose Software's head | Merge the PM622 PR, answer #623, schedule C2 | WP-14 4/4, WP-16 4/4, S3 built |
| **C2** | Fix defects found | Dispose Michael's run; G1/G3/G4/G5 | One ~45-minute session: install, make a real cartridge through the app, verify, dump, scripted error cases, one mid-make pull | WP-15 rungs 2–3 |
| **C3** | Final candidate if C2 found defects | Final WP-15 acceptance on the exact head | G2: his wife's unaided run, witnessed | WP-15 4/4, G2 |
| **C4** | — | — | Phase 2 sign-off | PM exit ADR: host scope frozen, Q-P2-1 recorded, goldens green |

C3 and C4 can share a day if C2 is clean. Q-P2-1(b) is ruled now, in ADR-195.

## 5. Questions for Michael

They are in [#623](https://github.com/mmsanders/Digital-Tape/issues/623). In short:

1. Do you accept the ADR-195 evidence reset? It is within PM authority, but it reverses the
   direction of several recent ADRs, so you should know and can veto it.
2. When can you do the C2 session (about 45 minutes at the Windows machine with a PNY card)?
3. Is your wife willing to be the G2 tester, and when? Please also pick the folder of music.
4. Optional: may Software and Verification continue straight into their next stage without
   waiting for you to restart them, as long as it is inside the same issue?
