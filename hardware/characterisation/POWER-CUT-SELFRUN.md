# Card power-cut test, Teensy self-run (WP-05 A-6, ADR-208)

**Owner:** Hardware Lead · **Status:** METHOD for independent review. **Nothing is built, energised,
bought or run.** Drafted 8 November 2026 for [#671](https://github.com/mmsanders/Digital-Tape/issues/671),
stage 2. Base: main `978efb2`.

This replaces [ATOMICITY-RIG.md](ATOMICITY-RIG.md) revision 2 (blob `322dfa8e` before its superseded banner) as the method to
build, because [ADR-208 §6](../../docs/DECISIONS.md#adr-208--hands-on-acceptance-for-physical-and-timing-criteria)
drops external rail traces, instrument-qualified timing and the uncertainty-U analysis. Revision 2
and its schema stay in the tree as history; nothing in them is deleted. §8 lists what this method
keeps from them and what it drops.

**What it can establish:** that on one card model, in SPI mode, a power cut during a single-block
write leaves the target block wholly old or wholly new and its neighbours unchanged, over at least
1,000 cuts in which the firmware saw the card busy at the moment it opened the switch. It cannot
establish the busy timing independently of the firmware, or behaviour in the product's SD 4-bit
bus mode (§7).

## 1. Circuit

One Adafruit 4682 microSD breakout (3 V only, no regulator or level shifter) on the breadboard,
wired to the Teensy 4.1's SPI pins. The card's 3.3 V rail is the only switched thing.

```
 Teensy 3V3 ──┬── 1 µF + 100 nF ── GND
              └── U1 TPS22918 VIN
                  U1 ON  ◄── Teensy pin CUT (high = card powered) ── 100 kΩ ── GND   (pull-down: off at reset)
                  U1 CT  ── 1 nF C0G ── GND                                         (soft start ≈ 1.7 ms typ.)
                  U1 QOD ── R_EXT 100 Ω ── VCARD                                    (discharge while ON is low)
                  U1 VOUT = VCARD ──┬── 4682 "3V" pin (card VDD)
                                    ├── 10 µF + 100 nF at the breakout
                                    └── 10 kΩ ──► Teensy ADC pin VMON (with 100 nF to GND at the pin)

 Teensy CS   ── 100 Ω ──► 4682 CS        Series resistors damp breadboard ringing at 4 MHz.
 Teensy SCK  ── 100 Ω ──► 4682 CLK
 Teensy MOSI ── 100 Ω ──► 4682 DI
 4682 DO     ───────────► Teensy MISO    100 kΩ pull-down at MISO (never a pull-up to always-on 3V3)
 GND common.  Test points: VCARD, CUT, MISO, GND (multimeter; optional clone analyser).
```

- **Load switch.** TI TPS22918 (already selected in revision 2, datasheet SLVSD76C). ON high
  connects VIN to VOUT; ON low disconnects it and turns on the quick-output discharge, which pulls
  VCARD to ground through R_PD (25 Ω typ., 35 Ω max) plus R_EXT. The 100 kΩ pull-down keeps the card
  off while the Teensy is in reset or the pin is floating.
- **Discharge, so the card really resets.** τ = (R_EXT + R_PD) × C ≈ 125–135 Ω × 10 µF ≈ 1.3 ms
  (analysis, not a measurement). VCARD is below 0.5 V after about 2.6 ms and effectively at 0 V after
  the 50 ms off-time (§2 step 9). The SD reset condition is VDD below 0.5 V; the off-time is about
  20 τ. Whatever capacitance the 4682 board itself carries adds to C, which is why the firmware
  measures VCARD at the end of every off-time instead of trusting this sum.
- **No back-power.** An unpowered card can be kept alive through the ESD diodes on its inputs if the
  Teensy holds CS, SCK or MOSI high. In SPI mode the card holds DO low for the whole busy phase
  without needing the clock, so the firmware can drive all three lines low **in the same step** as
  the cut (§2 step 8) and keep them low through the off-time. MISO has only a pull-down, and the
  breakout's own pull-ups go to VCARD. This replaces revision 2's Ioff buffers. A firmware fault that
  left a line high would show up as a high `vcard_off_mv` on that row (§3), which the judge refuses
  (§4, change P2).
- **Inrush.** 10 µF × 3.3 V / 1.68 ms ≈ 20 mA during the soft start, inside the Teensy's 3.3 V
  budget. Leaving CT open would cut the rise to tens of µs and pull hundreds of mA, so CT stays.

**Bench check before the first card (multimeter, Michael witnesses, no card):** with CUT held low
by firmware command and CS/SCK/MOSI driven low, VCARD reads < 50 mV; with CUT high it reads
3.2–3.4 V; and the firmware's `vcard_off_mv` agrees with the meter to within 50 mV at both levels.
Then the same with a card in. That is all the electrical qualification ADR-208 asks for; there is
no scope, rail trace or comparator.

## 2. Firmware procedure, one trial

The procedure follows ADR-208 §6 and the kept parts of WP-05. Times are microseconds from trial
start on one free-running MCU timer (the Cortex-M7 cycle counter, 600 MHz at default clock, or a GPT
at 150 MHz; the firmware prints which, once, at boot). SPI clock 400 kHz for initialisation and
4 MHz for the trial.

| Step | Action | Row field |
|---|---|---|
| 0 | Host sends `{iteration N, cut_offset_fraction f}` from the committed plan | — |
| 1 | CUT high. Wait for VCARD to settle (≥ 3 ms), then ≥ 74 clocks with CS high, CMD0, CMD8, ACMD41 loop, CMD58, **CMD59 (CRC on)** | `init_ms`; a failure is logged as a row, never skipped |
| 2 | CMD10, read the CID | `card_cid` (logged; gates nothing per ADR-208 §5 except "one card per run", §4) |
| 3 | Write `pattern(N−1)` (CMD24), wait for busy to end, read back (CMD17) | `precondition_ok`, `precondition_readback_hex` |
| 4 | Read target −2, −1, +1, +2 | `neighbour_baseline` |
| 5 | CMD24 with `pattern(N)`: R1, start token 0xFE, 512 bytes, CRC16 | `payload_complete` |
| 6 | Read the data-response token; accepted when `token & 0x1F == 0x05` | `data_response_accepted` |
| 7 | Clock 0xFF one byte at a time. The first byte that reads 0x00 is busy entry; the timer is read when that byte finishes | `busy_entry_us` |
| 8 | Keep clocking. Each byte: if it reads **0x00**, read the timer (`busy_sampled_us`); if that time is ≥ `busy_entry_us + f × T_sched`, then **in this order and with nothing between them**: drive CUT low, CS/SCK/MOSI low (pins switched from the SPI peripheral to GPIO-low), read the timer (`cut_us`). If a byte reads anything other than 0x00 before the cut time, busy has ended: read the timer (`busy_deassert_us`), still cut, and finish the row | `busy_sampled_us`, `cut_us`, `busy_deassert_us` |
| 9 | Hold the card off for 50 ms. In the last millisecond read VMON (average of 8 ADC samples) | `vcard_off_mv` |
| 10 | Release the lines to the SPI peripheral, CUT high, initialise as step 1, **CMD10 again** | `card_cid_after_cut` |
| 11 | Read the target and its four neighbours (CMD17; the card has been power-cycled, and the firmware keeps no block cache) | `readback_hex`, `neighbours` |
| 12 | Print the row, once, as one line on USB serial. Never edit or drop a row | `firmware_build`, `bus_mode`, `busy_line`, `sck_hz` |

**What "saw busy at the moment it opened the switch" means here.** The cut is issued only directly
after a byte that read 0x00, so DO was held low by the card for the whole of the 8 clocks
(2 µs at 4 MHz) that end at `busy_sampled_us`. The switch edge follows within a few CPU
instructions, so `cut_us − busy_sampled_us` is normally well under 1 µs. The row carries both
times; the judge, not the firmware, decides whether that gap is small enough (§4, change P1).

**T_sched** is the median busy time from 100 uncut writes, measured by the same firmware and
committed with the plan. It only spreads the cuts across the busy phase (f is planned over 0–1.5);
whether a cut qualifies is decided per row. Misses are expected and kept; `plan --extend` adds
attempts under the same run id until 1,000 rows qualify.

**What the firmware never does:** CMD48/CMD49, a retried write inside a trial, a dropped row, an
edited row, or a block cache across a power cycle.

## 3. Log format and how it reaches the judge

Each trial prints exactly one serial line:

```
ATOM {"iteration": 17, "run_id": "...", ... }
```

The prefix is `ATOM ` (five bytes, with the space); the rest of the line is one JSON object, a
**revision-3 row** as `media_atomicity.py` already reads it (schema in its module docstring; field
meanings in WP-05). Boot banners, the CID and timer report and debug prints never start with
`ATOM `. The host keeps the raw serial capture and makes the judge's input with nothing but a
prefix strip:

```
sed -n 's/^ATOM //p' serial.log > run.jsonl
media_atomicity.py judge --plan plan.json [--plan ext.json] --results run.jsonl --json verdict.json
```

Both `serial.log` and `run.jsonl` are kept, with their SHA-256 in the run record. No other
transformation is allowed: the firmware's line is the row.

| Row field | Source | Existing judge (plan v3) |
|---|---|---|
| `iteration`, `run_id`, `sku`, `revision`, `card_cid`, `plan_digest` | host passes run identity to the firmware once; `card_cid` from step 2 | validated, unchanged |
| `precondition_ok`, `precondition_readback_hex` | step 3 | validated, unchanged |
| `neighbour_baseline`, `neighbours`, `readback_hex` | steps 4 and 11 | validated and classified OLD/NEW/TORN/CORRUPT, unchanged |
| `bus_mode` = `"spi"`, `busy_line` = `"MISO"` | constant in this build | checked, unchanged |
| `payload_complete`, `data_response_accepted` | steps 5–6 | qualification, unchanged |
| `busy_entry_us`, `busy_sampled_us`, `cut_us`, `busy_deassert_us` | steps 7–8 | qualification: `busy_entry ≤ busy_sampled ≤ cut`, and no deassert at or before the cut |
| `card_cid_after_cut`, `vcard_off_mv`, `firmware_build`, `sck_hz`, `init_ms` | steps 9–12 | **carried but not checked** by plan v3; see §4 |

`sku` is the card's part number from its package and `revision` is `PNM/PRV` from the CID when the
firmware has read it, else the package revision text (ADR-208 §5; card identity is recorded in
`docs/evidence/cards/`).

**Off-target check (Hardware, 8 Nov, not a Verification disposition).** I ran the unchanged judge
(`media_atomicity.py`, SHA-256 `6edc55f5…0776cae`) on synthetic revision-3 rows made in this format,
1,100 attempts: a clean log gives **PASS** with 1,100 qualifying, exit 0; the same log with one
planted tear (iteration 501 read back as half `pattern(N−1)`, half `pattern(N)`) gives **FAIL**,
`torn_iterations: [501]`, exit 2. `make -C hardware atomicity-test` is green on the same base.
This shows the mapping needs no code change to run; it says nothing about a card.

## 4. Minimal judge changes proposed (not implemented)

The plan-v3 judge already does the old/new/torn classification, the neighbour checks, the fixed
1,000 minimum, one-card identity and keep-every-result. It has four gaps for this method. Each is
a **proposal**: the judge's tests are Verification's, so these are implemented only after
Verification publishes independent tests for them and they are imported unchanged first, the
same order as rig-r2.

| # | Gap in plan v3 today | Proposed rule | Why |
|---|---|---|---|
| P1 | A row with `busy_sampled_us = 101` and `cut_us = 50000` qualifies (checked 8 Nov with `qualifies()`): the sample can be any time before the cut | Policy constant `SAMPLE_TO_CUT_MAX_US = 5.0`; a row qualifies only if `0 ≤ cut_us − busy_sampled_us ≤ 5.0`. Also require `busy_deassert_us`, when present, to be ≥ `busy_sampled_us` (else record invalid) | Makes "busy at the moment of the cut" mean something. 5 µs is one 2 µs busy byte plus generous instruction slack at 600 MHz; the expected value is < 1 µs |
| P2 | Nothing checks that the card was actually unpowered | Policy constant `VCARD_OFF_MAX_MV = 200`; a validated row needs an integer `vcard_off_mv`, and above 200 mV is a **run problem** (FAIL), not a miss | A cut that didn't reset the card isn't a cut. 200 mV is well under the 0.5 V reset level and above ADC noise |
| P3 | `card_cid_after_cut` isn't compared | Present and different from `card_cid` is a run problem; absent is allowed when the CID couldn't be read, since ADR-208 §5 makes CID gate nothing | A card swapped or re-enumerated mid-run is caught when the data exists |
| P4 | Under plan v3, a row that saw busy end before the cut and reads OLD passes silently (only plan v4 reports `completed_write_reverted`) | Report it in the verdict as `completed_write_reverted` and FAIL the run, exactly as ADR-204 does for rig-r2. **PM decision**, because ADR-204 required an independently qualified method for completion proof and ADR-208 drops that. Safe default: fail closed | A write the card said was done must not come back old. Over-reporting is the safe direction; a reported case needs its row reviewed before anyone calls it a card defect |

Also proposed: `firmware_build` (40-hex source commit, printed in every row) must be one value
across the run and is reported in the verdict, so the MICHAEL-CHECKS entry (ADR-208 §7) can be
matched to it. Plan v4, the rig manifest, `U_US`, `CUT_DELAY_MAX_US` and the E0–E4 windows are
**not used** by this method; the judge keeps them for revision-2 history and its imported tests.

## 5. Negative controls

| Control | How | Must give | What it detects |
|---|---|---|---|
| **N1, planted tear (the named control)** | Off-target: a valid log with one row's `readback_hex` replaced by the first 256 bytes of `pattern(N−1)` and the last 256 of `pattern(N)` | Judge FAIL, that iteration in `torn_iterations`, exit 2 | A judge or mapping that can't see a torn block. Verification owns the authoritative version of this test |
| N2, planted neighbour damage | Off-target: one row's `neighbours["+1"]` differs from its baseline | FAIL, listed in `neighbour_damage` | A judge that ignores neighbours |
| N3, late cut (on the bench) | 20 trials at f = 3.0 | Every row shows `busy_deassert_us` before `cut_us`, non-qualifying, target classified | Firmware that cuts without checking busy |
| N4, no cut (on the bench) | Jumper CUT's switch input high (ON tied to 3V3) for 5 trials | `vcard_off_mv` ≈ 3300, run FAIL under P2 | A switch that doesn't switch, or a VMON that doesn't measure |
| N5, firmware tear (on the bench, Verification-reviewed build) | A debug build that rewrites half the target block after re-power on one chosen iteration | Judge FAIL on exactly that iteration | The whole path, firmware print to verdict, catching a real torn read |

N1 and N2 cost nothing and run off-target. N3–N5 run once on the bench before the campaign, with the
serial logs kept. A failed control is kept and blocks the campaign until the cause is fixed.

## 6. Campaign

1. Hardware check (§1), then N3–N5 with Michael watching.
2. Per card model: 100 uncut writes for T_sched, `media_atomicity.py plan --sku … --revision …
   --cid … --attempts 1500 --out plan.json`, commit the plan, run, strip, judge.
3. About 2,000 trials an hour (50 ms off plus re-init and five reads), so one model takes under an
   hour of bench time; leave it unattended once it starts.
4. Record in MICHAEL-CHECKS: date, firmware build, card identity, plan digest, serial log and
   verdict hashes. One TORN or CORRUPT block, or any neighbour damage, escalates to PM as a format
   blocker. It is never worked around in firmware.

## 7. Residual risk (recorded, not proven, per ADR-208)

- **Busy timing is only self-observed.** The firmware decides that DO was low and stamps both the
  sample and the cut on its own timer. Nothing external confirms that the switch opened while the
  card was still programming. The mitigations are structural (the cut is issued only straight after
  a 0x00 byte, and P1 bounds the gap) and statistical (with f spread over 0–1.5, OLD and NEW should
  both appear among qualifying rows; a run that is all-NEW would suggest cuts are landing after the
  program completes and should be reviewed).
- **"Unpowered" is self-observed too.** `vcard_off_mv` is the Teensy's own ADC through 10 kΩ; the
  multimeter check in §1 is the only cross-check.
- **Bus mode used: SPI at 4 MHz on MISO.** The product reads cards in SD 4-bit mode on the Teensy's
  built-in SDIO slot, whose power can't be switched without modifying the board. A card's internal
  programming after a single-block write is the same operation either way, but nothing here proves
  the controller behaves identically in both modes. A PASS is SPI-mode evidence; whether it
  qualifies the card for the product stays PM's scope decision (ATOMICITY-RIG revision 2 §6, still
  open).
- **One card per model.** ADR-208 asks for ≥ 1,000 qualifying cuts per card model, which one card
  supplies. Unit-to-unit variation within the model is not covered.

## 8. Kept from revision 2, and dropped

| Revision 2 | Here |
|---|---|
| TPS22918 load switch with QOD, R_EXT 100 Ω, CT 1 nF, 10 µF bulk | **Kept** |
| SPI at 4 MHz, CMD59 CRC on, CID before and after the cut | **Kept** |
| Every row classified, qualifying or not; keep every row; 1,000 fixed; torn is a blocker | **Kept** (the judge already does it) |
| Comparators A and B, LM4040 reference, 0.1 % divider, hysteresis resistor | **Dropped** (ADR-208: no instrument-qualified timing) |
| SN74LVC1G125 Ioff buffers | **Dropped**: lines driven low with the cut, checked by `vcard_off_mv` |
| Input-capture edge lists, U = 1.0 µs, E0–E4 analogue controls, scope, rig manifest, plan v4 | **Dropped** (ADR-208: no rail traces, external timebase or U) |
| Dry-run control A (wire truth with an analyser) | **Optional**, debugging only, with the clone analyser |
