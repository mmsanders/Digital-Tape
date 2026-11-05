# Card power-cut rig — design, revision 2 (WP-05 A-6)

**Owner:** Hardware Lead · **Status:** DESIGN for independent method review. **Nothing is built,
energised, bought or run.** Revision 2 drafted 2 November 2026 for
[P3-R2-HW (#651)](https://github.com/mmsanders/Digital-Tape/issues/651). Base: main `cc23b87`.
**Correction 1, 4 November 2026** (base main `51d0f8f`, ADR-204), answering V382's declaration
findings: A gets 15 mV of hysteresis (§2, §4.1); arming, polarity and record rules are explicit
(§3); §4.3 now states which direction each timing error pushes the verdict; control E4 tests A on
slow ramps (§7).

It answers the independent findings R374-1…5 (Verification `3d616c14`,
`findings/P3-R1-374/RIG-METHOD.md`, disposition NOT CLEARED). Revision 1 (#641) is preserved
unchanged at blob `641dbfe22812faebead895b264a40966999068b3` (PR #646 head `80d26364`). §9 lists every
revision-1 claim this revision withdraws or replaces.

- **Procedure:** [WP-05](../../docs/PACKAGES/WP-05.md), "Atomicity procedure".
- **Evidence schema and judge rules:** [ATOMICITY-SCHEMA-R2.md](ATOMICITY-SCHEMA-R2.md). That file
  is a declaration, implemented only where Verification's independent tests have been imported first
  (its status table, and §8 here).

**What this rig can establish:** SPI-mode characterisation of one exact card. It can't qualify a card
for the product's SD 4-bit / SDR50 bus, or for the card system (R374-5, §6).

## 1. What the rig is

A Teensy 4.1 drives one microSD card in **SPI mode at 4 MHz**. The card's 3.3 V rail runs through a
load switch with a built-in output discharge. For each planned trial the rig:
1. establishes the old block and the neighbours;
2. starts a single-block write;
3. enters the busy phase;
4. commands the rail off;
5. **measures** when the rail actually fell out of the card's operating range, and whether busy
   ended before that;
6. powers back up and reads everything again, including the CID.

Revision 1 inferred the cut from a software timestamp. Revision 2 measures two electrical events on
one hardware timer:
- **A, rail opening:** VCARD falls below a specified threshold that is always below 2.70 V.
- **B, busy end:** the card's DO rises above a specified threshold.

The judge qualifies a trial from those two edges and a fixed uncertainty, and fails closed on
anything ambiguous (schema §4).

## 2. Circuit

```
 Teensy 3V3 (always on) ─┬──────────── U1 TPS22918 VIN (1 µF + 100 nF at VIN)
                         │             U1 ON  ◄── Teensy pin CUTn (high = rail on), 100 kΩ to GND
                         │             U1 CT  ── 1 nF C0G to GND        (soft start, ≈1.7 ms typ.)
                         │             U1 QOD ── R_EXT 100 Ω ── U1 VOUT (discharge when ON low)
                         │             U1 VOUT = VCARD ─┬── card VDD (Adafruit 4682 "3V" pin)
                         │                              ├── 10 µF + 100 nF at the socket
                         │                              ├── U2a/U2b/U2c VCC (3 × SN74LVC1G125, switched)
                         │                              ├── card-side pull-ups (to VCARD only)
                         │                              ├── divider 10.0 kΩ / 37.4 kΩ (0.1 %) ─► U3 1IN+
                         │                              └── 100 kΩ ─► Teensy ADC pin (monitor only)
                         │
                         ├── U3 TLV3202 VCC (always on), 100 nF
                         └── 1.0 kΩ ── LM4040A 2.048 V (REF) ─┬─► U3 1IN−          (A threshold)
                                                              └─ 10.0 k / 10.0 k (0.1 %) ─► U3 2IN−  (1.024 V, B)

 Teensy CS   ─► U2a A ─► Y ─► card CS        U2 OE̅ pins tied to GND (always enabled while powered).
 Teensy MOSI ─► U2b A ─► Y ─► card DI        No unused gates: three single-gate parts.
 Teensy SCK  ─► U2c A ─► Y ─► card CLK       Ioff: ±10 µA max per input at VCC = 0 (datasheet §5.5).
 card DO ──────┬───────────────────────────► Teensy MISO (100 kΩ pull-down, never a pull-up)
               └───────────────────────────► U3 2IN+  (B: DO above 1.024 V = busy ended)

 U3 1OUT ── 2.2 MΩ (1 %) ─► U3 1IN+   (positive feedback: ≈ 15 mV of hysteresis at VCARD)
 U3 1OUT (A: high while VCARD above the threshold) ─► Teensy capture input A ┐ same timer,
 U3 2OUT (B: high when DO is high)                 ─► Teensy capture input B ┘ e.g. GPT, 150 MHz
 Test points: VCARD, U1 ON, U3 1OUT, U3 2OUT, DO, GND (for the scope and analyser)
```

- **Switch, R374-4.** The TPS22918 replaces the discrete P-FET, the N-FET discharge, the gate RC
  and the diode. When ON is low it disconnects VIN and connects VOUT to GND through the internal
  pull-down (R_PD) plus R_EXT. When ON is high it connects VIN to VOUT. Source: datasheet §8.3.2,
  Table 4, and the block diagram in §8.2.
- **Buffers, R374-3 and back-power.** Revision 1's SN74LVC125A doesn't state an Ioff
  (partial-power-down) rating in the current datasheet (SCAS290T), so "no clamp to VCC" was
  unsupported. The SN74LVC1G125 states Ioff ≤ ±10 µA at VCC = 0 with an input or output at 5.5 V
  (SCES223U, §5.5) and lists "Ioff … back-drive protection" as a feature. Each buffer's OE̅ is tied to
  GND. Each part has a single gate, so there are no unused inputs to tie off. When VCARD is 0 V the
  Teensy also drives CS, MOSI and SCK low (§3, step 9).
- **Rail threshold, R374-3.** Revision 1's always-on LVC gate (U3, RAIL_OK) is **removed**. A logic
  input has no specified threshold between VIL 0.8 V and VIH 2.0 V, and a maximum input transition
  rate of 8 ns/V, which a 100 µs RC tail violates. Its replacement is a comparator built for slow
  inputs, with a precision reference (§4.1).

### Part data used (primary sources, read 2 November 2026)

| Part | Datasheet | Values used |
|---|---|---|
| TPS22918 load switch | TI SLVSD76C (Jul 2017) | VIN 1–5.5 V. ON: VIH ≥ 1 V, VIL ≤ 0.5 V. R_PD 25 Ω typ., 35 Ω max at 3.3 V. QOD active only with ON low (Table 4). t_OFF 2 µs typ. (only typical values are given, §6.6). Rise time 1680 µs typ. with CT 1 nF at 3.3 V (Table 2). Load ≤ 200 µF with internal R_PD (§8.3.2.2) |
| TLV3202 dual comparator | TI SBOS561C (May 2024) | Supply 2.7–5.5 V. V_IO ≤ 6 mV over −40 to 125 °C (TLV3202). t_PD ≤ 55 ns over temperature, 20 mV overdrive. Input common mode from (VEE − 0.2) to (VCC + 0.2) V. Inputs clamp to the supply rails. Push-pull output. Internal hysteresis 1.2 mV typ. |
| LM4040A-2.048 reference | TI SNOS633N (Aug 2025) | ±0.1 % at 25 °C (A grade). ≤ 100 ppm/°C. Operating current 60 µA to 15 mA (front-page figures for the 2.5 V part; confirm the 2.048 V row in the cart) |
| SN74LVC1G125 buffer | TI SCES223U (Aug 2026) | Ioff ≤ ±10 µA at VCC = 0. Inputs tolerate 5.5 V. VIH 2 V, VIL 0.8 V at 3–3.6 V. t_pd ≤ 4.7 ns |
| SN74LVC125A (revision 1, removed) | TI SCAS290T (Sep 2024) | No Ioff rating stated. Δt/Δv ≤ 8 ns/V |

**SD card signal levels**, from the SD Physical Layer Simplified Specification's 3.3 V bus figures:
VDD 2.7–3.6 V, VOH ≥ 0.75 VDD, VOL ≤ 0.125 VDD. **I didn't re-read this in this round;**
Verification should confirm it against the version it pins.

## 3. One trial, step by step

The capture timer is one hardware timer with two input-capture channels (A, B). Its counter is also
read at software events, so every time in the row is on one timebase. The budget in §4.3 assumes a
150 MHz clock and also covers 24 MHz. The manifest records the actual timer, clock and pins.

| Step | Action | Recorded (schema §4) |
|---|---|---|
| 0 | Host sends `{iteration N, cut_offset_fraction f}` from the committed plan | — |
| 1 | ON high. VCARD soft-starts (≈ 1.7 ms typ.). Wait ≥ 1 ms more, then ≥ 74 clocks at 400 kHz with CS high, CMD0, CMD8, the ACMD41 loop, CMD58 and **CMD59 (CRC on)**. Then SCK to 4 MHz | `init_ms`. Failures are recorded, not hidden |
| 2 | **CMD10: read the CID** | `card_cid` |
| 3 | Write `pattern(N−1)` (CMD24), wait for busy to end, read it back (CMD17) | `precondition_ok`, `precondition_readback_hex` |
| 4 | Read LBAs target −2, −1, +1, +2 | `neighbour_baseline` |
| 5 | CMD24 with `pattern(N)`: R1, 0xFE, 512 bytes, CRC16 | `payload_complete` |
| 6 | Read the data-response token. Check A's output reads high, then **arm capture A and B**. If A reads low, the firmware arms anyway and records `rail_high_at_arm: false`, which the judge treats as a run problem | `data_response_accepted` (`token & 0x1F == 0x05`), `capture_armed_us`, `rail_high_at_arm` |
| 7 | Clock 0xFF continuously. The timer is read when the first 0x00 byte finishes: busy entry | `busy_entry_us` |
| 8 | At `busy_entry + f × T_sched`, read the timer, **then** drive ON low (cut command), so the pin edge is never earlier than the recorded time. **Keep clocking 0xFF** until capture ends, so the busy signal never depends on the clock stopping | `cut_command_us` |
| 9 | Capture runs until `rail_open + 50 µs`, or `cut_command + 2 ms` if A never trips. Then CS, MOSI and SCK are driven low. The rail stays off for 50 ms. The ADC monitor is read | `rail_open_us`, `rail_edges_us`, `busy_end_edges_us`, `capture_end_us`, `vcard_mv_before_repower` |
| 10 | ON high, initialise as in step 1, **CMD10 again** | `card_cid_after_cut`. A mismatch, or a failed initialisation, is a run problem |
| 11 | Read the target and its four neighbours. Nothing is cached between power cycles | `readback_hex`, `neighbours` |
| 12 | Emit the row, unchanged after emission. Every row also carries the firmware's built-in source commit and switch revision, and the SCK | `firmware_source_commit`, `switch_revision`, `sck_hz` |

**Edge records.** Every A and B edge between arming and the end of capture is recorded, in order.
Because A is high at arming, A's edges alternate falling, rising, falling… starting with a falling
edge, and `rail_open_us` is the first one. More than one A edge is "rail chatter", a non-qualifying
miss. A record that contradicts itself (an edge outside the window, out of order, or a claimed opening
that isn't the first recorded edge) is a run problem. The exact rules are schema §4.3–4.4.

**T_sched only spreads the cuts.** It's the median busy time from 100 uncut writes, committed with
the plan. Revision 1 claimed that using the *minimum* would put every fraction below 1 inside busy;
that claim is withdrawn (R374, clarification 1). Whether a cut landed in busy is decided per trial
from A and B, never from f. With f spread over 0–1.5, misses are expected. `plan --extend` continues
the run under the same run id until 1,000 rows qualify.

**What the rig never does:**
- it never issues CMD48 or CMD49;
- it never retries a failed write within a trial;
- it never drops a row;
- it never edits a row after emitting it.

## 4. Electrical analysis

These figures are **analysis from datasheets, not measurements.** §7 lists the measurements that
must confirm each one before a campaign.

### 4.1 Threshold A, rail opening (R374-3)

- **The point to measure:** the first moment VCARD is below 2.70 V, the bottom of the SD operating
  range. A busy end that happens while VCARD ≥ 2.70 V is signalled by a card that's in specification,
  and it must be caught.
- **Divider and reference:** 37.4 / (10.0 + 37.4) = 0.78903, Thevenin resistance 7.89 kΩ. Without
  feedback the trip point is 2.048 / 0.78903 = 2.596 V.
- **Hysteresis (correction 1):** 2.2 MΩ from 1OUT to 1IN+. While the output is high it lifts IN+ by
  about 4.5 mV, so VCARD has to fall further to trip. Nominal: **falling 2.590 V, rising 2.605 V**,
  15 mV apart, against the comparator's own 1.2 mV.
- **Worst case:**
  - reference ±0.1 %, plus 100 ppm/°C over ±10 °C on the bench;
  - divider resistors at 0.1 %, the feedback resistor at 1 %;
  - comparator offset ≤ 6 mV;
  - output high level 3.0–3.4 V.

  That gives a **falling trip between 2.575 V and 2.606 V**, at least **94 mV below 2.70 V**, and a
  rising trip between 2.591 V and 2.619 V. (Without hysteresis it was 2.582–2.610 V.)
- **Why this direction is fail-closed:** after the switch opens, VCARD falls monotonically (control
  E1 confirms it). So A trips no earlier than the moment VCARD actually crossed 2.70 V, and the
  capture window always extends past that moment. Any busy end in-spec is inside the window.
- **Slow input:** a comparator has no maximum input transition rate. Near the threshold, the
  discharge alone falls at about 1.9 V/ms (R_QOD × 10 µF ≈ 1.35 ms), and faster with card current.
  Once A trips, VCARD has to come back up by the 15 mV hysteresis to undo it, and after the cut it
  only falls. So a clean opening gives exactly one A edge. Any second edge is recorded and makes the
  trial a miss ("rail chatter"). An A edge **earlier** than the 2.70 V crossing would need about
  94 mV of noise on VCARD; control E4 checks for it on slow ramps.
- **No back-power path through this circuit:** the comparator's inputs see VCARD through 47.4 kΩ to
  GND. The inputs clamp only above VCC + 0.5 V, and VCARD can't exceed the switch's VIN, which is
  the same 3V3.

### 4.2 Threshold B, busy end (R374-2)

- **Trip point:** 1.024 V nominal, 1.015–1.033 V worst case.
- **Card levels:** at VDD 2.70–3.6 V the card's DO is ≤ 0.45 V low and ≥ 2.03 V high (0.125 and
  0.75 × VDD).
- **Margin:** about 0.57 V below the trip point for a low and 1.0 V above it for a high. So any busy
  end while the card is in specification gives a B rising edge.
- **What B adds to the line:** the 100 kΩ MISO pull-down and the comparator's 2 pF input. That
  doesn't change the card's levels.

### 4.3 Edge-alignment uncertainty U, and which way each error goes

Correction 1 replaces the single error sum with a directional argument, because the two comparators
see very different edges: A sees VCARD falling at volts per millisecond, and B sees DO switching in
nanoseconds.

**Definitions.** t70 is when VCARD actually falls through 2.70 V. tA and tB are the recorded A and B
edges. t_end is when the card actually raised DO at the end of busy. d_B is B's total recording delay.

**A is never early, only late.** A's falling threshold is at least 94 mV below 2.70 V, VCARD falls
monotonically after the cut (E1), and a comparator's delay is never negative. So tA ≥ t70, unless
about 94 mV of noise trips A early, which E4 excludes. A can be **late** by a lot: at 1.9 V/ms,
falling the last 125 mV takes up to about 65 µs, plus up to 55 ns of propagation (at 20 mV overdrive;
it's longer at very small overdrive). U doesn't need to cover that lag, because a late tA only pushes
decisions in the safe direction:
- **Qualification is safe.** A trial qualifies only if every busy end satisfies tB > tA + U. If the
  card actually ended busy at or before t70 (in specification), then tB = t_end + d_B ≤ t70 + d_B ≤
  tA + d_B. So if d_B ≤ U, that trial can't qualify. A's lag only makes it harder to qualify.
- **The rollback rule over-reports.** Completed-before needs tB < tA − U. Because tA can be later than
  t70, a busy end that came after VCARD left the operating range can still count as completed-before.
  That over-reports `completed_write_reverted` (a FAIL), and never hides one. Schema §6 notes it.

**So U must cover B's path, plus any channel offset that makes A read early:**

| Term | Bound |
|---|---:|
| Capture quantisation, both channels (1 tick each at 150 MHz) | 13 ns |
| Input synchroniser asymmetry (2 ticks) | 13 ns |
| B propagation (≤ 55 ns at 20 mV overdrive; DO's overdrive is ≥ 1 V) | 55 ns |
| DO rise from VOL to 1.024 V (≥ 2 mA into ≤ 30 pF is ≤ 15 ns; bounded at) | 100 ns |
| **Sum** | **≈ 0.18 µs** (≈ 0.32 µs at a 24 MHz capture clock) |

The judge uses **U = 1.0 µs** (schema §2), more than 3× the sum. It's a **model value until measured**:
- **E3** drives one fast edge into both channels. That's the waveform B actually sees, so it
  measures the capture skew and B's path. It isn't meant to represent A.
- **E4** drives A with representative slow ramps and checks the one property the safety argument
  needs from A: it never trips before VCARD reaches 2.70 V, and it gives one edge.
- **Dry-run controls A and B2** compare recorded B edges with the analyser trace of DO on a real card.

### 4.4 Switch and discharge overlap (R374-4)

The datasheet doesn't specify dead time between the pass FET and the discharge FET; both are driven
from one control through an inverter (§8.2). The design therefore **bounds the consequence instead of
claiming non-overlap.**
- **Overlap current:** the discharge path is R_EXT 100 Ω in series with R_PD, so even with both FETs
  fully on together, the current is ≤ 3.3 V / 100 Ω = **33 mA** and ≤ 109 mW, mostly in R_EXT. A 1/4 W
  part is enough. That's small next to the Teensy's 3.3 V supply (PJRC rates it at about 250 mA; I
  didn't re-read that figure this round), so an overlap of any length is neither a hazard nor a short.
- **Inrush at power-up:** C_load dV/dt = 10 µF × 3.3 V / 1.68 ms ≈ 20 mA (typical rise, CT 1 nF).
  That's inside the SD power-up ramp window and doesn't sag the Teensy rail.
- **Discharge:** τ = R_QOD × C ≈ (100 + 25…35) Ω × 10 µF ≈ 1.25–1.35 ms. The SD reset condition is
  below 0.5 V; VCARD reaches it within about 2.6 ms. The 50 ms off-time leaves it effectively at
  0 V (below 1 µV by calculation). The ADC reading is only a monitor; the analogue evidence comes
  from E1 and E2.
- **Back-power bound:** at most 3 × 10 µA of Ioff into R_QOD ≈ 135 Ω gives about **4 mV** on VCARD,
  far below 0.5 V. The 4682 board's own pull-ups go to VCARD. MISO has only a pull-down. E2 measures it.

## 5. Cuts per hour

These are unchanged from revision 1. The off-time is still 50 ms, and capture adds at most 2 ms per
trial. **Plan on about 2,000 trials an hour.** Dry-run control A reports the real rate.

## 6. Scope: SPI characterisation only (R374-5)

The judge's support for `bus_mode: "spi"` makes SPI a recorded protocol, not evidence that results
transfer to the product's SD 4-bit (SDR50) bus. Every row and verdict carries the bus mode, SCK, the
switch revision and the manifest hash, and an SPI verdict reports
`qualification_scope: "spi-characterisation"`. **A PASS from this rig doesn't qualify a card for the
product** unless PM disposes the exact qualification scope, or a native-mode rig campaign exists.
A native-mode rig is a separate future design: a switched SDIO slot with DAT0 on comparator B. This
design doesn't extend to SDR50 or to card-system qualification.

## 7. Controls: each must be able to fail

### Before any card is powered in a campaign

These need the circuit energised, which is **not authorised now**. They're listed so that review can
judge the method. Each one's raw files, instrument identities and hashes go into the manifest, **with
its result, pass or fail**. A failed control stays recorded, and the judge refuses a run whose
manifest records any control as failed or missing (schema §5.3). A re-run is a new manifest.

| Control | How | Pass | What it detects |
|---|---|---|---|
| **E0, thresholds (static)** | No card. Drive the divider input and DO input from a potentiometer, read the trip voltages with a DMM: A falling and rising, B rising, 5 repeats each | A falls between 2.57 and 2.61 V, B rises between 1.01 and 1.04 V (schema §2 windows). A's rising trip is recorded and must be above the falling one | A wrong resistor or reference, missing hysteresis, an offset beyond the datasheet |
| **E1, switch and discharge** | No card. 10 µF + 100 Ω dummy load. Scope VCARD, ON and A's output; measure the 3V3 dip with a 1 Ω shunt in series | VCARD falls monotonically from the cut, with no ringing back above the A threshold. Below 0.5 V within 3 ms. Rise 0.5–5 ms. 3V3 dip < 100 mV | A non-monotonic fall that would break §4.1, a failed QOD, inrush |
| **E2, back-power** | Card in, rail off. CS, MOSI and SCK first driven high, then toggled at 4 MHz for 1 s. Scope and DMM on VCARD | VCARD < 50 mV (analysis says ≈ 4 mV) | Any path that keeps the card alive. If it fails, no cut is real |
| **E3, capture skew (fast edges)** | No card. One GPIO step into both comparator inputs through a jumper, 1,000 edges | max \|A − B\| capture difference ≤ 300 ns. That's below U/3 | A slow channel or the wrong capture configuration. It qualifies B's path; it says nothing about A on slow ramps |
| **E4, A on slow ramps** | No card. The real switch and discharge, with no load, 1 kΩ and 33 Ω on VCARD (about 3 mA and 100 mA). Scope VCARD and A's output on a common trigger. 100 cuts per load, plus 20 with a 50 mV, 100 kHz disturbance coupled onto VCARD | On every cut A falls once, no earlier than VCARD's 2.70 V crossing on the scope (allowing the scope's stated timebase error), and doesn't rise again before VCARD is below 0.5 V | An early or chattering A edge: the one A failure that could make a trial qualify wrongly (§4.3) |

### Dry run (card in, no campaign)

| Control | How | What it proves |
|---|---|---|
| **A, wire truth** | 50 trials, all with analyser traces of SCK, MOSI, MISO, CS, ON, A out, B out | The row's tokens and edge times match the wire |
| **B, late cut** | f = 3.0 for 20 trials | Every one: "busy ended before the rail opened", non-qualifying, with the target and neighbours still classified |
| **B2, near busy end** | 200 trials with f swept 0.9–1.1 | Qualifying, ambiguous and ended-before-cut outcomes all appear, and each matches its trace |
| **C, no cut** | Jumper ON permanently high | "rail opening not observed", non-qualifying |
| **D, delayed cut** | Insert a ~1 ms RC on ON | "rail opening outside the cut delay bound", non-qualifying |
| **E, response decode** | DO opened for 5 trials | `data_response_accepted` false |
| **F, identity** | A second card mid-run | `card_cid` ≠ plan: a problem, FAIL |
| **G, judge** | Verification's independently published rig-r2 regressions (V#380), imported unchanged | The verdict path goes red on every declared failure, including damage on non-qualifying rows |

## 8. Sequencing and open questions

1. **Judge code:**
   - **R374-1 is implemented** against V380 (`bab04466`), imported unchanged. V382 disposed it PASS
     on `2faa1180`.
   - **The rig-r2 row predicate is implemented** against V382 `rig_timing_r1` (`8879dbac`, tree
     `ccf9bd21`), imported unchanged before the code.
   - **Plan v4, the manifest loader, rig-r2 row validation and `completed_write_reverted` are
     implemented** against Verification's `rig_records_r1` (`45a6dda0`, tree `0d38fbe2`), imported
     unchanged before the code. Its records are synthetic: a passing judge proves artifact
     consistency, not calibration, a physical cut or a card result.
   - If shared `tests/IMPORTS.json` or CI plumbing is needed, the exact delta goes to Software and PM.
2. **Rig firmware and host script** (`atomicity_host.py`) live under `hardware/characterisation/`.
   They're written after method clearance; their hashes go into the manifest.
3. **`completed_write_reverted` is decided** (ADR-204): it fails run integrity, earns no credit, and
   isn't relabelled TORN. Completed-before is strictly `busy_end < rail_open − U`.
4. **For PM: the SPI qualification scope** (§6).
5. **Card identity (A-1):** `--revision` = `PNM/PRV`. The manifest also records the raw CID, the
   decoded MID/OID/PNM/PRV/PSN/MDT, capacity from the CSD, and the photographed manufacturer part
   number with its hash. Nothing infers controller or silicon equivalence, and no retail speed label
   stands in for identity.

## 9. Revision-1 claims withdrawn or replaced

| Revision-1 claim | Status in revision 2 | Finding |
|---|---|---|
| Late-cut rows need no classification | Withdrawn: every validated row is classified | R374-1 |
| `busy_sampled_us` (last 0x00 byte) and `cut_us` (GPIO write time) prove busy at the cut | Withdrawn: measured A and B edges, ±U, fail-closed | R374-2 |
| The minimum of 100 busy durations makes every fraction below 1 land in busy | Withdrawn: T_sched is a schedule, qualification is per trial | R374 clarification |
| U3 (LVC) gives a ≈ 1.5 V rail threshold from the RC tail | Withdrawn: U3 removed, comparator plus reference instead | R374-3 |
| "LVC inputs have no clamp diode to VCC" (SN74LVC125A) | Withdrawn as unsupported: SN74LVC1G125 with a stated Ioff | R374-3 |
| Q1 off in about 1 µs, Q2 on 2 µs later, never both on | Withdrawn: one load switch with built-in discharge; overlap bounded to ≤ 33 mA by R_EXT | R374-4 |
| SPI evidence stands in for the 4-bit bus | Withdrawn: SPI characterisation only | R374-5 |
| CID compared once, implicitly | Both CID reads recorded; any mismatch is a problem | R374-2 |
