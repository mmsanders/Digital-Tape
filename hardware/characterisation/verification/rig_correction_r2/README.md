# WP-05 rig correction r2 — independent Stage A

Authority: V380 / ADR-203. Expectations authored before corrected implementation;
no corrected judge or circuit inspected. Original publications remain immutable.
This extends V3d616c14's probe; it does not replace that historical counterexample.

`python -B tests/rig_correction_r2/run.py --judge PATH/media_atomicity.py --out RESULT.json`
uses the preserved revision-3 `judge(plans, rows)` interface, production default,
and result names. Fixture pattern and canonical plan digest are independently
encoded here; no candidate pattern/digest helper supplies expected bytes.
All rows are simulated, including the positive protocol assertions. A positive
aggregation test establishes no rail opening, calibration, physical success or
card qualification. Production threshold remains 1,000 distinct qualifying cuts.

Coverage: positive 1,000 plus one lawful late miss; OLD target lawful; 999 short;
operator threshold override; late target TORN and CORRUPT; late damage at each of
four separately baselined neighbours; qualifying tear; missing/duplicate/unplanned
rows; wrong identity/run/plan; truncated/nonhex target/precondition; missing
neighbour/baseline; unproven old precondition; changed plan.
Corruption must be reported as well as preventing PASS. A valid late miss is
excluded from count, never from the corruption audit.

The CLI exits nonzero for any failed expectation. `--baseline-known-gaps` is only
an authenticated historical demonstration: it requires exact old blob
`34d014bff70a4e7421f55a6c4f34bec643e94b22` and exactly six known failing cases.
Its green CI means those failures were reproduced, not corrected or accepted.
It cannot be used on a different candidate. Default mode retains all six red
expectations until the correction passes. No old test bytes or results changed.

Controls mutate the actual loaded classifier to always-NEW and the actual policy
to minimum 1; the independent expectations reject both. Six report-predicate
controls additionally reject always-PASS/FAIL, a wrong minimum/count and a hidden
tear. Self-checks do not qualify a physical measurement method.

See [unbound method cases](EXPECTATIONS.md). Hardware must declare its corrected
input/output schema and trace/calibration grammar before those cases are bound.
Equivalent interface plumbing can be added in a new version; expectations cannot
be relaxed or derived from implementation. No raw generated campaign files are
committed: these small synthetic fixtures are deterministically regenerated in RAM.
