# WP-10 backlog rows 1–3 (R53, Verification #110)

Verifier-owned blind package for the top three rows of the #105 WP-10 backlog. It was authored from
the frozen public DRAFT-9 specs, re-verified at Product main `6e88b0f2458614dd9303bc6be8fc4d35535bdb73`
(TapeFS `3f08ec6d…a19d`, Engine API `38381732…baea6`, acceptance `ae77d13c…825d`). No `engine/`,
Product adapter, or Product implementation PR or issue was opened.

```sh
python3 audit.py      # backlog update vs the #105 ledger's nine backlog ids and the planner census
python3 selftest.py   # census + 79,820 clean synthetic observations + 9 causal controls (~90 s)
python3 synthetic_adapter.py > NEW.jsonl.gz
python3 replay.py evidence/synthetic/observations.jsonl.gz --manifest evidence/synthetic/manifest.json \
  --adapter-kind synthetic --adapter-source-sha <sha256 of LF-normalised synthetic_adapter.py>
```

- `deps.py` loads the accepted `crash_core_draft8` and `format_dup_identity_draft8` models in isolation.
  Their eight source files are pinned by Git blob; rows 2 and 3 reuse those models for fixtures and
  durable post-crash state.
- `dupfrag.py` is the row-1 transaction, durability and mount model, adapted from the #105 package.
- `oracle.py` holds the planner and checks. `backlog-update.json` holds the re-ranked backlog.
  `ADAPTER.md` is the public-only binding contract.

Synthetic evidence proves the verifier only.
