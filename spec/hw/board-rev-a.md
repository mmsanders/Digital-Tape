# Board rev A — the hardware/firmware contract

**Owner:** Hardware Lead · **Consumed by:** `firmware/prod/` · **Status:** skeleton, accreting
**Revision:** 0.2, 2 Sep 2026 · **Governed by:** PM Decisions 001 §3 and §5

<!-- CHANGES: every revision adds a block here. Firmware reads this first. -->

## CHANGES

### 0.2 — 2026-09-02
**No pin, rail or timing changes** — nothing for firmware to act on. Added §6 (characterised
media: the card SKU and measurement table PM Decisions 001 §1 asks to live here) and §7 (USB-C
and the cartridge loading path, following from ADR-105 captive card). §7 names a firmware device
path that is **not in any work package today**; that is the one line in this revision the
Software Lead should read.

### 0.1 — 2026-09-02
First issue. **No pin assignments yet** — nothing below is bindable. The document exists now
rather than at layout because the pin map is what firmware waits on, and because the bring-up
procedure and the entry gate (§5) must be written *before* fabrication, not after.

---

## How this document works

This is the **only** interface between `hardware/` and `firmware/prod/`. Not a schematic PDF,
not a conversation. Firmware writes against this file.

**The obligation is notification, not approval** (PM Decisions 001 §3). Any change to a pin, a
rail, or a timing constraint lands as a PR that:

1. names the Software Lead as reviewer,
2. carries a `CHANGES` entry at the top listing exactly what moved,
3. merges when firmware acknowledges. The PM does not gate it and the Hardware Lead does not
   wait on the PM.

A silent pin swap between revisions is the classic way to lose a week of bring-up to a problem
that is not in the code at all. The `CHANGES` block is the whole defence against that, so it is
written first and never batched.

**Status vocabulary.** Every row below carries one of:

| Tag | Meaning |
|---|---|
| `PROPOSED` | Hardware Lead's intent. **Do not write firmware against it.** |
| `FROZEN` | Fixed for this revision. Firmware may depend on it. Changing it needs a `CHANGES` entry. |
| `MEASURED` | Confirmed on real silicon, with the measurement recorded. |

Nothing in revision 0.1 is `FROZEN`. That is the honest state, not an omission.

---

## 1. Architecture

One board: i.MX RT1062, QSPI flash, PSRAM, SGTL5000 codec, two USDHC controllers driving both
card slots at UHS-I, LiPo with a switching charger, solenoid driver, LED banks.

| Block | Part | Status |
|---|---|---|
| MCU | i.MX RT1062 (600 MHz, 196-MAPBGA) | `PROPOSED` |
| Boot flash | QSPI NOR | `PROPOSED` |
| PSRAM | APS6404L class, QSPI | `PROPOSED` |
| Codec | **`SGTL5000XNBA3`** (HVQFN32, 5×5 mm, 0.5 mm pitch) | **`ACTIVE` confirmed** — NXP part page, 2 Sep 2026 |
| Card slots | 2 × microSD via USDHC1 / USDHC2, UHS-I | `PROPOSED` |
| Charger | Switching buck with hardware JEITA · `spec/hw/thermal-budget.md` §5 | `PROPOSED` |
| Solenoid driver | One-shot + RC lockout + PPTC · `thermal-budget.md` §6 | `PROPOSED` |

> **Codec — confirmed `ACTIVE` from NXP's own part page (2 Sep 2026). Specify
> `SGTL5000XNBA3`.** First primary-source confirmation of any part on this board.
>
> | | `SGTL5000XNBA3` | `SGTL5000XNBA3R2` |
> |---|---|---|
> | Status | **ACTIVE** | **ACTIVE** |
> | 12NC | 935430641557 | 935430641518 |
> | Packing | Tray, bakeable, drypack | Reel 13", drypack |
> | Min order qty | **490** | **5000** |
> | NXP direct stock | 257 | — |
> | **Factory lead time** | **39 weeks** | **39 weeks** |
> | Budgetary price | $3.47 @ 1K | $3.47 @ 1K |
>
> **Package: HVQFN32** — plastic, thermal-enhanced, very thin quad flat, no leads; 32 terminals;
> **0.5 mm pitch; 5 × 5 × 0.85 mm body**. Operating range **−40 °C to +85 °C**. Analog supply
> 1.62–3.6 V. Supplied in drypack and bakeable, so it is moisture-sensitive and the assembler
> must handle it accordingly — a line for the WP-27 assembly notes.
>
> This closes the lifecycle question that ran from round 1. The `Obsolete` on the aggregator was
> real but attached to `XNAA3`, discontinued by PCN 202201003DN when its punch-QFN line retired;
> `XNBA3` is NXP's own migration path and reads `ACTIVE` today. **A BOM written from search hits
> would have said `XNAA3`.**
>
> **Two findings larger than the question they came from:**
>
> **1. The lead time is 39 weeks, and this part is sole-source.** Nine months against a Phase 5
> that plans 8–12 weeks and 2–3 board spins. If we ever need to *order* this part rather than
> pull it from distributor stock, the schedule is gone. See `docs/PACKAGES/WP-05.md` order 1c —
> the fix is cheap and it is to buy them now, long before a board exists.
>
> **2. NXP direct is not a channel we can use.** Minimum order 490 (tray) or 5000 (reel) against
> a project that needs perhaps twenty. We buy through a distributor who breaks trays, which makes
> the distributor stock check a real dependency rather than a formality.
>
> **One item still open, and it is new.** The page lists a **Product Change Notice against
> `XNBA3`, issued 2025-04-16, effective 2025-05-26** — the same issue date as PDN 202504001DN,
> which contains no SGTL parts. A PCN is not a discontinuation, and the part reads `ACTIVE`, so
> this is very likely a process or assembly-site change. But its *content* is unread, and if it
> touches the package or the moisture-sensitivity level it lands on the footprint and the
> assembly notes. Worth one look before layout, not before schematic capture.

