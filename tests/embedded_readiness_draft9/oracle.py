#!/usr/bin/env python3
"""Independent DRAFT-9 WP-13 embedded-readiness oracle."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
import re

EVIDENCE_FORMAT = "WP13-EMBEDDED-EVIDENCE-1"
RAM_LIMIT = 200 * 1024
RODATA_LIMIT = 32 * 1024
STACK_LIMIT = 8 * 1024
REQUIRED_TOOLS = ("cc", "nm", "readelf", "size")
SPEC_BUNDLE = "DRAFT-9"
SPEC_HASHES = {
    "spec/tapefs-v1.md": "3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d",
    "spec/engine-api.md": "383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6",
    "spec/acceptance.md": "ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d",
}
ALLOWED_CALLBACK_WRAPPERS = {
    ("dev_read", "tape_dev.read", "engine/src/dev.h", None),
    ("dev_write", "tape_dev.write", "engine/src/dev.h", None),
    ("dev_flush", "tape_dev.flush", "engine/src/dev.h", None),
    ("dev_progress", "tape_progress_fn", "engine/src/dev.h", "tape_progress_fn"),
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
    if provenance.get("spec_bundle") != SPEC_BUNDLE:
        schema.append(f"provenance.spec_bundle must be {SPEC_BUNDLE}")
    if provenance.get("spec_hashes") != SPEC_HASHES:
        schema.append("provenance.spec_hashes do not match the embedded DRAFT-9 bundle")
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
        if not isinstance(row, dict) or row.get("wrapper") not in {
                "dev_read", "dev_write", "dev_flush", "dev_progress"}:
            er.append("stack excluded external edge is not one of the four named callback funnels")
            break
    gates.append(Gate("WP13-G4","Maximum engine stack", not er and max_stack <= STACK_LIMIT,
                      {"max_path_bytes":max_stack,"max_path":st.get("max_path",[])},
                      STACK_LIMIT, tuple(er)))

    er = []
    ind = _dict(e.get("indirect_calls"), "indirect_calls", er)
    if ind.get("analysis_complete") is not True:
        er.append("indirect-call analysis incomplete")
    if ind.get("source_inventory_complete") is not True:
        er.append("engine source inventory incomplete")
    inventory = _list(ind.get("source_inventory"), "indirect_calls.source_inventory", er)
    if not inventory:
        er.append("engine source inventory is empty")
    seen_paths = set()
    for row in inventory:
        if not isinstance(row, dict):
            er.append("malformed engine source inventory row")
            continue
        path, digest = row.get("path"), row.get("sha256")
        if (not isinstance(path, str) or not path.startswith("engine/") or
                not path.endswith((".c", ".h")) or path in seen_paths or
                not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            er.append("invalid or duplicate engine source inventory row")
        seen_paths.add(path)
    if ind.get("call_expression_inventory_complete") is not True:
        er.append("call-expression inventory incomplete")
    calls = _list(ind.get("call_expression_inventory"),
                  "indirect_calls.call_expression_inventory", er)
    if not calls:
        er.append("call-expression inventory is empty")
    classified_permitted = set()
    for row in calls:
        if not isinstance(row, dict):
            er.append("malformed call-expression inventory row")
            continue
        if (not isinstance(row.get("path"), str) or
                not isinstance(row.get("line"), int) or row.get("line") < 1 or
                not isinstance(row.get("expression"), str) or not row.get("expression")):
            er.append("incomplete call-expression inventory row")
        cls = row.get("classification")
        if cls not in {"direct", "permitted_indirect", "forbidden_indirect", "ambiguous"}:
            er.append("unknown call-expression classification")
        if cls == "permitted_indirect":
            classified_permitted.add((row.get("wrapper"), row.get("target"),
                                      row.get("path"), row.get("callback_type")))
        elif cls in {"forbidden_indirect", "ambiguous"}:
            er.append(f"{cls} call expression present")
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
        normalized.add((row.get("wrapper"), row.get("target"), row.get("path"),
                        row.get("callback_type")))
    if normalized != ALLOWED_CALLBACK_WRAPPERS:
        er.append("permitted callback sites are not exactly the four named funnels in engine/src/dev.h")
    if classified_permitted != ALLOWED_CALLBACK_WRAPPERS:
        er.append("call-expression inventory does not contain exactly the four named permitted funnels")
    if violations:
        er.append("forbidden indirect call site(s) present")
    if ambiguous:
        er.append("ambiguous/unresolved call expression(s) present")
    gates.append(Gate("WP13-G5","Indirect-call confinement", not er,
                      {"source_inventory_count":len(inventory),
                       "call_expression_inventory_count":len(calls),
                       "permitted_callback_sites":sites,"violations":violations,
                       "ambiguous_or_unresolved":ambiguous},
                      "only four named callback funnels in engine/src/dev.h", tuple(er)))

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
