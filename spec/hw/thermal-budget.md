# Thermal and safety budget — WP-34

**Owner:** Hardware Lead · **Status:** living document, versioned not frozen (PM Decisions 001 §3)
**Revision:** 0.1, 2 Sep 2026 · **Applies to:** production board rev A
**Estimates, not measurements.** WP-37 replaces every `EST` in this document with a measured
number. Until it does, treat the margins as indicative.

> **This document is generated in part.** The tables come from
> `hardware/thermal/budget.py`. Edit the inputs there and run `make -C hardware thermal`.
> `make -C hardware thermal-check` fails if this file is stale, so the numbers cannot drift
> away from the model that produced them.

---

## 0. What this document concluded

Three things, and only the third is what the charter expected.

1. **The bulk thermal case is not the problem, and it is more comfortable than assumed.** The
   copy — the loudest electrical event in the product — is thermally free, because 30 seconds
   is nothing against a 10-minute enclosure time constant. A sealed case is fine.
2. **The sustained worst case is not the copy. It is playing while charging**, which is also
   the single most likely thing this device is ever doing. That case runs ~9.8 K over ambient
   inside a sealed box, and in a 35 °C room it lands **within 0.2 K of the 45 °C JEITA charge
   ceiling**. The failure is not damage; it is a device that silently stops charging on a warm
   afternoon, in a product with no screen to explain itself. §4 and §7.
3. **The solenoid needs two protections, not one.** The charter's hardware one-shot bounds
   pulse *width* and does nothing about *duty cycle*. A firmware retrigger loop delivers most of
   the coil's rated power through a correctly functioning one-shot. §6.

A fourth, smaller: the charter's ~2.2 W worst case did not count both microSD cards at
sustained UHS-I. With them, the copy case is **2.74 W**. It does not change any conclusion,
because of finding 1 — but it would have if the copy ran for ten minutes instead of thirty
seconds.

---

## 1. Scope and method

Every part dissipating more than 50 mW gets a line (Hardware Charter §06). Below that they are
folded into rail quiescent figures.

Three modes are budgeted: **idle** (asleep, waiting for a button), **playback** (one card
streaming, audio out), and **copy** (both cards at UHS-I, the electrical worst case). Each is
budgeted with and without charging.

Heat leaves the enclosure by one path only. It is sealed — no vents, which keeps crumbs and
sand out of the slots — so there is no forced or through-flow convection. That gives a
two-stage resistance:

```
      junction ──► board ──► internal air ──► case wall ──► ambient
                   └── §3 "board→air step" ──┘└─ §3 "case rise" ─┘
```

The board→air step is the number I trust least. In a sealed volume there is very little
internal convection, so it is dominated by radiation and by conduction through the mounting.
It is also the step the charter's 8 K figure omits entirely — 8 K is a case-to-ambient number.
**WP-37 measures this step first**, because every other margin in this document sits on it.

### Environment and enclosure

| Input | Value | Source |
|---|---|---|
| Enclosure | 110 × 75 × 28 mm sealed | Hardware Charter §04 |
| Surface area | 268.6 cm² | computed |
| Combined h, case→ambient | 9 W/m²K | EST, free convection + radiation, ±30% |
| Effective h, board→internal air | 22 W/m²K | **EST, the weakest number here** |
| Thermal mass | 150 J/K | EST — ~150 g of plastic, board and cell |
| Ambient design points | 25 / 30 / 35 °C | 35 °C is a warm room or a sunny windowsill |

---

## 2. Per-rail power budget

<!-- BEGIN GENERATED: loads -->
| Load | Rail | Idle | Playback | **Copy** | Source |
|---|---|---:|---:|---:|---|
| i.MX RT1062 @ 600 MHz | `+3V3` | 20 mW | 363 mW | **594 mW** | EST |
| PSRAM (APS6404L QSPI) | `+3V3` | 0 mW | 49 mW | **99 mW** | EST/UNVERIFIED |
| QSPI flash | `+3V3` | 0 mW | 26 mW | **49 mW** | EST/UNVERIFIED |
| SGTL5000 + headphone amp | `+3V3A` | 0 mW | 116 mW | **16 mW** | EST |
| microSD, source slot | `+3V3` | 0 mW | 148 mW | **660 mW** | EST |
| microSD, destination slot | `+3V3` | 0 mW | 0 mW | **726 mW** | EST |
| LED banks | `+3V3` | 0 mW | 33 mW | **82 mW** | EST |
| +1V8 rail quiescent | `+1V8` | 0 mW | 4 mW | **14 mW** | EST |
| **Load subtotal** | | **20 mW** | **740 mW** | **2242 mW** | |
| Buck loss @ 90% | `VBAT` | 2 mW | 82 mW | 249 mW | EST |
| Charger loss @ 90% | `+5V` | 233 mW | 233 mW | 233 mW | EST |
| Cell I²R @ 60 mΩ | `VBAT` | 15 mW | 15 mW | 15 mW | EST |
| **Total in the box, charging** | | **270 mW** | **1070 mW** | **2.74 W** | |
<!-- END GENERATED: loads -->

