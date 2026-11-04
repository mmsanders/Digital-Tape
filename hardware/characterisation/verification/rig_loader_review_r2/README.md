# V390 loader boundary review r2

Hardware baf176c fixes the seven published rig_review_r1 cases, but its new
backstop covers only grammar checks. Four new boundary cases require malformed
input to return a three-part loader result with nonempty problems. Ordinary
invalid objects and missing files pass; NUL manifest filenames and deeply nested
JSON (10,000 nested arrays) raise before that backstop.
The first Linux run accepted a2,000-level fixture that raises on Windows Python3.10;
the stronger portable parser-boundary fixture replaces it before publication. These are new review-discovered regressions,
not retrospective tests-first claims. Import unchanged before corresponding fixes.
Depends only on Python3.10+ and the supplied Product judge.

```
python -B tests/rig_loader_review_r2/run.py --judge PATH/media_atomicity.py --out NEW_OUTPUT
```

A fifth case requires failed-E0 setup to retain TORN, CORRUPT and all four
neighbour-damage observations with no proof/credit. Depends on sibling rig_records_r1.

Strict mode requires all five cases. `--record-known-findings` pins the canonical
baf176c judge SHA256 and requires exactly the two known failures; green means HOLD
reproduced. Two result-predicate controls reject missing refusal and false success.
No substitute Product loader, physical file/device or rig result is used. Older
packages remain unchanged; valid/setup/damage behavior is checked by their suites.
