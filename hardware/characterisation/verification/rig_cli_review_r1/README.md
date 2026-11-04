# V392 judge CLI parser-boundary review r1

Hardware's c55e5ad return explicitly declares deeply nested plan/results refusal,
exit2 instead of traceback, as already implemented without a corresponding case.
These independent expectations were authored from that declared contract before
inspecting the delta. This publication makes no retrospective tests-first claim.
No engine/firmware change is involved. Earlier packages stay unchanged.

```
python -B tests/rig_cli_review_r1/run.py --judge CANDIDATE/media_atomicity.py --negative-judge BAF176C/media_atomicity.py --out NEW_OUTPUT
```

Three cases: valid authenticated production1000+lateNEW run is PASS/exit0;
a10,000-level JSON plan and result each refuse with exit2 and no traceback.
The actual previous judge must pass the positive and fail exactly both parser
cases. Three predicate controls reject blanket success, traceback and blanket
refusal. Fixtures depend on the unchanged sibling rig_records_r1 package; all
records are synthetic. Raw generated campaign streams are not committed.
