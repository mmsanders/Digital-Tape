#!/usr/bin/env python3
from __future__ import annotations
import hashlib
from pathlib import Path
from oracle import SPEC_BUNDLE, SPEC_HASHES, evaluate

ROOT = Path(__file__).resolve().parent

def site(wrapper, target, callback_type=None):
    return {"wrapper":wrapper, "target":target, "path":"engine/src/dev.h",
            "callback_type":callback_type}

def call(wrapper, target, line, callback_type=None):
    return {"path":"engine/src/dev.h", "line":line,
            "expression":f"{target}(...)", "classification":"permitted_indirect",
            "wrapper":wrapper, "target":target, "callback_type":callback_type}

def good():
    sites = [
        site("dev_read", "tape_dev.read"),
        site("dev_write", "tape_dev.write"),
        site("dev_flush", "tape_dev.flush"),
        site("dev_progress", "tape_progress_fn", "tape_progress_fn"),
    ]
    calls = [
        {"path":"engine/src/tape.c","line":12,"expression":"helper()",
         "classification":"direct"},
        call("dev_read", "tape_dev.read", 21),
        call("dev_write", "tape_dev.write", 30),
        call("dev_flush", "tape_dev.flush", 39),
        call("dev_progress", "tape_progress_fn", 48, "tape_progress_fn"),
    ]
    return {
      "format":"WP13-EMBEDDED-EVIDENCE-1",
      "provenance":{
        "product_commit":"a"*40,"product_tree":"b"*40,"verifier_tree":"c"*40,
        "spec_bundle":SPEC_BUNDLE,"spec_hashes":SPEC_HASHES.copy(),
        "tool_versions":{"cc":"cc synthetic 1","nm":"nm synthetic 1",
                         "readelf":"readelf synthetic 1","size":"size synthetic 1"}},
      "ram":{"data_bytes":64,"bss_bytes":128,"tape_instance_size_bytes":100000,
             "summed_bytes":100192},
      "rodata":{"rodata_bytes":16000},
      "allocator":{"scan_complete":True,"forbidden_references":[]},
      "stack":{"analysis_complete":True,"max_path_bytes":4096,
               "max_path":["tape_mount","helper"],
               "dynamic_or_unknown_frames":[],"unresolved_internal_edges":[],
               "recursive_cycles":[],
               "excluded_external_callback_edges":[{"wrapper":"dev_read"},
                                                    {"wrapper":"dev_progress"}]},
      "indirect_calls":{"analysis_complete":True,
          "source_inventory_complete":True,
          "source_inventory":[
            {"path":"engine/src/dev.h","sha256":"d"*64},
            {"path":"engine/src/tape.c","sha256":"e"*64}],
          "call_expression_inventory_complete":True,
          "call_expression_inventory":calls,
          "permitted_callback_sites":sites,
          "violations":[],"ambiguous_or_unresolved":[]},
      "engine_state":{"symbol_scan_complete":True,"mutable_symbols":[],
                      "common_symbols":[],"read_only_object_symbol_count":7},
    }

def need(cond, msg):
    if not cond:
        raise AssertionError(msg)

def fail_one(mutator, gate):
    e = good()
    mutator(e)
    r = evaluate(e)
    rows = {x["id"]: x for x in r["gates"]}
    need(not r["overall_pass"], gate + " mutation escaped overall")
    need(not rows[gate]["passed"], gate + " mutation escaped gate")