By rail:

<!-- BEGIN GENERATED: rails -->
| Rail | Idle | Playback | Copy |
|---|---:|---:|---:|
| `+1V8` | 0 mW | 4 mW | 14 mW |
| `+3V3` | 20 mW | 620 mW | 2211 mW |
| `+3V3A` | 0 mW | 116 mW | 16 mW |
<!-- END GENERATED: rails -->

**Assumptions worth challenging.** Audio is treated as muted during a copy — the device is not
playing and copying at once. If that is wrong, add ~115 mW to the copy column; it changes
nothing, because of §3. The two microSD figures (200 mA read, 220 mA write) are pessimistic
picks; the WP-05 card characterisation measures current alongside throughput, so these become
`MEAS` in revision 0.2. The `+1V8` rail carries almost no DC load — it is a signalling rail —
so its cost is the regulator's quiescent draw, not the number in the table.

---

## 3. Scenarios — steady state and transient

<!-- BEGIN GENERATED: scenarios -->
| Scenario | Duration | Power in box | Case rise (steady) | Board→air step | Realised rise |
|---|---|---:|---:|---:|---|
| Asleep, charging | indefinite | 0.27 W | 1.1 K | 1.4 K | **2.5 K** (reaches steady state) |
| Playback, charging | indefinite | 1.07 W | 4.4 K | 5.4 K | **9.8 K** (reaches steady state) |
| Copy, not charging | 30 s | 2.49 W | 10.3 K | 12.6 K | **0.5 K** bulk + local (see below) |
| Copy + charging (WP-37 stress) | 30 s | 2.74 W | 11.3 K | 13.8 K | **0.5 K** bulk + local (see below) |
| Copy + charging, held (fault) | indefinite | 2.74 W | 11.3 K | 13.8 K | **25.2 K** (reaches steady state) |

Enclosure surface area **268.6 cm²**; thermal time constant **τ = 621 s (10 min)**.
<!-- END GENERATED: scenarios -->

**This table is the whole argument.** A copy dissipates 2.74 W, which sounds alarming and is
not, because it runs for 30 seconds against a 621-second time constant: the enclosure absorbs
85 J and rises about half a kelvin. The device cannot get hot doing the thing it was designed
to do quickly.

What *can* get hot is the thing it does for hours. Playback while charging is only 1.07 W, but
it is sustained, so it reaches steady state and it is the case that governs.

**The last row is a fault, not a use case** — copy held indefinitely by a stuck firmware state.
It is in the table because WP-37 tests exactly that for an hour, and because it is the case
that would justify vents if any case did. It does not: even held, it settles at a survivable
temperature. It is a legibility problem (§7), not a damage problem.

---

## 4. The JEITA margin, by ambient

Sustained worst case against the charge ceiling:

<!-- BEGIN GENERATED: ambient -->
| Ambient | Internal air (sustained worst case) | Margin to 45 °C JEITA ceiling |
|---|---:|---:|
| 25 °C | 34.8 °C | +10.2 K |
| 30 °C | 39.8 °C | +5.2 K ⚠️ |
| 35 °C | 44.8 °C | +0.2 K ⚠️ |

Sustained worst case is **playback while charging at 1.07 W**, not copy — see §3.
<!-- END GENERATED: ambient -->

**Read the bottom row carefully.** In a 35 °C room, a device left playing on the charger sits
essentially on the 45 °C cutoff. The cutoff then fires, correctly, and charging stops. Nothing
is damaged and nothing is unsafe — the protection did its job. But there is no screen, so what
a child experiences is a device that stopped charging for no reason they can see.

Four mitigations, in order of how much they buy:

1. **Suspend charging during a copy.** A copy is 30 seconds. Dropping charge current to zero
   for its duration is imperceptible — nobody notices 30 seconds of a 90-minute charge — and it
   removes the highest-power case from the sustained set entirely. It costs one control line
   the charger already has. **This is the cheapest thermal win in the design and I intend to
   take it.**
2. **Put distance between the cell and the heat.** The NTC must read the *cell*, not the board.
   The cell compartment (rigid, isolating it from screw bosses and flex — Hardware Charter §04)
   does double duty as a thermal break if it is placed away from the charger and the RT1062.
   This is a layout constraint, and it goes into `board-rev-a.md` before layout starts.
