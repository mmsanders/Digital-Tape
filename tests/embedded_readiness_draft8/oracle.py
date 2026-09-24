#!/usr/bin/env python3
"""Independent DRAFT-8 WP-13 embedded-readiness oracle."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

EVIDENCE_FORMAT = "WP13-EMBEDDED-EVIDENCE-1"
RAM_LIMIT = 200 * 1024
RODATA_LIMIT = 32 * 1024
STACK_LIMIT = 8 * 1024
REQUIRED_TOOLS = ("cc", "nm", "readelf", "size")
ALLOWED_CALLBACK_WRAPPERS = {
    ("dev_read", "read", "engine/src/dev.h"),
    ("dev_write", "write", "engine/src/dev.h"),
    ("dev_flush", "flush", "engine/src/dev.h"),
}

@dataclass(frozen=True)
class Gate:
    id: str
    name: str
    passed: bool
    measured: Any
    limit: Any
    errors: tuple[str, ...]

def _int(v: Any, name: str, errors: list[str]) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        errors.append(f"{name} must be a non-negative integer")
        return 0
    return v

def _dict(v: Any, name: str, errors: list[str]) -> dict:
    if not isinstance(v, dict):
        errors.append(f"{name} must be an object")
        return {}
    return v

def _list(v: Any, name: str, errors: list[str]) -> list:
    if not isinstance(v, list):
        errors.append(f"{name} must be an array")
        return []
    return v

def evaluate(e: dict) -> dict:
    schema: list[str] = []
    if not isinstance(e, dict):
        return {"format":"WP13-EMBEDDED-RESULT-1","overall_pass":False,
                "schema_errors":["evidence must be an object"],"gates":[]}
    if e.get("format") != EVIDENCE_FORMAT:
        schema.append("wrong or missing evidence format")

    provenance = _dict(e.get("provenance"), "provenance", schema)
    for key in ("product_commit", "product_tree", "verifier_tree"):
        val = provenance.get(key)
        if not isinstance(val, str) or not val:
            schema.append(f"missing provenance.{key}")
    tools = _dict(provenance.get("tool_versions"), "provenance.tool_versions", schema)
    for tool in REQUIRED_TOOLS:
        if not isinstance(tools.get(tool), str) or not tools.get(tool):
            schema.append(f"missing tool version: {tool}")

    gates: list[Gate] = []

    er: list[str] = []
    ram = _dict(e.get("ram"), "ram", er)
    data = _int(ram.get("data_bytes"), "ram.data_bytes", er)
    bss = _int(ram.get("bss_bytes"), "ram.bss_bytes", er)
    inst = _int(ram.get("tape_instance_size_bytes"), "ram.tape_instance_size_bytes", er)
    total = data + bss + inst
    reported = ram.get("summed_bytes")
    if reported is not None and reported != total:
        er.append(f"ram.summed_bytes mismatch: reported {reported!r}, recomputed {total}")
    gates.append(Gate("WP13-G1","RAM sum", not er and total <= RAM_LIMIT,
                      {"data_bytes":data,"bss_bytes":bss,"tape_instance_size_bytes":inst,
                       "summed_bytes":total}, RAM_LIMIT, tuple(er)))

    er = []
    rom = _dict(e.get("rodata"), "rodata", er)
    ro = _int(rom.get("rodata_bytes"), "rodata.rodata_bytes", er)
    gates.append(Gate("WP13-G2",".rodata", not er and ro <= RODATA_LIMIT,
                      {"rodata_bytes":ro}, RODATA_LIMIT, tuple(er)))

    er = []
    alloc = _dict(e.get("allocator"), "allocator", er)
    if alloc.get("scan_complete") is not True:
        er.append("allocator symbol scan incomplete")
    refs = _list(alloc.get("forbidden_references"), "allocator.forbidden_references", er)
    gates.append(Gate("WP13-G3","Allocator symbols", not er and len(refs) == 0,
                      {"forbidden_references":refs}, "none", tuple(er)))

    er = []
    st = _dict(e.get("stack"), "stack", er)
    if st.get("analysis_complete") is not True:
        er.append("stack call-graph analysis incomplete")
    max_stack = _int(st.get("max_path_bytes"), "stack.max_path_bytes", er)
    for field in ("dynamic_or_unknown_frames","unresolved_internal_edges","recursive_cycles"):
        vals = _list(st.get(field), f"stack.{field}", er)
        if vals:
            er.append(f"stack.{field} is non-empty")
    excluded = _list(st.get("excluded_external_callback_edges"),
                     "stack.excluded_external_callback_edges", er)
    for row in excluded:
        if not isinstance(row, dict) or row.get("wrapper") not in {"dev_read","dev_write","dev_flush"}:
            er.append("stack excluded external edge is not one of the three dev_* callback funnels")
            break
    gates.append(Gate("WP13-G4","Maximum engine stack", not er and max_stack <= STACK_LIMIT,
                      {"max_path_bytes":max_stack,"max_path":st.get("max_path",[])},
                      STACK_LIMIT, tuple(er)))

    er = []
    ind = _dict(e.get("indirect_calls"), "indirect_calls", er)
    if ind.get("analysis_complete") is not True:
        er.append("indirect-call analysis incomplete")
    violations = _list(ind.get("violations"), "indirect_calls.violations", er)
    ambiguous = _list(ind.get("ambiguous_or_unresolved"),
                      "indirect_calls.ambiguous_or_unresolved", er)
    sites = _list(ind.get("permitted_callback_sites"),
                  "indirect_calls.permitted_callback_sites", er)
    normalized = set()
    for row in sites:
        if not isinstance(row, dict):
            er.append("malformed permitted callback site")
            continue
        normalized.add((row.get("wrapper"), row.get("member"), row.get("path")))
    if normalized != ALLOWED_CALLBACK_WRAPPERS:
        er.append("permitted callback sites are not exactly the three dev_* funnels in engine/src/dev.h")
    if violations:
        er.append("forbidden indirect call site(s) present")
    if ambiguous:
        er.append("ambiguous/unresolved call expression(s) present")
    gates.append(Gate("WP13-G5","Indirect-call confinement", not er,
                      {"permitted_callback_sites":sites,"violations":violations,
                       "ambiguous_or_unresolved":ambiguous},
                      "only three dev_* callback funnels", tuple(er)))

    er = []
    state = _dict(e.get("engine_state"), "engine_state", er)
    if state.get("symbol_scan_complete") is not True:
        er.append("engine mutable-symbol scan incomplete")
    mutable = _list(state.get("mutable_symbols"), "engine_state.mutable_symbols", er)
    common = _list(state.get("common_symbols"), "engine_state.common_symbols", er)
    if mutable:
        er.append("engine-owned mutable OBJECT/TLS symbol(s) present")
    if common:
        er.append("COMMON symbol(s) present")
    ro_count = _int(state.get("read_only_object_symbol_count"),
                    "engine_state.read_only_object_symbol_count", er)
    gates.append(Gate("WP13-G6","Caller-owned mutable state", not er,
                      {"mutable_symbols":mutable,"common_symbols":common,
                       "read_only_object_symbol_count":ro_count},
                      "no mutable engine-owned symbols", tuple(er)))

    gd = [asdict(g) for g in gates]
    return {
        "format":"WP13-EMBEDDED-RESULT-1",
        "overall_pass": not schema and all(g.passed for g in gates),
        "schema_errors": schema,
        "tape_instance_size_bytes": inst,
        "gates": gd,
    }
