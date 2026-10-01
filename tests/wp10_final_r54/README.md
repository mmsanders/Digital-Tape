# WP-10 final backlog rows and closing ledger (R54, Verification #118)

This is a verifier-owned blind package. It was authored from the frozen DRAFT-9 specs, re-verified at
Product main `66c6abc69d83cff10da32a6b446690fcd0b927fb`:

| Spec | SHA-256 |
|---|---|
| TapeFS | `3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d` |
| Engine API | `383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6` |
| acceptance | `ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d` |

No `engine/`, Product adapter, or Product implementation PR or issue was opened while authoring it.

```sh
python3 audit.py      # closing ledger: #105's 61 rows + WP10.dup.rerun_crash, none uncovered
python3 selftest.py   # census, row-4 identity census and PM finding cells, clean synthetic, 9 controls
python3 synthetic_adapter.py > NEW.jsonl.gz
python3 replay.py evidence/synthetic/observations.jsonl.gz --manifest evidence/synthetic/manifest.json \
  --adapter-kind synthetic --adapter-source-sha <sha256 of LF-normalised synthetic_adapter.py>
```

## Files

- `deps.py`: byte-identical to the #110 `deps.py`. It loads the accepted `crash_core_draft8` and
  `format_dup_identity_draft8` models, pinned by Git blob. Those blobs are identical on Product main.
- `dupmodel.py`: byte-identical to the #116 `model.py`, blob `53d0b75e`, pinned in `model.py`.
- `model.py`: the row 1–3 fixtures and the row 4 representatives.
- `oracle.py`: the planner and the checks.
- `coverage-ledger.json`: the closing ledger.
- `ADAPTER.md`: the public-only binding contract.
- `COVERAGE.md`: the rows and PM finding **V-R54-03**.

Synthetic evidence proves only the verifier.