---

## 2. Pin map

**Empty by design.** Filled during WP-26 (schematic capture), one `PROPOSED` block at a time,
promoted to `FROZEN` when the schematic passes PM review.

| Signal | Port / pin | Direction | Pull | Status |
|---|---|---|---|---|
| *(none assigned)* | | | | |

Sections reserved so firmware can see the shape of what is coming: USDHC1 (source slot),
USDHC2 (destination slot), I²S to codec, I²C control, button matrix, LED banks, solenoid gate,
slot detect lines, charger status and NTC, USB-C.

## 3. Power-up sequence

`PROPOSED`, from `spec/hw/thermal-budget.md`:

1. Cell voltage above the low-voltage latch-off threshold (~3.2 V) before the load switch closes.
2. `+3V3` before `+1V8`. The 1.8 V rail is a signalling rail and must not be live into an
   unpowered card.
3. Card slots stay unpowered until the MCU asserts slot power, so an insert during boot cannot
   partially enumerate.
4. Solenoid rail last, and gated off by the one-shot's power-on state. **An undriven gate is an
   off gate** — pull-down at the FET, not a firmware convention.

Timing constraints are `PROPOSED` and unmeasured. Firmware must not depend on them yet.

## 4. Test points

Required on rev A. A board you cannot instrument is a board you respin blind.

- Every rail: `VBAT`, `+5V`, `+3V3`, `+3V3A`, `+1V8`, solenoid rail
- Both slot detect lines
- `CLK`, `CMD` and `DAT0` on each USDHC, placed for a ground-spring probe rather than a clip
- The 1.8 V switch control line
- Charger `STAT` and the cell NTC node
- The solenoid gate, **both sides of the one-shot** — so "did firmware ask" and "did hardware
  allow" are separately observable. Without that, a solenoid fault is an argument.

## 5. UHS-I bring-up — ownership and the entry gate

Per PM Decisions 001 §5.

**Hardware Lead owns:** the bring-up procedure, the test points, the fallback strategy, and
delivering a board that passes the entry gate below.
**Software Lead owns:** the driver, delay-line tuning, and the throughput number.

### The entry gate

> On rev A, an **unmodified reference driver** — NXP's SDK USDHC example — completes a 1 GB read
> and a 1 GB write on **each** slot at **SDR50** with **zero CRC retries**.

| Outcome | Owner | Meaning |
|---|---|---|
| Board fails the gate | **Hardware** | Layout, power integrity, or a respin. Hardware Lead's call which. |
| Board passes, throughput misses | **Software** | Driver and tuning. |

Both remain jointly accountable for the copy-time criterion. The gate exists so that neither can
be argued into owning the other's problem while the schedule burns. It needs no oscilloscope,
which is the point: it is checkable by whoever is holding the board.

**Why SDR50 and not SDR104 for the gate.** SDR104 depends on delay-line tuning, which is
software's half. SDR50 does not. A gate that requires the other party's work to pass is not a
gate. And SDR50 is sufficient for the requirement — see the bus headroom table in
`docs/PACKAGES/WP-05.md`: at 50 MB/s the 90-minute copy needs 63% bus utilisation.

### Rev A hedges — build the escape routes in, not after

The charter's principle, restated as buildable requirements:

| Hedge | Why |
|---|---|
| 1.8 V switching circuit populated but **bypassable with 0 Ω jumpers** | A board that fights at SDR104 still runs at high speed without new fabrication |
| Solenoid boost rail **jumper-selectable** | Coil voltage is a guess until a mechanism exists |
| Charge current **resistor-set** | `thermal-budget.md` can turn it down without a respin |
| Test points per §4 | |

