# Thermal and safety budget — WP-34

**Owner:** Hardware Lead · **Status:** living document, versioned not frozen (PM Decisions 001 §3)
**Revision:** 0.2, 2 Sep 2026 · **Applies to:** production board rev A

> **STATUS: three IR-015 findings — charger 45 °C enforcement, solenoid sustained-power bound,
> transient junction temperatures. Numbers in §T-1, §T-2, §T-4 are provisional.**
>
> **A response is filed against each** (§5.1–5.3, §6, §3; `ADR-111`, `ADR-116`, and the
> per-device junction model). **They are not closed until the PM or a reviewer accepts them** —
> the author of a response does not get to mark it accepted.
>
> **No board is fabricated and no cell is charged until all three are accepted.** Merging this
> document is not approving the design (PM Decisions 003 §4).

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
3. **The solenoid limit is an energy budget, and it selects the coil.** The charter's one-shot
   bounds pulse *width* and does nothing about sustained power. Against DRAFT-3's 0.25 W over
   10 s, the governing number is **125 mJ per actuation** — because the limit has to clear a
   child pressing stop and play twice a second. The 9 W coil and 30 ms pulse assumed in rev 0.1
   were **2.2× over that budget**, and that assumption was mine. §6.

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

### Per-device junction temperatures

<!-- BEGIN GENERATED: junction -->
| Device | θ_JA | τ | P (copy) | **T_j after a 30 s copy** | T_j if held forever | T_j max |
|---|---:|---:|---:|---:|---:|---:|
| MCU (RT1062, 196-MAPBGA) | 35 °C/W | 20 s | 590 mW | **41.6 °C** | 70.8 °C | 105 °C |
| Buck regulator (3V3) | 50 °C/W | 6 s | 250 mW | **38.0 °C** | 62.7 °C | 125 °C |
| Charger (buck, thermal pad) | 45 °C/W | 8 s | 230 mW | **35.7 °C** | 60.5 °C | 125 °C |

At 25 °C ambient. Hot-room case (35 °C ambient, held indefinitely):

| Device | T_j | Margin to T_j max |
|---|---:|---:|
| MCU (RT1062, 196-MAPBGA) | 80.8 °C | **+24.2 K** |
| Buck regulator (3V3) | 72.7 °C | **+52.3 K** |
| Charger (buck, thermal pad) | 70.5 °C | **+54.5 K** |

**Why the fast term matters and the lumped model missed it.** The enclosure's time constant is 621 s; a QFN's is 6–20 s. Over a 30 s copy the box barely moves — half a kelvin — while the regulator gets within a few percent of its own steady rise. Averaging the two into one mass reports the box's answer for the die, which is the wrong answer by roughly the entire local rise. Each device is now carried separately, with its own θ_JA and its own τ.

**The result is comfortable, and that is a finding rather than a relief** — it says the sealed enclosure is not the constraint anywhere, so the thermal argument for vents does not exist at any point in the design. Every θ_JA here is `EST` until WP-37 measures it; θ_JA in particular depends on copper pour area, which is a layout output, so these numbers are a budget layout must hit rather than a prediction of what it will do.
<!-- END GENERATED: junction -->

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
budget; NTC bonded to the **cell**, not the board; the charge window enforced in the charger's
own hardware via its thermistor input, so no firmware path can widen it.

| Element | Choice | Why |
|---|---|---|
| Charger | Switching buck, ~90 % efficient, thermistor input with JEITA thresholds · `TI BQ25896` class · **UNVERIFIED** | A linear charger dropping 5 V→3.7 V at 500 mA puts **650 mW** into a grain of rice. The switching part puts **47 mW** into a part with a thermal pad. |
| Charge current | Resistor-set, 500 mA default | So it can be turned *down* if WP-37 surprises us, without a respin |
| Cell NTC | See §5.1 — **B = 3950 K**, bonded to the cell body | Reads the thing the limit protects. A board-mounted NTC reads the board and is wrong in both directions |
| Cell protection | Protected cell (PCM) **+** secondary protection IC **+** PTC on the battery line | Three independent layers |
| Cell placement | Rigid compartment, thermally distant from charger and MCU, never user-accessible | Drop survival and §4 mitigation 2 in one feature |
| Copy interlock | Charge suspended for the duration of a copy (ADR-102) | §4 mitigation 1 |
| Deep discharge | Hardware load switch below ~3.2 V, released on charger insert; charger ship mode for storage | Carried from H-10. **Must not add perceptible wake latency** — `acceptance.md`; if it does, that is an escalation, not a trade |

