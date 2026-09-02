# tools/

Repository tooling. See `docs/DECISIONS.md` ADR-005 for why it lives outside the Charter §03 tree.

## `tools/ci/`

Every gate is a standalone script that runs locally exactly as it runs in CI.

```
./tools/ci/all.sh          # every gate, reporting all of them
```

| Gate | Enforces |
|---|---|
| `build.sh` | Engine, ports and harness compile clean at `-Werror`, C99 |
| `audit-allocation.sh` | Guardrail 08 — no malloc family, no libc file I/O, by undefined-symbol reference. **Engine archive only** |
| `audit-indirect.sh` | Guardrail 09 — all `tape_dev` access funnels through `engine/src/dev.h`, plus a link-time backstop against function pointers in data sections |
| `audit-stack.py` | Guardrail 08 — max stack depth ≤ 8 KiB from GCC's own `-fstack-usage`/`-fcallgraph-info`. **Subsumes the recursion check**: a cycle makes depth unbounded |
| `audit-memory.sh` | Guardrail 08 — RAM ≤ 200 KiB, `.rodata` ≤ 32 KiB. Both print every run |
| `verify-gates.sh` | **The meta-gate.** Plants a real violation for each gate above, asserts it goes red, removes it, asserts it goes green. A gate that has never failed has not been tested |
| `unit.sh` | Software Lead scaffolding self-tests plus the Verification Lead's crash infrastructure. **Not acceptance** |
| `run-golden.sh` | Contract 3 — the golden suite. Delegates to `tests/harness/run-golden.sh`: manifest-driven, byte-exact comparison, audible diff on failure. Fixtures and manifest are the Verification Lead's |

### Two archives, and why the gates scope to one

`libtape.a` is `engine/src` — the engine proper, subject to every gate.
`libtape_port.a` is `engine/port` — block-device shims, subject to none of them.

The file-backed port *is* libc file I/O, which guardrail 08 forbids in the engine. That is the
whole point of the block-device boundary: the engine never learns a file exists. If a gate ever
runs over the port archive it will fail, and the fix is the gate, not the port.

### Why these gates and not the previous ones

Issues #11 and #12 retired the old allocation/recursion audits, which parsed disassembly with
regular expressions. Two things were wrong with that, and both were found by reviewing my own
scaffold rather than by it failing:

- **The invariant was not the one written down.** "At most two indirect call sites" is not
  guardrail 09. *Every indirect call targets a `tape_dev` callback* is — and no regex over
  disassembly can decide it. It is now decidable by construction: three wrappers, one file, a
  source-level gate that fails with a filename and a line number.
- **"No recursion" was a proxy.** The requirement is a bounded stack. Measuring depth directly
  gives a number worth reading in review, and recursion falls out for free.

### Verified in both directions, now automatically

`verify-gates.sh` does this in CI rather than by hand each round. 11/11 checks: each gate goes
red on a real violation and green without it. Confirmed catches: a direct `d->read()`
call in `engine/src`; a static function-pointer table in `.data.rel.ro`; mutual recursion
(including the tail-call form the optimiser emits as `jmp`); a 12 KB call chain; a 300 KB
`.bss`; a 40 KB `.rodata`; `malloc` and `fopen` references. VLAs are rejected at compile time by
`-Wvla` before the audit runs.

**One gate bug worth remembering.** `audit-indirect.sh` reported PASS while the engine called a
callback directly: the search pattern began with `-`, grep parsed it as an option, exited 2, and
`|| true` swallowed it. A gate that cannot run must **fail**, not pass. Every search in that
script now goes through a wrapper that treats a grep exit ≥ 2 as a broken gate.

### Known limitation

The memory audit measures the archive. The authoritative number for firmware is the linked
image's map file, which also accounts for stack and for what the toolchain elided. That gate
gets added when Stream 4 links. The RAM budget will also gain the engine instance from
`tape_instance_size()` once DRAFT-3 defines it.
