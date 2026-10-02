# WP-10 residue destinations (DRAFT-10 V10-001, Verification #138)

This is a verifier-owned blind package for the acceptance WP-10 **Residue destinations** paragraph and the new
and changed tapefs §9.5/§9.6 crash-table rows. It was authored against issued DRAFT-10 at Product main
`d8243c95c88f38ce8b7fd6ad0de4280dd735d7a1`:

- TapeFS `2a6a9f7b…9c17eba`;
- Engine API `aa042e41…c66b33a`;
- acceptance `50aa63bd…9b9e547`.

No `engine/`, Product adapter or Product implementation was opened.

```sh
python3 audit.py      # supersession record, DRAFT-10 ledger delta and manifest vs the planner
python3 selftest.py   # census, fixtures, convergence, sample clean run, 4 causal controls (~2.5 min)
python3 synthetic_adapter.py | python3 replay.py - --manifest evidence/synthetic/manifest.json \
  --adapter-kind synthetic --adapter-source-sha <sha256 of LF-normalised synthetic_adapter.py>   # ~10 min
python3 d9_census.py  # optional: regenerates evidence/d9_census.json (~4 min)
```

| File | Role |
|---|---|
| `pins.py` | Loads the DRAFT-10 `wp10_backlog_r54/model.py`, pinned by Git blob (`0981d100`), which in turn pins R29-B |
| `plan.py` | Groups, fixtures, §9.6 format order, injection coordinates and phases, census |
| `oracle.py` | Exact model checks, phase-to-crash-table checks, and the identity property |
| `synthetic_adapter.py` | A conforming engine on an independent fault-injecting device; `MUTANTS` are causal controls |
| `ADAPTER.md` | The public-only Product binding contract |
| `COVERAGE.md` | Rows, census, assertions and controls |
| `SUPERSESSION.md` / `.json` | The accepted DRAFT-9 rows this package replaces (S1, S2) or relaxes (S3) |
| `ledger-d10.json` | WP-06 / WP-10 / WP-12a ledger status under DRAFT-10 (V10-002…V10-005) |

**Evidence.** The full synthetic stream (17,025,380 injections) is not committed. `manifest.json` binds its
SHA-256, and CI regenerates and replays it. Synthetic evidence proves the verifier only.
