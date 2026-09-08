# Mount integration results for independent disposition

**Run by:** temporary Software Lead, 7 September 2026. Not independent acceptance.

Tests: unmodified verifier `tests/mount_draft8/` from
`4ee116fa040bb5ce040325e0076365abf8b0f8f9`; landed on product main through PR #27.
Contract: exact DRAFT-8 issued through PR #25. Both `.jsonl.gz` files preserve the
raw JSONL byte-for-byte using gzip without timestamps; `gzip -dc FILE` reads them.
The per-case logs include probe binary SHA-256, fixture hash, seed, observed API
results/callback events and assertion failures. No assertion or fixture was edited.

| Run | Engine input | Result |
|---|---|---|
| `pr20-before.jsonl.gz` | PR #20 at `56c50e226f55b509728811515da7a6d588d15c27` | 289 cases; 15 failures |
| `pr20-after.jsonl.gz` | Published PR #20 commit `740c97e998c7672d9e98916102be84430993521b` | 289 cases; zero failures |

The failures were four pre-read device-size cases and eleven stale-superblock
selection/repair cases. Fixes implement DRAFT-8's DEVICE_ADDRESSABLE guard before
any callback and preserve/repair the stale partner using exact candidate bytes.
No allocator, sequence-consumption, warm-start, state-transition or operation
implementation was added by this fix. Those pre-existing branch components remain
uncovered by the independent tranche and **unmerged**.

Mechanical integration uses the real public `tape.h`, never candidate_api.h:

```sh
make -C engine all
make -C tests/mount_draft8 engine PUBLIC_HEADER=tape.h \
  CPPFLAGS=-I../../../engine/include ENGINE_OBJECTS=../../../build/engine/libtape.a
python3 tests/mount_draft8/run.py \
  --adapter tests/mount_draft8/build/engine_probe \
  --log tests/mount_draft8/build/engine-results.jsonl
```

Original run used equivalent absolute include/archive paths from the scratch
checkout. Compiler: system `cc`, strict C99 engine warning gates. Also reproduced:
390 implementer checks plus existing crash-infrastructure binaries; no-allocation
and indirect-call gates; stack 1,536 / 8,192 bytes; RAM/instance 156,456 / 204,800
bytes; `.rodata` 1,040 / 32,768 bytes. None substitutes for verifier acceptance.

**Verification request:** inspect these observations and the already-authored
tests/contract only; do not open uncovered implementation or implementation-derived
tests. Confirm disposition of the covered mount assertions, or file precise findings.
VT8-001 and the remaining COVERAGE.md exclusions are unchanged. This request does
not ask you to approve or merge PR #20 as a whole.