### 5.1 The TS network — closing the charger finding

`spec/acceptance.md` requires charging suspended below 0 °C and above **45 °C**, in hardware.
PM Decisions 002-A §1 leaves the mechanism to us and offers three routes. **This is route 1**,
and it works — but not with the thermistor anyone would reach for first.

The charger's TS thresholds are fixed *fractions of REGN*. What is adjustable is the temperature
each fraction corresponds to, set by the divider built around the NTC. Two resistors, two
constraints: put the hot suspend at 45 °C and the cold suspend at 0 °C.

<!-- BEGIN GENERATED: charger_design -->
**The thermistor is the design variable, and the obvious one does not work.**

| NTC | B (K) | B needed for a 0 / 45 °C fit | Usable? | Best margin |
|---|---:|---:|---|---:|
| 103AT class | 3435 | 3162 bare minimum | no — RT2 goes negative | — |
| B = 3950 K | 3950 | 3162 bare minimum | **yes** | 4.4 K |
| B = 4250 K | 4250 | 3162 bare minimum | **yes** | 5.7 K |

A B = 3435 K thermistor — the 103AT part everyone reaches for — spans *exactly* enough to place both thresholds at 0 °C and 45 °C and **nothing more**. Ask it for any inward margin and the required span exceeds what it can deliver, so the algebra returns a negative RT2. A steeper thermistor is not a refinement here; it is the difference between a design and an arithmetic coincidence.

**Chosen: a B = 3950 K thermistor**, giving **4.4 K** of inward margin on each limit.

| Quantity | Value |
|---|---:|
| `RT1` (REGN → TS) | **9.76 kΩ**, 1 % |
| `RT2` (TS → GND, parallel with NTC) | **do not fit** — the solve wants 4.6 MΩ, which is electrically open. Keep the footprint. |
| NTC | **10 kΩ at 25 °C, B = 3950 K**, 1 %, bonded to the cell |
| Nominal suspend points | 4.4 °C and 40.6 °C |

Where each charger threshold lands:

| Threshold | Fraction of REGN | Lands at | Meaning |
|---|---:|---:|---|
| `VT1` | 73.25 % | **+4.3 °C** | **cold suspend — charging stops** |
| `VT2` | 68.75 % | **+8.6 °C** | cool — reduced charge current |
| `VT3` | 48.00 % | **+27.3 °C** | warm — charge voltage −200 mV |
| `VT5` | 34.75 % | **+40.5 °C** | **hot suspend — charging stops** |

`VT2` and `VT3` are not free parameters — they fall where the divider puts them. They land inside the window and give a reduced-current band and a reduced-voltage band on the way to each cutoff, which is the taper behaviour proposed as T-2. It comes free with this network rather than needing its own circuit.

**On `RT2`: keep the footprint, do not fit the part.** With a steep enough thermistor the solve pushes RT2 into the megohms, which is electrically the same as leaving it out — the network is just `RT1` and the NTC. Fitting a 4.6 MΩ resistor beside a high-impedance sense node buys nothing and invites leakage and noise. The pad stays because RT2 is the one knob that trades margin between the cold and hot thresholds, and rev A is an experiment: if the real cell NTC misbehaves, that pad is how it gets corrected without a respin.
<!-- END GENERATED: charger_design -->

### 5.2 Worst-case corners

<!-- BEGIN GENERATED: charger_corners -->
| Suspend threshold | Nominal | Worst-case window | Binding corner | Limit | Verdict |
|---|---:|---|---:|---:|---|
| Cold (`VT1`) | +4.3 °C | +2.2 … +6.3 °C | **+2.2 °C** | ≥ 0 °C | **pass** |
| Hot (`VT5`) | +40.5 °C | +39.1 … +41.9 °C | **+41.9 °C** | ≤ 45 °C | **pass** |

