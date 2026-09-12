# Return — P1-R3-HW, Hardware Lead

**Assignment:** [#52](https://github.com/mmsanders/Digital-Tape/issues/52), label `hardware-lead`,
issue updated `2026-09-12T15:48:30Z`
**Input product main:** `91268789cc5a5026baa9bb7e3120671626897a74`
**Prior return integrated:** PR #47, merge `8d9e8bdffc245d797702a2b3a461348672b0644a`
**PM evidence:** `docs/REVIEW/P1-R3-PM-DISPOSITION.md`
**Returned:** 12 September 2026 · **Next owner:** PM for disposition
**Status:** `EVIDENCE HARDENING — no acceptance, no measurement, no gate change`

## 1. The finding, and why it was right

PR #47 added an inequality to `check_criteria()`: the **bound** part's supply envelope must
contain `V_LOGIC`. It was prompted by a real catalogue listing of an HC part number
(NXP `74HC221DB112`) at 4.5–5.5 V — selecting it would put the one-shot outside its supply
range at the 3.3 V rail, and no other check in the model would have noticed.

**That criterion was demonstrated once, in a shell, and nothing in the repository retained the
demonstration.** So deleting those four lines would have been a silent, green regression — the
exact fail-open class IR-018-14 removed from this file. Worse, it is the same mistake in
miniature that `spec/hw/VERSION.md` exists to prevent: a check whose evidence lived outside the
repository is not a check.

**The generic `--mutate` control does not cover it.** That one replaces `check_criteria`
wholesale, so it proves the suite notices a *totally dead* gate — not that this particular
inequality is alive.

## 2. What is now retained

Four checks and one mutation mode in `hardware/thermal/test_solenoid.py`, section 11. Each is a
fixed assertion, so the suite's count is fixed at **30** rather than varying with outcome.

| # | Retained assertion | What it would catch |
|---|---|---|
| 1 | The committed 2–6 V envelope does **not** itself trip the criterion | A baseline that was already red, making every other result meaningless |
| 2 | Injecting 4.5–5.5 V at 3.3 V adds **exactly one** failure | The inequality being absent, dead, or firing more broadly than intended |
| 3 | That one added failure **is** the supply-envelope criterion | A coincidental other criterion being mistaken for this one |
| 4 | Its message names **both** the injected envelope and the rail | An unattributable failure string, which an auditor cannot distinguish |
| 5 | The control stays specific **while an unrelated criterion is also failing** | The distinguishability requirement, under noise rather than only in the clean case |

**The specificity comes from differencing against the baseline**, not from string-matching
alone. Check 5 is what proves it: with `COIL_W = 12.0` W the power criterion fails in *both*
runs, so it cancels, and the injected envelope remains the only failure the control attributes
to itself. Without that difference, "some criterion failed" could have passed for "this
criterion is alive".

## 3. The control's own negative control

`supply_removal_is_caught()` runs on every invocation and requires that deleting the inequality
breaks the central assertion. `python3 test_solenoid.py --mutate-supply` makes the same deletion
the headline: it strips **only** that finding from `check_criteria`'s output, leaving every other
criterion intact, and then requires both that the suite goes red **and that it is the
supply-envelope checks which fail** — not some unrelated check going red for another reason.

**A genuine source deletion was also confirmed**, not only the simulation. Copying
`solenoid_timing.py` and `test_solenoid.py` to a scratch directory and physically removing the
four lines of the inequality produced:

```
  FAIL RED: injecting a 4.5..5.5 V part at the 3.3 V rail adds exactly one failure (got 0: [])
  FAIL RED: that one added failure is the SUPPLY-ENVELOPE criterion and not a coincidental other one (got '')
  FAIL the supply-envelope failure names both the injected envelope and the rail, so it cannot be mistaken for another criterion (got '')
  FAIL the control stays specific while an unrelated criterion is also failing

4 of 30 checks FAILED
exit=1
```

The monkeypatched mutation and the real four-line deletion agree, which is the point of running
both: the committed test uses the project's existing monkeypatch idiom, and the source deletion
confirms that idiom is faithful.

`make -C hardware solenoid-test` now invokes all three modes, so the targeted mutation is part
of the gate rather than something a person has to remember to run.

## 4. Checks actually run

| Command | Outcome |
|---|---|
| `make -C hardware spec-check` | **exit 0** — `OK spec/hw manifest: 3 files, content and revision agree` |
| `make -C hardware thermal-check` | **exit 0** — budget/charger up to date; solenoid prints `VERDICT PROVISIONAL (1 qualification gap(s) open -- this is NOT qualification of the circuit)` |
| `make -C hardware solenoid-test` | **exit 0** — `30 checks pass` · `proven able to go red` · `supply-envelope criterion: deleting it specifically turns the suite red` |
| `make -C hardware fabrication-gate-test` | **exit 0** — 8 checks + 3 CLI tests; gate proven able to go red and able to open on an accepted fixture |
| `make -C hardware fabrication-gate` | **exit 2 — CLOSED, five blocking items, unchanged** |
| `tools/ci/verify-spec-bundle.sh` | **exit 0** — all three frozen files OK |
| `python3 test_solenoid.py --mutate` | **exit 0** — generic fail-open control still caught (11 of 30 red under it) |
| `python3 test_solenoid.py --mutate-supply` | **exit 0** — targeted deletion caught, by the right checks |

**No `spec/hw` file changed**, so no revision bump or `spec-bless` was due, and `spec-check`
confirms the manifest still agrees. CAD targets were not run: CadQuery is absent from this
environment, and a missing dependency is not a passing test.

## 5. Files changed

| File | Change |
|---|---|
| `hardware/thermal/test_solenoid.py` | Section 11 (five retained checks), `with_supply_range()`, `supply_failures_added_by_injection()`, `supply_control_survives_unrelated_noise()`, `supply_removal_is_caught()`, `mutate_supply()`, count 24 → 30 |
| `hardware/Makefile` | `solenoid-test` reports 30 and invokes `--mutate-supply` |
| `docs/STATUS-HARDWARE.md` | Minimal: the solenoid row and closing paragraph now describe a retained control instead of an outstanding requirement |
| `docs/REVIEW/returns/P1-R3-HW.md` | This return |

## 6. Exclusions and remaining holds

**Nothing about the design changed.** No datasheet value, measurement or part acceptance is
inferred; the ±14 % timing term is still ASSUMED and IR-018-16 is still open; the verdict is
still **PROVISIONAL**; the selected card study, print and fabrication decisions are untouched;
the charger and transient responses are untouched and still unaccepted. Fabrication and cell
charging remain **CLOSED** with the same five blockers. No `engine/`, `firmware/` or frozen-spec
edit. No hardware interface changed, so no Software notification is due.

**Independent Verification has no dependency on this and is not asked to accept it.** Green
regressions are not safety qualification. Closing the issue records that the work stopped, not
that it is correct, merged or accepted.
