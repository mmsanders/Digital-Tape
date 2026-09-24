# WP-13 embedded-readiness coverage matrix

| Gate | Frozen criterion | Independent evidence / oracle | Negative control |
|---|---|---|---|
| WP13-G1 | `.data + .bss + tape_instance_size() <= 200 KiB` | Per-object data/bss census plus verifier-owned runtime instance-size probe; oracle recomputes the sum and reports the measured instance size | Sum raised above 204800 |
| WP13-G2 | `.rodata <= 32 KiB` | Per-object read-only-data census with compiler aliases retained | Read-only data raised to 32769 |
| WP13-G3 | No allocator symbol links | Complete undefined-symbol inventory; explicit forbidden-reference list must be empty | Synthetic `malloc` reference |
| WP13-G4 | Stack <= 8 KiB by call-graph analysis | Compiler frame sizes + complete internal call graph; unresolved internal edge, unknown frame or recursion fails closed | 8193-byte path and unresolved-edge controls |
| WP13-G5 | No indirect call outside `dev.h` | Complete source/call-expression classification; exactly three permitted `dev_read/dev_write/dev_flush` callback sites | Extra indirect call and missing-funnel controls |
| WP13-G6 | No engine-owned state outside caller `mem` | Every engine object symbol classified by type + ELF section writability; mutable OBJECT/TLS and COMMON lists must be empty | Four-byte synthetic hidden `.bss` static |

## Evidence separation

The six rows remain individually legible in `WP13-EMBEDDED-RESULT-1`.
A package result contains:
- one PASS/FAIL record per gate;
- measured value/limit;
- gate-local errors;
- separate schema/provenance errors;
- top-level `tape_instance_size_bytes`.

No product adapter PASS field is authoritative.

## Fail-closed boundaries

The following are evidence failures rather than grounds to infer a pass:
- missing tool provenance;
- missing engine object/source inventory;
- incomplete allocator/symbol scan;
- incomplete stack graph;
- unbounded/unknown stack frame;
- unresolved internal call edge;
- recursive call-graph cycle;
- ambiguous indirect call expression;
- an indirect-call whitelist other than the exact three frozen `dev_*` funnels;
- COMMON or mutable engine-owned symbol storage.

## Explicit exclusions

This package does not accept or test:
- runtime functional behavior;
- PCM/audio/goldens/listening;
- WP-07 allocator ownership/edit fuzz semantics (distinct from allocator *symbol* absence);
- WP-10 crash/durability behavior;
- WP-12/WP-12a operation semantics;
- firmware/hardware measurements;
- wall-time/throughput performance beyond the six frozen resource/structure gates;
- any work package other than WP-13.

A later exact product binding that passes all six rows still requires independent
Verification disposition before complete WP-13 product acceptance.
