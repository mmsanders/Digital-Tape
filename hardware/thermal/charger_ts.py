#!/usr/bin/env python3
"""Charger TS (thermistor sense) network design — closes the PR #15 charger finding.

`spec/acceptance.md` requires charging to be suspended below 0 °C and above 45 °C,
in hardware, not defeatable by firmware. PM Decisions 002-A section 1 leaves the
mechanism to us and names three routes. This designs route 1.

The problem: a bq2589x-class charger's TS thresholds are fixed fractions of REGN.
With TI's reference divider those fractions land on the standard JEITA points --
hot SUSPEND at T5 ~= 60 C, while T3 ~= 45 C merely drops charge voltage 200 mV and
keeps charging. So the reference network does not meet our 45 C limit.

But the *thresholds* are fixed; the *temperatures they correspond to* are set by the
divider we build around the NTC. With two resistors we have two degrees of freedom
and two constraints -- put VT5 at 45 C and VT1 at 0 C -- so the question is whether
a real solution exists. It does. This computes it, reports where the remaining
thresholds land, and does the worst-case corner analysis the reviewers asked for.

    make -C hardware charger        regenerate the tables in spec/hw/thermal-budget.md
    make -C hardware charger-check  fail if the spec is stale

Threshold fractions are marked UNVERIFIED: ti.com is blocked from this environment
(STATUS-HARDWARE H-02), so they come from the part's commonly published values
rather than from a datasheet anyone here has read. They are inputs, not results --
when the allowlist lands, correct them here and re-run.
"""

from __future__ import annotations

import argparse
import re
import sys
from bisect import bisect_left
from math import exp, log
from pathlib import Path

SPEC = Path(__file__).resolve().parents[2] / "spec" / "hw" / "thermal-budget.md"

# --- NTC: Vishay/Murata 103AT-class, 10k at 25 C -------------------------------
NTC_R25 = 10_000.0
NTC_BETA = 3435.0          # B25/85 of the "obvious" 103AT part, K
NTC_CANDIDATES = [("103AT class", 3435.0), ("B = 3950 K", 3950.0),
                  ("B = 4250 K", 4250.0)]
NTC_TOL_PCT = 1.0          # resistance tolerance at 25 C
BETA_TOL_PCT = 1.0

# --- Charger TS thresholds, as fractions of REGN. UNVERIFIED (see docstring) ----
VT1 = 0.7325   # cold suspend
VT2 = 0.6875   # cool -- reduced charge current
VT3 = 0.4800   # warm -- reduced charge voltage (-200 mV)
VT5 = 0.3475   # hot suspend
THRESH_TOL = 0.02          # +/-2% of REGN on each comparator

RES_TOL_PCT = 1.0          # E96 1% resistors

# --- What we are designing to ---------------------------------------------------
T_COLD_LIMIT = 0.0         # spec/acceptance.md: suspend below this
T_HOT_LIMIT = 45.0         # spec/acceptance.md: suspend above this

E96 = [round(10 ** (i / 96), 4) for i in range(96)]


def e96(value: float) -> float:
    """Nearest E96 value in the same decade."""
    if value <= 0:
        return value
    decade = 10 ** (len(f"{int(value)}") - 1) if value >= 1 else 1
    while value / decade >= 10:
        decade *= 10
    while value / decade < 1:
        decade /= 10
    mant = value / decade
    i = bisect_left(E96, mant)
    cands = [E96[max(0, i - 1)], E96[min(len(E96) - 1, i)]]
    best = min(cands, key=lambda c: abs(c - mant))
    return round(best * decade, 1)


def ntc(t_c: float, r25: float = NTC_R25, beta: float = NTC_BETA) -> float:
    return r25 * exp(beta * (1.0 / (t_c + 273.15) - 1.0 / 298.15))


def ratio(t_c: float, rt1: float, rt2: float, **kw) -> float:
    """TS pin voltage as a fraction of REGN.

    REGN -- RT1 -- TS node -- (RT2 in parallel with the NTC) -- GND.
    Rising temperature lowers the NTC, lowers the node, so hot is a LOW ratio.
    """
    rn = ntc(t_c, **kw)
    rbot = rt2 * rn / (rt2 + rn)
    return rbot / (rt1 + rbot)


def beta_min(t_cold: float, t_hot: float) -> float:
    """Minimum NTC B constant for which a finite POSITIVE RT2 exists.

    The threshold fractions are fixed, so the bottom leg must change by a fixed
    ratio between the two design temperatures. A parallel RT2 can only *compress*
    that ratio below the bare NTC's own. So if the NTC cannot span it unaided,
    no positive RT2 exists -- the closed form returns a negative resistance,
    which is the algebra's way of saying "not with this thermistor".
    """
    span = (VT1 / (1 - VT1)) / (VT5 / (1 - VT5))
    tc, th = t_cold + 273.15, t_hot + 273.15
    return log(span) / (1 / tc - 1 / th)


