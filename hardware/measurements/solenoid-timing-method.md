# Proposed method — one-shot guaranteed pulse width at 3.3 V (IR-018-16)

**Work package:** WP-34 / WP-04 bench · **Owner:** Hardware Lead proposes; Michael witnesses;
Verification audits · **Status:** `PROPOSED — not run, not accepted, no parts ordered`

> This document proposes a method. **It reports no measurement.** No number in it is evidence
> of anything, and nothing here is an acceptance of the IR-015 solenoid response.

## 1. The gap this closes, stated exactly

`spec/hw/thermal-budget.md` §6 rests on a one-shot timing tolerance of **±14 %**
(`IC_TOL` in `hardware/thermal/solenoid_timing.py`). That figure is **extrapolated** from a
single datasheet test point — 602…798 µs at Cx = 0.1 µF, Rx = 10 kΩ, **VCC = 5 V** — and is
then applied to a **390 ms** interval at **3.3 V** with a different R/C. Neither the interval,
the R/C, nor the rail is the condition the published figure covers.

As of 12 September 2026 the **part is bound** — TI `CD74HC221E` (16-DIP) for the bench,
`CD74HC221M96` (16-SOIC) for the board, both catalogued at 2–6 V, which covers 3.3 V. What is
**not** bound is the part's **guaranteed minimum and maximum pulse width at 3.3 V** over the
intended R/C and temperature range. Every host serving that datasheet is blocked from the
lead's environment (`ti.com`, `mm.digikey.com`, `rocelec.widen.net`, `nexperia.com`), so the
table cannot be read here. See `hardware/sourcing/2026-09-12-parts.md`.

**Two routes close it.** Either someone reads the manufacturer's pulse-width table at 3.3 V and
the assumed corner is replaced by a guarantee, or the circuit is measured. The routes are not
equivalent: a datasheet gives a *guaranteed* limit across process spread, a bench measurement
gives *these* parts on *this* day. **A measurement of five parts is not a process guarantee**,
and §9 below says what it can and cannot support.

## 2. Why this is runnable while the fabrication gate is CLOSED

**It needs no board and no cell.** The measurand is the one-shot's own output pulse, on a
breadboard: IC, timing resistor, timing capacitor, a 3.3 V bench supply, a signal source and an
oscilloscope. **The coil is not connected.** No PCB is fabricated, no lithium cell is charged
or even present, and no energy is stored anywhere in the setup.

That is the whole reason to propose it now. `make -C hardware fabrication-gate` reads **CLOSED**
and must continue to; this method sits entirely outside what that gate holds, and running it
does not open it. **If any step in a revision of this method comes to require a coil, a cell or
a fabricated board, that revision is out of scope and goes back to the PM.**

## 3. Procedure

1. Record the exact parts: manufacturer, MPN, date/lot code from the package, and the
   distributor order they came from. **Five devices minimum**, so device spread is visible
   rather than assumed.
2. Measure each timing resistor and capacitor **individually** on the DMM/LCR before fitting,
   and record the measured values. The analysis currently allocates ±1 % (R) and ±5 % (C); if
   the parts are measured, those terms shrink to instrument uncertainty and the IC term is
   isolated, which is the point of the exercise.
3. Build the pulse half at the design point: R = 143 kΩ, C = 100 nF C0G, nominal 10 ms.
4. Build the inhibit half at the design point: R = 557 kΩ, C = 1 µF film, nominal 390 ms.
   **Both halves are measured.** The 390 ms interval is the one the safety bound rests on and
   it is the one furthest from any published test point.
5. Set VCC to **3.300 V measured at the IC's own supply pins**, not at the supply's display.
   Record the measured rail with every reading.
6. Trigger each half at least **20 times** per device per condition and record every pulse
   width, not a mean. Trigger from a clean edge source, not by hand.
7. Repeat the full set at each temperature condition in §5.
8. Record what was **not** done. If the temperature extremes are not reachable, say so here
   rather than reporting an ambient-only spread as if it covered the range.

## 4. Instruments

