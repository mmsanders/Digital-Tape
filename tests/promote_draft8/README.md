# Promote — DRAFT-8 classification and uninterrupted metadata paths

Verifier-owned package authored independently from TapeFS §4.5 and §9.3.0–§9.3.2.
It covers entry classification plus representative uninterrupted FRESH branches.
It is **not** WP-10 crash/RESUME acceptance and is not product acceptance by itself.

The fixtures deliberately keep a high-sequence A partner structurally valid but
semantically invalid. That makes it contribute to `cartridge_sequence` without
silently becoming the live Side A index.

## Cases

The package has 16 executable cases:

- empty Side B, including counters at `0xFFFFFFFF`: `INVALID_ARG`, zero writes;
- degraded-B: mount **Side A**, then promote returns `NO_VALID_INDEX`, zero writes;
- NOTHING TO DO, including counters at `0xFFFFFFFF`: `TAPE_OK`, zero writes;
- branch-exact sequence and superblock-generation exhaustion for:
  - FRESH adopt-in-place with phase 2 completing (`sequence_needed=3`, `generation_needed=2`);
  - FRESH adopt-in-place with step-5 decline (`1`, `2`);
  - FRESH allocating with phase 2 completing (`4`, `2`);
- exact counter-boundary successes ending at `0xFFFFFFFD`;
- cartridge-full with counter headroom, plus a compound full+exhausted case proving
  counter refusal occurs before the FRESH capacity refusal;
- uninterrupted adopt-complete, adopt-decline and allocating-complete metadata paths.

Completed-path checks bind exact final superblock/index bytes, exact sequence
consumption, exact +2 superblock generation, stage clearing, partner-first
superblock writes, index commit ordering, chunk-write destination coverage, and
the invariant that no below-`a_high_water` chunk write occurs before phase 2.

The VO08 envelope in this tranche contains superblocks and index slots, not chunk
payload bytes. Therefore it verifies **where** the uninterrupted path writes but
does not claim copied-audio byte identity or rendered-audio correctness.

## Self-test

```sh
python3 tests/promote_draft8/selftest.py
```

## Product evidence

Implement the contract in `ADAPTER.md`, then run:

```sh
python3 tests/promote_draft8/runner.py \
  --adapter-cmd './wp_promote_probe' \
  --adapter-kind product \
  --adapter-id '<stable adapter id>' \
  --adapter-source '<adapter source path or immutable id>' \
  --adapter-build '<reproducible build description>' \
  --product-commit '<Digital-Tape implementation commit>' \
  --verifier-commit '<Digital-Tape-Verification commit>' \
  --evidence-dir '<empty evidence directory>'
```

The runner authenticates the retained DRAFT-8 TapeFS, Engine API and acceptance
bytes before executing cases and hash-binds the package, observations, adapter
status, input/output media and verdicts.

Replay without invoking the product:

```sh
python3 tests/promote_draft8/replay.py '<evidence directory>'
```

## Deliberate exclusions

RESUME rows, crash boundaries, V7-001 two-interruption closure, WP-12a argument
stability/re-entry/state-matrix coverage, copied-audio byte identity, rendered
PCM/listening, random edit histories, and the caller-owned stored-position table
integration are not covered here. In particular, DRAFT-8's requirement that a
terminal successful promote clears stored positions remains a separate
firmware/integration acceptance item.
