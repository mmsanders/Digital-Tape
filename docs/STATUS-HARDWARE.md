# STATUS — HARDWARE

**Updated:** 2026-09-02 · **Phase:** 0 · **Updated by:** Hardware Lead · **Reports to:** PM

The Hardware Lead's window into `hardware/` and `spec/hw/`. Companion to `docs/STATUS.md`,
which stays the Software Lead's. Review packets live in `docs/REVIEW/hardware-lead.md`; this
file is state, not argument.

**Scope:** WP-04, WP-05, WP-22–27, WP-29, WP-30, WP-34, WP-37.

---

## What changed since last time

**PM Decisions 001 received and acted on.** All four escalations answered. WP-34 unblocked, and
it is written.

**WP-34 — `spec/hw/thermal-budget.md` rev 0.1.** Estimates only; no measurements exist. It
found three things:

1. **The bulk thermal case is more comfortable than assumed, and the copy is thermally free.**
   30 seconds against a 621-second enclosure time constant raises bulk temperature ~0.5 K. A
   sealed case is fine. The charter's ~2.2 W did not count both microSD cards at sustained
   UHS-I — the real copy figure is 2.74 W — and it does not matter, because of the duration.
2. **The sustained worst case is not the copy. It is playing while charging**, which is also the
   most likely thing this device ever does. At 35 °C ambient that lands **within 0.2 K of the
   45 °C JEITA charge ceiling**. Not a damage problem: a device that silently stops charging on
   a warm afternoon, with no screen to explain itself. Four mitigations in §4; the cheapest is
   ADR-102.
3. **The solenoid one-shot does not close the hole it was specified for.** A retrigger loop
   delivers essentially full coil power through a correctly functioning one-shot. ADR-101 adds
   an RC lockout and a PPTC backstop for about fifteen cents.

The budget is **computed, not asserted** — `hardware/thermal/budget.py` generates its tables and
`make -C hardware thermal-check` fails if the document drifts from the model.

**WP-05 — parts order drafted, two carts.** Order 1a (~$115) is the six card SKUs and a rated
reader; it answers issue #5 and should go today. Order 1b (~$152) is the bench build. One of the
six cards is expected to fail, deliberately: a test where everything passes has not been shown
to discriminate.

**WP-04 — packet WP04-01 is built and sendable.** Nine printed carriers, a hook bar and a test
frame on one plate that fits a 220 × 220 bed, plus the card, the results template and the next
packet pre-planned against six possible outcomes. Hook depth bracketed 0.6–2.1 mm, wider than
the charter's suggestion so both endpoints are expected to be obviously wrong. Three
identical-geometry controls are hidden in the ranking (ADR-104).

**`spec/hw/board-rev-a.md` started**, mostly empty by design, carrying the `CHANGES` protocol,
the notification obligation, the test-point list, and the PM's SDR50 entry gate written down
**before** fabrication.

**Toolchain: CadQuery installed and working.** `make -C hardware` regenerates every artefact
from source. KiCad deliberately not installed — see Blocked.

**Every ruling in PM Decisions 001 is now logged.** It was cited in eight files but recorded in
none — `ADR-105`…`ADR-109` fix that, so the decisions survive without the memo. Issues #5–#8 are
closed with their resolutions, and mirrored into `docs/ESCALATIONS.md`, which had never carried
the four hardware escalations.

**Two things the memo asked for by name that I had missed**, both now in `spec/hw/board-rev-a.md`
(rev 0.2): §6 is the card SKU and measurement table §1 asks to live there, and §7 is the USB-C
cartridge-loading path that follows from the captive-card decision. §7 names **a firmware device
path that is in no work package** — the cost ADR-105 added. Raised for the PM.

**Hardware ADRs moved to a reserved `ADR-1xx` range.** My first four collided with four of the
Software Lead's on an unmerged branch; nobody would have seen it until the merge.

**`spec/` restructured per PM Decisions 001 §3.** `spec/hw/` created with its own README;
the superseded `spec/thermal-budget.md` placeholder deleted; `spec/README.md` now carries the
two-tier table. **These three touches are transcriptions of the PM's own decision, not Hardware
Lead spec changes** — flagged rather than assumed, and reversible in one commit.

---

## In flight

| Work | State |
|---|---|
| WP-34 thermal budget | **Rev 0.1 issued.** Estimates; WP-37 replaces them |
| WP-05 parts order | **Drafted.** Waiting on Michael to order |
| WP-04 packet WP04-01 | **Built.** Waiting on Q-006, sendable today on stated assumptions |
| `spec/hw/board-rev-a.md` | Skeleton. Accretes through WP-26 |
| WP-26 schematic | Not started — gated on the codec question below |

## Blocked

**Codec confirmed `ACTIVE` from NXP's own part page — the first primary-source confirmation of
any part on this board.** Specify **`SGTL5000XNBA3`**, 12NC 935430641557, **HVQFN32**, 5 × 5 ×
0.85 mm, 0.5 mm pitch, −40 °C to +85 °C. The `Obsolete` on the aggregator was real but attached
to `XNAA3`, retired with its punch-QFN line; `XNBA3` is NXP's own migration path. **A BOM written
from search hits would have said `XNAA3`.** WP-26 is unblocked.