All 32 corners enumerated, not RSS: resistors ±1 %, NTC R25 ±1 %, B ±1 %, comparator ±2 % of REGN.

**Safety is one-sided on each threshold.** Suspending early is harmless — the device declines a charge it could have taken. Suspending late means charging a lithium cell below freezing or above 45 °C. So the binding numbers are the cold window's *minimum* and the hot window's *maximum*, and centring the nominal on 0 / 45 would put half the tolerance band on the wrong side of a safety limit.
<!-- END GENERATED: charger_corners -->

### 5.3 What this closes, and what it leaves open

**Closed.** A `BQ25896`-class part *can* meet a 45 °C hot-suspend limit, with a deliberately
designed divider and a steeper thermistor than the obvious one. Route 2 (a different charger)
and route 3 (a series thermal cutoff) are not needed, and the reduced-current and
reduced-voltage bands that fall out of the divider give the taper behaviour proposed as T-2 for
free.

**Open, and it is a live risk.** The threshold fractions above are `UNVERIFIED` — `ti.com` is
still blocked from this environment, so they come from the part's commonly published values
rather than a datasheet anyone here has read. **They are inputs, not results.** If the real
fractions differ, `RT1` changes and the required NTC B may change with it; the method and the
one-sided-margin argument hold regardless. `hardware/thermal/charger_ts.py` takes them as named
constants at the top — correcting them is a one-line edit and a re-run.

## 6. Solenoid path — two limits, three layers

`spec/acceptance.md` DRAFT-3 states the bound as **power, not duty**:

> Average coil power ≤ **0.25 W over any rolling 10 s window**, enforced in hardware, not
> defeatable by firmware.

Power, because power is what damages a coil — pulse width and duty fall out of it. Two earlier
numbers (50 ms in DRAFT-1, 5 % duty in DRAFT-2) were asserted rather than derived, and both were
wrong; this one is derived, and **it derives the coil**.

The constraint that gives it teeth is the PM's: the bound must sit **above the fastest legitimate
use** — a child alternating stop and play about twice a second — and **below the coil's
continuous rating**. If those two do not leave a gap, the answer is a shorter pulse or a
lower-power coil, **not a looser limit**. So:

> 2 actuations/s × E_pulse ≤ 0.25 W  →  **E_pulse ≤ 125 mJ**

A PPTC remains a third-layer backstop and **may not be the element that establishes the bound** —
it is history-dependent and has no deterministic worst case. The two monostables do it alone.

<!-- BEGIN GENERATED: solenoid_values -->
| Quantity | Value | Against | Verdict |
|---|---:|---|---|
| Energy budget at 2 Hz sustained | **125 mJ** per actuation | 0.25 W ÷ 2 Hz | the governing number |
| Coil, specified by energy | **5.0 W** | | selection constraint |
| Pulse (**placeholder — WP-04 measures this**) | 15 ms nominal, 12.6…**17.4 ms** | ≤ 50 ms | **pass**, 2.9× |
| Energy per actuation | **75 mJ** | ≤ 125 mJ | **pass**, 1.67× |
| Lockout | 450 ms nominal, **378**…522 ms | | |
| Fastest the hardware allows | one per **395 ms** | must be ≤ 500 ms so real use is not blocked | **pass** |
| Average at 2 Hz legitimate use | **0.174 W** | ≤ 0.25 W | **pass** |
| Average in a retrigger fault | **0.220 W** | ≤ 0.25 W | **pass**, 1.14× |

Timing tolerance ±16 %, arithmetic sum not RSS. One `74HC221`: A half sets the pulse (R = 214 kΩ, C = 100 nF **C0G**), B half holds the lockout (R = 1368 kΩ, C = 470 nF **film**), retriggered by A's falling edge so it sits downstream of the pulse and no gate input can defeat it.
<!-- END GENERATED: solenoid_values -->

### 6.1 Against the acceptance test