**Rev A is an experiment.** The budget carries three spins for this reason. A rev A that teaches
three things is a success; a rev A that works perfectly is luck.

### Fallback ladder

`SDR104 → SDR50 → high-speed 4-bit`, the only sanctioned retreat (guardrail 10). Reaching the
floor is a PM escalation because it trades against tape length.

One thing the ladder does not say, and should be read alongside it: **at 25 MB/s the bottom rung
cannot meet 30 s for a 90-minute cartridge at all** — the charter already prices it at 43 s. It
*does* meet it for a 60-minute cartridge (25.4 s). So the bottom rung is not a retreat for the
90-minute format; it is a different format. That is the same trade Q-002 puts to Michael, arriving
from the electrical side.

## 6. Characterised media

**PM Decisions 001 §1 names this file as where card SKUs live**, alongside the measured numbers
and the date measured. Empty until order 1a lands.

A card model is not a part here — **an exact SKU with its revision is**. SD manufacturers revise
controllers silently inside a part number, so "an A2 V30 card" is not a specification and a
requirement met by one can break in the field with no change on our side. The recorded baseline
is the only thing that makes a later re-test meaningful.

| Role | SKU | Revision / CID | Worst-case windowed write | Measured | Verdict |
|---|---|---|---|---|---|
| *(none characterised yet)* | | | | | |

**Conditions** (fixed in advance by ADR-109, so the rule cannot be relitigated once someone has
a number they like): card filled to ~80%, transfer ≥ 1200 MB, worst 64 MB window reported rather
than average. Run with `hardware/characterisation/measure_sustained_write.py`; every result
commits its full per-window series to `hardware/characterisation/results/`, not just a verdict.

**Decision rule.** ≥ 2 SKUs at ≥ 35 MB/s worst case → the 90-minute cartridge stands. Otherwise
60 minutes becomes the standard tape, which also drops the bus requirement to SDR50 and retires
the hardest electrical work on this board.

Tape length is a superblock field (`nominal_length_s`, ADR-008), so **this answer does not block
the format freeze or any software** — it sets a format-time constant, not a format.

## 7. USB-C and the cartridge loading path

**The cartridge's microSD is captive (ADR-105).** `tapectl` and the GUI therefore reach the card
**through the player**: the production board exposes the device itself as the cartridge over
USB-C. There is no path in which a card is removed from a cartridge and put in a reader.

`PROPOSED`, and it carries an obligation this document should not let anyone forget:

| | |
|---|---|
| Board | USB-C for charging **and** data. The data path is not optional and not a debug port. |
| Firmware | A device path exposing the mounted cartridge to a host. **Not in any work package today.** |
| `host/` | `tapectl` and the GUI target that path rather than a block device on a reader. |

**The middle row is the cost ADR-105 added and nobody has scoped.** It is cheap to plan now and
expensive to discover in Phase 4 with the shell already drawn. Raised for the PM in
`docs/REVIEW/hardware-lead.md`; flagged here because this is the document firmware reads.

Whether that path is USB mass storage over the raw partition or something narrower is the
Software Lead's call, not mine — but the board must carry USB-C data either way, so the
hardware half is settled and can proceed.

## 8. Open items

| # | Item | Blocked on |
|---|---|---|
| 1 | Every pin assignment | WP-26 schematic capture |
| 2 | ~~SGTL5000 lifecycle~~ — **closed.** `XNBA3` confirmed `ACTIVE`, 39-week lead time, HVQFN32 | — |
| 2a | **Distributor stock for a buy-ahead of ~20 codecs.** 39-week factory lead time on a sole-source part | **Blocked** — H-02. Order 1c |
| 2b | Content of the PCN against `XNBA3` (2025-04-16). Package or MSL change would hit the footprint | Before layout — H-02 |
| 2c | 32-pin `XNBA3` vs 20-pin `XNLA3`; land pattern from the current datasheet | WP-26 |
| 2d | **RT1062 lead time and MOQ — unknown, and it is the other sole-source part** | **Blocked** — H-02 |
| 3 | Charger, one-shot and protection part numbers confirmed orderable | Distributor access — H-02 |
| 4 | Cell placement fixed relative to charger and MCU | `thermal-budget.md` §4 — a layout constraint, must land before layout |
| 5 | Cartridge edge-connector geometry and stub length | Cartridge spike; STATUS-HARDWARE H-05 |
| 6 | Power-up timing constraints measured | Rev A bring-up |
| 7 | Card SKUs characterised and recorded in §6 | Order 1a arriving |
| 8 | The USB-C device path in §7 scoped into a work package | **PM** — it is the cost ADR-105 added |
