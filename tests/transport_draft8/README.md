# Transport extras — set_side transitions + warm-start validation

Independent DRAFT-8 verifier package authored from Engine API §5, §6 and §10
plus the WP-08 / WP-11 acceptance criteria. No product implementation is
inspected.

This branch is **not product acceptance** and is not a listened golden.

## set_side coverage

The package contains both transition paths explicitly required by WP-08:

- `SS-PLAYING-A-TO-B`: establish genuine Playing state and
  `at_end=true` on non-empty Side A, switch to shorter Side B while the
  +1.0x rate remains active, prove position/flags/info reset, prove the old
  ring cannot render before service, then prove one serviced/rendered frame
  advances tell to exactly 1.
- `SS-IDLE-A-TO-B`: switch while stopped, set +1.0x **after** the switch,
  then make the same pre-service underrun and post-service advancement checks.

Additional state-matrix rows cover successful same-side A, degraded-B refusal
and its same-A exception, and armed BUSY with state preservation.

## Warm-start coverage

Warm descriptors are not represented merely by a case name. The adapter records
the descriptor arguments actually passed to `tape_mount`, and the oracle
checks them against the case.

Negative rows cover, in the frozen algorithm's order:

1. `warm == NULL`;
2. `data == NULL`;
3. zero valid frames;
4. one-byte-short data buffer;
5. an ordinary past-end range;
6. the mandatory near-`UINT32_MAX` checked-64-bit overflow regression;
7. resume outside the valid range;
8. UUID-only mismatch; and
9. side-only mismatch.

A tenth row supplies fully valid metadata and requires
`warm_start_used=true`. This is deliberately **not** a listened/sample-identity
claim; it anchors the negatives by proving that the engine can reach the
algorithm's `use` branch.

## Synthetic self-test

```sh
python3 tests/transport_draft8/selftest.py
```

The mutation suite catches stale-ring playback, uncleared endpoint state,
changed/zeroed Playing rate, old-side metadata, degraded/armed refusal state
changes, collapsed warm-descriptor shapes, incorrect predicate ordering, an
implementation that always ignores warm buffers, render block I/O, and terminal
unmount failure.

The synthetic adapter also refuses an `INPUT.vo08` that is not byte-identical
to the verifier's case fixture.

Real product observations remain the next integration step. Warm-buffer sample
identity still belongs to the WP-11 listened golden suite.
