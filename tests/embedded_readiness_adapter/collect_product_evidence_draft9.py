#!/usr/bin/env python3
"""DRAFT-9 WP-13 product evidence collector for tests/embedded_readiness_draft9.

Software-owned plumbing only. It builds the unmodified engine, measures it,
and hands normalized WP13-EMBEDDED-EVIDENCE-1 to the unchanged verifier-owned
runner, which alone decides the six gates.

Everything except the indirect-call analysis and provenance is the DRAFT-8
collector's code, imported unchanged: collect_product_evidence.py stays byte-
identical because it is the binding behind the accepted DRAFT-8 evidence.

G5 (indirect-call confinement) is rebuilt for the DRAFT-9 interface. Every
syntactic call expression in the engine comes from clang's own AST
(-ast-dump=json), not from pattern matching, so the call-expression inventory
is complete by construction. Each call is classified by what its callee
resolves to:

  direct              callee is a named function (including builtins)
  permitted_indirect  one of the four named funnels in engine/src/dev.h:
                      dev_read/dev_write/dev_flush -> tape_dev.read/write/flush,
                      dev_progress -> the caller-supplied tape_progress_fn
  forbidden_indirect  any other call through a pointer or member
  ambiguous           a callee shape this classifier does not recognise

The DRAFT-8 relocation backstop (an engine function address stored in a data
section) still reports into violations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect_product_evidence as d8  # noqa: E402  (unchanged DRAFT-8 collector)

ROOT = d8.ROOT
ENGINE = d8.ENGINE
PKG = ROOT / "tests" / "embedded_readiness_draft9"
VERIFIER_TREE = "8e5d0853755e54032b7d5304caf1190a03376393"
VERIFIER_PUBLICATION = "74a2f96d5fa50972f2a20bc391fc6bd363554cb1"
IMPORT_COMMIT = "69496d184761a1b66d3d921e420f9725bdc6c5d1"
PRODUCT_BASE = "7910ae3701fbfd94b5ea0558a69a29955da1dd5c"
SPEC_BUNDLE = "DRAFT-9"
SPEC_FILES = ("spec/tapefs-v1.md", "spec/engine-api.md", "spec/acceptance.md")
DEV_H = "engine/src/dev.h"
DEVICE_FUNNELS = {"dev_read": "read", "dev_write": "write", "dev_flush": "flush"}
PROGRESS_FUNNEL = "dev_progress"
PROGRESS_TYPE = "tape_progress_fn"

Fail = d8.Fail


def spec_identity():
    """The canonical spec/ bytes this product is built against."""
    ver = (ROOT / "spec" / "VERSION.md").read_text(encoding="utf-8")
    if f"**Bundle:** {SPEC_BUNDLE}" not in ver:
        raise Fail(f"spec/VERSION.md is not bundle {SPEC_BUNDLE}")
    return {p: d8.sha(ROOT / p) for p in SPEC_FILES}


def verify_provenance():
    """Declared identities are checked against history before any measurement."""
    if subprocess.run(["git", "merge-base", "--is-ancestor", IMPORT_COMMIT, "HEAD"],
                      cwd=ROOT).returncode != 0:
        raise Fail(f"verifier import {IMPORT_COMMIT} is not an ancestor of HEAD")
    if d8.git("rev-parse", f"{IMPORT_COMMIT}^") != PRODUCT_BASE:
        raise Fail(f"import parent is not the declared product base {PRODUCT_BASE}")
    if d8.git("rev-parse", f"{IMPORT_COMMIT}:tests/embedded_readiness_draft9") != VERIFIER_TREE:
        raise Fail(f"verifier import {IMPORT_COMMIT} does not carry tree {VERIFIER_TREE}")
    vt = d8.git("rev-parse", "HEAD:tests/embedded_readiness_draft9")
    if vt != VERIFIER_TREE:
        raise Fail(f"verifier tree mismatch {vt}")
    return vt


# --- clang AST call-expression inventory ------------------------------------

def _annotate_locations(node, state):
    """clang's JSON omits a location's file/line when unchanged from the previous
    printed location, in document order. Replay that order and pin every
    location to an explicit (file, line). Also records every file reached."""
    if isinstance(node, dict):
        if "offset" in node:
            if "file" in node:
                state["file"] = node["file"]
            if "line" in node:
                state["line"] = node["line"]
            node["_file"], node["_line"] = state["file"], state["line"]
            state["reached"].add(state["file"])
        for key, value in node.items():
            if key != "includedFrom":
                _annotate_locations(value, state)
    elif isinstance(node, list):
        for item in node:
            _annotate_locations(item, state)


def _loc(rng):
    """The spelling location of a range's begin: where the call is written."""
    begin = rng.get("begin", {})
    for key in ("spellingLoc", "expansionLoc"):
        sub = begin.get(key)
        if sub and sub.get("_file") and sub["_file"].startswith("engine/"):
            return sub["_file"], sub["_line"], sub.get("col")
    if begin.get("_file"):
        return begin["_file"], begin["_line"], begin.get("col")
    return None, None, None


