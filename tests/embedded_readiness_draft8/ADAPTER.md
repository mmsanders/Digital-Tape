# WP-13 embedded-readiness product binding contract

This package was authored from frozen DRAFT-8 public requirements before inspecting
the product engine implementation. A later Software round may mechanically bind an
exact product candidate to this package; Software must not alter verifier-owned files.

## Evidence interface

The product binding supplies one UTF-8 JSON object to `runner.py --evidence` with
format `WP13-EMBEDDED-EVIDENCE-1`. The verifier computes all PASS/FAIL decisions;
the adapter must not supply authoritative verdict fields.

Retain alongside the JSON:
- exact product commit/tree and imported verifier tree;
- complete build command log;
- raw section/symbol reports;
- every compiler stack-usage and call-graph file used;
- complete engine source-file hash manifest used for the indirect-call audit;
- exact tool version output.

The JSON `provenance.tool_versions` must at minimum contain non-empty `cc`,
`nm`, `readelf`, and `size` strings. Any additional scanner used for indirect
calls must also be identified in retained provenance.

## Build comparability

Resource and stack measurements must come from an audit build of the exact product
engine bytes using the product configuration and optimization/macros. The binding may
add only instrumentation/metadata flags required to emit stack/call-graph evidence
(for GCC, `-fstack-usage -fcallgraph-info=su,da`). If this cannot be done without
changing code-generation-relevant options, report the discrepancy and fail closed.

LTO or another mode that prevents complete per-function/object attribution may not be
silently disabled and treated as equivalent. Either produce a complete equivalent
analysis or mark the relevant analysis incomplete.

## WP13-G1 — RAM sum

Report:
- `ram.data_bytes`
- `ram.bss_bytes`
- `ram.tape_instance_size_bytes`
- `ram.summed_bytes`

The verifier recomputes the sum and requires:

`.data + .bss + tape_instance_size() <= 204800`

The measured instance size must come from compiling and linking the verifier-owned
`instance_size_probe.c` against the exact product public header/library and running
that probe. Do not substitute a constant or parse an implementation header.

For object/ELF classification, retain a per-object section census. Treat compiler
small-data aliases as their canonical classes rather than a naming loophole:
- data class: `.data`, `.data.*`, `.sdata`, `.sdata.*`;
- bss class: `.bss`, `.bss.*`, `.sbss`, `.sbss.*`.

COMMON storage is separately forbidden by G6 and must not be omitted from evidence.

## WP13-G2 — read-only data

Report `rodata.rodata_bytes`, with a retained per-object section census.

Count read-only data families emitted for constants/tables:
- `.rodata`, `.rodata.*`;
- `.srodata`, `.srodata.*`;
- `.data.rel.ro`, `.data.rel.ro.*` when the toolchain emits relocation-backed
  objects that are read-only after relocation.

The required limit is 32768 bytes. If the target toolchain uses an equivalent
read-only data section under a different name, the binding must identify and include
it rather than excluding it for lack of the literal string `.rodata`.

## WP13-G3 — allocator symbols

Set `allocator.scan_complete=true` only after inspecting the complete undefined
symbol set of every engine object/archive member. Retain raw `nm -u` (or equivalent)
output and the tool version.

`allocator.forbidden_references` contains every reference to an allocator/free
symbol, including at least:
`malloc`, `calloc`, `realloc`, `free`, `aligned_alloc`,
`posix_memalign`, `memalign`, `valloc`, `pvalloc`, `strdup`, `strndup`.

The list must be empty.

## WP13-G4 — maximum engine stack

The binding must build a complete function-level engine call graph and combine it
with compiler-emitted per-function stack usage.

Report:
- `stack.analysis_complete`;
- `stack.max_path_bytes`;
- `stack.max_path`;
- `stack.dynamic_or_unknown_frames`;
- `stack.unresolved_internal_edges`;
- `stack.recursive_cycles`;
- `stack.excluded_external_callback_edges`.

A frame with a compiler-proven finite upper bound may participate using that bound.
An unbounded/dynamic-unknown frame goes in `dynamic_or_unknown_frames` and fails.
Every internal direct edge must resolve. Recursion/cycles fail. Any ambiguous or
unresolved internal edge fails rather than being omitted.

External callback edges may terminate the *engine* stack path only when they leave
through one of the three frozen callback funnels `dev_read`, `dev_write`,
`dev_flush`; report those edges explicitly. No other unknown/indirect edge can be
excluded from the bound.

The maximum complete engine path must be <= 8192 bytes.

## WP13-G5 — indirect-call confinement

This is a complete-source/call-graph classification, not a grep for one known defect.
The source inventory must include every engine `.c` and `.h` file with hashes.

Report:
- `indirect_calls.analysis_complete`;
- `indirect_calls.permitted_callback_sites`;
- `indirect_calls.violations`;
- `indirect_calls.ambiguous_or_unresolved`.

The permitted set must be exactly:
- `dev_read` calling member `read` in `engine/src/dev.h`;
- `dev_write` calling member `write` in `engine/src/dev.h`;
- `dev_flush` calling member `flush` in `engine/src/dev.h`.

The frozen `tape_dup` device-identity comparison is not an indirect call and grants
no extra call-site exception. Any other indirect call, or any call expression the
scanner cannot classify, makes the gate red.

## WP13-G6 — no engine-owned mutable state

This gate is independent of the numeric RAM budget. A four-byte hidden static is a
failure even though it fits under 200 KiB.

Inspect the symbol table and section flags of **every engine object/archive member**.
Retain raw `readelf -SW` and `readelf -sW` (or equivalent) output.

Populate `engine_state.mutable_symbols` with every engine-defined symbol of type
OBJECT or TLS that resides in an allocated writable section, including local
file/function statics. Populate `engine_state.common_symbols` with every COMMON
symbol. Set `symbol_scan_complete=true` only if all members were classified.

Read-only OBJECT symbols in non-writable sections are allowed and counted in
`read_only_object_symbol_count`; constants/read-only tables are not engine-owned
mutable state.

Both mutable/common lists must be empty.

## Required later Software behavior

Software may add only mechanical build/collection glue around this verifier package.
It must retain raw evidence and produce the normalized JSON above. It must not:
- edit the six thresholds or classifications;
- drop objects/functions/sources from a scan;
- replace the verifier-owned instance-size probe;
- mark an incomplete graph/scan complete;
- whitelist an additional indirect-call site;
- suppress a mutable symbol or allocator reference.

A green product run is evidence, not self-acceptance. Independent Verification must
audit the exact binding/raw evidence before WP-13 product acceptance.
