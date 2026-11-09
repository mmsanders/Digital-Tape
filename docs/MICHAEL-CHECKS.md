# Michael's hands-on checks

The sign-off record for criteria judged by hand, ear and eye
([ADR-208](DECISIONS.md#adr-208--hands-on-acceptance-for-physical-and-timing-criteria)).
One entry per check, newest at the bottom. A check is complete when it has all of the
following:
- the date;
- the firmware build hash;
- the criterion;
- what Michael tried;
- the numbers the firmware logged, with the serial log attached or its SHA-256;
- the verdict.

**Verdicts:**
- **acceptable**
- **not acceptable**, with a note: too slow, too loud, too quiet, wrong, and so on.

**How the verdict decides:**
- For the perceptual/timing criteria ADR-208 names, a met target with an unacceptable
  verdict fails; an acceptable recorded timing miss may pass under that method.
- A miss of more than 20% needs a recorded PM disposition before acceptance.
- The verdict never waives strict zero commit underruns, the inclusive resume window
  against the last logged position, callback-derived copy progress, atomicity/count/
  record-integrity requirements, or the output-cap margin.
- Preserve failed attempts and actual numbers. The record must match the candidate,
  exact raw log and source-build/binary linkage declared for its method. Simulations
  and injected-delay controls are not physical acceptance entries.

**Output caps:**
- Record the phone app, the headphones or speaker distance, and the reading at maximum
  volume.
- The reading must be at or below the ADR-208 margin value (headphones ≤ 80 dB).
- Never raise a cap above its measured reading.

Verification checks that each entry exists and that its build hash and log match the
candidate. It does not audit instruments.

| Date | Build | Criterion | What was tried | Firmware logged | Verdict |
|---|---|---|---|---|---|
| — | — | *No checks yet: the bench build does not exist* | | | |
