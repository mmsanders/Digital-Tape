# Phase 3 bench parts list

**Owner:** Hardware Lead drafts · **Michael approves and orders** · **Drafted:** 1 November 2026
for [P3-R1-HW (#641)](https://github.com/mmsanders/Digital-Tape/issues/641).
**Input:** main `3826018`. Serves WP-05 A-5 and the round-2 milestone in
[the Phase 3 plan](../../docs/PHASE3-PLAN.md).

> **This is a list, not an order.** Nothing is bought, and no lead can buy anything. Every line is
> Michael's to approve, edit, place and pay for. A parts order never opens board fabrication or cell
> charging.

## Revision 4: staged cart, 10 November 2026 ([#675](https://github.com/mmsanders/Digital-Tape/issues/675) stage 1)

**Base:** main `21b2da3`. **For Michael to approve, edit, place and pay for. Nobody else orders.**
ADR-209 puts the first board on the critical path, so the cart is now split into four groups.
**Only group 1 is needed now.** Revision 3 below stays as history; its totals were estimates, not
a checkout.

### Group 1 — buy first (verified 10 November 2026)

These are enough for USB bring-up, boot, native SD on the Teensy's own slot, the build-to-log link
and stack measurement. Audio over I²S needs the audio board as well.

| # | Part | SKU | Vendor | Qty | Price | Stock | Why |
|---|---|---|---|---:|---:|---|---|
| 1 | Teensy 4.1 **without Ethernet**, headers soldered | DEV-20360 | [SparkFun](https://www.sparkfun.com/teensy-4-1-without-ethernet-headers.html) | 1 | $33.60 | In stock | The bench MCU; its built-in SDIO slot is the work slot. Ethernet isn't used. The with-Ethernet headers version (DEV-16996, $35.95) shows **Backorder** |
| 2 | Teensy 4 Audio Shield Rev D (SGTL5000) | DEV-15845 | [SparkFun](https://www.sparkfun.com/teensy-4-audio-shield-rev-d.html) | 1 | $9.80 | In stock | Codec and headphone out. PJRC's page says Rev D/D2 fits Teensy 4.0 and 4.1, using pins 7, 8, 20, 21, 23 (audio), 18, 19 (I²C) and 10–13 (its own SD) |
| 3 | Male header, 40-pin breakaway | PRT-00116 | [SparkFun](https://www.sparkfun.com/straight-header-male-pth-0-1in-40-pin.html) | 1 | $1.95 | In stock | 28 pins for the audio board's two 14-pin rows, so it sits on the breadboard beside the Teensy (**28 solder joints**) |
| 4 | Full-size breadboard, 830 points | 239 | [Adafruit](https://www.adafruit.com/product/239) | 1 | $5.95 | In stock | Teensy (24 rows), audio board (14 rows) and two buttons fit on one board |
| 5 | Breadboard wire bundle | 153 | [Adafruit](https://www.adafruit.com/product/153) | 1 | $4.95 | In stock | About nine jumpers to the audio board, plus buttons |
| 6 | Tactile buttons, 12 mm, 10-pack | 1119 | [Adafruit](https://www.adafruit.com/product/1119) | 1 | $2.50 | In stock | Bench Play and Stop |
| 7 | USB A to micro-B cable, 3 ft | 592 | [Adafruit](https://www.adafruit.com/product/592) | 1 | $2.95 | In stock | Power, flashing and the serial log. **Skip it if you already have a micro-B cable that carries data**, not just charging |
| | | | | | **$61.70** | | SparkFun $45.35 + Adafruit $16.35 |

- **How this was checked:** each vendor page was read on 10 November 2026. The price and stock are
  the ones the page showed then. **Tax and shipping weren't quoted** (they need a checkout), so
  expect two shipments. If SparkFun has the breadboard, wires, buttons and cable in the same order,
  one shipment is cheaper; I didn't check those SparkFun SKUs.
- **Wiring, not stacking.** The audio board goes beside the Teensy with jumpers: MCLK 23, BCLK 21,
  LRCLK 20, TX 7, RX 8, SDA 18, SCL 19, 3.3 V and GND. Stacking on a Teensy whose pins are already
  in the breadboard would need extended headers (SparkFun PRT-17152, $1.80, **Backorder** on
  10 Nov), and it would hide the built-in SD slot.
- **Soldering:** only the 28 audio-board header pins. A Teensy without headers (DEV-20359, $29.60,
  in stock) saves $4 but adds 48 joints and two more header strips ($3.90), so it's not worth it.
- **Before using headphones:** keep the output at a fixed low level, and check the volume with the
  headphones off the ear (FW-1 §5).

### Group 2 — later, WP-18 to WP-20 (estimates; prices read 1–2 Nov, not rechecked)

| Lines (revision 3) | What | Total |
|---|---|---:|
| 8 (qty 1) | microSD breakout for the second (source) slot, Adafruit 4682 | $3.50 |
| 9–10 | Speaker amplifier PAM8302 and 40 mm speaker | $8.90 |
| 11–12 | MEMS mic and three 3.5 mm jacks | $7.80 |
| 13–14 | Two NeoPixel sticks and the level shifter | ≈$12.50 |
| 15–17 | Hall sensors (two variants) and magnets. **Magnets are a swallowing hazard** | $9.66 |
| 4 (second) | Second breadboard | $5.95 |
| | | **≈$48.31** |

### Group 3 — later, the self-run power-cut test (estimates)

| Lines (revision 3) | What | Total |
|---|---|---:|
| 8 (qty 1) | microSD breakout for the switched card, Adafruit 4682 | $3.50 |
| P1–P5 | TPS22918 ×2, SOT-23-6 adapter ×2, 1 nF C0G ×2, resistor kit, capacitor kit | ≈$25.55 |
| I1 | Basic multimeter, SparkFun TOL-12966 (search snapshot 8 Nov). **Buy it with group 1 if you have no meter at all;** it's handy for bring-up | $21.50 |
| | | **≈$50.55** |

Don't order group 3 until V405 has reviewed the self-run checker and the cut firmware has its own
reviewed interface. Nothing physical is cleared today.

### Group 4 — optional, never an acceptance dependency

| What | Total |
|---|---:|
| 24 MHz 8-channel clone USB logic analyser, debugging only | ≈$12.00 |

**All four groups:** ≈$172.56 before tax and shipping. Only group 1's $61.70 is a checked quote.
Not bought: a lab analyser, sound-level meter, coupler, reader or anything for the CID.

## Revision 3: the ADR-208 cart, 8 November 2026 (history; estimates, superseded by revision 4) ([#671](https://github.com/mmsanders/Digital-Tape/issues/671) stage 1)

**Base:** main `978efb2`. **For Michael to approve. Nobody orders; every line is yours to edit, place
and pay for.** [ADR-208](../../docs/DECISIONS.md#adr-208--hands-on-acceptance-for-physical-and-timing-criteria)
replaces lab instruments with firmware self-measurement and your verdict, and caps instruments at
about $30. This cart **replaces** the 2 November selection and the round 2 delta below, which stay
as history.

**What changed from the round 2 delta:**
- **Removed:** the bench logic analyser (line 18, $26.95), the SPL meter, calibrator and coupler
  (M1–M2), the true-RMS meter (M3), both scope options, and the whole comparator half of the rig:
  TLV3202, LM4040 reference, 0.1 % resistors, trimmer, 2.2 MΩ hysteresis resistor, SOIC adapter and
  the SN74LVC1G125 buffers. None of these is needed by any ADR-208 method.
- **Kept:** every prototype part (lines 1–17) and the rig's load switch with its passives.
- **Added:** a basic multimeter, and an optional clone logic analyser marked debugging-only.

### Prototype parts

| # | Part | SKU | Qty | Price | Why |
|---|---|---|---:|---:|---|
| 1 | Teensy 4.1, headers fitted | SparkFun DEV-16996 | 1 | $35.95 | The bench MCU; built-in SDIO slot is the work slot |
| 2 | Teensy 4 audio board Rev D (SGTL5000) | SparkFun DEV-15845 | 1 | $9.80 | Codec: headphone out, line in/out, mic input; where the output cap lives |
| 3 | 40-pin male header | SparkFun PRT-00116 | 2 | $3.90 | Puts the audio board on the breadboard |
| 4 | 830-point breadboard | Adafruit 239 | 2 | $11.90 | One for the Teensy, one for audio, keys and the power-cut circuit |
| 5 | Jumper wire bundle | Adafruit 153 | 1 | $4.95 | Wiring |
| 6 | 12 mm tactile buttons, 10-pack | Adafruit 1119 | 1 | $2.50 | Bench keys until the latching keys are fitted |
| 7 | USB A to micro-B data cable | Adafruit 592 | 1 | $2.95 | Power, flashing and the serial log. Skip if you have a data cable |
| 8 | microSD breakout, 3 V only | Adafruit 4682 | 2 | $7.00 | One is the second (source) slot; one is the power-cut test's switched slot |
| 9 | Class-D amplifier, 2.5 W | Adafruit 2130 (PAM8302) | 1 | $3.95 | Speaker amp; shutdown pin mutes the speaker, gain trim sets a hardware ceiling |
| 10 | 40 mm 4 Ω speaker | Adafruit 3968 | 1 | $4.95 | The device's speaker size. Out of stock 1 Nov; any 40 mm 4–8 Ω ≥ 1 W will do |
| 11 | Analog MEMS mic breakout | Adafruit 2716 | 1 | $4.95 | Record source when no aux plug |
| 12 | 3.5 mm stereo jack with switch | Adafruit 1699 | 3 | $2.85 | Aux in, headphone/aux out (plug detect), one spare |
| 13 | NeoPixel stick, 8 LEDs | Adafruit 1426 | 2 | $11.90 | The 16-LED status array |
| 14 | 3 V → 5 V buffer for the LED data line | SN74AHCT125N | 1 | ≈$0.60 | NeoPixel data from a 3.3 V pin |
| 15 | Linear Hall sensor ±169 mT | TI DRV5055A4QLPG | 4 | $3.08 | Rew/FF press depth, main variant |
| 16 | Linear Hall sensor ±85 mT | TI DRV5055A3QLPG | 4 | $3.08 | Rew/FF press depth, sensitive variant; the bench picks one |
| 17 | N52 disc magnet 4.76 × 3.18 mm | K&J D32-N52 | 10 | $3.50 | In the Rew/FF keys. **Swallowing hazard: keep away from the kids** |
| | | | | **$117.81** | |

### Power-cut test parts ([POWER-CUT-SELFRUN](../characterisation/POWER-CUT-SELFRUN.md) §1)

| # | Part | SKU | Qty | Price | Why |
|---|---|---|---:|---:|---|
| P1 | Load switch with built-in output discharge | TI TPS22918DBVR (SOT-23-6) | 2 | ≈$1.20 | Switches the card's 3.3 V and pulls it to 0 V on the cut, so the card really resets. One spare |
| P2 | SOT-23-6 to DIP adapter | SparkFun BOB-00717 | 2 | $2.50 | Puts P1 on the breadboard (one soldering job). One spare |
| P3 | 1 nF C0G capacitor | any 50 V C0G, 0.1" leads | 2 | ≈$0.40 | P1's soft start, so the card rail doesn't pull the Teensy down at power-up |
| P4 | Resistor kit, 1/4 W | SparkFun COM-10969 | 1 | $9.95 | 100 kΩ pull-down on the switch, 100 Ω discharge and series resistors, 10 kΩ to the ADC; also bench LEDs and keys. Backordered 1 Nov; any assortment |
| P5 | Capacitor kit | SparkFun KIT-13698 | 1 | $11.50 | 10 µF bulk and 100 nF / 1 µF decoupling at the card and the switch |
| | | | | **$25.55** | |

### Instruments (ADR-208 §4, about $30)

| # | Instrument | SKU | Qty | Price | Why |
|---|---|---|---:|---:|---|
| I1 | Basic digital multimeter | SparkFun TOL-12966 | 1 | $21.50 | Checks the card rail is 0 V when cut and 3.3 V when on, and that the firmware's own reading agrees. Skip it if you already own any multimeter |
| I2 | *Optional.* 24 MHz 8-channel clone USB logic analyser | any FX2 clone (e.g. HiLetgo), works with PulseView | 1 | ≈$12.00 | **Debugging only. Never an acceptance requirement.** Lets us look at the SPI wires if the firmware misbehaves |
| | | | | **$33.50** | $21.50 without the optional analyser |

### Totals (parts only, before tax and shipping)

| | Total |
|---|---:|
| Prototype parts | $117.81 |
| Power-cut test parts | $25.55 |
| **Parts subtotal** | **$143.36** |
| Instruments | $33.50 |
| **Cart total** | **$176.86** |
| Cart total without the optional analyser | $164.86 |

- **Instrument subtotal $33.50**, or $21.50 required. That is ADR-208's "about $30".
- **Prices:** lines 1–17, P2, P4 and P5 were read on the vendors' pages on 1–2 November (stock was as
  shown then); I1 is SparkFun's listed price seen in search results on 8 November, not a page read.
  **≈ means estimated, not read** (DigiKey's bot check blocks part pages; the clone analyser's price
  varies by listing, ≈$12–17 seen 8 Nov). Confirm everything in the cart.
- **Smaller first order:** lines 1–7 alone ($71.95) still play an app-made cartridge. Lines 8–17
  and P1–P5 can follow when WP-18–20 and the power-cut test start.
- **Soldering:** the audio board's headers and the P1 adapter. Everything else is breadboard.

## Superseded history: the 2 November selection and the round 2 delta

> Kept unchanged below for the record. Revision 3 above replaces it.

## Decision: 2 November 2026

Michael approved **"Minimum bench + rig"** (on the #641 thread). That is:

| Lines | What | Total |
|---|---|---:|
| 1–7 | Minimum set | $71.95 |
| 19–25 | Atomicity rig | $30.50 |
| 8 (qty 1, not 2) | The rig's card slot, which the rig section lists as part of the rig | $3.50 |
| 18 | Logic analyser, which the rig's dry-run control A needs. Backordered; any 24 MHz FX2-class clone is fine | $26.95 |
| | **Approved cart** | **$132.90** |

Deferred: the rest of lines 8–17 (second slot, speaker, mic, jacks, LEDs, Hall sensors, magnets)
and the measurement kit M1–M3. Michael places and pays for the order; prices marked ≈ are confirmed
in the cart.

**Not ordered** (Michael, 2 November, PM650). The $132.90 is a planning figure, not a quote.

## Round 2 correction delta (P3-R2-HW #651)

The independent rig review (R374) changed the rig circuit, so the rig half of the selection above no
longer matches [ATOMICITY-RIG.md](../characterisation/ATOMICITY-RIG.md) revision 2. This is the one
concrete delta for PM and Michael. **Nothing in it is approved:** not the substitutions, the
instruments, the optional second Teensy, nor the changed total. The two parts are separate
decisions.

### Part 1: ordinary firmware bench. Unchanged, and doesn't depend on the rig

| Lines | What | Price | Status |
|---|---|---:|---|
| 1–7 | Minimum set | $71.95 | Reusable as selected. Ordinary unbatched playback doesn't need the rig (PM650) |
| 18 | Logic analyser | $26.95 | Reusable. Serves F3 on the bench and rig control A. Backordered 1 Nov |

### Part 2: power-cut rig. Still NOT CLEARED, so don't order before Verification clears revision 2

| Revision-1 line | Revision 2 | Read price | ≈ price |
|---|---|---:|---:|
| 8 (4682 slot ×1) | **Reused** | $3.50 | |
| 19 SN74LVC125AN ×2 | **Replaced:** TI SN74LVC1G125DBVR ×4 (3 + 1 spare). It has a stated Ioff rating | | ≈$1.60 |
| 20 DMG2305UX ×3 | **Replaced:** TI TPS22918DBVR ×2 (1 + spare). A load switch with built-in discharge | | ≈$1.20 |
| 21 BSS138 ×3 | **Dropped** (discharge is inside the TPS22918) | — | — |
| 22 SOT-23 adapters ≈$5 | **Replaced:** SparkFun BOB-00717 SOT23-to-DIP ×6 ($1.25, in stock 2 Nov). Confirm it takes the 5- and 6-pin SOT-23 | $7.50 | |
| 23 1N4148 ×5 | **Dropped** | — | — |
| 24 Resistor kit | **Reused** (R_EXT 100 Ω, pull-downs). Backordered 1 Nov | $9.95 | |
| 25 Capacitor kit | **Reused** (10 µF, 1 µF, 100 nF). Check it has a 1 nF C0G for CT; if not, see below | $11.50 | |
| new | TI TLV3202AIDR dual comparator ×2 (1 + spare), SOIC-8 | | ≈$2.00 |
| new | SparkFun BOB-13655 SOIC-8-to-DIP adapter ×1 ($3.75, in stock 2 Nov) | $3.75 | |
| new | TI LM4040AIZ-2.0 reference (A grade, TO-92) ×2 | | ≈$3.00 |
| new | 0.1 % resistors: 10.0 kΩ ×4, 37.4 kΩ ×2 | | ≈$3.00 |
| new | 1 nF C0G capacitor ×2, 10 kΩ trimmer pot ×1 (for control E0) | | ≈$1.40 |
| new (correction 1, 4 Nov) | 2.2 MΩ 1 % resistor ×2 (A hysteresis, 1 + spare). E4's 1 kΩ and 33 Ω dummy loads come from the kit (33 Ω at ≥ 1/2 W: two 68 Ω 1/4 W in parallel) | | ≈$0.20 |
| | **Rig parts, revision 2, including line 8** | **$36.20** | **≈$12.40** |

- **Rig parts including line 8:** revision 1 was $34.00 (lines 8 and 19–25), revision 2 is ≈$48.60,
  so **+≈$14.60**.
- **The selected cart** (lines 1–7, 8, 18 and the rig) goes from $132.90 to **≈$147.50**, before
  tax and shipping.
- **≈ means not read.** DigiKey's bot check blocked part pages again; these are typical
  distributor prices. Confirm them in the cart.

### Part 2a: instruments that revision 2 needs before the rig is energised

R374-3 and R374-4 need analogue evidence (controls E0–E2). Revision 1 said "no oscilloscope", and
that no longer holds.

| Need | Option | Price | Note |
|---|---|---:|---|
| 2-channel scope, ≥ 20 MHz, for E1 and E2 | **(a)** Hantek 6022BE class USB scope | ≈$70, not read | Cheapest that meets E1/E2. 8-bit, so it isn't the threshold instrument |
| | **(b)** Digilent Analog Discovery 3 | $379.00, read 2 Nov at digilent.com | 2-channel 125 MS/s scope plus a 16-channel logic analyser. It could replace line 18 |
| DMM for the E0 thresholds | M3 brought forward (true-RMS, e.g. UNI-T UT61E+) | ≈$60, not read | Skip it if Michael has a DMM with a dated calibration. Verification approves the instrument |

**Totals with instruments:** ≈$277.50 with option (a) and a new DMM, or ≈$586.50 with option (b).
Without a new DMM, take $60 off either. Whether the instruments are bought, borrowed or substituted
is Michael's call, and Verification approves the models.

**A second Teensy** ($35.95) is still optional, and not approved. Without it, the rig borrows the bench
Teensy.

## How the prices were read

- **Read live on 1 Nov 2026** from the vendor's product page: SparkFun, Adafruit, K&J Magnetics,
  VXB and Transcat lines, plus the two DigiKey Hall-sensor lines. Stock is as shown that day.
- **≈ means estimated, not read.** DigiKey put up a bot check on the other part pages, and I don't
  get past those. Confirm those prices in the cart. Together they come to under $10.
- Prices are in USD and **exclude shipping and tax.** The full set uses six vendors. Expect roughly
  $8–15 shipping each, or combine orders where a vendor stocks the same part.

## The two carts

| Cart | What it gets you | Total (parts only) |
|---|---|---:|
| **Minimum** (round 2) | Teensy 4.1 + audio board on a breadboard, the built-in microSD slot, two keys for Play and Stop, and headphones at a fixed low level. Enough to play an app-made cartridge (FW-1 §1, F5) | **$71.95** |
| **Full** | Minimum, plus the second slot, speaker, mic, aux jacks, LED status, Rew/FF depth sensing, logic analyser, atomicity rig and the acoustic measurement kit | **$848.49** |
| Full, without the measurement kit | Everything except the SPL meter, calibrator and multimeter (lines M1–M3) | $175.26 |

**Measurement kit (M1–M3, $673.23)** is 79% of the full cart. It's needed only when WP-19 measures
the two output caps, so it can be bought last. I recommend ordering **minimum + bench + rig now
($175.26)** and the measurement kit when WP-19's contract is issued.

**Soldering is needed** for the audio board's headers, the SOT-23 adapters and the rig. The
Teensy 4.1 comes with headers fitted. If the soldering iron turns out not to be available, tell me:
a ready-made adaptor costs more but needs no iron, and I'll swap the lines.

## Minimum set — round 2

| # | Part | Exact model / SKU | Vendor | Qty | Unit | Ext. | Why | Serves |
|---|---|---|---|---:|---:|---:|---|---|
| 1 | Teensy 4.1 with headers fitted | SparkFun **DEV-16996** (PJRC Teensy 4.1, Ethernet chip, pins soldered) | [SparkFun](https://www.sparkfun.com/teensy-4-1-headers.html) | 1 | $35.95 | $35.95 | The FW-1 target MCU. Built-in SDIO microSD slot is the WP-17 work slot. In stock. (No-Ethernet variant DEV-20360 is $33.60, also fine) | WP-17 F1–F6 |
| 2 | SGTL5000 audio board | **Teensy 4 Audio Shield Rev D**, SparkFun **DEV-15845** (PJRC Audio Adaptor Rev D) | [SparkFun](https://www.sparkfun.com/teensy-4-audio-shield-rev-d.html) | 1 | $9.80 | $9.80 | Codec named in FW-1 §1: headphone out, line in/out, mic input, I²S. In stock | WP-17, WP-19 |
| 3 | Male header, 40-pin breakaway | SparkFun **PRT-00116** | [SparkFun](https://www.sparkfun.com/straight-header-male-pth-0-1in-40-pin.html) | 2 | $1.95 | $3.90 | Pins for the audio board, so it sits on the breadboard and wires to the Teensy (see the note after this table) | WP-17 |
| 4 | Full-size breadboard, 830 points | Adafruit **239** | [Adafruit](https://www.adafruit.com/product/239) | 2 | $5.95 | $11.90 | One for the Teensy (0.6" wide, 48 pins), one for audio, keys and the rig | A-5 |
| 5 | Breadboard wire bundle | Adafruit **153** | [Adafruit](https://www.adafruit.com/product/153) | 1 | $4.95 | $4.95 | Jumpers. Adafruit's premium M/M jumper packs (758, 1956) were out of stock on 1 Nov | A-5 |
| 6 | Tactile buttons, 12 mm, 10-pack | Adafruit **1119** | [Adafruit](https://www.adafruit.com/product/1119) | 1 | $2.50 | $2.50 | Bench Play and Stop (FW-1 §1.4). The full set uses six of the ten: Record, Play, Stop, Copy, plus spares | WP-17 F5, WP-20 |
| 7 | USB A to micro-B data cable | Adafruit **592** | [Adafruit](https://www.adafruit.com/product/592) | 1 | $2.95 | $2.95 | Power, flashing and the F1 PCM/hash stream. Skip it if Michael has a micro-B *data* cable | WP-17 F1 |
| | | | | | | **$71.95** | | |

**The audio board doesn't stack on the Teensy 4.1 here.** It's wired beside it with about nine jumpers:
- MCLK 23, BCLK 21, LRCLK 20, TX 7, RX 8;
- SDA 18, SCL 19;
- 3.3 V and GND.

This leaves every other Teensy pin free for keys, the second slot and the rig. Stacking would need the
extended header kit (SparkFun PRT-17152, $1.80, on backorder 1 Nov), which also covers SPI pins 10–13
that the second slot wants.

**Headphone safety (FW-1 §5).** Until the WP-19 cap lands, the bench output stays at a fixed low level.
Nobody wears headphones on the bench without first checking the volume with the headphones off the ear.

## Full set — added to the minimum

### Second slot, audio paths and status (WP-18, WP-19, WP-20)

| # | Part | Exact model / SKU | Vendor | Qty | Unit | Ext. | Why | Serves |
|---|---|---|---|---:|---:|---:|---|---|
| 8 | microSD breakout, 3 V only, SPI or SDIO | Adafruit **4682** | [Adafruit](https://www.adafruit.com/product/4682) | 2 | $3.50 | $7.00 | One is the WP-18 rear (source) slot. One is the atomicity-rig slot: it has no regulator or level shifter, so the rig can switch the card's own rail. In stock | WP-18, WP-05 A-6 |
| 9 | Mono class-D amplifier, 2.5 W | Adafruit **2130** (PAM8302) | [Adafruit](https://www.adafruit.com/product/2130) | 1 | $3.95 | $3.95 | Speaker amp fed from the SGTL5000 line out. Its **SD (shutdown) pin** mutes the speaker for headphones and recording. Its **gain trim pot** gives a hardware ceiling under the codec cap | WP-19 speaker, mute, S cap |
| 10 | Speaker, 40 mm, 4 Ω | Adafruit **3968** | [Adafruit](https://www.adafruit.com/product/3968) | 1 | $4.95 | $4.95 | The ~Ø40 driver from DEVICE-DESIGN §4. **Out of stock 1 Nov.** Any 40 mm, 4–8 Ω, ≥ 1 W speaker will do for the bench | WP-19 |
| 11 | Analog MEMS microphone breakout | Adafruit **2716** (Knowles SPW2430) | [Adafruit](https://www.adafruit.com/product/2716) | 1 | $4.95 | $4.95 | MEMS, as in the device. Analog output into the SGTL5000 mic/line input, so no second I²S port is needed | WP-19 mic, record source |
| 12 | 3.5 mm stereo jack, breadboard | Adafruit **1699** | [Adafruit](https://www.adafruit.com/product/1699) | 3 | $0.95 | $2.85 | Aux in and headphone/aux out. **Both have disconnect switches**, which give the plug-detect inputs for "headphones mute speaker" and "aux in wins over mic". The third is a spare | WP-19 |
| 13 | NeoPixel stick, 8 × RGB | Adafruit **1426** | [Adafruit](https://www.adafruit.com/product/1426) | 2 | $5.95 | $11.90 | Two sticks make the 16-LED status array: position, end of tape, red for cartridge full, record light. The 16-LED ring (Adafruit 1463) was out of stock 1 Nov; take it instead if it's back | WP-20, WP-18 progress |
| 14 | 3 V → 5 V level shifter | **SN74AHCT125N** (DIP-14) | [DigiKey](https://www.digikey.com/en/products/result?keywords=SN74AHCT125N) | 1 | ≈$0.60 | ≈$0.60 | NeoPixel data from a 3.3 V pin, with the LEDs on USB 5 V at low brightness. Adafruit's 1787 was out of stock | WP-20 |
| 15 | Linear Hall sensor, ±169 mT | TI **DRV5055A4QLPG** (TO-92) | [DigiKey](https://www.digikey.com/en/products/result?keywords=DRV5055A4QLPG) | 4 | $0.77 | $3.08 | Rew/FF depth sensing ([REW-FF-DEPTH](../controls/REW-FF-DEPTH.md)): the main variant. Two keys plus spares | WP-20 depth scrub |
| 16 | Linear Hall sensor, ±85 mT | TI **DRV5055A3QLPG** (TO-92) | [DigiKey](https://www.digikey.com/en/products/result?keywords=DRV5055A3QLPG) | 4 | $0.77 | $3.08 | The more sensitive variant. Which one wins is settled on the bench, and the pair costs $6 | WP-20 |
| 17 | Magnet, N52 disc, 4.76 × 3.18 mm | K&J **D32-N52** | [K&J Magnetics](https://www.kjmagnetics.com/d32-n52-neodymium-disc-magnet) | 10 | $0.35 | $3.50 | Pressed into the Rew/FF keys. **Keep them away from children:** small magnets are a swallowing hazard. The device design must capture the magnet completely (REW-FF-DEPTH §5) | WP-20 |
| 18 | Logic analyser, 24 MHz, 8 channels | SparkFun **TOL-18627** | [SparkFun](https://www.sparkfun.com/usb-logic-analyzer-24mhz-8-channel.html) | 1 | $26.95 | $26.95 | F3 warm instant-on (wake GPIO → I²S data) and the atomicity rig's wire traces. Works with sigrok/PulseView. **Backorder 1 Nov.** Any 24 MHz FX2-class clone will do (see "What each instrument can claim") | WP-17 F3, WP-05 A-6 |
| | | | | | | **$72.81** | | |

### Atomicity rig (WP-05 A-6), design in [ATOMICITY-RIG](../characterisation/ATOMICITY-RIG.md)

The rig also uses line 8 (its card slot), line 18 (the analyser), and a second Teensy *or* the
bench Teensy borrowed (see the rig design §1).

| # | Part | Exact model / SKU | Vendor | Qty | Unit | Ext. | Why |
|---|---|---|---|---:|---:|---:|---|
| 19 | Quad buffer, 5 V-tolerant inputs | **SN74LVC125AN** (DIP-14) | [DigiKey](https://www.digikey.com/en/products/result?keywords=SN74LVC125AN) | 2 | ≈$0.80 | ≈$1.60 | U2 is powered from the *switched* card rail, so the Teensy can't back-power the card through CS/SCK/MOSI. U3 is always on and gives the rail-present signal |
| 20 | P-MOSFET, logic level, SOT-23 | Diodes **DMG2305UX-7** | [DigiKey](https://www.digikey.com/en/products/result?keywords=DMG2305UX-7) | 3 | ≈$0.40 | ≈$1.20 | Q1 is the card rail switch (Vgs(th) ≤ 0.9 V, so a 3.3 V pin turns it fully on and off). Two spares |
| 21 | N-MOSFET, SOT-23 | onsemi **BSS138** | [DigiKey](https://www.digikey.com/en/products/result?keywords=BSS138) | 3 | ≈$0.25 | ≈$0.75 | Q2 is the active discharge, pulling the card rail to 0 V within microseconds of the cut |
| 22 | SOT-23 to DIP adapters | Any 0.1" SOT-23 adapter PCB set (Adafruit 1230 was out of stock 1 Nov) | — | 1 set | ≈$5.00 | ≈$5.00 | So Q1 and Q2 can go on the breadboard |
| 23 | Small-signal diode | **1N4148** | [DigiKey](https://www.digikey.com/en/products/result?keywords=1N4148) | 5 | ≈$0.10 | ≈$0.50 | Fast gate turn-off path |
| 24 | Resistor kit, 1/4 W, 500 pieces | SparkFun **COM-10969** | [SparkFun](https://www.sparkfun.com/resistor-kit-1-4w-500-total.html) | 1 | $9.95 | $9.95 | Gate, discharge, pull-up/down and LED resistors for the rig and bench. **Backorder 1 Nov.** Any 1/4 W assortment will do |
| 25 | Capacitor kit | SparkFun **KIT-13698** | [SparkFun](https://www.sparkfun.com/sparkfun-capacitor-kit.html) | 1 | $11.50 | $11.50 | Decoupling at the card socket, the gate RC soft start, and the Hall sensor bypass. In stock |
| | | | | | | **$30.50** | |

### Acoustic measurement kit (WP-19 caps): buy when WP-19's contract is issued

| # | Part | Exact model / SKU | Vendor | Qty | Unit | Ext. | Why |
|---|---|---|---|---:|---:|---:|---|
| M1 | Sound level meter, IEC 61672-1:2013 **Class 2**, with calibration certificate | VXB "Type 2 Sound Level Meter With Calibration Certificate" (listing gives no maker part number) | [VXB](https://vxb.com/products/type-2-sound-level-meter-with-calibration-certific) | 1 | $317.95 | $317.95 | Speaker cap (S): A-weighted, time-averaged, at 50 cm. Headphone cap (H): with a coupler. **Substitute any Class 2 meter that has a dated certificate and an Leq function**: Verification should approve the model before purchase |
| M2 | Acoustic calibrator, 94 dB at 1 kHz, IEC 60942 Class 2 | **B&K Precision CAL73** | [Transcat](https://www.transcat.com/b-k-precision-cal73-cal73) | 1 | $295.28 | $295.28 | Field check of M1 before and after every session, as EN 71-1 §8.28 and ISO 11201/11202 practice expect. Without it a drift can't be detected |
| M3 | True-RMS multimeter (AC mV) | Any true-RMS DMM rated ≥ 20 kHz, e.g. UNI-T **UT61E+** | — | 1 | ≈$60.00 | ≈$60.00 | Electrical half of the H-cap method (jack voltage, EN 50332-2 style) and rig rail checks. Skip it if Michael already has one |
| | | | | | | **$673.23** | |

The coupler for the headphone cap is **printed, not bought**: a flat-plate coupler sized for M1's
microphone, printed on the A1 Mini. Its limits are below.

## What each instrument can claim

These are estimates for planning. The measured figures come from Verification's audit of each run.

| Instrument | Calibration | What it can support | What it cannot |
|---|---|---|---|
| Logic analyser (18) | None. Timebase from a crystal, typically ±50 ppm | F3: a 100 ms interval to ±1 sample (41.7 ns at 24 MS/s) plus ±5 µs timebase. Rig: SPI at the 4 MHz rig clock gives 6 samples per bit, so every byte and token can be decoded | Analog levels. Its "rail present" channel is a logic threshold, not a voltage measurement |
| M1, Class 2 meter | Manufacturer certificate (dated) | Engineering estimate of LpA. Class 2 tolerance at 1 kHz is about ±1.4 dB, and wider at frequency extremes | **Not** the Class 1 instrumentation EN 71-1 §8.28.1.2 requires for compliance testing. Not a free-field-qualified room. Bench results are design evidence; certification is a lab test (Phase 5) |
| M2, calibrator | Class 2, about ±0.5 dB at 94 dB | Detects M1 drift between sessions | Doesn't make M1 Class 1 |
| Printed coupler + M1 | None; geometry only | Relative headphone level, repeatable on the same headphones | Not an IEC 60318-4 ear simulator. Absolute error could be ±3–5 dB and depends on frequency. The H cap's absolute value rests on the electrical method (jack voltage plus the reference headphones' sensitivity), with the coupler as a cross-check |
| Hall sensors (15, 16) | Per-key two-point calibration (rest and full press) at boot or in the factory | Depth to well under 0.1 mm at the light end (REW-FF-DEPTH §3) | Absolute travel. Depth is relative to each key's own calibration |

## Not on this list

- **Cards.** The three owned PNY 64 GB V30 cards are the atomicity and WP-05 samples. The rig reads
  each card's CID itself (ATOMICITY-RIG §6), so no special reader is needed for A-1 identity.
- **Battery, charger, cells and any board fabrication.** CLOSED. The bench runs on USB.
- **An oscilloscope** *(revision 1; superseded by the round 2 delta, Part 2a).* The rig records its
  rail with a logic threshold and the Teensy's own timestamps, which the analyser cross-checks. If
  Verification wants an analog rail trace, a two-channel USB scope is the next line to add. I haven't
  priced it.
- **An ear simulator (IEC 60318-4).** It costs thousands. The electrical method plus the printed
  coupler stands in for the bench; the compliance lab has one.
