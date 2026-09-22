# Format / duplicate / empty-promote refusal tranche

Verifier-owned DRAFT-8 package for the raw-operation refusal boundary and the
empty-Side-B promote refusal. It is independent of WP-10 crash tables and of
format/duplicate identity-assignment success paths.

Normative basis: TapeFS §2.1, §9.5 items 1–4, §9.6 preconditions; Engine API
invariants 18, 22 and 30; acceptance WP-06d and WP-10 refusal rows.

This package is not product acceptance by itself. Product evidence is produced
only by `runner.py` against an adapter identified as `product`.

## Cases

| ID | Assertion |
|---|---|
| `FMT-RO` | `write == NULL` → `TAPE_ERR_READ_ONLY`, zero writes |
| `FMT-GEOM-0` | `block_count == 0` → `TAPE_ERR_GEOMETRY`, zero callbacks |
| `FMT-GEOM-1` | `block_count == 1` → `TAPE_ERR_GEOMETRY`, zero callbacks |
| `FMT-GEOM-BASE` | `block_count == LBA_CHUNK_BASE` → `TAPE_ERR_GEOMETRY`, zero callbacks |
| `FMT-GEOM-FIT` | addressable device one block short of `GEOMETRY_OK` → `TAPE_ERR_GEOMETRY`, zero writes |
| `FMT-ORDER-RO` | read-only + bad geometry → `TAPE_ERR_READ_ONLY` |
| `DUP-ALIAS` | destination aliases source → `TAPE_ERR_INVALID_ARG`, `more_work=false`, zero writes |
| `DUP-RO` | destination `write == NULL` → `TAPE_ERR_READ_ONLY`, zero writes |
| `DUP-GEOM-0` | destination `block_count == 0` → `TAPE_ERR_GEOMETRY`, zero callbacks |
| `DUP-GEOM-1` | destination `block_count == 1` → `TAPE_ERR_GEOMETRY`, zero callbacks |
| `DUP-GEOM-BASE` | destination `block_count == LBA_CHUNK_BASE` → `TAPE_ERR_GEOMETRY`, zero callbacks |
| `DUP-GEOM-FIT` | addressable destination one block short of `GEOMETRY_OK` → `TAPE_ERR_GEOMETRY` |
| `DUP-TOO-SMALL` | geometry passes but Side A needs more chunks → `TAPE_ERR_DEST_TOO_SMALL` |
| `DUP-ORDER-ALIAS` | alias + read-only + bad geometry/capacity → alias `INVALID_ARG` |
| `DUP-ORDER-RO` | read-only + bad geometry/capacity → `READ_ONLY` |
| `DUP-ORDER-GEOM` | bad geometry + insufficient capacity → `GEOMETRY` |
| `PROMOTE-EMPTY` | empty Side B → `TAPE_ERR_INVALID_ARG`, `more_work=false`, zero writes |

All format/duplicate refusals must occur before raw destination-superblock
classification. The exact `0`, `1`, and `LBA_CHUNK_BASE` geometry rows have the
stronger acceptance requirement of zero block-device callbacks of any kind.

## Self-test

```sh
python3 tests/format_dup_draft8/selftest.py
```

The self-test mutation-checks results, `more_work`, writes, tracked-media
mutation, destination-superblock reads, exact geometry callback silence, alias
evidence, and missing-call handling.

## Product evidence

See `ADAPTER.md`, then run:

```sh
python3 tests/format_dup_draft8/runner.py \
  --adapter-cmd './wp_fmt_dup_probe' \
  --adapter-kind product \
  --adapter-id '<stable adapter id>' \
  --adapter-source '<adapter source path>' \
  --adapter-build '<reproducible build description>' \
  --source-commit '<Digital-Tape implementation commit>' \
  --source-tree '<Digital-Tape implementation tree>' \
  --evidence-dir '<empty evidence directory>'
```

Replay the captured evidence with:

```sh
python3 tests/format_dup_draft8/replay.py '<evidence directory>'
```

Excluded: raw-superblock template/fallback success work, identity-assignment
commits, WP-10 crash injection, two-interruption partner-first closure,
generation-exhausted zeroing outcomes, destination remount classification,
long-operation continuation/state-matrix coverage, and product success paths.
