# Card power-cut rig — design (WP-05 A-6)

**Owner:** Hardware Lead · **Status:** DESIGN for method review. Nothing is built or run.
**Drafted:** 1 November 2026 for [P3-R1-HW (#641)](https://github.com/mmsanders/Digital-Tape/issues/641),
input main `3826018`.

**Verification reviews this method before any run** (WP-05, "Independent acceptance"). The rig
firmware and raw transaction and rail traces must be reviewable before any physical-atomicity
acceptance. This document is the method; the firmware comes after Verification's review.

**Procedure this implements:** [WP-05](../../docs/PACKAGES/WP-05.md) "Atomicity procedure".
**Judge:** [media_atomicity.py](media_atomicity.py) (plan revision 3, IR-018). Every field named
below is a field that `judge` validates or qualifies on.

## 1. What the rig is

A Teensy 4.1 drives one microSD card in **SPI mode** through a breakout whose 3.3 V rail the
Teensy can switch off within about a microsecond, and discharge to 0 V. For each planned trial
the rig:
1. establishes the old block and neighbours;
2. starts a single-block write;
3. watches the protocol to the busy phase;
4. opens the rail at the planned point in busy;
5. powers back up and reads everything again.

It emits one JSON row per planned trial over USB serial.

Parts are lines 8, 18 and 19–25 of [PHASE3-BENCH.md](../sourcing/PHASE3-BENCH.md). The rig can borrow
the bench Teensy, since the rig needs no audio board, but a dedicated second Teensy keeps the rig
wiring permanent. That choice is Michael's (+$35.95).

### Why SPI mode, and what that leaves open

The Teensy's built-in slot runs native 4-bit SDIO, but its card rail is wired straight to the board's
3.3 V and can't be switched. Its DAT0 busy is also not exposed at a timestamped pin. An external slot
on GPIO in SPI mode gives the rig:
- a switchable rail;
- full software visibility of every protocol phase, byte by byte;
- a bus slow enough (4 MHz) for the $27 analyser to decode every transaction.

`judge` accepts `bus_mode: "spi"` with `busy_line: "MISO"` (IR-018-07).

**Open for Verification and PM:** the product bus is SD 4-bit (SDR50, Phase 5). This design assumes
the card's internal power-loss behaviour during programming doesn't depend on which host bus
delivered the block. That is an assumption, not a measurement. If Verification requires native-mode
evidence, a 4-bit variant needs a separate switched slot on the Teensy's SDIO pins plus DAT0 capture.
That is a later rig change; this one doesn't preclude it.

## 2. Wiring

```
 Teensy 4.1 (3V3 out) ──┬──────────────────────────── U3 VCC (always on)
                        │
                        S
                   Q1  DMG2305UX (P-FET)        VCARD ──┬── card VDD (Adafruit 4682 "3V" pin)
       pin 2 ──┬─[10k]──G   D ───────────────────────┤     ├── U2 VCC (SN74LVC125A, switched)
   (CUT, high = off)    │                             │     ├── 10 µF + 100 nF at the socket
               └─[1N4148]┘ (anode at pin: fast off)    │     ├── pull-ups for card side, to VCARD only
                    22 nF gate-to-source (soft start)  │     ├── U3 input A1 ─► U3 Y1 ─► pin 4  RAIL_OK
                    100k gate-to-source (off at boot)  │     └── pin 14 (A0) VCARD sense
                                                       │
       pin 3 ──[100R]── G  Q2 BSS138 (N-FET)  D ─[10R]─┘
       (DISCHARGE)      100k G-to-GND           S ── GND

 Teensy  pin 10 CS   ──► U2 A1 ─► Y1 ─► card CS (DAT3)        U2 = SN74LVC125A powered from VCARD.
 Teensy  pin 11 MOSI ──► U2 A2 ─► Y2 ─► card DI (CMD)         LVC inputs have no clamp diode to VCC,
 Teensy  pin 13 SCK  ──► U2 A3 ─► Y3 ─► card CLK              so a high Teensy pin cannot feed the
 card DO (DAT0) ───────────────────────► Teensy pin 12 MISO   card through them when VCARD is off.
                                         (pull-down, never pull-up: a pull-up to 3V3 would back-power)

 Analyser CH0 SCK · CH1 MOSI · CH2 MISO · CH3 CS · CH4 pin 2 CUT · CH5 RAIL_OK · CH6 pin 5 PHASE · CH7 pin 3 DISCHARGE
```

The parts of this circuit that matter:
- **No back-powering.** A card held up through its I/O protection diodes doesn't lose power when
  the rail opens, and every "cut" would be fiction. The rig removes every path:
  - every line into the card comes from U2, which is powered from VCARD;
  - card-side pull-ups go to VCARD;
  - MISO has a pull-down only.

  The negative control in §7 (control C) proves it.
- **Clean cut.** Pin 2 high turns Q1 off through the diode in about a microsecond. About 2 µs
  later pin 3 turns Q2 on. Q1 and Q2 are never on together (Q2 would short 3.3 V through 10 Ω). Q2
  then pulls VCARD down with a time constant of about 0.1 ms on 10 µF.
- **Soft start.** The 10 kΩ / 22 nF gate network ramps VCARD over a few hundred microseconds,
  inside the SD power-up window (about 0.1–35 ms ramp). The value is tuned on the bench.
- **Safe at boot.** The 100 kΩ resistors hold Q1 off and Q2 off until the firmware drives them.
- **Rail evidence.** RAIL_OK (U3, always on, input from VCARD) gives a timestamped logic edge when
  VCARD falls through the LVC input threshold (about 1.5 V at 3.3 V). Pin 14 reads VCARD with the
  ADC to confirm it is below 0.5 V before every re-power. The SD specification's power-cycle rule is
  below 0.5 V for at least 1 ms; the rig holds it below for 50 ms.

## 3. One trial, step by step

Clock: the Teensy's DWT cycle counter at 600 MHz, converted to microseconds from trial start
(resolution 1.7 ns). In practice it is quantised by the SPI byte time, 2 µs at 4 MHz. PHASE (pin 5)
pulses at every step boundary so the analyser trace can be aligned to the row.

| Step | Action | Recorded |
|---|---|---|
| 0 | Host sends `{iteration N, cut_offset_fraction f}` from the committed plan | — |
| 1 | Power up: VCARD ramps, wait ≥ 1 ms, ≥ 74 clocks at 400 kHz with CS high, CMD0, CMD8, ACMD41 loop, CMD58 (CCS), **CMD59 CRC on**. Then SCK goes to 4 MHz | init time; failures are recorded, not hidden |
| 2 | **CMD10, read the CID** (16 bytes, CRC checked) every trial, after every power-up | `card_cid`: from the card, never from the plan |
| 3 | Write `pattern(N−1)` to the target LBA (CMD24), wait for busy to end, read it back (CMD17) | `precondition_ok`, `precondition_readback_hex` (must equal pattern N−1 exactly) |
| 4 | Read LBAs target−2, −1, +1, +2 | `neighbour_baseline` {-2,-1,+1,+2}: fresh each trial, never carried over |
| 5 | CMD24 with `pattern(N)`: R1, start token 0xFE, 512 bytes, CRC16 | `payload_complete`: true only if all 512 + 2 bytes were clocked out |
| 6 | Read the data-response token | `data_response_accepted`: true only if `token & 0x1F == 0x05` (accepted, not CRC or write error) |
| 7 | Clock 0xFF and read MISO. The first 0x00 byte is busy entry | `busy_entry_us` |
| 8 | Keep polling. Target cut time: `t_cut = busy_entry_us + f × T_ref`. On each 0x00 byte, if now ≥ t_cut: **pin 2 high (cut)**, then pin 3 high | `busy_sampled_us` (the last 0x00 byte, ending within one byte time of the cut); `cut_us` (time pin 2 was written) |
| 8′ | If a non-zero byte is read before t_cut, programming finished: the write completed, so cut anyway (to keep the trial shape) and record it | `busy_deassert_us ≤ cut_us`, so `judge` scores the trial **non-qualifying**, as intended |
| 9 | RAIL_OK falls; hold the rail off for 50 ms; confirm VCARD < 0.5 V on pin 14 | `rail_low_us`, `vcard_mv_before_repower` (extra fields; `judge` ignores unknown fields) |
| 10 | Pin 3 low, pin 2 low: power up and initialise as in step 1, then CID again | the CID must equal step 2's, or the row is flagged |
| 11 | Read the target and four neighbours. There's no host cache: the Teensy holds nothing between power cycles | `readback_hex`, `neighbours` {-2,-1,+1,+2} |
| 12 | Emit the row and go back to step 0 | — |

Every row also carries `bus_mode: "spi"`, `busy_line: "MISO"`, `T_ref` (`busy_ref_us`), the SCK rate
and the rig firmware's commit hash.

**T_ref, the cut scale.** Before the campaign, the rig does 100 uncut writes of the same pattern
cycle to the same block and records each busy duration, from busy entry to the first non-zero byte.
`T_ref` is the **minimum** observed duration, not the median, so every fraction below 1.0 lands in
busy. The calibration file is committed with the plan, before the run.

The plan's fractions are spread uniformly over 0–1.5, so about one attempt in three is expected to
land after programming finished and score non-qualifying. A 1,500-attempt plan
(`--attempts 1500`, as WP-05 states) therefore yields about 1,000 qualifying cuts, right at the
threshold. Expect to need `plan --extend` once. The extension is auditable and under the same run id.

**What the rig never does:**
- it never issues CMD49/CMD48, so the card's optional cache stays at its power-on default (disabled);
- it never retries a failed write within a trial;
- it never drops a row;
- it never edits a row after emitting it.

An initialisation failure after a cut is itself a result. The row is emitted with what is known, and
`judge` reports it as a problem.

## 4. Cuts per hour

| Phase | Typical |
|---|---|
| Off time (fixed) | 50 ms |
| Power-up and init (ACMD41 loop) | 100–400 ms, card dependent; measured in the dry run |
| Precondition write, verify, 4 baseline reads | ≈ 8 ms |
| Cut write | ≤ 3 ms |
| Second init and 5 reads | 100–400 ms |
| Row out (≈ 6 KiB hex over USB) | ≈ 1 ms |
| **Per trial** | **≈ 0.3–0.9 s** |

**Rate: about 4,000–12,000 trials per hour in principle. Plan on 2,000 per hour.** At that rate a
1,500-attempt plan runs in under an hour per card, and one extension adds minutes. The dry run (§7,
control A) reports the real rate before the committed run.

The target block is rewritten about 3,000 times per campaign, which is negligible wear.

## 5. From the rig to the verdict

```
make -C hardware atomicity-test                       # judge self-tests first (WP-05)
media_atomicity.py plan --sku S --revision R --cid C --attempts 1500 --out plan.json
git commit plan.json + tref-calibration.json          # committed BEFORE the run
rig host script: streams each trial in plan.json to the rig, appends every returned row to
                 run.jsonl (line-buffered, fsync per row), adds run_id/sku/revision/plan_digest
media_atomicity.py judge --plan plan.json [--plan ext.json] --results run.jsonl --json RESULT
```

- The host script (`hardware/characterisation/atomicity_host.py`, not yet written) takes `run_id`,
  `sku`, `revision` and `plan_digest` from the committed plan. **`card_cid` comes from the card in
  every row** (steps 2 and 10). The judge cross-checks it against the plan, and a mismatch fails the
  row, so a swapped card is caught.
- One planned attempt produces exactly one row. If the rig resets mid-trial, the host writes a row
  for that iteration with `precondition_ok: false` and the reason, rather than skipping it. Missing
  is a broken run (IR-018-02).
- Analyser traces: every trial of the dry run, and every 50th trial plus every non-qualifying and
  every problem trial of the committed run. Each trace's SHA-256 is recorded beside the run. Traces
  over 1 MiB go to a release asset (CLAUDE.md §4).

## 6. Card identity (A-1)

USB card readers on Windows generally can't read the CID; they don't pass CMD10 through. The rig
reads it natively in step 2, so **the rig is also the A-1 identity reader.** A one-shot "identify"
mode prints and decodes, for each card:

| CID field | Bits | Use |
|---|---|---|
| MID, manufacturer ID | [127:120] | Identity |
| OID, OEM/application ID | [119:104] | Identity |
| PNM, product name (5 ASCII) | [103:64] | Identity, shown next to the retail name |
| PRV, product revision (BCD n.m) | [63:56] | **Proposed as `--revision`** |
| PSN, serial | [55:24] | Distinguishes the three cards |
| MDT, manufacture date | [19:8] | Revision drift between purchases |

It also prints the CSD (CMD9) for capacity. The manufacturer part number isn't in the CID: Michael
photographs the card and packaging markings, and the photo's hash goes in the identity record.
**Which string is the "revision" in the plan is for Verification and PM to fix.** My proposal is
`PNM/PRV` plus MDT recorded alongside.

## 7. Controls: each one must be able to fail

| Control | How | What it proves |
|---|---|---|
| A — Dry run, card in, no campaign | 50 trials with traces of every one; compare the rig's row timestamps and tokens to the decoded analyser trace | The rig reports what's on the wire: token value, busy entry and the cut edge |
| B — Late cut | Force f = 3.0 for 20 trials | Every one has `busy_deassert_us ≤ cut_us`, and `judge` counts it non-qualifying. Shows a completed write can't be scored as a cut |
| C — Back-power | Rail off, SPI pins toggling at full rate for 1 s, VCARD on pin 14 and RAIL_OK | VCARD stays < 0.5 V. If it rises, the isolation has failed and no cut is real |
| D — Wrong card | Swap in a second PNY card mid-dry-run | Its CID differs, and `judge` rejects those rows |
| E — Response decode | Lift MISO (open) for 5 trials | `data_response_accepted` is false, and the trial doesn't qualify |
| F — Judge | The existing `test_media_atomicity.py` cases, including TORN and neighbour damage | The verdict path goes red on a tear. This is already in the repo; run it first |

Controls A–E are part of the dry run, and their traces and rows are evidence. A rig that passes A
but fails C is not a rig.

## 8. What this design does not claim

- No card is qualified by this document, by a dry run or by `judge`'s self-test. Those are three
  separate facts (WP-05).
- SPI-mode evidence and the 4-bit product bus: see §1, open.
- The rig's own firmware is characterisation tooling under `hardware/characterisation/`, not product
  firmware. It doesn't touch `firmware/` or `engine/`. PM can say if that placement should change.
- A torn block is a format blocker, escalated to PM. It is never worked around in firmware.
