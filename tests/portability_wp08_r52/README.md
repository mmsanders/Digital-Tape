# WP-08 R52 exact two-toolchain playback arithmetic

This verifier-owned package freezes 41 deterministic DRAFT-9 playback vectors
and compiles one observation adapter source under real GCC and Clang.  Both
executables must emit byte-identical public PCM, tell values, endpoint flags,
and public-call traces, and both byte streams must independently satisfy the
Python integer oracle.  Compiler labels never substitute for executing the two
binaries.

Run from this directory:

```sh
python3 selftest.py --gcc gcc --clang clang
python3 selftest.py --gcc gcc --clang clang --emit NEW_EVIDENCE_DIRECTORY
python3 replay.py evidence
(cd evidence && sha256sum -c SHA256SUMS)
```

The normal self-test exits nonzero if either compiler is missing, compilation
fails, either execution fails, either stream misses the oracle, or the streams
differ by even one byte.  Evidence generation refuses to overwrite a path.
The checked-in evidence was produced by the branch CI recipe on Ubuntu 24.04;
its manifest records the exact observed compiler identity and common flags.

`reference_adapter.c` is verifier self-test code, not Product.  A future
Product binding must obey `ADAPTER.md`, use the same adapter source and raw
fixtures under both toolchains, and produce separate observations for replay.
This package does not inspect or accept Product implementation.

## Frozen inputs

| Input | SHA-256 |
|---|---|
| TapeFS | `3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d` |
| Engine API | `383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6` |
| acceptance | `ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d` |

Normative anchors are Engine API §§6.1–6.3 and §8.  The oracle uses unbounded
Python integers to avoid inheriting C signed-shift, overflow, or rounding
behavior.  `plan.json` and the manifest bind the exact census and source.