def _strip(expr):
    while expr.get("kind") in ("ImplicitCastExpr", "ParenExpr") and expr.get("inner"):
        expr = expr["inner"][0]
    return expr


def _member_base_type(member):
    base = member.get("inner", [{}])[0]
    return base.get("type", {}).get("qualType", "")


def _classify(call, function):
    callee = _strip(call["inner"][0])
    kind = callee.get("kind")
    row = {"callee_kind": kind}
    if kind == "DeclRefExpr":
        ref = callee.get("referencedDecl", {})
        rkind, name = ref.get("kind"), ref.get("name")
        rtype = ref.get("type", {}).get("qualType", "")
        row.update(callee=name, callee_decl_kind=rkind, callee_type=rtype)
        if rkind == "FunctionDecl":
            row.update(classification="direct", target=name)
            return row
        if rkind in ("ParmVarDecl", "VarDecl"):
            if function == PROGRESS_FUNNEL and rkind == "ParmVarDecl" and rtype == PROGRESS_TYPE:
                row.update(classification="permitted_indirect", wrapper=PROGRESS_FUNNEL,
                           target=PROGRESS_TYPE, callback_type=PROGRESS_TYPE)
            else:
                row.update(classification="forbidden_indirect", target=name)
            return row
    if kind == "MemberExpr":
        member = callee.get("name")
        base_type = _member_base_type(callee)
        row.update(callee=member, member_base_type=base_type)
        wanted = DEVICE_FUNNELS.get(function)
        if wanted == member and "tape_dev" in base_type:
            row.update(classification="permitted_indirect", wrapper=function,
                       target=f"tape_dev.{member}", callback_type=None)
        else:
            row.update(classification="forbidden_indirect", target=member)
        return row
    if kind in ("UnaryOperator", "ArraySubscriptExpr", "CallExpr",
                "ConditionalOperator", "CStyleCastExpr", "BinaryOperator"):
        row.update(classification="forbidden_indirect", target=kind)
        return row
    row.update(classification="ambiguous", target=kind)
    return row


def _walk_calls(node, function, out):
    if not isinstance(node, dict):
        return
    if node.get("kind") == "FunctionDecl" and node.get("name") and node.get("inner"):
        function = node["name"]
    if node.get("kind") == "CallExpr":
        out.append((function, node))
    for child in node.get("inner", []) or []:
        _walk_calls(child, function, out)


def _parse(path, raw_dir, cc="clang"):
    cmd = [cc, "-std=c99", "-fsyntax-only", "-I", "engine/include", "-I", "engine/src"]
    if path.endswith(".h"):
        cmd += ["-x", "c"]
    cmd += ["-Xclang", "-ast-dump=json", path]
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    safe = path.replace("/", "__")
    (raw_dir / f"{safe}.clang.stderr.txt").write_text("$ " + " ".join(cmd) + "\n" + p.stderr)
    if p.returncode != 0:
        return None, p.returncode
    (raw_dir / f"{safe}.ast.sha256").write_text(hashlib.sha256(p.stdout.encode()).hexdigest() + "\n")
    return json.loads(p.stdout), 0


