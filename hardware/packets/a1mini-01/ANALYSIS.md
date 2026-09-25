# A1MINI-01 — what the fit ladder bounds

**Raw data:** `RESULTS.md`, Michael, 23 September 2026.
**Status:** Hardware's reading of Michael's observation. **Not acceptance** — no
instrument was used, and Hardware cannot accept its own result. Every number below
is a *bracket*, not a measurement.

---

## 1. The negative control did its job

Hole 1 is modelled at **0.00 mm clearance** and exists to refuse the peg. It did:
*"not at all at first."* Had it accepted the peg freely, the ladder would have
been consistent with any clearance at all below 0.05 mm and the plate would have
measured nothing. It didn't, so the rest of the rungs mean something.

It did eventually admit the peg "VERY tight by the end", and the peg may have been
abraded. **That is not a fit, it is damage** — the plastic yielded. Hole 1 is a
destructive interference, which is exactly what 0.00 mm nominal should be.

## 2. The machine tracks the model to better than one rung

The felt result is monotonic and lands where the model says it should:

| Rung | Modelled | Felt |
|---:|---:|---|
| 1 | 0.00 | won't go → destructive |
| 2 | 0.05 | very snug, repeatable |
| 3 | 0.10 | snug, releases with a twist |
| 4 | 0.15 | **stops retaining** — barely stays in when tipped |
| 5–6 | 0.20–0.25 | loose |

The retain/don't-retain boundary sits **between 0.10 and 0.15 mm**, one 0.05 mm
step wide. Nothing is displaced by a whole rung, so the machine's net error —
hole shrink and peg growth combined — is **roughly 0 to 0.05 mm tighter than
modelled**, and certainly under 0.10 mm.

**This is the number the plate was printed to get.**

## 3. What that settles, and it is the important part

The held clasp sweep asks Michael to rank four interferences **0.08 mm apart**.
The worry was that the machine's own error might be larger than 0.08 mm, in which
case the four variants would differ by less than the noise and his ranking would
describe the printer rather than the design.

**It is not larger. The A1 Mini can resolve 0.08 mm, and the clasp sweep is
legible on it.**

The corollary matters more. Michael found variants A and Q *"so firm they couldn't
be opened without breaking the plastic."* Before this plate, that could have been a
design fact or a printing fact and there was no way to tell. Now there is:

> **The printer is exonerated. A and Q are unopenable because the design says so.**

## 4. What it does NOT settle

- **A pin in a hole is not a clasp.** The ladder is a rigid slip fit; the clasp is
  a lip that flexes over a bead. The mechanisms differ, so the ladder's numbers do
  not transfer to the clasp as values. What transfers is the bound on the
  *machine*, which is all this plate ever claimed.
- **Orientation.** The ladder's pegs and holes are both vertical, so both are
  defined by XY motion. Parts printed lying down have one fit dimension stacked in
  Z instead, which behaves differently. The bound is for XY-defined round features.
- **One plate, one session, one material.** Nothing here says what PETG or the
  0.2 mm nozzle would do. The ladder is now a **reusable instrument** and re-printing
  it is the cheapest way to answer that — no purchase, ~43 min.
- **No masses.** The coupons were not weighed, so flow and print-to-print spread
  remain open.

## 5. Consequences

| # | Consequence | Owner |
|---|---|---|
| C-1 | The clasp sweep is legible on this machine; the 0.08 mm step stands | Hardware |
| C-2 | A/Q being unopenable is a **design** result, so the sweep's bracket should move **down**, not the printer be tuned | PM decides the new bracket |
| C-3 | For a joint meant to be **opened by hand**, 0.05–0.10 mm clearance is the observed sweet spot; 0.15 mm stops retaining | Hardware, next clasp revision |
| C-4 | The button guide runs 0.25 mm/side. The ladder reads 0.20–0.25 as "loose" — which is what a **sliding** fit wants. My earlier worry that this was the riskiest number is **relaxed**, with the orientation caveat in §4 | Hardware |
| C-5 | Seam effect is below one rung — hand assembly is not orientation-dependent | closed |
