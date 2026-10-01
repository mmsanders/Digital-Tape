# WP-08 R52 Product adapter contract

The future Product adapter is observation plumbing.  It calls only the frozen
public API and records every supplied block-device callback; it must not read
private engine state, derive goldens from Product output, filter events, use a
tolerance comparison, or consume an adapter verdict.

## One source, two builds

Compile the exact same adapter source and fixture builder twice, once with GCC
and once with Clang.  Use the same flags for both where supported and record:

- the full first compiler `--version` line and exact flags;
- SHA-256 of adapter source and every generated input;
- Product commit/tree and raw fixture SHA-256;
- the canonical plan digest; and
- each unabridged JSONL byte stream and its SHA-256.

A compiler being absent, a skipped vector, or one failed build/run is a hard
failure.  Compiler-name macros or labels are metadata only.  Replay requires
the two public-observation streams to be byte-identical before applying the
oracle.

## Per-vector script

Use a fresh valid Side-B mount whose exact interleaved stereo s16 frames and
physical run subdivision equal the selected `plan.json` row.  Preserve and
hash the raw superblock, both B candidates with CRC-covered entry bytes, and
all referenced PCM bytes.  Then:

1. `tape_mount(B)`;
2. `tape_seek(seek)`;
3. `tape_set_rate(rate)`;
4. `tape_service(7)` until `more_work == false`;
5. one `tape_render(requested)`;
6. `tape_tell()` and `tape_status()` immediately after render.

Record symbolic public results, arguments, returned counts, tell, `at_start`,
`at_end`, exact little-endian PCM bytes, and every callback caused by each
public call, unfiltered, as `{"op", "lba", "count", "rc"}` for a read or write
and `{"op": "flush", "rc"}` for a flush.  Record the fixture device's
`block_count` at the top level of each observation.

The callback rule for each call:

- **`tape_mount` and `tape_service`** may read media, as a device-backed mount
  and ring fill must (tapefs §4.1/§4.2, engine-api §6). They must perform zero
  writes and zero flushes, and every read must lie inside `block_count`. Mount
  must read both superblock copies (tapefs §4.1 phase 1).
- **`tape_seek`, `tape_set_rate` and `tape_render`** must each have an explicit
  empty callback list.

The
reference evidence uses the compact schema emitted by `reference_adapter.c`;
the Product binding may add raw-media fields, but may not omit or rewrite the
fields consumed by `oracle.py`.

Mechanical include/library paths and callback wrappers are the only permitted
binding edits.  Do not change plan values, compiler-dependent code paths,
fixtures, expected values, or oracle assertions to fit Product.
