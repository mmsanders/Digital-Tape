# WP-10 final backlog (#118): public-observation adapter contract

**Rules for the adapter.**
- Use public calls only, with caller-owned devices.
- Do not import this oracle, read private engine state, or emit verdicts. The oracle rejects any of these
  field names: `verdict`, `passed`, `permitted`, `expected`, `outcome_ok`, `row_ok`, `same_audio`,
  `identity_ok`, `selected_slot`, `phase`, `pass`.

**Output.**
- Emit one `wp10-final-r54-observation-v1` object per `oracle.iter_cases()` entry, in order, as gzip JSONL.
- Every object carries `schema`, `index`, `row` and `kind`.
- "Events" are device callbacks: `{"op": "read"|"write", "lba", "count"}` or `{"op": "flush"}`.

## Rows 1 and 2: contract cases (`kind` `contract`)

**Fixture.** Build the fixture image byte for byte on the accepted C69 geometry: 5 chunks, 12 s,
`block_count` 7,169.
- Row 1 uses `model.row1_image(model.ROW1[case][0])`.
- Row 2 uses `model.row2_image(model.ROW2[case][0])`.

**Calls.**
1. Mount the listed side (row 2 always mounts `B`) on a writable device.
2. Make one call:
   - `tape_reset_side_b()`;
   - `tape_arm(TAPE_REC_OVERWRITE)`; or
   - `tape_respool(65535)` repeated until `more_work == false`, or until the first non-`TAPE_OK` result.
   Record every call's result and its final `more_work` in `call`.

**Emit:**

- `case`;
- `image_sha256_before` and `image_sha256_after`: SHA-256 of the whole device image before the mount and
  after the call;
- `mount: {fn: "tape_mount", side, result}`;
- `call: {fn, result[, more_work]}`;
- `events`: every write and flush callback made during the call, in order. Reads may be omitted.
- `after_raw`: lowercase hex of the device after the call, with these keys:
  - `P` and `M`: LBA 0 and LBA 7168, 512 B each;
  - `A0`, `A1`, `B0` and `B1`: the first two blocks of each slot, 1,024 B each.

## Row 3: post-crash re-spool render (`kind` `respool_render`), one object per fixture

**Fixture.** `model.row3_image(fixture)`.

**Pre-state.**
1. Mount Side B.
2. Render the whole side at 1.0× from frame 0. Emit `pre.mount_B = {result, info: {total_frames,
   entry_count, side_b_valid}, pcm_sha256}`, where `pcm_sha256` covers the little-endian `tape_render`
   output.
3. Mount Side A on a fresh device and render it. Emit `pre.a_pcm_sha256`.

**Clean run.**
1. Mount Side B on a fresh device.
2. Call `tape_respool(64)` until `more_work == false`, recording each call as
   `{fn, block_budget, result, more_work}` in `clean.calls`.
3. Record `clean.events`: every read, write and flush callback across those calls.
4. Remount Side B and emit `clean.post_mount_B` in the pre-state format.

**Crash runs.** Enumerate crash runs from **your own clean trace** in `oracle.row3_injections(clean.events)`
order:

```
for mode in ("flush_required", "write_through"):
    ["write", k, landed] for each clean write k, landed 0..512;
    then ["flush", j] for each clean flush j.
```

For each crash run, replay the same fixture on a fresh device and cut power at that coordinate. Durability
follows tapefs §8.1:
- **write-through:** every completed write is durable at once;
- **flush-required:** completed writes become durable when a flush returns. At the cut, pending write `i` of
  `n` survives iff bit `n−1−i` of `(ordinal mod 2^n)` is set, where `ordinal` is the crash's 0-based
  position in this fixture's list;
- **the injected write:** its first `landed` bytes land over the durable contents, in both modes. At
  `landed` 512 it counts as a completed write.

Then, on fresh devices holding only the durable bytes, mount Side B and Side A and render each whole side.

Emit `crashes`, one object per crash run:
- `mode` and `inject`;
- `fired`;
- `prefix_len`: the 1-based position of the injected callback in `clean.events`;
- `remount_B`: in the pre-state format;
- `remount_A: {result, pcm_sha256}`.

## Row 4: crashes inside the duplicate re-run (`kind` `rerun_crash`)

**Devices.**
- **Destination:** `dupmodel.rerun_destination(shape)` on the R29-B 4-chunk / 9 s geometry. The
  `dupmodel.TRACKED` blocks come from the model; every other block is zero.
- **Source:** a separate device, the 128-frame source from #116 ADAPTER.md row 2: Side A `{0,0,128}`, chunk
  0 block 0 = `SOURCE_AUDIO`.
- **Calls:** `tape_dup(src, dst, FRESH_DUP_UUID, 0, 9, 65535)`, repeated until `more_work == false`.

**Run.**
1. **First run.** Inject `first_inject` in `first_mode`, as in #105 ADAPTER.md: `["write", k, landed]` or
   `["flush", j]`, counted from the first destination callback. Every representative leaves exactly one
   permitted durable image, so the settle rule does not matter here.
2. **Power returns.** The same destination device now holds only its durable bytes, with no format in
   between.
3. **Re-run.** Run `tape_dup` again and inject `inject` in `mode`. Use the flush-required survivor rule from
   row 3, with `ordinal` = case `index`.
4. **Remount.** On fresh devices holding the durable bytes, remount `ro_A` (write NULL), `rw_A` (with
   `pcm_sha256` of the whole-side render) and `rw_B`, as in #105 ADAPTER.md.

**Emit:**
- the case identity fields;
- `first_durable_sha256`: the `dupmodel.TRACKED` digest after the first run;
- `fired`;
- `trace_sha256`: the re-run's write/flush callbacks up to and including the injected one, in #105's trace
  format;
- `durable_sha256`;
- `source_sha256_before` and `source_sha256_after`;
- the three mounts: `{result, repair_events, info?, pcm_sha256?}`.

## Replay

```sh
replay.py --adapter-kind product --adapter-source-sha SHA --product-commit SHA --product-tree SHA
```

The replay manifest counts the PM finding cells (V-R54-03, `COVERAGE.md`). A passing replay still needs
independent disposition.
