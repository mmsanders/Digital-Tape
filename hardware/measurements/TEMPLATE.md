# Measurement record — <what was measured>

> Copy this file. One record per measurement session. Fill every field or write `n/a` and say
> why — a blank field is indistinguishable from a field nobody thought about.

**Work package:** WP-NN · **Criterion:** <the acceptance criterion this is evidence for>
**Date:** · **Measured by:** · **Witnessed by:**
**Status:** `DRAFT` | `SUBMITTED FOR AUDIT` | `AUDITED — <name>, <date>`

---

## 1. What this is evidence for

The criterion, quoted verbatim from `spec/acceptance.md` or the package file, with its limit.
**Quote it; do not paraphrase it.** A paraphrase is where a limit drifts.

## 2. Procedure

Numbered steps, in enough detail that someone else could repeat it without asking a question.
Include what was *not* done and why, if a step was skipped.

## 3. Instruments

| Instrument | Make / model | Serial or identifying mark | Calibration or last-checked | Resolution | Stated accuracy |
|---|---|---|---|---|---|

**Firmware, software and board revisions used**, exactly — including the git SHA of anything
built for this.

## 4. Conditions

Ambient temperature and humidity, supply voltage, battery state, enclosure open or closed,
anything else that would change the answer. **Measured, not assumed.**

## 5. Raw readings

Every reading, in the order taken, before any processing. Outliers included and marked, not
removed. If the instrument produced a log, commit the log and name it here.

```
```

## 6. Derivation

How the raw readings become the reported number. Arithmetic shown. If a script did it, name
the script and its git SHA, and the script must be in this repository.

## 7. Result

| Quantity | Measured | Limit | Margin | Pass / fail |
|---|---:|---:|---:|---|

## 8. Uncertainty

Where the number could be wrong, and by how much. Instrument accuracy, reading resolution,
placement, thermal settling, repeat spread. **A result without an uncertainty is not auditable**
— the auditor cannot tell a 0.2 K margin from a 0.2 K measurement error.

## 9. What would change this result

The honest paragraph. What was assumed, what was convenient, what a hostile reader would attack
first.
