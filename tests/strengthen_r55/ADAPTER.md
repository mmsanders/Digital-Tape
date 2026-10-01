# #126 strengthening rows: public-observation adapter contract

- Use public calls only, on caller-owned devices.
- Do not import this oracle, read private engine state, or emit verdicts. The oracle rejects `verdict`,
  `passed`, `permitted`, `expected`, `outcome_ok`, `row_ok`, `same_audio`, `floor_ok`, `pass2_ran` and
  `premise_ok`.
- Emit one `strengthen-r55-observation-v1` object per `oracle.iter_cases()` entry, in order, as gzip JSONL.
- Every object carries `schema`, `index`, `row`, `kind` and the case's identity fields.
- Build each fixture image **byte for byte** from `rows.py`. The oracle checks its SHA-256.

## Row 1: the copy carries every audio block (`kind` `dup_audio`)

The geometry is #116's R29-B layout: 4 chunks, 9 s, `block_count` 6,145.

- **Source:** a separate device holding `rows.dup_source_image(frames)`. Side A is `{0,0,frames}`, and every frame
  of chunks `[0, len_A)` is `rows.source_frame(chunk, frame)`, which is coordinate-unique and non-zero.
- **Destination:** a separate device holding `rows.dup_destination_image(destination)`. The reusable shape carries
  `rows.old_frame` in every chunk.
- **Call:** `tape_dup(src, dst, FRESH_DUP_UUID, 0, 9, 65535)` until `more_work == false`.

Emit:

- `source_image_sha256`, the SHA-256 of the source device image;
- `destination_image_sha256_before`, the SHA-256 of the destination device image before the call;
- `call: {fn, result, more_work}`;
- `source_pcm_sha256`, the source Side A rendered at 1.0×;
- `copy_raw_sha256`, the SHA-256 of the destination's raw bytes `[chunk-store base, base + frames·4)` read
  straight from the device after the call. These are the copied frames in tapefs §9.5 layout `{0,0,frames}`.
- `mount_A` and `mount_B`: fresh mounts of the destination, each as
  `{result, info: {total_frames, entry_count}, pcm_sha256}`.

## Row 2: WP-06f re-spool pass-2 *run* branch from a Side-A mount (`kind` `respool_pass2_run`)

- **Fixture:** `rows.pass2_image()`, the C69 layout (5 chunks, 12 s). `a_high_water` is 2, Side A is
  `{0,0,10}`, and live B0 is `[{2,0,10},{3,0,10}]`. Live B therefore densely fills `[2, 4)` and the floor is 4.
  `len` is 1, so a lawful lower run exists after pass 1.
- **Calls:** mount **Side A**, then call `tape_respool(64)` until `more_work == false`, recording each call as
  `{fn, block_budget, result, more_work}`.

Emit:

- `image_sha256_before`;
- `mount`;
- `calls`;
- `events`: every write and flush callback, as `{op, lba, count}`. Every write outside the chunk store also
  carries `data`, the written blocks as lowercase hex, so the oracle can rebuild both sides' live set at each
  write.
- `mount_B_after`: a fresh Side-B mount, `{result, info: {total_frames, entry_count}, pcm_sha256}`.

## Row 3: #99 capacity A-slot premise (`kind` `capacity_premise`)

Run the #99 capacity case named `capacity_case` exactly as `capacity_wp09_r52/ADAPTER.md` specifies. That
includes the full fixture, with an empty A0 at sequence 1 and an invalid A1.

Emit that package's `wp09-capacity-r52-v1` fields, with two changes:

- `raw_before` carries **six** keys: `primary`, `mirror`, `A0`, `A1`, `B0` and `B1`, each slot as
  `{header, entries}`, read from media before the operation.
- `fixture_sha256` covers all six.

The oracle checks the A-slot premise from those raw bytes. It then replays the unchanged #99 oracle on the
four-key subset.

## Replay

```
replay.py --adapter-kind product --adapter-source-sha SHA --product-commit SHA --product-tree SHA
```

A passing replay still needs independent disposition.
