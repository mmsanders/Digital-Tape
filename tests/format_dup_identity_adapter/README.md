# R29 format/duplicate product binding

Software-owned mechanical binding for the verifier-owned
`tests/format_dup_identity_draft8/` tree.

The binding authenticates exact tree
`f76ab23d17beb9212f8ee1d17d3d1875b74abc7d`, executes the real public C API,
models only raw block-device durability/injection, and emits raw bytes/public call
facts. It does not import or call the verifier oracle.

The C worker receives the exact raw destination bytes produced by the verifier
fixture module. Its dual working/durable sparse block images implement
`flush_required` and `write_through`; the Python streaming adapter supplies only
the verifier protocol and raw observations.

If a canonical case fails, the verifier runner retains
`failure-reproducer.json`. Per #226, Software classifies that first failure before
any engine change and does not skip ahead to later cases.

## Contract families

The 43 contract cases run in the same worker (`K` command). Each observation is
raw: public call results, the chronological block-callback trace of every
device, and the operation counters ADAPTER.md names. `progress_blocks` is the
last `blocks_done` the engine delivered to the progress callback;
`destination_event_count` and `chunk_write_lbas` come from the destination
trace; `operation_token` is a non-causal adapter label.

Setup facts that are Software's, not the verifier's: the source cartridge is a
10 s Side-A mount of 100 non-silent frames (a second, 131,073-frame source exists
only for the `dup_capacity` refusal); rows start from Mounted, idle except the
render column, which needs a Playing source; the destination-failure case fails
the destination's first chunk-region write (ordinal 6); the faulted source is
reached publicly through a `tape_reset_side_b` whose own write fails.

**White-box observation, flagged for Verification.** No public call exposes the
source's `rate_q16_16`, transport row, play-window indices or fault flag, which
the destination-failure and faulted-source families ask for. The worker reads
them from the instance via `engine/src/tape_internal.h`, read-only, and emits
the raw fields (`raw_instance`) beside the derived row name. Position comes from
public `tape_tell`; ring bytes are hashed from the caller-owned `play_ring`.