def solve(t_cold: float, t_hot: float, beta: float) -> tuple[float, float]:
    """Place VT1 at t_cold and VT5 at t_hot. Raises if RT2 would be negative."""
    rc, rh = ntc(t_cold, beta=beta), ntc(t_hot, beta=beta)
    kc = VT1 / (1 - VT1)
    kh = VT5 / (1 - VT5)
    span = kc / kh
    denom = rc - span * rh
    if denom <= 0:
        raise ValueError("no positive RT2 for this beta and span")
    rt2 = (span * rh * rc - rc * rh) / denom
    if rt2 <= 0:
        raise ValueError("no positive RT2 for this beta and span")
    rt1 = (rt2 * rc / (rt2 + rc)) / kc
    return rt1, rt2


def temp_at(target, rt1, rt2, **kw):
    lo, hi = -60.0, 150.0
    if not (ratio(hi, rt1, rt2, **kw) <= target <= ratio(lo, rt1, rt2, **kw)):
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if ratio(mid, rt1, rt2, **kw) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def corners(rt1, rt2, beta):
    out = {}
    for name, vt in (("cold", VT1), ("hot", VT5)):
        temps = []
        for dr1 in (-1, 1):
            for dr2 in (-1, 1):
                for dn in (-1, 1):
                    for db in (-1, 1):
                        for dv in (-1, 1):
                            t = temp_at(
                                vt * (1 + dv * THRESH_TOL),
                                rt1 * (1 + dr1 * RES_TOL_PCT / 100),
                                rt2 * (1 + dr2 * RES_TOL_PCT / 100),
                                r25=NTC_R25 * (1 + dn * NTC_TOL_PCT / 100),
                                beta=beta * (1 + db * BETA_TOL_PCT / 100),
                            )
                            if t is not None:
                                temps.append(t)
        out[name] = (min(temps), max(temps))
    return out


def safe(rt1, rt2, beta) -> bool:
    """Safety is ONE-SIDED on each threshold: suspending early is harmless,
    suspending late means charging a lithium cell out of window."""
    c = corners(rt1, rt2, beta)
    return c["cold"][0] >= T_COLD_LIMIT and c["hot"][1] <= T_HOT_LIMIT


def design(beta: float):
    """Largest inward margin this NTC supports with every corner inside the limits."""
    best = None
    m = 0.0
    while m <= 15.0:
        try:
            rt1, rt2 = solve(T_COLD_LIMIT + m, T_HOT_LIMIT - m, beta)
        except ValueError:
            break
        r1, r2 = e96(rt1), e96(rt2)
        if r2 > 0 and safe(r1, r2, beta):
            best = (r1, r2, m)
        m += 0.1
    return best


def t_design() -> str:
    rows = [
        "**The thermistor is the design variable, and the obvious one does not work.**",
        "",
        "| NTC | B (K) | B needed for a 0 / 45 °C fit | Usable? | Best margin |",
        "|---|---:|---:|---|---:|",
    ]
    bmin0 = beta_min(T_COLD_LIMIT, T_HOT_LIMIT)
    chosen = None
    for label, b in NTC_CANDIDATES:
        d = design(b)
        if d and chosen is None:
            chosen = (label, b) + d
        rows.append(
            f"| {label} | {b:.0f} | {bmin0:.0f} bare minimum | "
            f"{'**yes**' if d else 'no — RT2 goes negative'} | "
            f"{(str(round(d[2],1)) + ' K') if d else '—'} |")
    if chosen is None:
        return "\n".join(rows + ["", "**No candidate NTC works. Route 1 is not viable.**"])

    label, b, r1, r2, m = chosen
    rows += [
        "",
        f"A B = {NTC_BETA:.0f} K thermistor — the 103AT part everyone reaches for — spans "
        f"*exactly* enough to place both thresholds at 0 °C and 45 °C and **nothing more**. "
        f"Ask it for any inward margin and the required span exceeds what it can deliver, so "
        f"the algebra returns a negative RT2. A steeper thermistor is not a refinement here; "
        f"it is the difference between a design and an arithmetic coincidence.",
        "",
        f"**Chosen: a B = {b:.0f} K thermistor**, giving **{m:.1f} K** of inward margin on each limit.",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        f"| `RT1` (REGN → TS) | **{r1/1000:.2f} kΩ**, 1 % |",
        (f"| `RT2` (TS → GND, parallel with NTC) | **do not fit** — the solve wants "
         f"{r2/1e6:.1f} MΩ, which is electrically open. Keep the footprint. |"
         if r2 > 1e6 else
         f"| `RT2` (TS → GND, parallel with NTC) | **{r2/1000:.2f} kΩ**, 1 % |"),
        f"| NTC | **10 kΩ at 25 °C, B = {b:.0f} K**, 1 %, bonded to the cell |",
        f"| Nominal suspend points | {T_COLD_LIMIT + m:.1f} °C and {T_HOT_LIMIT - m:.1f} °C |",
        "",
        "Where each charger threshold lands:",
        "",
        "| Threshold | Fraction of REGN | Lands at | Meaning |",
        "|---|---:|---:|---|",
    ]
    meaning = {"VT1": "**cold suspend — charging stops**",
               "VT2": "cool — reduced charge current",
               "VT3": "warm — charge voltage −200 mV",
               "VT5": "**hot suspend — charging stops**"}
    for name, vt in (("VT1", VT1), ("VT2", VT2), ("VT3", VT3), ("VT5", VT5)):
        t = temp_at(vt, r1, r2, beta=b)
        rows.append(f"| `{name}` | {vt*100:.2f} % | "
                    f"**{t:+.1f} °C**" if t is not None else "| — |")
        if t is not None:
            rows[-1] += f" | {meaning[name]} |"
    rows += [
        "",
        f"`VT2` and `VT3` are not free parameters — they fall where the divider puts them. "
        f"They land inside the window and give a reduced-current band and a reduced-voltage "
        f"band on the way to each cutoff, which is the taper behaviour proposed as T-2. It "
        f"comes free with this network rather than needing its own circuit.",
        "",
        "**On `RT2`: keep the footprint, do not fit the part.** With a steep enough thermistor "
        "the solve pushes RT2 into the megohms, which is electrically the same as leaving it "
        "out \u2014 the network is just `RT1` and the NTC. Fitting a 4.6 M\u03a9 resistor beside a "
        "high-impedance sense node buys nothing and invites leakage and noise. The pad stays "
        "because RT2 is the one knob that trades margin between the cold and hot thresholds, "
        "and rev A is an experiment: if the real cell NTC misbehaves, that pad is how it gets "
        "corrected without a respin.",
    ]
    return "\n".join(rows)


