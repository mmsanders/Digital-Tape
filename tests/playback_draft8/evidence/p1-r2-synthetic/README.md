# P1-R2-V synthetic verifier evidence

This is verifier-package evidence only. It contains no product-engine execution and makes no product acceptance or human-listening claim.

Source verifier commit: `afa7f280efa5d2dfeb966c44a2eff369b3e30f73`.
Source `tests/playback_draft8/` tree: `8293d51cae969ae044aa33872708dffe2fff9c3a`.

The synthetic public-call adapter passed all three assigned families: exact +1.0x forward playback, first-frame-after-seek at every run boundary and +/-1, and exact -1.0x reverse from end. `manifest.json` binds the complete input package, authenticated DRAFT-8 specification bytes, verifier source identity, adapter identity, raw observation, three observed PCM outputs, and saved result.

Offline replay from the repository root is:

```sh
python3 tests/playback_draft8/replay.py tests/playback_draft8/evidence/p1-r2-synthetic
```

Missing, extra, or tampered evidence; altered package/spec/fixture/candidate bytes; or verifier-source identity drift is a failing condition.