Fill `TEMPLATE.md` §3 for the actual session. The method requires at minimum:

| Instrument | Requirement | Why this requirement |
|---|---|---|
| Oscilloscope | Timebase accuracy **stated on the record**, ≥ 10× the shortest interval in resolution | The measurand is time; an unstated timebase error is an unbounded error on the result |
| DMM | 4½ digit, recently checked | Rail voltage is a condition of the answer, not a detail |
| LCR or DMM with C range | Reads 100 nF and 1 µF to ≤ 1 % | Separates the R/C term from the IC term |
| Thermometer | ±1 °C, probe **at the IC package**, not room air | The IC's junction is what sets the K-factor |
| Bench supply | 3.3 V, current-limited | — |

Record the git SHA of anything built for the session, per `TEMPLATE.md` §3.

## 5. Conditions

| Condition | Target | If unreachable |
|---|---|---|
| Ambient | 23 ± 2 °C | Record actual; this one is not optional |
| Cold | 0 °C (the cold corner `T_COLD_C` already used for the coil) | Report the cold term as **still unbound**; do not interpolate |
| Hot | 45 °C (the charger hot-suspend limit, so the numbers align) | Report the hot term as **still unbound** |

A domestic freezer and a closed box with a thermostatically controlled warm source are both
acceptable if — and only if — the package temperature is measured and logged throughout, and
condensation is kept off the board on the cold leg. **An uncontrolled "it was cold outside" is
not a condition**, and a record that cannot say what the package temperature was during a
reading cannot support a temperature term at all.

## 6. Raw fields to capture

One row per trigger, not per device:

```
device_id, mpn, lot_code, half (A|B), r_measured_ohm, c_measured_f,
vcc_measured_v, package_temp_c, trigger_index, pulse_width_s, scope_timebase_accuracy_ppm
```

Commit the scope's own log where it produces one. Outliers stay in, marked, per
`measurements/README.md`.

## 7. Derivation

For each half and condition, report the **extreme** measured values, not a mean ± σ — the
analysis needs a worst corner, and a mean hides it. Compare the observed spread against
`IC_TOL` after subtracting the measured R/C contribution. Show the arithmetic.

## 8. Uncertainty

At minimum: scope timebase accuracy; trigger-to-threshold definition (state the voltage
threshold used for "pulse start" and "pulse end" — HC output thresholds are supply-dependent
and this choice moves the answer); R and C measurement accuracy; package temperature accuracy
and settling time; device-to-device spread as measured, plus the fact that five devices from
one lot bound one lot.

## 9. What this can and cannot support

**Can:** replacing an *extrapolated* ±14 % with a *measured* spread for these parts at this
rail, at the conditions actually achieved; and detecting the failure mode that matters most —
that the real spread at 390 ms and 3.3 V is materially **wider** than 14 %, which would put the
0.25 W bound in question rather than confirm it.

**Cannot:** establish a process guarantee. Five devices from one lot is not the population a
datasheet limit covers. If the measured spread lands close to ±14 %, the honest disposition is
that the assumption is *not contradicted*, not that it is proven — and `TIMING_BOUND_VERIFIED`
should stay `False` until a manufacturer limit at this rail is actually read. **The flag means
"a guaranteed limit was read", and a measurement is not that.** Whoever dispositions this
result has to decide that question explicitly; it is not the measurer's to decide, and it is
certainly not mine.

## 10. What this needs before it can run

- **Michael's approval and purchase** of the bench parts. A rough set is five one-shots, the
  timing R and C, and a breadboard; the distributor line items are in
  `hardware/sourcing/2026-09-12-parts.md`. **No order is placed and none is authorized here.**
- **Verification's review of this method before it runs**, per PM Decisions 001 §4 and
  `WP-05`/`WP-24`'s standing "criteria to the Verification Lead before the run" rule. The
  failure mode with a self-designed test is the criterion, not the measurement.
- Michael witnessing the session, per PM Decisions 006 §5.

**Acceptance fields are deliberately left unsigned.** The author of a response does not get to
accept it.
