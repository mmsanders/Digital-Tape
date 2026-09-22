# Product adapter for `transport_draft8`

Software-owned mechanical binding for the independently published
`tests/transport_draft8` package. The verifier tree is not modified.

The probe accepts exactly the verifier contract:

```sh
wp_transport_probe CASE_ID INPUT.vo08 OUTPUT.vo08
```

It drives only public `tape.h` APIs, records every block callback with the active
public-call phase, records the actual warm descriptor supplied to `tape_mount`,
and emits `WP-TRANSPORT-OBSERVATION-1` JSON. The compact VO08 envelope carries
superblocks and index slots; unspecified chunk reads return deterministic poison
bytes because this tranche asserts transport state and metadata, not PCM identity.

Run against the product engine:

```sh
make -C engine all
make -C tests/transport_adapter all
python3 tests/transport_adapter/run_product.py \\
  --evidence tests/transport_adapter/evidence/p1-r25-product
```

A green product run is observation only. Independent Verification owns the
blind disposition. This tranche does not claim listened/sample identity,
broader playback/rate goldens, crash behavior, or long-operation state.
