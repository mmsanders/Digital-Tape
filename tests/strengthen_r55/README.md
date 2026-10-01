# #126 strengthening rows (R55, Verification #126)

A verifier-owned blind package with three new rows. Each one makes an accepted row able to see a defect it
currently cannot. None invalidates an accepted PASS.

It was authored from the frozen DRAFT-9 specs, re-verified at Product main `2e54e0fc`:

| Spec | SHA-256 |
|---|---|
| TapeFS | `3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d` |
| Engine API | `383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6` |
| Acceptance | `ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d` |

It also builds on my own published packages, pinned by Git blob in `pins.py`:

- `wp10_final_r54` (#118): its `model.py`, `dupmodel.py` and `deps.py`;
- `capacity_wp09_r52` (#99): its `oracle.py`, and `synthetic.py` as maintained in #126.

No `engine/`, Product adapter, or Product implementation PR or issue was opened.

```sh
python3 audit.py      # pins, census, case set
python3 selftest.py   # 40 clean synthetic cases, 9 controls on exact kill sets
python3 synthetic_adapter.py > NEW.jsonl.gz
python3 replay.py evidence/synthetic/observations.jsonl.gz --manifest evidence/synthetic/manifest.json \
  --adapter-kind synthetic --adapter-source-sha <sha256 of LF-normalised synthetic_adapter.py>
```

See `COVERAGE.md` for the rows and `ADAPTER.md` for the binding contract. Synthetic evidence proves the verifier
only.