3. **Taper rather than cut.** Standard JEITA has a reduced-current band below the hard ceiling.
   Charging at 0.2C from 40–45 °C instead of stopping at 45 °C means the device slows down
   before it gives up, and mostly never reaches the ceiling because the reduced current lowers
   the dissipation that was pushing it there. Self-correcting, and free in a charger that
   implements JEITA in hardware.
4. **Say something.** §7.

With (1) and (3) the 35 °C row stops being marginal. Both are in the proposed topology.

---

## 5. Charge path

**Topology:** switching (buck) charger, thermal-pad package, over a copper pour sized from this
budget; NTC on the cell, not the board; JEITA enforced **in the charger's own hardware** via its
thermistor input, so no firmware path can widen the window.

| Element | Choice | Why |
|---|---|---|
| Charger | Switching buck, ~90% efficient, integrated JEITA thermistor input · `TI BQ25896` class · **UNVERIFIED** | A linear charger dropping 5 V→3.7 V at 500 mA puts **650 mW** into a grain of rice. The switching part puts **47 mW** into a part with a thermal pad. That is a 14× reduction for about a dollar. |
| Charge current | Resistor-set, 500 mA default | Resistor-set so it can be turned *down* if WP-37 surprises us, without a respin. Rev A hedge. |
| Cell NTC | 10 kΩ NTC bonded to the cell body | Reads the thing the limit protects. A board-mounted NTC reads the board and reports a number that is wrong in both directions. |
| Cell protection | Protected cell (PCM) **+** secondary protection IC **+** PTC on the battery line | Three independent layers. The PCM is a component someone else built; the secondary IC is our own guarantee. **UNVERIFIED** part selection. |
| Cell placement | Rigid compartment, isolated from screw bosses and flex, thermally distant from charger and MCU, never user-accessible | Drop survival and §4 mitigation 2 in the same feature |
| Copy interlock | Charge suspended for the duration of a copy | §4 mitigation 1 |

**Deep discharge — carried over from STATUS-HARDWARE H-10.** No hard power-off plus a LiPo plus
six months in a drawer ends below 2.5 V. The PCM cuts off, which is safe but leaves a degraded
cell. Rev A carries a **hardware low-voltage latch-off** (load switch releasing the system below
~3.2 V, re-armed on charger insert) and uses the charger's **ship mode** for storage between
build and gift. Neither is perceptible in normal use — the device still wakes instantly on a
button press from any state a child will put it in — so this does not trade against the
instant-on guardrail. Flagged for PM confirmation in §9.

---

## 6. Solenoid path — why one protection is not enough

The Hardware Charter is right that this is the best twenty cents in the design, and right that
it is not a firmware responsibility. It is also incomplete, and the gap is the interesting part.

<!-- BEGIN GENERATED: solenoid -->
| Quantity | Value | Note |
|---|---:|---|
| Coil power while energised | **9.0 W** | 9 V into 9 Ω, ~1.00 A |
| Energy per actuation | 270 mJ | 30 ms pulse |
| One-shot ceiling (hardware) | 50 ms | 1.7× the nominal pulse |
| Worst case a one-shot alone permits | **9.0 W continuous** | a retrigger loop; this is why on-time alone is not enough |
| Duty backstop ceiling | 0.5% over 10 s | = 0.04 W average, survivable indefinitely |
| Route B, all four at once | **4.0 A** | unstaggered — the charter's peak-current objection |
| Route B, staggered 10 ms | **1.00 A** | over 40 ms, imperceptible |
<!-- END GENERATED: solenoid -->

**The gap.** A one-shot bounds how long a *single* assertion lasts. It says nothing about how
often assertions may occur. Firmware stuck in a retrigger loop at 100 Hz delivers a 50 ms pulse
every 10 ms, the coil sees essentially its full 9 W continuously, and the one-shot fires
correctly the entire time. The exact failure the charter describes — a stuck firmware state
cooking a coil built for 30 ms pulses — is **fully reachable through a working one-shot.**

**Topology: three parts, none of which firmware can reach.**

| Part | Job | Cost |
|---|---|---|
| Non-retriggerable one-shot (`74HC221` class) | Caps on-time at 50 ms regardless of how long the MCU holds the line | ~$0.20 |
| RC lockout on the trigger | Enforces a minimum off-time, so retriggers inside the recovery window are ignored | ~$0.02 |
| PPTC on the solenoid rail (hold ≈ 100 mA, trip ≈ 200 mA) | Average-current backstop. Passes a 30 ms 1 A pulse without noticing; opens within a few hundred ms of sustained conduction | ~$0.15 |

Plus a flyback diode across each coil and a gate pull-down, so an undriven gate is an off gate
during reset and brown-out.