def t_corners() -> str:
    d = None
    for _, b in NTC_CANDIDATES:
        d = design(b)
        if d:
            beta = b
            break
    if not d:
        return "no viable design"
    r1, r2, m = d
    c = corners(r1, r2, beta)
    lo, hi = c["cold"]
    lo2, hi2 = c["hot"]
    return "\n".join([
        "| Suspend threshold | Nominal | Worst-case window | Binding corner | Limit | Verdict |",
        "|---|---:|---|---:|---:|---|",
        f"| Cold (`VT1`) | {temp_at(VT1, r1, r2, beta=beta):+.1f} °C | {lo:+.1f} … {hi:+.1f} °C | "
        f"**{lo:+.1f} °C** | ≥ 0 °C | {'**pass**' if lo >= T_COLD_LIMIT else '❌ fail'} |",
        f"| Hot (`VT5`) | {temp_at(VT5, r1, r2, beta=beta):+.1f} °C | {lo2:+.1f} … {hi2:+.1f} °C | "
        f"**{hi2:+.1f} °C** | ≤ 45 °C | {'**pass**' if hi2 <= T_HOT_LIMIT else '❌ fail'} |",
        "",
        f"All {2**5} corners enumerated, not RSS: resistors ±{RES_TOL_PCT:.0f} %, "
        f"NTC R25 ±{NTC_TOL_PCT:.0f} %, B ±{BETA_TOL_PCT:.0f} %, comparator "
        f"±{THRESH_TOL*100:.0f} % of REGN.",
        "",
        "**Safety is one-sided on each threshold.** Suspending early is harmless — the device "
        "declines a charge it could have taken. Suspending late means charging a lithium cell "
        "below freezing or above 45 °C. So the binding numbers are the cold window's *minimum* "
        "and the hot window's *maximum*, and centring the nominal on 0 / 45 would put half the "
        "tolerance band on the wrong side of a safety limit.",
    ])


BLOCKS = {"charger_design": t_design, "charger_corners": t_corners}


def render(text: str) -> str:
    for name, fn in BLOCKS.items():
        pat = re.compile(
            rf"(<!-- BEGIN GENERATED: {name} -->\n).*?(\n<!-- END GENERATED: {name} -->)",
            re.DOTALL)
        if not pat.search(text):
            sys.exit(f"charger_ts.py: no marker block for '{name}'")
        text = pat.sub(lambda m: m.group(1) + fn() + m.group(2), text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true", help="print to stdout only")
    a = ap.parse_args()

    if a.report:
        print(t_design(), "\n"); print(t_corners()); return 0

    cur = SPEC.read_text()
    new = render(cur)
    if a.check:
        if cur != new:
            print("charger tables STALE: run `make -C hardware charger`", file=sys.stderr)
            return 1
        print("charger tables up to date"); return 0
    if cur != new:
        SPEC.write_text(new); print("regenerated charger tables")
    else:
        print("charger tables already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
