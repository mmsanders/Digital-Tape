# STATUS — HARDWARE

**Updated:** 2026-09-02 · **Phase:** 0 · **Updated by:** Hardware Lead · **Reports to:** PM

The Hardware Lead's window into `hardware/` and `spec/hw/`. Companion to `docs/STATUS.md`,
which stays the Software Lead's. Review packets live in `docs/REVIEW/hardware-lead.md`; this
file is state, not argument.

**Scope:** WP-04, WP-05, WP-22–27, WP-29, WP-30, WP-34, WP-37.

---

## What changed since last time

**The print packet was broken and it was my bug.** `plate.3mf` had malformed XML that no slicer
would open. Root cause: a regex replacement template where `\1` followed by `20` parsed as the
**octal escape** `\120` = `'P'`, eating the opening `<metadata>` tag. It was introduced by the
change that made the file byte-reproducible. A second, independent bug put one object at
Y = −11 mm, off the bed, because my bounds check tested only the far edges.

**Both are now impossible rather than fixed.** Geometry is shelf-packed from measured bounding
boxes; `validate()` checks all four edges per object and refuses to write a broken packet;
`check_3mf()` parses every XML entry after writing; `make -C hardware packet-validate` re-checks
the committed artefact and a CI job runs it. **Rev 2 needs a bed of only 162 × 65 mm** and the
card says so.

**The gate I had was measuring the wrong thing.** It asked "are the bytes identical each time?"
and never "is the file valid?", so it passed happily on malformed XML — the same failure as an
allocation gate running green over 98 KB of `.bss`. `CLAUDE.md` §1 says every gate must be proven
able to go red; mine had never been shown a broken packet.

**Media atomicity added** — the criterion, the rig spec and `media_atomicity.py`, self-tested
against an injected tear. It also checks the **neighbouring blocks**, which the criterion does
not ask for: an FTL can garbage-collect during a power cut and damage blocks nobody wrote, which
is equally fatal and free to catch in the same run.

**The three IR-015 findings have responses on `main`** (ADR-111, ADR-116, and the per-device
junction model) and PM Decisions 004 §3 predates that merge. **They are not closed** — I have not
marked them so, because the author of a response does not accept it. The fabrication gate stands.

**`board-rev-a.md` §2 now carries a real pin map** — signal names, directions and pulls, no pin
numbers. Firmware can start against it. Two rows matter most: `SOL_REQ` vs `SOL_GATE` (firmware
asks, hardware allows) and `CHG_INHIBIT`, which must be released on every copy exit path
including errors, or the device silently refuses to charge.

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
