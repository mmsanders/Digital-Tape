# engine/ — Stream 1

Portable C99. No operating system beneath it, no hardware above it. Roughly 60% of the
software in this project, and it runs on a laptop with nothing attached.

**Packages:** WP-06, 07, 08, 09, 12, 13, 36
**Depends on:** `spec/tapefs-v1.md` and `spec/engine-api.md`, both frozen at the Phase 0 gate
**Blocks:** Streams 3, 4 and 5 entirely

**Done when** every call in the API spec is implemented, the golden suite passes, and the
static memory audit holds under 200 KB with zero post-init allocation.

## Rejected on sight

- Any dependency beyond libc
- Any `#ifdef` naming a board, chip or peripheral
- Any API that returns a heap pointer
- Any code path that writes to a side bound read-only

## Layout

| Path | |
|---|---|
| `include/tape.h` | The public API. The only header a consumer includes |
| `src/` | Implementation |
| `port/` | Block-device shims: `file`, `sim` (deliberately flaky), `sd` |

`port/` is the only place that knows a block device can be anything other than two function
pointers. Nothing in `src/` may reference a port.
