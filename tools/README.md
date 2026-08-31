# tools/

Repository tooling. Not a stream, and not in the Charter §03 tree — see
`docs/DECISIONS.md` ADR-005 for why it exists here and what it would cost to move.

## `tools/ci/`

Every gate is a standalone script that runs locally exactly as it runs in CI. No gate
depends on GitHub Actions, so "works on my machine" and "works in CI" are the same claim.

```
./tools/ci/all.sh          # every gate, reporting all of them
```

| Gate | Enforces |
|---|---|
| `build.sh` | The engine compiles clean at `-Werror`, C99, no warnings |
| `audit-allocation.sh` | Guardrail 08 — no malloc family, no libc file I/O, by undefined-symbol reference |
| `audit-recursion.py` | Guardrail 08 — no recursion, by call-graph cycle detection over the archive. Also enforces the indirect-call budget of 2, which is guardrail 09's block-device pair |
| `audit-memory.sh` | Guardrail 08 — static RAM under 200 KB, plus a `-fno-common` regression check |
| `run-golden.sh` | Contract 3 — the golden suite. Wiring only; `tests/` belongs to the Verification Lead |

### These gates are expected to fail at Phase 0

That is the WP-04 acceptance criterion. **Do not relax a gate to make CI green.** The engine
is empty and there are no fixtures; the gates go green when WP-06 and WP-10 land.

### They have been verified in both directions

Each audit was checked against deliberately violating code as well as clean code — a gate
that only ever fails on emptiness proves nothing. Verified catches: `malloc`/`fopen`
references, direct and mutual recursion (including the tail-call form the optimiser emits as
`jmp`), a 300 KB `.bss`, and a third indirect call site.

### Known limitation

The memory audit measures the archive. The authoritative number for firmware is the linked
image's map file, which also accounts for stack and for what the toolchain elided. That gate
gets added when Stream 4 links.
