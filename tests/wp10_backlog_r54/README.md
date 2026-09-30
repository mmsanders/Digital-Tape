# WP-10 backlog rows: mount repair, dup re-run, dup destination shape (R54, Verification #116)

Verifier-owned blind package for the top three rows of the #110 backlog. It was authored from the frozen
DRAFT-9 specs, re-verified at Product main `6e88b0f2458614dd9303bc6be8fc4d35535bdb73` (TapeFS `3f08ec6d…a19d`,
Engine API `38381732…baea6`, acceptance `ae77d13c…825d`). No `engine/`, Product adapter, or Product
implementation PR or issue was opened.

```sh
python3 audit.py      # backlog update vs the #110 six-row backlog and the planner census
python3 selftest.py   # census, §9.5 interruption classes, 68,854 clean synthetic, 7 causal controls (~3 min)
python3 synthetic_adapter.py > NEW.jsonl.gz
python3 replay.py evidence/synthetic/observations.jsonl.gz --manifest evidence/synthetic/manifest.json \
  --adapter-kind synthetic --adapter-source-sha <sha256 of LF-normalised synthetic_adapter.py>
```

- `deps.py` loads the accepted R29-B builders, pinned by Git blob.
- `model.py` is the crash, mount and duplicate model.
- `oracle.py` holds the planner and checks.
- `backlog-update.json` holds the re-ranked backlog, now 3 rows.
- `ADAPTER.md` is the public-only binding contract.

Synthetic evidence proves the verifier only.
