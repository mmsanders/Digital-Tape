# Michael's hands-on checks

The sign-off record for criteria judged by hand, ear and eye
([ADR-208](archive/DECISIONS-ADR-001-209.md#adr-208--hands-on-acceptance-for-physical-and-timing-criteria)).
One entry per check, newest at the bottom. A check is complete when it has all of the
following:
- the date;
- the firmware build id (printed by `build` and on the `WAKE` line);
- the criterion;
- what Michael tried;
- the numbers the firmware printed;
- the verdict.

**Verdicts:**
- **acceptable**
- **not acceptable**, with a note: too slow, too loud, too quiet, wrong, and so on.

**How the verdict decides:**
- For the perceptual/timing criteria ADR-208 names, a met target with an unacceptable
  verdict fails; an acceptable recorded timing miss may pass under that method.
- A miss of more than 20% is Michael's explicit call, noted in the row.
- The verdict never waives strict zero commit underruns, the inclusive resume window
  against the last logged position, callback-derived copy progress, atomicity/count/
  record-integrity requirements, or the output-cap margin.
- Keep failed attempts and the real numbers. A simulation or the `wake150` control run
  is not an acceptance entry.

**Output caps:**
- Record the phone app, the headphones or speaker distance, and the reading at maximum
  volume.
- The reading must be at or below the ADR-208 margin value (headphones ≤ 80 dB).
- Never raise a cap above its measured reading.

**Where the numbers come from.** The firmware prints them: copy the line from the serial
monitor into the table (for warm wake, the `WAKE …` line, which carries the build id).
A screenshot or a pasted log is fine. Nothing else is required (ADR-210).

| Date | Build | Criterion | What was tried | Firmware logged | Verdict |
|---|---|---|---|---|---|
| — | — | *No checks yet: the bench build does not exist* | | | |
