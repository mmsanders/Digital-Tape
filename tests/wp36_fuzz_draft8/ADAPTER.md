# WP-36 fuzz mechanical product-adapter contract

The later Software binding must link the real public product API while preserving the
verifier-owned generator and runner unchanged.

## Source capability / assertion boundary

For every generated sequence the mounted source `tape_dev` must have **literal**:

```c
dev.write = NULL;
```

A non-NULL wrapper that counts, swallows, rejects or logs writes is nonconforming.
The exact product engine and adapter must be built with the frozen debug `dev_write`
assertion active. The adapter should fail compilation if `NDEBUG` is defined, and the
product CI binding must make the engine build mode auditable (for example a clean
`-UNDEBUG` rebuild).

The verifier treats process death, signal, assertion, timeout, malformed output or
premature EOF as failure. Because no source write callback exists, this fail-closed
process boundary is how an attempted internal `dev_write` becomes observable.

## Invocation and persistent protocol

The runner invokes:

```text
wp36_fuzz_product_adapter --fixture SOURCE.vo08
```

The adapter loads the verifier fixture and immediately emits one tab-separated line:

```text
HELLO  WP36-FUZZ-ADAPTER-1  product  NULL  debug
```

(`HELLO`, format, adapter kind, source-write binding, assertion mode; tabs between
fields.) It must flush stdout.

The runner then streams exactly 100,000 sequence lines. Wire grammar:

```text
SEQ <index> <16-hex-seed> <A|B> <op-count> <semicolon-separated operations>
```

with tab separators. Operation tokens are:

- `seek=<uint64>` → `tape_seek`
- `tell` → `tape_tell`
- `rate=<int32>` → `tape_set_rate`
- `render=<uint32>` → `tape_render`
- `service=<positive-uint32>` → `tape_service`
- `status` → `tape_status`
- `info` → `tape_get_info`
- `side=A|B` → `tape_set_side`

For **each** SEQ line the adapter must start a fresh engine instance against the
original verifier fixture, mount the requested side with resume frame 0 and
`warm == NULL`, execute every operation in order, then unmount. It emits and flushes:

```text
RES <format> <index> <seed> <ops-executed> <read-callbacks> <flush-callbacks>
    <event-overflow-0|1> <mount-result> <unmount-result> <OK-count>
    <UNDERRUN-count>,<OTHER-count>
```

on one tab-separated line, where `<format>` is `WP36-FUZZ-RESULT-1`.
`OK + UNDERRUN + OTHER` must equal the operation count. These generated transport
operations may return `TAPE_OK` or, for a short render, `TAPE_ERR_UNDERRUN`; OTHER
must therefore be zero. Read/flush counts are retained as compact coverage diagnostics.

After the final result the runner sends `DONE`; the adapter must exit 0.

## Completeness / anti-synthesis requirements

- Execute the verifier line exactly; do not generate a second random sequence in the adapter.
- Do not skip calls based on an expected result.
- Do not rewrite operation order or arguments.
- Reset the engine instance for every sequence so one generated sequence cannot mask another.
- Callback/event counters must fail closed on overflow.
- The adapter must not turn an engine assertion/crash into a normal result line.
- The Software wrapper must retain exact product commit/tree, verifier publication/tree,
  adapter source/binary hashes, compiler assertion mode, `summary.json`, and any failure
  reproducer emitted by the verifier runner.

No huge raw 100,000-sequence log is required or desired; `summary.json` plus the fixed
RNG/seed/plan digest and any exact failure reproducer are the evidence contract.