**Two findings larger than the question that produced them.**

**1. The lead time is 39 weeks on a sole-source part.** Nine months, against a Phase 5 that plans
8–12 weeks and 2–3 spins. If we ever have to *order* this codec rather than pull it from a
distributor's shelf, the schedule is gone and no amount of good layout recovers it. **Order 1c
(~$110, twenty pieces) converts that into a box in a drawer** and is the cheapest schedule
insurance available anywhere on this project. Drafted; it should go with order 1a.

**2. NXP direct is not a channel we can use.** Minimum order 490 (tray) or 5000 (reel) against a
project needing perhaps twenty. The whole supply route is "a distributor happens to have stock",
which is true until it isn't — and I cannot check whether it is true now (H-02). If distributors
hold none, a second-source codec becomes an architectural question and a `pm-decision` issue.
Not raised yet, because $110 probably retires it.

**The same question is open for the RT1062 and nobody has asked it.** It is the other sole-source
part and it *is* the board. Lead time and MOQ unknown.

One new item, small: NXP lists a **PCN against `XNBA3` issued 2025-04-16**. A PCN is not a
discontinuation and the part reads `ACTIVE`, so it is very likely a process or site change — but
its content is unread, and a package or moisture-sensitivity change would land on the footprint.
One look before layout, not before schematic capture.

**H-02, vendor egress — confirmed hard, and it is the standing constraint.** Six supplied URLs
were tried directly (NXP ×3, DigiKey, Mouser, JLCPCB) plus two PCN mirrors: **all blocked at the
proxy's CONNECT layer**, by WebFetch and by curl. This is the environment's network policy, not a
link problem. General web *search* works and got the lifecycle question most of the way; **a PDF
of the part page, saved by a human, finished it and produced both findings above.** That is the
current working method, and it does not scale to a BOM.

Allowlisting `nxp.com`, `digikey.com`, `mouser.com` and `jlcpcb.com` is the fix. Every remaining
part number carries `UNVERIFIED`.

**H-03, ERC — unchanged.** Only KiCad 7.0.11 is installable; `kicad-cli sch erc` needs KiCad 8.
`make -C hardware erc` now **fails loudly** with the reason rather than skipping quietly, so the
gap is visible the day a board exists instead of passing green. DRC is fine on 7.0.11.

**Q-006, the library printer.** WP04-01 assumes PLA / 0.2 mm / no supports / 220 × 220. All four
are guesses about a machine nobody here has seen. The packet is sendable with the assumptions
stated on the card; ten minutes of asking would make it correct instead.

---

## Spending

Running total, per PM Decisions 001 §6 ($150/order, $600 cumulative without asking).

| Order | What | Est. | Status |
|---|---|---:|---|
| 1a | Six card SKUs + rated reader | ~$115 | Drafted, under authority |
| 1b | Bench build | ~$152 | Drafted, **$2 over** the per-order limit |
| | **Cumulative committed** | **$0** | Nothing ordered yet |
| | **Cumulative if both placed** | **~$267** | of $600 |

Order 1b is $2 over. It is a genuinely separate cart from a different vendor with a different
urgency, not a split to slide under the limit — but it needs a nod rather than an assumption.

## Acceptance criteria flipped to passing

None. Nothing has been measured. Every criterion written this cycle is marked
`SELF-REPORTED — no independent confirmation`, which PM Decisions 001 §4 makes standing
convention rather than a placeholder.

Criteria for WP-04 and WP-05 go to the Verification Lead **before** the tests run, per §4 — the
failure mode with a self-designed test is the criterion, not the measurement.

## What will hurt in three weeks

- **The codec question is the one to chase.** If the SGTL5000 is genuinely obsolete it is a
  schematic-level change, and every week it stays unanswered is a week closer to discovering it
  during WP-26 instead of before it. It is five minutes of someone else's browser.
- **WP04-01 is built and not moving.** It is the critical path — WP-04 blocks WP-20 and WP-22,
  and WP-22 is the six-to-ten-week long pole. The packet has been ready since today and is held
  by a ten-minute question.
- **The 0.2 K JEITA margin is computed against the estimate I trust least.** The board→air
  coupling in a sealed box is a guess (±30% would move that margin by several kelvin in either
  direction). WP-37 measures it, but WP-37 is Phase 5. If it turns out worse than estimated, the
  fix is a layout constraint — cell placement — and layout happens in Phase 5 too. **The
  constraint needs to be in `board-rev-a.md` before layout, not after**, which is why §4's
  mitigation 2 is written as a layout requirement rather than a recommendation.
- **Nothing has been independently reviewed.** Taking up PM Decisions 001 §8 on the solenoid
  protection circuit specifically — its whole job is to be correct when firmware is wrong, and
  that is exactly what a second reader catches and a self-review does not.
