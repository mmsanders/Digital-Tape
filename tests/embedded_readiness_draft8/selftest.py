#!/usr/bin/env python3
from __future__ import annotations
from oracle import evaluate

def good():
    return {
      "format":"WP13-EMBEDDED-EVIDENCE-1",
      "provenance":{
        "product_commit":"a"*40,"product_tree":"b"*40,"verifier_tree":"c"*40,
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
               "excluded_external_callback_edges":[{"wrapper":"dev_read"}]},
      "indirect_calls":{"analysis_complete":True,
          "permitted_callback_sites":[
            {"wrapper":"dev_read","member":"read","path":"engine/src/dev.h"},
            {"wrapper":"dev_write","member":"write","path":"engine/src/dev.h"},
            {"wrapper":"dev_flush","member":"flush","path":"engine/src/dev.h"}],
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

    fail_one(lambda e:e["indirect_calls"]["violations"].append(
             {"path":"engine/src/x.c","line":7,"expression":"fp()"}), "WP13-G5")
    print("PASS indirect-call negative control")

    fail_one(lambda e:e["engine_state"]["mutable_symbols"].append(
             {"object":"x.o","symbol":"hidden","section":".bss","size":4}), "WP13-G6")
    print("PASS engine-owned-state negative control")

    e = good()
    del e["provenance"]["tool_versions"]["readelf"]
    need(not evaluate(e)["overall_pass"], "missing tool provenance escaped")
    print("PASS malformed-provenance negative control")

    e = good()
    e["indirect_calls"]["permitted_callback_sites"].pop()
    need(not evaluate(e)["overall_pass"], "missing callback funnel escaped")
    print("PASS callback-funnel completeness negative control")

    print("PASS all WP-13 embedded-readiness package self-tests")

if __name__ == "__main__":
    main()
