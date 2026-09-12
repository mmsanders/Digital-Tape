# VT8-001 — auditable DRAFT-8 operation tranche

This verifier-owned package is authored from the frozen DRAFT-8 contract without
inspection or import of product implementation. It covers two deliberately narrow
public-operation cases and is **not** full WP-07/WP-10 acceptance.

Normative DRAFT-8 SHA-256 values:

- TapeFS `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- Engine API `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- Acceptance `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

`runner.py` hashes the **actual bytes** in `--spec-dir` before a case runs and copies
those bytes into the evidence bundle. Its default is the independently authenticated
`tests/mount_draft8/spec/` copy. The repository-root `spec/` is historical and must
not be used as DRAFT-8 authority.

## Cases

### `VT8-001-RB-ALLSLOT`

Mount Side A on degraded-B media, observe `side_b_valid == false` through the public
API, call `tape_reset_side_b`, unmount, then remount Side B. The fixture has live A at
sequence 10, a structurally valid A partner at sequence 900 that is semantically
invalid for A, and equal-sequence B slots at 500. The result must write B0 at 901,
copy live-A entries with `side=1`, move no audio, leave the stage-0 superblock
unchanged, and make B selectable. The B0 index commit must be exactly entry block,
flush, header block, flush.

### `VT8-001-REC-ALLOCSEQ`

Mount Side B, seek to frame 128, arm splice, feed exactly 128 accepted frames, service
to completion, commit, unmount and remount Side B. The fixture has
`a_high_water == free_next == 3` and a structurally valid high sequence 700 in a slot
that is semantically invalid for A. The recording must allocate only chunk 3, durably
flush all service writes before commit metadata begins, commit B1 at sequence 701 as
`[(0,0,128),(3,0,128)]`, leave the stage-0 superblock unchanged, and derive
`free_next == 4` after remount. Commit I/O is exactly entries, flush, header, flush.

Whole-trace validation rejects illegal callback I/O from scripted calls, validates
callback ranges and return codes, and binds the verdict to public-call results such
as `accepted`, `more_work`, operation results, and the remount side. Legitimate
metadata reads during mount/remount and service reads remain permitted.

## Self-test and evidence replay

Run:

```sh
python3 tests/ops_draft8/selftest.py
```

It accepts two conforming synthetic observations, rejects the original six mutations,
and adds controls for P1-R1-V01/V02, the recording chunk-data barrier, callback range
and return values, and public-call results. It also proves spec-byte authentication
and that replay fails closed on missing or tampered evidence.

A real or synthetic adapter run uses:

```sh
python3 tests/ops_draft8/runner.py \
  --adapter /path/to/vt8_ops_probe \
  --adapter-kind product \
  --adapter-source <immutable-source-id> \
  --adapter-build '<compiler/build provenance>' \
  --verifier-source <verification-commit> \
  --evidence-dir /path/to/evidence

python3 tests/ops_draft8/replay.py /path/to/evidence
```

The evidence directory persists the exact raw input/final VO08 envelopes as deterministic gzip archives (with both archive and decompressed-raw SHA-256 bindings), adapter stdout
and stderr, complete callback/public-call observations, per-case verdicts, adapter
identity/build/source provenance, exact spec bytes and a hash-bound manifest. Replay
recomputes the verdict without invoking the engine or adapter. Synthetic evidence is
package evidence only and is never product acceptance.

See `COVERAGE.md` for assertion/spec mapping and exclusions, and
`../NEXT-TRANCHES.md` for the dependency-ordered plan beyond this return.
