# P1-R19-SW — VT8-001 two-case product run against the corrected package

**Issue:** [#102](https://github.com/mmsanders/Digital-Tape/issues/102) ·
**Date:** 19 September 2026 UTC ·
**Both cases PASS. Offline replay PASSES.**

This packet is **raw observation, not acceptance.** A green run accepts no source,
no helper design, no WP-07, no package, no PCM or golden, and does not authorize
merging held PR [#96](https://github.com/mmsanders/Digital-Tape/pull/96).

## What changed since P1-R17, and what did not

The engine and the product adapter did not change at all. `engine/` is tree
`7f73812ff5ade35d95b848c0df1fd0458aad22ca` and `tests/ops_adapter/` is tree
`6f6df812ae346933dff91aebb739feb0e2f0a113` — byte for byte the P1-R17 candidate.
All 25 held engine/header/adapter blobs were recorded before the synchronization
merge and re-read after it; the two lists are identical.

What changed is the verifier package. P1-R17 reported that the VT8-001 fixture
superblock declared `nominal_length_s = 60` alongside `total_chunks = 16`, which
TapeFS DRAFT-8 §2 derives as **21**, so both cases failed §4.1 phase 2 step 5 at
the first `tape_mount` and never reached the operation under test. Verification
corrected the generator to derive `total_chunks` from `nominal_length_s`, giving 21
chunks and a 23,553-block device, and added generator-side controls that reject a
stored/derived mismatch and undersized media.

P1-R17 also reported that `replay.py` could not close over a failing run, because
it recomputed only `hardened.check(...)` while the runner also recorded
`adapter returned {rc}`. `VT8-EVIDENCE-2` and the manifest-bound
`VT8-ADAPTER-STATUS-1` record now carry the adapter outcome explicitly, so runner
and replay agree either way. That is why the replay below passes rather than
diverging by one string.

## Provenance

| Object | Identity |
|---|---|
| Product main at import | `48cc23fdbe6273dfe73f17fbdddf8e9fcc5ab3d9` |
| Verifier publication | `digital-tape-verification@15dd16eb499f5c148bff7c5b4b67ff75ae7a0f32` |
| `tests/ops_draft8` tree | `3667a2830ba80dbcedad03b97870d1127001ab59` |
| Pre-run code commit | `e1aaf5f3f441e5126e821a0bd2cfa54a98894294` |
| Candidate `engine/` tree | `7f73812ff5ade35d95b848c0df1fd0458aad22ca` |
| `tests/ops_adapter/` tree | `6f6df812ae346933dff91aebb739feb0e2f0a113` |
| `vt8_ops_probe.c` blob | `b920d111428f5407e604f0d5db12da331c4eed6c` |
| Adapter binary SHA-256 | `9dc0522ea21fb6a16943a206aa309984b0f783b00a07d4495d024ecdbb158fac` |
| `oracle.py` / `hardened.py` / `runner.py` SHA-256 | `3e213af2…0dcca5` / `0e88b276…7ee0dc` / `d7e3ffe1…f1fadb` |
| Toolchain | `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`, `python3 3.11.15` |

## Results

| Case | Adapter outcome | Exit | Verdict | Errors |
|---|---|---|---|---|
| `VT8-001-RB-ALLSLOT` | `exited` | 0 | **PASS** | none |
| `VT8-001-REC-ALLOCSEQ` | `exited` | 0 | **PASS** | none |

`manifest.json` SHA-256 `8166e9d35103ea205e741691b889db4db61d48c5bee3249ce659ee9470a356eb`
`run.jsonl` SHA-256 `1604cedc5582bc14fb208b0580b16a5177af258c343b0cd54aeb913db6e4ab16`

Offline replay recomputes both verdicts without invoking the engine or adapter:
**REPLAY PASS — evidence complete, hash-bound, DRAFT-8 authenticated.**

## Observed operation traces

`VT8-001-RB-ALLSLOT` — §8 ordering, entries then header, no superblock or chunk write:

```
reset_b  write lba 265 count 1      (B0 entry array)
reset_b  flush
reset_b  write lba 264 count 1      (B0 header — the commit point)
reset_b  flush
```

`VT8-001-REC-ALLOCSEQ` — chunk data behind one barrier, then metadata only:

```
service  write lba 5120 count 1     (the newly allocated chunk)
service  flush                      (§8 step 2 durability barrier)
service  read  lba 2048 count 1     (play-window fill)
commit   write lba 393 count 1      (B1 entry array)
commit   flush
commit   write lba 392 count 1      (B1 header — the commit point)
commit   flush
```

`seek`, `arm`, `feed` and `unmount` issue no block I/O; `commit` performs no read.

## Exclusions — what this packet does NOT establish

Nothing about warm start; overwrite or overdub; `tape_abort`; zero-frame commit;
crash injection or recovery; FAULTED quarantine; promote, re-spool, duplicate or
format; stage clearing (both fixtures remain `promote_stage == 0`); interior splice
or splice at an entry boundary; partial-block record drain; multi-chunk allocation;
`CARTRIDGE_FULL` short accept; long-operation continuation; target performance;
media atomicity; PCM comparison; goldens; or human listening.

The two cases do not establish WP-07, WP-10, WP-11, WP-12a, an operation/state
freeze, or product-engine acceptance. PR #96 remains held.
