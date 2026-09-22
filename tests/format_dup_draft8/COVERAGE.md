# Format / dup / empty-promote refusal matrix

| ID | Cases | Assertion | Basis / control |
|---|---|---|---|
| FMT-A01 | `FMT-RO` | read-only format returns `READ_ONLY`, zero writes | TapeFS §9.6; invariant 18 |
| FMT-A02 | `FMT-GEOM-0/1/BASE` | `DEVICE_ADDRESSABLE` failures return `GEOMETRY`, zero callbacks | TapeFS §2.1/§9.6; WP-06d; callback mutation controls |
| FMT-A03 | `FMT-GEOM-FIT` | addressable but undersized geometry still returns `GEOMETRY` | `GEOMETRY_OK` line 3; result/write controls |
| FMT-A04 | `FMT-ORDER-RO` | read-only is evaluated before geometry | TapeFS §9.6 ordered preconditions |
| DUP-A01 | `DUP-ALIAS` | aliasing returns `INVALID_ARG`, `more_work=false`, zero writes | TapeFS §9.5 item 1 |
| DUP-A02 | `DUP-RO` | read-only destination returns `READ_ONLY`, zero writes | TapeFS §9.5 item 2 |
| DUP-A03 | `DUP-GEOM-0/1/BASE` | `DEVICE_ADDRESSABLE` failures return `GEOMETRY`, zero callbacks | TapeFS §2.1/§9.5 item 3; WP-06d |
| DUP-A04 | `DUP-GEOM-FIT` | addressable but undersized geometry still returns `GEOMETRY` | `GEOMETRY_OK` line 3 |
| DUP-A05 | `DUP-TOO-SMALL` | geometry passes but source timeline does not fit → `DEST_TOO_SMALL` | TapeFS §9.5 item 4 |
| DUP-A06 | `DUP-ORDER-ALIAS/RO/GEOM` | complete 1→2→3→4 error precedence is executable | TapeFS §9.5 normative order; V4-006 |
| RAW-A01 | all format/dup refusals | zero writes and no destination-superblock classification read | TapeFS §9.5 item 5 / §9.6 classification after refusals |
| PR-A01 | `PROMOTE-EMPTY` | empty Side B → `INVALID_ARG`, `more_work=false`, zero writes | Engine API invariants 22/30; TapeFS §9.3 |

The oracle intentionally does **not** impose zero callbacks on every refusal.
Only the exact `block_count ∈ {0,1,LBA_CHUNK_BASE}` geometry cases carry the
explicit zero-callback acceptance requirement. Other refusal rows assert zero
writes plus the ordering consequence that raw destination-superblock
classification has not begun.

The package includes an executable product runner and hash-bound offline replay.
It remains a narrow tranche: crash tables, success-path cartridge construction,
generation-exhausted fallback behavior, remount classification, and WP-12a
continuation/state-machine coverage stay excluded.
