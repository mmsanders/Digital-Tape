# WP-10 DRAFT-9 crash-injection reconciliation and top-three gap rows (R53)

Verifier-owned blind package for Verification issue #105. It was authored from the frozen public
specs at Product `39d2076fa204991ec9c0d43f00b502942556bf9a`, the published verifier packages, and
their dispositions. No `engine/`, Product adapter, or Product implementation PR or issue was opened.

Frozen hashes: TapeFS `3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d`; Engine API
`383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6`; acceptance
`ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d`. DRAFT-9 changes only V9-001
(WP-13); the WP-10 text and all media semantics are byte-identical to DRAFT-8.

```sh
python3 audit.py      # ledger vocabulary, citations, 3 published rows <-> planner census, ranked backlog
python3 selftest.py   # census + §9.5/§9.6 table cross-check + 57,539 clean synthetic + 7 causal controls (~80 s)
python3 synthetic_adapter.py > NEW.jsonl.gz
python3 replay.py evidence/synthetic/observations.jsonl.gz --manifest evidence/synthetic/manifest.json \
  --adapter-kind synthetic --adapter-source-sha <sha256 of LF-normalised synthetic_adapter.py>
```

- `coverage-ledger.json` is the authority; `COVERAGE.md` explains the ranking.
- `model.py` holds the transactions, the durability model and the mount classifier.
- `oracle.py` holds the planner and the checks.
- `ADAPTER.md` is the public-only Product binding contract.

Superblock and WIP-template bytes come from `format_dup_identity_draft8/fixture.py`, pinned by Git
blob `86df43a254479464559e299855e900d5637836a9`. Synthetic evidence proves the verifier only.
