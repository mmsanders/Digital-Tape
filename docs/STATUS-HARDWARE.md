# STATUS — HARDWARE

**Updated:** 2026-09-05 · **Phase:** 0 · **Updated by:** Hardware Lead · **Reports to:** PM

The Hardware Lead's window into `hardware/` and `spec/hw/`. Companion to `docs/STATUS.md`,
which stays the Software Lead's. Argument lives in `docs/REVIEW/hardware-lead.md`; this file is
state.

**Scope:** WP-04, WP-05, WP-22–27, WP-29, WP-30, WP-34, WP-37.

> **This file was three rounds stale when I opened it** — dated 2 Sep, still listing the
> cancelled order 1c as "send with 1a", still carrying a codec suffix superseded on 3 Sep and a
> spend total that went with it. Rewritten, not patched. Noted because a stale status is worse
> than no status: the PM has no other window and cannot tell it has stopped moving.

---

## What changed since last time

**The cartridge clasp is designed and assessed** — `spec/hw/cartridge-shell.md`, answering
Decisions 006 §2. Michael can have the no-screw clasp. Retention is a **continuous seam with
discontinuous engagement**: the tongue-and-groove line runs the whole perimeter, the retaining
interference only along the long walls, stopping short of the corners, because a rectangle
cannot open at a corner by bending. **0.75 % peak strain opening, 0.086 % at rest** — creep is
designed out rather than tolerated, and the closed assembly is checked by boolean.

**Your cycle target accepted, plus three criteria that can actually fail.** 20 cycles at ≤ 20 %
loss will pass — the design holds zero strain at rest — so S-2 (90 days closed, 23 °C and
45 °C), S-3 (1.0 m drop) and S-4 (a 30 N pinch must not open it) are where the risk is.

**WP04-01 is rev 4 and carries both experiments.** The clasp sweep shares the latch plate:
**1.6 h against a 6 h library limit, 150 × 149 mm against a conservative 180 × 180 bed.** One
trip, two answers. Sendable today.

**The nylon correction is applied** (Decisions 006 §1). The A1 line runs PLA, PETG and TPU and
not nylon. The shell is designed for PETG throughout, so it costs this package nothing; it still
bites WP-22's latch, which is a genuine fatigue part and may need a service bureau.

**Two defects in already-shipped documents, found while working.** `CARD.md`'s headline told
Michael to print `plate.3mf` while its own table said `plate.stl` — the first line he reads was
the wrong one. `WP-04.md` carried a live paragraph describing a variant deleted two revisions
earlier. Both fixed.

## In flight

| Work | State | Who |
|---|---|---|
| WP-04 packet WP04-01 | **Rev 4 built, nothing blocking.** With Michael to print | Michael |
| WP-24 cartridge shell | **Assessment delivered** (ADR-117). Variants on the plate | Hardware Lead |
| WP-05 parts order | Order 1a checkout-ready. Waiting on Michael | Michael |
| WP-34 thermal budget | **Rev 0.3.** Estimates; three IR-015 responses filed, none accepted | Hardware Lead |
| `spec/hw/board-rev-a.md` | Rev 0.5, pin map populated, no pin numbers. Accretes through WP-26 | Hardware Lead |
| WP-26 schematic | Not started. Codec settled, so unblocked | Hardware Lead |

## Blocked, and on what

**The fabrication gate holds.** No board is fabricated and no cell is charged until the three
IR-015 findings are accepted. A response is filed against each; **I do not get to mark my own
responses accepted.** This is the only hard gate on the hardware stream and it is waiting on the
PM or a reviewer, not on work.

**H-02, vendor egress — partially lifted, still binding.** `www.nxp.com`, `www.lcsc.com` and
`www.jlcpcb.com` now resolve; DigiKey and Mouser serve a JS shell or 403 to any non-browser
client. The `www.` prefix is required, and **WebFetch and curl do not share an allowlist**. Net
effect: lifecycle questions are answerable, **stock and price are not**, and no filament
datasheet is reachable — which is why every material property in `cartridge-shell.md` is marked
EST.

**H-03, ERC — unchanged.** Only KiCad 7.0.11 is installable; `kicad-cli sch erc` needs KiCad 8.
`make -C hardware erc` fails loudly rather than skipping, so the gap is visible the day a board
exists. DRC is fine on 7.0.11.

**Not blocked any more:** Q-006 (answered "proceed on the default"; rev 4 is laid out to it) and
the codec (`SGTL5000XNBA3R2`, second source `SGTL5000XNLA3R2`, ADR-115).

## Spending

Per PM Decisions 001 §6 — $150/order, $600 cumulative without asking.

| Order | What | Est. | Status |
|---|---|---:|---|
| 1a | Six card SKUs + rated reader | ~$115 | **Checkout-ready with Michael** |
| 1b | Bench build | ~$152 | Drafted, **$2 over** the per-order limit — needs a nod |
| ~~1c~~ | ~~Codec buy-ahead~~ | — | **Cancelled**, Decisions 003 §2 |
| | **Cumulative committed** | **$0** | Nothing ordered yet |
| | **If 1a and 1b both placed** | **~$267** | of $600 |

## Acceptance criteria flipped to passing

**None, and none can yet.** Nothing has been measured. Every criterion written this cycle is
marked `SELF-REPORTED — no independent confirmation`, which Decisions 001 §4 makes standing
convention rather than a placeholder.

**What did change is what "passing" will require.** Decisions 006 §5: the safety measurements
are witnessed by Michael *and* independently audited by the Verification Lead from method and
raw data. Recorded as ADR-118, with the record format in `hardware/measurements/TEMPLATE.md`.
WP-24's S-4 is written to that standard from the start rather than retrofitted.

## What will hurt in three weeks

- **WP04-01 has now been ready and not printed for three days**, and it is the critical path —
  WP-04 blocks WP-20 and WP-22, and WP-22 is the six-to-ten-week long pole. It is no longer
  blocked on anything I can act on. Every day it sits is a day off the end of Phase 4.
- **The 0.2 K JEITA margin still rests on the estimate I trust least** — board-to-air coupling
  in a sealed box, where ±30 % moves the margin by several kelvin either way. WP-37 measures it
  and WP-37 is Phase 5, but the mitigation is a *layout* constraint (cell placement) and layout
  is Phase 5 too. It has to be in `board-rev-a.md` before layout, not after.
- **S-2 is a 90-day clock that has not started**, and it cannot start until a PETG pair exists,
  which needs a printer. It is the longest-lead criterion on the hardware stream and it is
  invisible on every schedule because nobody has drawn it.
- **Every material number in `cartridge-shell.md` is an estimate**, and the plate is bracketed
  to measure around that rather than to assume it. If the ranking comes back with everything
  holding or nothing holding, my stiffness figures are wrong and the next plate needs a
  datasheet first — which needs egress we do not have.
- **Nothing in `hardware/` has been independently reviewed since IR-018.** Two rounds of
  findings there were all in *what a check was asking*, never in the engineering; the three
  self-caught defects this round were the same pattern. That pattern does not fix itself by
  being named, and I am not the right party to confirm it has stopped.
