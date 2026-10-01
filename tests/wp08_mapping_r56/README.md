# WP-08 mapped-run rows (Verification #129, R56)

A verifier-owned blind package. It is the gap half of the WP-08 coverage reconciliation; the ledger half is
`LEDGER.md` and `wp08-ledger.json`.

It was authored from the frozen DRAFT-9 specs:

| Spec | SHA-256 |
|---|---|
| TapeFS | `3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d` |
| Engine API | `383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6` |
| Acceptance | `ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d` |

It reuses only the #118 C69-layout builders and audio pattern (`wp10_final_r54`), pinned by Git blob in `pins.py`.
No `engine/`, Product adapter, or Product implementation PR or issue was opened.

```sh
python3 audit.py      # pins, census, case set, ledger consistency
python3 selftest.py   # 62 clean synthetic cases, 6 controls on derived exact kill sets
python3 synthetic_adapter.py > NEW.jsonl.gz
python3 replay.py evidence/synthetic/observations.jsonl.gz --manifest evidence/synthetic/manifest.json \
  --adapter-kind synthetic --adapter-source-sha <sha256 of LF-normalised synthetic_adapter.py>
```

Synthetic evidence proves the verifier only.
