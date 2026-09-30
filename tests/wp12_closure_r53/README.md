# WP-12 / WP-12a DRAFT-9 coverage reconciliation and closure gaps (R53)

Verifier-owned blind package for Verification issue #104. It was authored from the frozen public
specs at Product `39d2076fa204991ec9c0d43f00b502942556bf9a`, the published verifier packages, and
their independent dispositions. No Product implementation, adapter, implementation PR, or issue
was opened.

Frozen hashes: TapeFS `3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d`; Engine API
`383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6`; acceptance
`ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d`. DRAFT-9 changes only the WP-13
`dev_progress` funnel (V9-001); WP-12/WP-12a text and all media semantics are byte-identical to the
DRAFT-8 bases of the accepted packages.

```sh
python3 audit.py      # ledger vocabulary, citations, ledger <-> plan mapping, tranche minimum
python3 selftest.py   # 7 positive synthetic cases + 6 causal mutant controls
python3 synthetic_adapter.py > NEW.jsonl.gz
python3 replay.py evidence/synthetic/observations.jsonl.gz --manifest evidence/synthetic/manifest.json \
  --adapter-kind synthetic --adapter-source-sha <sha256 of LF-normalised synthetic_adapter.py>
```

`coverage-ledger.json` is the authority (see `COVERAGE.md`). `ADAPTER.md` is the public-only
Product binding contract. Synthetic evidence proves the verifier only, never Product behavior.
`fixtures.py` imports metadata builders from `respool_draft8/oracle.py` and
`promote_draft8/fixture.py`, pinned by Git blob SHA.
