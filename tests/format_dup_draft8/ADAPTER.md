# Mechanical adapter contract

The verifier invokes one case at a time:

`wp_fmt_dup_probe CASE_ID INPUT.vo08 OUTPUT.vo08`

`CASE_ID` is one of the 17 rows in `README.md`. `INPUT.vo08` is the verifier
fixture. For duplicate cases, use that fixture as the mounted source and
initialize the destination backing bytes byte-identically unless the case is
`DUP-ALIAS`, where source and destination must be the same device. The
case-specific `dest_blocks`, `dst_nominal_length_s`, writability and alias
conditions come from the case ID/oracle; advertised `tape_dev.block_count` may
therefore differ from the fixture backing extent encoded in `INPUT.vo08`.

`OUTPUT.vo08` is the tracked write-target image after the tested call:
destination for format/duplicate, mounted cartridge for promote. Every row in
this tranche is a zero-write outcome, so it must be byte-identical to the input
fixture. Any write to either source or destination must also appear in `events`
and will fail the oracle.

Stdout must contain exactly one JSON object:

```json
{
  "format": "WP-FMTDUP-OBSERVATION-1",
  "case_id": "DUP-TOO-SMALL",
  "adapter_kind": "product",
  "adapter_id": "stable-product-adapter-id",
  "calls": [],
  "events": []
}
```

`calls` records public API calls and results. `events` is the complete,
chronological block-device callback trace **from the operation under test only**;
setup/teardown mount callbacks are excluded. Each callback event uses
`op = read|write|flush` and `device = source|destination`; reads/writes include
`lba` and `count`. Do not filter callbacks merely because they appear harmless.

Scripts:

- Format rows call `tape_format` once against the named raw destination
  constraints.
- Duplicate rows mount the source on Side A, clear the callback trace, call
  `tape_dup` once with a positive budget, record the refusal and
  `more_work`, then unmount. The destination is a raw `tape_dev`, not a
  second mount.
- `PROMOTE-EMPTY` mounts Side B, clears the callback trace, calls
  `tape_promote` once with a positive budget, and records
  `TAPE_ERR_INVALID_ARG` with `more_work=false`.

Ordering cases deliberately combine failures. Do not simplify their device
configuration: they exist to prove the normative error precedence.

The exact geometry rows `*-GEOM-0`, `*-GEOM-1`, and `*-GEOM-BASE` must have an
empty `events` array. Other refusals are **not** globally required to have zero
callbacks, but all rows prohibit writes and format/duplicate rows prohibit
destination-superblock classification reads before the refusal.

`adapter_kind=synthetic` is reserved for verifier self-check plumbing. Product
evidence must identify as `product`. Do not change fixtures, event filtering or
expected results to fit a product build.
