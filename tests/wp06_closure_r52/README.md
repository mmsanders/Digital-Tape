# WP-06 DRAFT-9 coverage reconciliation and closure gaps

This verifier-owned blind package was authored from Product public specs at `2cdad5f43b593754244221f42e79de4a4e61179c`, published verifier packages, retained public observations, and independent dispositions. No Product implementation was inspected.

Run `python3 audit.py` to validate the complete ledger/gap mapping and `python3 selftest.py` for the seven positive synthetic observations plus seven causal negative controls. Generate parser evidence with `python3 synthetic_adapter.py | gzip -n -9 > observations.jsonl.gz`, then use `replay.py` with a non-overwriting manifest. Synthetic evidence validates only the verifier; it is never Product evidence.

Frozen hashes: TapeFS `3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d`; Engine API `383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6`; acceptance `ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d`.

Return classification is **C**: the observable remainder is ready for PM→Software two-commit import, but two frozen WP-06e rows are unobservable under the same frozen stage oracle. See `COVERAGE.md` for the contradiction and `ADAPTER.md` for the public-only schema.
