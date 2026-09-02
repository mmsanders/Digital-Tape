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
   ADR-011.
3. **The solenoid one-shot does not close the hole it was specified for.** A retrigger loop
   delivers essentially full coil power through a correctly functioning one-shot. ADR-010 adds
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
identical-geometry controls are hidden in the ranking (ADR-013).

**`spec/hw/board-rev-a.md` started**, mostly empty by design, carrying the `CHANGES` protocol,
the notification obligation, the test-point list, and the PM's SDR50 entry gate written down
**before** fabrication.

**Toolchain: CadQuery installed and working.** `make -C hardware` regenerates every artefact
from source. KiCad deliberately not installed — see Blocked.

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

**H-02, vendor egress — unchanged, and it now has a name attached.** No distributor,
manufacturer or fab domain is reachable. The concrete consequence has arrived: **a distributor
aggregator lists the SGTL5000 as `Obsolete`** while NXP's longevity programme is quoted as
assuring supply. I cannot resolve it. It is the codec in the one-board architecture and on the
Teensy Audio Shield in order 1b, so both builds inherit the question. Five minutes from anyone
with distributor access settles it, and now is the cheapest time. Every part number in
`spec/hw/` and `WP-05.md` carries `UNVERIFIED`.

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