def indirect_draft9(raw, inventory, obj):
    ast_dir = raw / "clang-ast"
    ast_dir.mkdir()
    paths = [row["path"] for row in inventory]
    parsed = {}
    standalone_failures = []
    reached = set()
    rows = {}
    for path in paths:
        ast, rc = _parse(path, ast_dir)
        if ast is None:
            standalone_failures.append({"path": path, "clang_exit": rc})
            continue
        parsed[path] = True
        state = {"file": path, "line": 0, "reached": set()}
        _annotate_locations(ast, state)
        reached |= state["reached"]
        calls = []
        _walk_calls(ast, None, calls)
        for function, call in calls:
            file, line, col = _loc(call.get("range", {}))
            if file is None or not file.startswith("engine/"):
                continue   # system-header code, not engine source
            row = _classify(call, function)
            text = (ROOT / file).read_text(encoding="utf-8").splitlines()[line - 1].strip()
            row.update(path=file, line=line, column=col, function=function, expression=text)
            if row.get("wrapper") and file != DEV_H:
                # A permitted-looking wrapper anywhere but dev.h is not a funnel.
                row["classification"] = "forbidden_indirect"
                row.pop("wrapper")
            rows[(file, line, col, row["callee_kind"], row.get("callee"))] = row
    inventory_rows = [rows[k] for k in sorted(rows, key=lambda k: (k[0], k[1], k[2] or 0, str(k[4])))]

    permitted, violations, ambiguous = [], [], []
    for r in inventory_rows:
        if r["classification"] == "permitted_indirect":
            permitted.append({"wrapper": r["wrapper"], "target": r["target"], "path": r["path"],
                              "callback_type": r.get("callback_type")})
        elif r["classification"] == "forbidden_indirect":
            violations.append({k: r[k] for k in ("path", "line", "function", "expression", "target")})
        elif r["classification"] == "ambiguous":
            ambiguous.append({k: r[k] for k in ("path", "line", "function", "expression", "target")})
    uniq = {(p["wrapper"], p["target"], p["path"], p["callback_type"]): p for p in permitted}
    permitted = [uniq[k] for k in sorted(uniq, key=lambda k: (k[0], k[1]))]

    # DRAFT-8 backstop: an engine function address stored in a data section is a
    # dispatch table the call-expression view cannot see.
    for o in obj["objects"]:
        section = None
        for line in (raw / "objects" / f"{o.name}.objdump-r.txt").read_text().splitlines():
            m = d8.re.match(r"RELOCATION RECORDS FOR \[(.+)\]:", line)
            if m:
                section = m.group(1)
                continue
            m = d8.re.match(r"^[0-9A-Fa-f]+\s+R_\S+\s+(\S+)", line)
            if not m or not section:
                continue
            if not any(section.startswith(x) for x in (".data", ".rodata", ".sdata", ".init_array",
                                                        ".fini_array", ".ctors", ".dtors")):
                continue
            target = d8.re.sub(r"[+-]0x[0-9A-Fa-f]+$", "", m.group(1))
            if target.startswith(".text") or target in obj["defined"]:
                violations.append({"object": o.name, "section": section, "target": m.group(1),
                                   "expression": "engine function address stored in data"})

    # A header that is not self-contained (it relies on its includer, as C
    # allows) still counts as covered when a translation unit that parsed
    # reached it: its calls are in that TU's AST. Every .c must parse, and
    # every source must be covered one way or the other.
    uncovered = [f for f in standalone_failures
                 if f["path"].endswith(".c") or f["path"] not in reached]
    covered_via_includer = [f["path"] for f in standalone_failures if f not in uncovered]
    inventory_complete = not uncovered and all(p in parsed or p in reached for p in paths)
    if uncovered:
        ambiguous.append({"reason": "engine source neither parsed nor reached", "failures": uncovered})
    report = {
        "analysis_complete": inventory_complete and not ambiguous,
        "scanner": "clang -fsyntax-only -Xclang -ast-dump=json, every engine .c/.h as a translation unit",
        "headers_covered_via_includer": covered_via_includer,
        "source_inventory_complete": inventory_complete,
        "source_inventory": inventory,
        "call_expression_inventory_complete": inventory_complete,
        "call_expression_inventory": [
            {k: r.get(k) for k in ("path", "line", "column", "function", "expression", "classification",
                                   "callee_kind", "callee", "target", "wrapper", "callback_type")}
            for r in inventory_rows],
        "permitted_callback_sites": permitted,
        "violations": violations,
        "ambiguous_or_unresolved": ambiguous,
    }
    (raw / "indirect-call-scan.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, required=True)
    ns = ap.parse_args()
    ev = ns.evidence if ns.evidence.is_absolute() else ROOT / ns.evidence
    if ev.exists():
        shutil.rmtree(ev)
    raw = ev / "raw"
    raw.mkdir(parents=True)
    d8.PKG = PKG   # the verifier-owned instance-size probe comes from THIS package
    try:
        vt = verify_provenance()
        head = d8.git("rev-parse", "HEAD")
        pc = os.environ.get("PRODUCT_COMMIT") or head
        if pc != head:
            raise Fail(f"workspace/head mismatch PRODUCT_COMMIT={pc} HEAD={head}")
        pt = d8.git("rev-parse", "HEAD^{tree}")
        spec_hashes = spec_identity()
        versions = {"cc": d8.version(os.environ.get("CC", "cc")), "nm": d8.version("nm"),
                    "readelf": d8.version("readelf"), "size": d8.version("size"),
                    "objdump": d8.version("objdump"), "ar": d8.version("ar"),
                    "make": d8.version("make"), "clang_ast_scanner": d8.version("clang"),
                    "python": sys.version.splitlines()[0]}
        (raw / "tool-versions.json").write_text(json.dumps(versions, indent=2, sort_keys=True) + "\n")
        d8.build(raw)
        inst = d8.probe(raw)
        obj = d8.objects(raw)
        inv, _stripped = d8.sources(raw)
        ind = indirect_draft9(raw, inv, obj)
        st = d8.stack(raw, obj, {"permitted_callback_sites": [
            {"wrapper": p["wrapper"], "member": p["target"], "path": p["path"]}
            for p in ind["permitted_callback_sites"]]})
        st["excluded_external_callback_edges"] = [
            {"wrapper": p["wrapper"], "target": p["target"], "path": p["path"],
             "callback_type": p["callback_type"]} for p in ind["permitted_callback_sites"]]
        (raw / "stack-analysis.json").write_text(json.dumps(st, indent=2, sort_keys=True) + "\n")
        evidence = {
            "format": "WP13-EMBEDDED-EVIDENCE-1",
            "provenance": {
                "product_commit": pc, "product_tree": pt, "product_base": PRODUCT_BASE,
                "verifier_import_commit": IMPORT_COMMIT, "verifier_publication": VERIFIER_PUBLICATION,
                "verifier_tree": vt, "spec_bundle": SPEC_BUNDLE, "spec_hashes": spec_hashes,
                "engine_makefile_sha256": d8.sha(ENGINE / "Makefile"), "tool_versions": versions,
                "engine_source_inventory_count": len(inv), "engine_object_count": len(obj["objects"]),
            },
            "ram": {"data_bytes": obj["data"], "bss_bytes": obj["bss"], "tape_instance_size_bytes": inst,
                    "summed_bytes": obj["data"] + obj["bss"] + inst},
            "rodata": {"rodata_bytes": obj["rodata"]},
            "allocator": {"scan_complete": True, "forbidden_references": obj["forbidden"]},
            "stack": st,
            "indirect_calls": {k: ind[k] for k in (
                "analysis_complete", "source_inventory_complete", "source_inventory",
                "call_expression_inventory_complete", "call_expression_inventory",
                "permitted_callback_sites", "violations", "ambiguous_or_unresolved")},
            "engine_state": {"symbol_scan_complete": True, "mutable_symbols": obj["mutable"],
                             "common_symbols": obj["common"],
                             "read_only_object_symbol_count": obj["ro_count"]},
        }
        ep, rp = ev / "evidence.json", ev / "result.json"
        ep.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        cmd = [sys.executable, str(PKG / "runner.py"), "--evidence", str(ep), "--result", str(rp)]
        rr = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (ev / "runner.log").write_text("$ " + " ".join(cmd) + "\n" + rr.stdout)
        prov = {"product_commit": pc, "product_tree": pt, "product_base": PRODUCT_BASE,
                "import_commit": IMPORT_COMMIT, "verifier_publication": VERIFIER_PUBLICATION,
                "verifier_tree": vt, "spec_bundle": SPEC_BUNDLE, "spec_hashes": spec_hashes,
                "evidence_sha256": d8.sha(ep),
                "result_sha256": d8.sha(rp) if rp.is_file() else "MISSING", "runner_exit": rr.returncode,
                "raw_build_log_sha256": d8.sha(raw / "build.log"),
                "source_inventory_sha256": d8.sha(raw / "engine-source-sha256.json"),
                "indirect_call_scan_sha256": d8.sha(raw / "indirect-call-scan.json")}
        (ev / "PROVENANCE.json").write_text(json.dumps(prov, indent=2, sort_keys=True) + "\n")
        d8.manifest(ev)
        counts = {}
        for r in ind["call_expression_inventory"]:
            counts[r["classification"]] = counts.get(r["classification"], 0) + 1
        print(f"product_commit={pc}\nproduct_tree={pt}\nverifier_import_commit={IMPORT_COMMIT}\n"
              f"verifier_tree={vt}\nspec_bundle={SPEC_BUNDLE}")
        print(f"ram_summed_bytes={obj['data'] + obj['bss'] + inst}\nrodata_bytes={obj['rodata']}\n"
              f"allocator_forbidden_refs={len(obj['forbidden'])}\nstack_max_path_bytes={st['max_path_bytes']}")
        print(f"source_inventory={len(inv)}\ncall_expressions={len(ind['call_expression_inventory'])} {counts}")
        for p in ind["permitted_callback_sites"]:
            print(f"permitted {p['wrapper']} -> {p['target']} [{p['path']}] type={p['callback_type']}")
        print(f"indirect_violations={len(ind['violations'])}\nindirect_ambiguous={len(ind['ambiguous_or_unresolved'])}")
        print(f"mutable_symbols={len(obj['mutable'])}\ncommon_symbols={len(obj['common'])}")
        print(f"evidence_sha256={prov['evidence_sha256']}\nresult_sha256={prov['result_sha256']}\n"
              f"runner_exit={rr.returncode}")
        print(rr.stdout.strip())
        return rr.returncode
    except Exception as e:
        (ev / "COLLECTION-FAILURE.txt").write_text(f"{type(e).__name__}: {e}\n")
        d8.manifest(ev)
        print(f"COLLECTION FAILURE: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