<!-- BEGIN GENERATED: solenoid_test -->
The limit only means something if it clears real use and still bounds a fault. Both, at the working point above:

| Case | Rate | Average coil power | Against 0.25 W |
|---|---|---:|---|
| One press | 0.2 /s | **0.017 W** | **pass** |
| Brisk use | 1.0 /s | **0.087 W** | **pass** |
| **Child mashing stop/play** | 2.0 /s | **0.174 W** | **pass** |
| Firmware retrigger loop, 100 Hz input | 2.5 /s | **0.220 W** | **pass** |

The last row is the fault case and it is the one the hardware actually bounds: a 100 Hz gate input is throttled by the lockout to one pulse per 395 ms, whatever firmware does. The row above it is a child, and it passes with room — which is the point the limit was restated to make.

**Why the coil dropped from 9 W to 5 W.** At 9 W a 30 ms pulse is 270 mJ, and two of those a second is 0.54 W — more than double the limit. No lockout fixes that without also blocking the child, because the energy is spent inside a single legitimate actuation. The fix has to be the coil or the pulse, exactly as the PM's note says. **The 9 W / 30 ms figure was my assumption, not a measurement**, and it is the third number this project has found wrong by costing it.

**The pulse length is a placeholder and is marked as one.** WP-04 measures the shortest pulse that reliably releases the latch; that number, plus margin, replaces the 15 ms above and the lockout resistor follows it. Until then the working point demonstrates that a compliant design exists — it does not claim to be the final one.
<!-- END GENERATED: solenoid_test -->

### 6.2 The third layer, and what it is not

A **PPTC on the coil rail** (hold ≈ 100 mA) remains, and it is worth its fifteen cents — but as
a backstop against faults the timing chain cannot see: a shorted FET, a wiring error, a coil
that fails low-resistance. It is explicitly **not** how the duty limit is met, because a PPTC's
trip point depends on its own recent history and ambient temperature, so it cannot be given a
deterministic worst case. The limit is met by the two monostables above; the PPTC catches what
they cannot.

Plus a flyback diode across each coil and a gate pull-down, so an undriven gate is an off gate
through reset and brown-out.

### 6.3 What this costs, stated plainly

**The lockout no longer blocks anything a child does.** At 450 ms nominal the hardware permits an
actuation every 395 ms worst case, against the 500 ms period of the fastest legitimate use. The
earlier 1.2 s lockout would have blocked it — that design met a duty limit by making the product
slower, which is the failure the restated limit exists to prevent.

**The cost moved to the coil.** Specifying by energy means the solenoid is chosen for ≤ 125 mJ per
actuation rather than for raw force, and a 5 W coil pulsed 15 ms is a weaker actuator than 9 W
pulsed 30 ms. Whether it still releases the latch is **not something this document can assert** —
it is what WP-04 measures. If the mechanism needs more energy than the budget allows, that is a
real conflict between a safety limit and a mechanism, and it goes to the PM rather than being
absorbed by widening the limit.

**Both numbers here are placeholders and are labelled as such.** WP-04 supplies the pulse; the
coil follows from the energy budget; the lockout resistor follows from both. What the working
point demonstrates is that a compliant design *exists* — not that this is it.

### 6.4 On Route A versus Route B

The charter counts "four solenoids' worth of peak current" against Route B.
**Staggering the four firings by 10 ms holds peak current at one solenoid's worth** over a
120 ms sequence nobody can perceive, and the one-shots make the stagger a hardware property
rather than a firmware promise. Route A should win on mechanism and on feel, in WP-04 — not on
a current argument that costs two logic halves to make go away.

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
| 5a | ~~Codec operating range~~ — **confirmed −40 °C to +85 °C** from NXP's part page. Against §4's ~45 °C sustained worst case, ~40 K of margin | Closed |
| 6 | Charger, secondary protection and solenoid part numbers confirmed orderable | **Blocked** — no distributor access, H-02 |

## Revision history

| Rev | Date | Change |
|---|---|---|
| 0.1 | 2026-09-02 | First issue. Estimates only; no measurements exist yet. |
