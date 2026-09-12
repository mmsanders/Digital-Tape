# IR-015 — evidence index for independent review

**Owner:** Hardware Lead compiles · **Reviewer:** PM or Verification Lead dispositions
**Compiled:** 12 September 2026, assignment [#42](https://github.com/mmsanders/Digital-Tape/issues/42)
**Status:** `INDEX ONLY — no finding is closed and no acceptance is recorded here`

> **Acceptance fields in this document are deliberately blank.** The author of a response does
> not get to accept it (CLAUDE.md §2, `spec/hw/thermal-budget.md` banner). This index exists so
> a reviewer can find what each response rests on without reading three documents to discover
> what is missing from them.

All three findings hold `make -C hardware fabrication-gate` **CLOSED**. Two further items
(the IR-018-16 qualification gap and the PROVISIONAL solenoid verdict) hold it independently,
so accepting all three IR-015 responses would **not** by itself open the gate.

---

## IR-015-charger — 45 °C hot-suspend enforcement

| | |
|---|---|
| **Response** | `spec/hw/thermal-budget.md` §5.1–5.3, revision 0.6; `ADR-111` |
| **Model** | `hardware/thermal/charger_ts.py` |
| **Claim** | A `BQ25896`-class charger meets a 0 °C / 45 °C hardware suspend with `RT1` = 9.76 kΩ 1 %, `RT2` footprint unfitted, and a 10 kΩ B = 3950 K NTC bonded to the cell. Worst case: cold +2.2 °C (limit ≥ 0), hot +41.9 °C (limit ≤ 45) |
| **Method quality** | All 32 corners enumerated rather than RSS'd; safety treated as one-sided per threshold. This is the strongest of the three responses |
| **Load-bearing assumption** | **The TS threshold fractions (73.25 / 68.75 / 48.00 / 34.75 % of REGN) are `UNVERIFIED`.** They come from the part's commonly published values, not a datasheet anyone on this project has read. `ti.com` is blocked — confirmed again 12 Sep 2026 |
| **If the assumption is wrong** | `RT1` changes and the required NTC B may change with it. **The method and the one-sided-margin argument survive**; the component values do not. `charger_ts.py` carries the fractions as named constants so a correction is one edit and a re-run |
| **Missing before acceptance** | (a) the threshold fractions from the manufacturer's datasheet; (b) the actual NTC's measured R25 and B, not its marking; (c) confirmation the NTC is thermally bonded to the cell and not to the board |
| **Instruments for the eventual measurement** | Calibrated reference thermometer ±0.5 °C at the cell surface; DMM for REGN and TS node; controlled temperature ramp through both thresholds |
| **Raw fields** | `cell_temp_c, ts_node_v, regn_v, charge_current_a, charge_enabled, ramp_direction` — recorded through the transition in both directions, since hysteresis is part of the behaviour |
| **Uncertainty to state** | Thermometer accuracy and placement, thermal lag between cell surface and NTC, REGN regulation, comparator offset |
| **Independent acceptance** | ☐ *unsigned* |

## IR-015-solenoid — average coil power ≤ 0.25 W over any rolling 10 s window

| | |
|---|---|
| **Response** | `spec/hw/thermal-budget.md` §6, revision 0.6; `ADR-116` |
| **Model** | `hardware/thermal/solenoid_timing.py`; checks `hardware/thermal/test_solenoid.py` |
| **History** | **Reviewed twice, rejected twice.** IR-018-11…15 found the original working point (5.0 W, 15 ms, 450 ms) fails at 0.330 W once electrical corners are included — the first model had reported 0.220 W and a 1.14× pass. IR-018-16…17 then found the pulse-to-lockout handoff could be raced and the timing tolerance was bound to neither a part nor a rail. IR-018-17 is resolved; **IR-018-16 is not** |
| **Claim** | With B spanning the whole cycle and admission gated on B alone, the fault-case rolling-window average stays under 0.25 W at every corner, and the slowest inhibit still clears the fastest legitimate press |
| **Verdict** | **PROVISIONAL — explicitly not a PASS.** `verdict()` refuses to return PASS while any qualification gap is open |
| **Load-bearing assumption** | **`IC_TOL` = ±14 %, ASSUMED.** Extrapolated from a 602…798 µs datasheet test point at Cx = 0.1 µF, Rx = 10 kΩ, **VCC = 5 V**, then applied to a **390 ms** interval at **3.3 V** with a different R/C |
| **Changed this round** | The **orderable part is now bound** — TI `CD74HC221E` (bench) / `CD74HC221M96` (board), catalogued 2–6 V, covering the 3.3 V rail, with dated distributor price and stock (`hardware/sourcing/2026-09-12-parts.md`). A new check fails if the bound part's supply envelope does not contain `V_LOGIC`, with a demonstrated negative control |
| **Still missing** | The part's **guaranteed minimum/maximum pulse width at 3.3 V** over the intended R/C and temperature. Every host serving that table is blocked. `TIMING_BOUND_VERIFIED` stays `False` |
| **Also still open** | **The pulse length is a placeholder** (10 ms nominal). WP-04 measures the shortest pulse that reliably releases the latch. If it returns above ~10 ms the feasibility table sets what the coil must drop to — and if the mechanism then needs more energy than the budget allows, that is a genuine conflict between a safety limit and a mechanism and **goes to the PM**, not absorbed by widening the limit |
| **Proposed method** | `hardware/measurements/solenoid-timing-method.md` — breadboard, **no coil, no cell, no fabricated board**, so it runs while the fabrication gate stays CLOSED. Needs Michael's purchase approval and Verification's pre-review |
| **Independent acceptance** | ☐ *unsigned* |

## IR-015-transient — per-device junction temperatures through the copy

| | |
|---|---|
| **Response** | `spec/hw/thermal-budget.md` §3 per-device junction model, revision 0.6 |
| **Model** | `hardware/thermal/budget.py` |
| **Claim** | Carrying each device with its own θ_JA and its own τ, a 30 s copy reaches T_j 41.6 °C (MCU), 38.0 °C (3V3 buck), 35.7 °C (charger) at 25 °C ambient. Held indefinitely at 35 °C ambient the worst margin is **+24.2 K** (MCU) |
| **What it corrected** | The earlier lumped model averaged the enclosure and the die into one mass. The enclosure's time constant is 621 s and a QFN's is 6–20 s, so over a 30 s copy the lumped model reported the box's answer for the die — wrong by roughly the entire local rise |
| **Load-bearing assumption** | **Every θ_JA is `EST`.** θ_JA depends on copper pour area, which is a **layout output** — so these are a budget layout must hit, not a prediction of what layout will do |
| **Missing before acceptance** | (a) measured θ_JA per device on the actual board, which cannot exist before a board does; (b) WP-37's thermal validation run, including the one-hour stuck-copy fault case; (c) the layout that the θ_JA budget is binding on |
| **Dependency worth stating plainly** | This response **cannot be fully closed before a board exists**, and a board cannot be fabricated while the gate is CLOSED. That is not circular — the gate is held by the charger and solenoid findings, which are closable on the bench — but it does mean IR-015-transient is the **last** of the three to close, and a reviewer should not treat its openness as inaction |
| **Instruments** | Thermocouples or a calibrated thermal camera with emissivity stated per surface; ambient logged throughout; enclosure in its real configuration, closed |
| **Raw fields** | `device_id, sensor_type, sensor_position, t_device_c, t_ambient_c, elapsed_s, scenario, enclosure_state` |
| **Uncertainty to state** | Sensor accuracy and attachment, emissivity assumption if optical, ambient drift over a one-hour run, the difference between case temperature measured and junction temperature inferred — **θ_JC is itself an estimate and inferring T_j from T_case inherits it** |
| **Independent acceptance** | ☐ *unsigned* |

---

## What a reviewer should take from this index

**The three are not equally ready.** The charger response is complete in method and blocked only
on a datasheet constant. The solenoid response is structurally repaired but rests on an assumed
timing corner and a placeholder pulse length, and has a proposed bench method that does not
require opening any gate. The transient response is sound in method and cannot finish before a
board exists.

**None of them is accepted, and this document does not accept them.** Two of the three are
blocked on environment access — a manufacturer datasheet — rather than on engineering, which is
worth knowing before anyone spends money or bench time working around it.