The PPTC is the part that closes the duty-cycle hole, and it closes it *physically*: it does not
matter what sequence of edges firmware produces, sustained conduction opens the circuit. Total
addition over the charter's single one-shot: about **fifteen cents**.

**A note on Route A versus Route B.** The charter counts "four solenoids' worth of peak current"
against Route B. The table above shows that objection is cheap to retire: **staggering the four
firings by 10 ms keeps peak current at one solenoid's worth** over a 120 ms sequence nobody can
perceive, and the one-shots make the stagger a hardware property rather than a firmware promise.
Route A remains preferable on mechanism and authenticity. It should be chosen for those reasons,
in WP-04, on how it feels — **not** on a peak-current argument that costs two logic packages to
make go away. Recorded so the spike is judged on the right axis.

---

## 7. Touch temperature, and the limit nobody wrote down

A child holds this device continuously. That makes external surface temperature a safety limit
in its own right, and it is not in `spec/acceptance.md` today.

IEC 62368-1 touch-temperature limits for a plastic enclosure under continuous handling sit
around **48 °C**. Against §3: sustained worst case puts the *case* at ambient + 4.4 K, so 35 °C
ambient gives a ~39 °C surface. Comfortable, with about 9 K of margin. **This is a limit we pass
easily and should still write down**, because the thing that would erode it is a future decision
to raise charge current, and a limit nobody recorded is a limit nobody checks.

*The 48 °C figure needs confirming against the current edition of the standard, which I cannot
fetch from this environment (STATUS-HARDWARE H-02). It is conservative enough that the margin
holds under any nearby value.*

**And the legibility problem.** When the JEITA window refuses a charge, the correct safety
behaviour is indistinguishable, to a seven-year-old, from a broken toy. Recommendation: the
charge indicator gets a distinct slow pulse for "too warm to charge right now" — an *indicator*,
not a control, so it does not add a control to the device (escalation trigger #3). It needs
Michael's taste for what it looks like and the PM's confirmation that it does not trip the
guardrail. Raised in §9 rather than decided here.

---

## 8. Proposed for `spec/acceptance.md` — PM to transcribe

PM Decisions 001 §3 puts *limits* in `spec/acceptance.md` (PM-owned, frozen) and *measurements*
here. These are the numbers this budget was written against. **I have not written them into
`spec/acceptance.md`** — that file is frozen and not mine.

| # | Proposed criterion | Basis |
|---|---|---|
| T-1 | Charging is permitted only while **0 °C ≤ T_cell ≤ 45 °C**, enforced in charger hardware via a cell-mounted NTC. No firmware path widens the window. | Hardware Charter §06 |
| T-2 | Charge current is reduced to ≤ 0.2C in **0–10 °C** and **40–45 °C**; resume hysteresis ≥ 3 K. | §4 mitigation 3; prevents ceiling chatter |
| T-3 | Solenoid on-time ≤ **50 ms** per actuation, bounded in hardware. | §6 |
| T-4 | Solenoid duty ≤ **0.5% over any 10 s window**, bounded in hardware and independent of the one-shot. | §6 — the criterion the charter was missing |
| T-5 | No accessible surface exceeds **48 °C** at 35 °C ambient in any sustained mode. | §7, IEC 62368-1 class limit |
| T-6 | Output ≤ **85 dB(A)** on an IEC 60318-4 ear simulator with the specified headphones, at maximum volume register, over a full-scale 1 kHz sine *and* the loudest golden fixture. | Guardrail 11, made measurable |
| T-7 | Cell is disconnected by hardware below **~3.2 V**; re-armed on charger insert. | §5, deep-discharge |

T-6 is worth a comment: guardrail 11 says "85 dB against specified headphones", which is a
system property. Stating the coupler and the two test signals is what turns it from a claim into
something Michael and a meter can check together — and PM Decisions 001 §4 makes that a witnessed
measurement.

---

## 9. Open items

| # | Item | Status |
|---|---|---|
| 1 | Proposed limits T-1…T-7 transcribed into `spec/acceptance.md` | **PM** |
| 2 | Charge-refusal indicator behaviour — confirm an indicator does not trip escalation trigger #3, then Michael's taste on what it looks like | **PM, then Michael** |
| 3 | Low-voltage latch-off confirmed as compatible with the instant-on guardrail | **PM** — recommendation in §5 |
| 4 | Board→air coupling measured; it is the weakest estimate here | WP-37 |
| 5 | microSD current measured alongside throughput | WP-05 characterisation |
| 6 | Charger, secondary protection and solenoid part numbers confirmed orderable | **Blocked** — no distributor access, H-02 |

## Revision history

| Rev | Date | Change |
|---|---|---|
| 0.1 | 2026-09-02 | First issue. Estimates only; no measurements exist yet. |
