# WP-09 R52 positive capacity short accept

This verifier-owned tranche closes the positive capacity edge deliberately left
open by `tests/record_draft8`: all three record modes, start/middle/end, and
three independently constructed near-capacity shapes.  It was authored from
the frozen public DRAFT-9 specifications.  It neither inspects Product source
nor treats synthetic observations as Product acceptance.

## Reproduce

From this directory:

```sh
python3 selftest.py
python3 replay.py evidence/observations.jsonl.gz \
  --manifest /tmp/wp09-r52-synthetic-manifest.json \
  --adapter-kind synthetic \
  --adapter-source-sha256 7f4deb37a20c2e242aa12487bee178253e8da56c9d1a04b7c57c358c33cd6608
(cd evidence && sha256sum -c SHA256SUMS)
```

`selftest.py` validates every case, proves adapter verdict labels have no
authority, and requires seven deliberately bad observations to fail.  The
checked-in gzip is deterministic, contains all 27 raw observation records, and
is replayable without network access.  To regenerate it into a new directory,
run `python3 selftest.py --emit NEW_DIRECTORY`; existing paths are never
overwritten.

For a real Product run, a mechanical adapter complying with `ADAPTER.md`
creates the same JSONL schema.  Replay it with `--adapter-kind product`, the
adapter source SHA-256, and the exact Product commit and tree.  A PASS then
means only that those observations satisfy this tranche; no adapter-provided
verdict is consulted.

## Frozen specification identity

| Public input | SHA-256 |
|---|---|
| `spec/tapefs-v1.md` | `3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d` |
| `spec/engine-api.md` | `383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6` |
| `spec/acceptance.md` | `ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d` |

The normative anchors are Engine API §7 and §7.1, TapeFS §6–§9.1, and
acceptance WP-09 plus “Cartridge full mid-record.”  `plan.json` is the exact
case plan; its canonical digest is printed by the self-test and replay.

See `COVERAGE.md` for the assertion boundary.  This package does not claim
whole-WP acceptance, firmware behavior, crash coverage, performance, or audio
quality.