def main():
    for rel, expected in SPEC_HASHES.items():
        embedded = ROOT / rel
        need(embedded.is_file(), f"missing embedded spec: {rel}")
        actual = hashlib.sha256(embedded.read_bytes()).hexdigest()
        need(actual == expected, f"embedded spec hash mismatch: {rel}")
    need((ROOT / "spec/VERSION.md").is_file(), "missing embedded VERSION.md")
    print("PASS embedded DRAFT-9 specification bytes")

    r = evaluate(good())
    need(r["overall_pass"], "good synthetic evidence rejected")
    need(len(r["gates"]) == 6, "not exactly six gates")
    need(r["tape_instance_size_bytes"] == 100000, "instance size not reported")
    print("PASS conforming six-gate evidence")

    fail_one(lambda e:e["ram"].update(data_bytes=105000,bss_bytes=100000,
                                      tape_instance_size_bytes=10000,summed_bytes=215000),
             "WP13-G1")
    print("PASS RAM-sum negative control")
    fail_one(lambda e:e["rodata"].update(rodata_bytes=32769), "WP13-G2")
    print("PASS rodata negative control")
    fail_one(lambda e:e["allocator"]["forbidden_references"].append(
             {"symbol":"malloc","object":"x.o"}), "WP13-G3")
    print("PASS allocator-symbol negative control")
    fail_one(lambda e:e["stack"].update(max_path_bytes=8193), "WP13-G4")
    print("PASS stack-bound negative control")
    fail_one(lambda e:e["stack"]["unresolved_internal_edges"].append("f -> ?"), "WP13-G4")
    print("PASS incomplete-stack negative control")

    def add_fifth(e):
        e["indirect_calls"]["permitted_callback_sites"].append(
            site("dev_other", "other_callback"))
        e["indirect_calls"]["call_expression_inventory"].append(
            call("dev_other", "other_callback", 57))
    fail_one(add_fifth, "WP13-G5")
    print("PASS fifth-wrapper negative control")

    def outside_dev_h(e):
        e["indirect_calls"]["violations"].append(
            {"path":"engine/src/x.c","line":7,"expression":"fp()"})
        e["indirect_calls"]["call_expression_inventory"].append(
            {"path":"engine/src/x.c","line":7,"expression":"fp()",
             "classification":"forbidden_indirect"})
    fail_one(outside_dev_h, "WP13-G5")
    print("PASS outside-dev.h indirect-call negative control")

    def wrong_progress(e):
        e["indirect_calls"]["permitted_callback_sites"][-1].update(
            target="other_callback", callback_type="other_fn")
        e["indirect_calls"]["call_expression_inventory"][-1].update(
            target="other_callback", callback_type="other_fn")
    fail_one(wrong_progress, "WP13-G5")
    print("PASS dev_progress target/type negative control")

    def missing_progress(e):
        e["indirect_calls"]["permitted_callback_sites"].pop()
        e["indirect_calls"]["call_expression_inventory"].pop()
    fail_one(missing_progress, "WP13-G5")
    print("PASS required-dev_progress completeness negative control")

    fail_one(lambda e:e["indirect_calls"]["ambiguous_or_unresolved"].append(
             {"path":"engine/src/y.c","line":8,"expression":"maybe()"}), "WP13-G5")
    print("PASS ambiguous-call negative control")
    fail_one(lambda e:e["indirect_calls"].update(source_inventory_complete=False),
             "WP13-G5")
    print("PASS incomplete-source-inventory negative control")
    fail_one(lambda e:e["indirect_calls"].update(call_expression_inventory_complete=False),
             "WP13-G5")
    print("PASS incomplete-call-inventory negative control")

    fail_one(lambda e:e["engine_state"]["mutable_symbols"].append(
             {"object":"x.o","symbol":"hidden","section":".bss","size":4}), "WP13-G6")
    print("PASS engine-owned-state negative control")

    e = good()
    del e["provenance"]["tool_versions"]["readelf"]
    need(not evaluate(e)["overall_pass"], "missing tool provenance escaped")
    print("PASS malformed-provenance negative control")
    e = good()
    e["provenance"]["spec_hashes"]["spec/engine-api.md"] = "0"*64
    need(not evaluate(e)["overall_pass"], "wrong DRAFT-9 spec binding escaped")
    print("PASS spec-binding negative control")

    print("PASS all DRAFT-9 WP-13 embedded-readiness package self-tests")

if __name__ == "__main__":
    main()
