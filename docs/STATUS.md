# STATUS

**Updated:** 2026-08-31 · **Phase:** 0 (format freeze) · **Updated by:** Software Lead

---

## What changed since last time

**Charter revised (31 Aug) and reviewed.** Four changes: the Verification Lead is now ChatGPT
rather than a Claude instance and has no repository access; a new three-rule seam governs the
exchange with it; action 02 must resolve two newly-named spec defects before freezing; and those
two defects are stated with a proposed resolution.

Absorbed into `CLAUDE.md`. My full response is in **`docs/REVIEW/software-lead.md`** — the PM
asked each lead to file there so it can process all three together.

**Headline from that review:** both defects are real. Defect B's proposed resolution
(*"`tape_dup` assigns the destination a freshly generated UUID"*) **cannot be implemented as
written** — the engine has no entropy source and may not acquire one under guardrails 08 and 09.
The fix is one parameter: the caller supplies the UUID. Defect A's resolution is sound but
requires a `tape_seek` and a position getter that **are not in the plan's API list at all**,
despite WP-08's acceptance criteria assuming seek exists.

**Plan Rev B received and checked.** WP-02 and WP-03 are unblocked. Its numbers are internally
consistent — the 22 KB Side B map figure independently confirms 12-byte index entries, and
byte rate, tape size, chunk duration and copy rate all reconcile exactly. Adopted as the input
to both specs (ADR-007).

**WP-01 — repository scaffolded.** Tree per Charter §03, `CLAUDE.md` carrying the twelve
guardrails verbatim, four `docs/` files. Each stream directory carries its own README so a
sub-agent dropped into one subtree can state the constraints without reading the whole repo.

**Charter §09 action 04 — CI stood up on the empty engine.** Five gates, all failing, which is
the point. Build at `-Werror`; allocation audit by undefined-symbol reference; recursion audit
by call-graph cycle detection; static RAM against 200 KB; golden-suite runner.

Each audit was verified against deliberately violating code, not only against emptiness. Two
real defects were found and fixed: unrelocated external calls in an unlinked archive read as
self-recursion, and tail-call recursion compiles to `jmp` and bypassed the call-graph walk.

**Correction to the last report.** That CI work was labelled WP-04. That is wrong — WP-04 is
Michael's transport spike. The three audits are **WP-13**'s acceptance criterion wired ahead of
Phase 1; `run-golden.sh` is **WP-11** runner wiring. Corrected in `PACKAGES/README.md` and
`tools/README.md`. The commit message on `f3b5d54` still carries the wrong label.

**`docs/PACKAGES/README.md`** now indexes all 37 packages with owner, stream and status.

## In flight

| Work | Owner | State |
|---|---|---|
| WP-01 repo scaffold | Software Lead | Done, unconfirmed |
| WP-13 gates (early) / WP-11 runner | Software Lead | Wired, 5/5 red as intended |
| Charter review packet | Software Lead | **Filed** — `docs/REVIEW/software-lead.md` |
| WP-02 `spec/tapefs-v1.md` | Software Lead | Drafting — **will not freeze** pending Verification |
| WP-03 `spec/engine-api.md` | Software Lead | Next, after WP-02 |

## Blocked

Nothing is blocked. Two open questions are being worked around rather than waited on:

**1. The preroll cache does not fit the engine's memory budget.** Plan §04 sizes the preroll
at 512 KiB and §05 says those three seconds "come out of RAM while the card comes up". The
engine's static budget is 200 KB (guardrail 08, WP-13). 512 KiB does not fit in 200 KB, and
this is not a rounding problem — it is 2.5×.

Recommendation: the preroll buffer is **caller-provided**, passed into `tape_mount`, so it sits
in firmware's budget (the RT1062 has OCRAM and external PSRAM) and not the engine's. That keeps
both guardrail 08 and guardrail 09 intact and costs one parameter. Raised as issue #3; WP-03
proceeds on this assumption and says so.

**2. Side B can only grow to 1.50× its original length.** A 32 KiB index slot holds ~2,725
entries at 12 bytes; a full 90-minute tape needs 1,817. Splicing adds entries. The plan does
not say what happens when a splice would overflow the slot, and there is no screen to explain
it. Raised as issue #4 — the mechanism is the Software Lead's call, but *what a child
experiences at the wall* is Michael's, so it is also queued in FOR-MICHAEL.md.

**3. The Verification seam has no stated mechanism.** The Verification Lead has no repository
access and receives `spec/` as text — but the charter does not say who carries the text. This is
the highest-frequency interaction in the project: Stream 2 works against every spec revision and
signs off every work package. If the transport is a human relaying documents, then the structure
built to remove Michael as a bottleneck has a human bottleneck at its centre, and Phase 1 should
be scheduled against the relay rate rather than agent throughput. Detailed in the review packet
§3.1; **this is the item I would most like answered before Stream 1 starts.**

**4. `main` branch protection is not verified.** Plan §03 says "nothing merges to main without
your review". Repository settings are not the Software Lead's to change.

## Acceptance criteria flipped to passing

None. No Verification Lead is assigned, so nothing can be independently signed off — including
WP-01 and the gates above, which are the Software Lead's own claims about its own work.

## What will hurt in three weeks

- **The Verification Lead exists on paper but not yet in practice**, and Phase 1 is about to
  start. The charter is explicit that tests are written against the spec *before or alongside*
  the implementation, never after reading it, and that ordering cannot be recovered
  retroactively. It is now also the reviewer that has to attack the two spec defects before the
  format can freeze — so it is on the critical path twice over.
- **Rule 1 of the seam is not enforceable as written, because the repository is public.**
  "Do not show it the engine implementation before it has written the tests" is discipline, and
  the charter's own reasoning (guardrails 05 and 06) says discipline is the weak form. I have
  proposed a structural version — engine implementation stays on unmerged branches until Stream
  2's tests land on `main` — which I can implement unilaterally if the PM approves. Review packet
  §3.2.
- **No Hardware Lead.** WP-34 (thermal budget) is a Phase 0 package and is not started. The
  plan is explicit that it is *"written before the schematic, not after"*.
- **The 90-minute question is open and it touches the format.** Plan §13 ask #02 asks Michael
  to confirm 90 minutes is worth the UHS-I risk; 60 minutes would hit the copy target on a much
  safer interface. That changes the Side A store from 952 MB to 635 MB. WP-02 will parameterise
  region sizes from a superblock field so the answer does not force a re-spec, but it should be
  settled before the format freeze rather than after.
- **CI is red on purpose and will stay red for weeks.** A permanently-red pipeline stops being
  read, and the first genuine failure will arrive against a background of red. Worth splitting
  the build gate out once WP-06 lands so it can go green independently of the fixtures.
