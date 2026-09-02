# STATUS — HARDWARE

**Updated:** 2026-09-02 · **Phase:** 0 · **Updated by:** Hardware Lead · **Reports to:** PM

The Hardware Lead's window into `hardware/` and `spec/hw/`. Companion to `docs/STATUS.md`,
which stays the Software Lead's. Review packets live in `docs/REVIEW/hardware-lead.md`; this
file is state, not argument.

**Scope:** WP-04, WP-05, WP-22–27, WP-29, WP-30, WP-34, WP-37.

---

## What changed since last time

**The four PR #15 blockers are closed.** All three engineering findings now have generated,
self-checking analysis — `make -C hardware thermal-check` fails if the document drifts from the
scripts behind it.

**The charger finding produced the sharpest result of the round.** A `BQ25896`-class part *can*
hold a 45 °C hot-suspend, but **not with the thermistor anyone reaches for first**. A B = 3435 K
NTC spans exactly enough to place both thresholds on 0 °C and 45 °C and nothing more; ask it for
any tolerance margin and the algebra returns a **negative resistor**. It needs **B = 3950 K**.
And the margin is not optional, because safety here is one-sided — suspending early is harmless,
suspending late means charging a lithium cell out of window. A design centred on the limits would
have passed review and shipped half its tolerance band on the wrong side of a safety limit.
ADR-111.

**Solenoid:** one `74HC221` does both halves — 30 ms pulse, 1.2 s lockout — meeting the 5 %
rolling-1 s duty limit at **3.34 % worst case** over ±16 % tolerance, without the PPTC, which is
now explicitly a third layer. Dielectrics are written into the ADR because X7R here would widen
the pulse and shorten the lockout, both unsafe, while passing every room-temperature test.
ADR-112.

**Junction temperatures** are now per-device on a two-time-constant model. The result is
comfortable — MCU 41.6 °C after a 30 s copy, 80.8 °C held forever in a 35 °C room against a
105 °C limit — and that is a finding rather than a relief: **the sealed enclosure is not the
constraint anywhere**, so the thermal argument for vents does not exist at any point.

**C-60 applied.** High-speed 4-bit at 3.3 V is now the primary path on both slots; the 1.8 V
switching circuit stays on the schematic unpopulated with 0 Ω bypass links. Card characterisation
drops from a gate to a headroom measurement, and the parts cart moves to V30 / 32 GB.

**One cross-memo conflict found and raised rather than resolved silently.** Decisions 001 set the
rev A entry gate at **SDR50**; Decisions 002 then made the 1.8 V circuit unpopulated. SDR50 is a
UHS-I mode and needs 1.8 V signalling — so a board built to the second memo cannot run the gate
set by the first. Gate moved to high-speed 4-bit, which preserves everything it was for. ADR-113.

**A vendor domain opened.** JLCPCB is now reachable (five others still are not) and its parts API
answered two open items at once: the codec is an **`Extended`** library part with **74** in stock
for the 32-pin variant and **1205** for the 20-pin. That makes the second source obvious and
cheap — **the same silicon in a smaller package**, costing a footprint change and no firmware
work. ADR-115.

**Four read-back findings on `spec/acceptance.md`**, two of which matter: the worst-case thermal
test asks for charge-during-copy, which ADR-102 deliberately prevents (rev A now carries a bypass
link); and the touch-temperature limit became relative, which does not bound touch temperature at
all. `docs/REVIEW/hardware-lead.md` round 3.

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
| 1a | Six card SKUs + rated reader | ~$115 | Drafted, under authority. **Send today** |
| 1b | Bench build | ~$152 | Drafted, **$2 over** the per-order limit |
| 1c | Codec buy-ahead, 20 × `SGTL5000XNBA3` | ~$110 | Drafted, under authority. **Send with 1a** |
| | **Cumulative committed** | **$0** | Nothing ordered yet |
| | **Cumulative if all three placed** | **~$377** | of $600 |

Order 1b is $2 over. It is a genuinely separate cart from a different vendor with a different
urgency, not a split to slide under the limit — but it needs a nod rather than an assumption.

**1a and 1c are the two that should not wait.** 1a answers the tape-length question before the
format freeze; 1c retires a nine-month lead time on a sole-source part for $110. 1b is useless
until there are printed carriers to put the switches in, so it can wait on Q-006.

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
