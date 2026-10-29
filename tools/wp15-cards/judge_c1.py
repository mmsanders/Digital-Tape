#!/usr/bin/env python3
"""#624 C1 correction: judge the `supplement` and `queries` sections of an s3_bundle.py
BUNDLE.json with Verification's own predicates, unchanged:

  supplement rows   tests/c1_closeout_r1/make_supplement.py  own_p1 / input_refusal,
                    plus the immutable wp15_cards_make_r1 oracle.equivalence
  queries rows      tests/wp15_boundary_query_r1/oracle.check (APP-1A §7)

Raw files are authenticated against the bundle's SHA-256 map as runner.py does. Each
platform must return a real HOST_QUERY_FAILED both before and after the authorized open
and its known-policy-refusal neighbour. Two negative controls, mutations of this run's
own observations, must be refused by the same predicates. Judges nothing else; the
immutable runner.py judges `rows`, and Verification disposes.

  judge_c1.py BUNDLE_DIR --out RESULT.json
"""
import argparse, copy, hashlib, importlib.util, json, sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2] / "tests"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


supplement = load("c1_make_supplement", TESTS / "c1_closeout_r1" / "make_supplement.py")
s3 = supplement.old
boundary = load("c1_boundary_query", TESTS / "wp15_boundary_query_r1" / "oracle.py")


def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


def rejected(f, r):
    try:
        f(r)
    except (AssertionError, KeyError, TypeError):
        return True
    return False


def judge(root):
    b = json.loads((root / "BUNDLE.json").read_text())

    def raw(n):
        assert n in b["files"], n
        p = (root / n).resolve()
        assert p.is_relative_to(root.resolve()) and p.is_file()
        assert sha(p) == b["files"][n], n
        return p

    out = {"source": b["source_sha"], "platform": b["platform"], "supplement": [], "queries": [], "negative_controls": []}
    for row in b.get("supplement", []):
        r = json.loads(raw(row["record"]).read_text())
        for kind in ("stdout", "stderr", "report"):
            r[kind + "_hex"] = raw(row[kind]).read_bytes().hex()
        r["equivalent_pair"] = False
        if "equivalence" in row:
            e = row["equivalence"]
            p = [json.loads(raw(n).read_text()) for n in e["processes"]]
            s3.equivalence(raw(e["stdout"][0]).read_bytes(), [raw(n).read_bytes() for n in e["stdout"][1:]], p[0]["exit"],
                           [x["exit"] for x in p[1:]], sha(raw(e["make_image"])), sha(raw(e["separate_image"])))
            r["equivalent_pair"] = True
        if row["kind"] == "own_p1":
            assert r["equivalent_pair"], "own-p1 success needs its equivalence pair"
            result = supplement.own_p1(r)
            bad = copy.deepcopy(r)
            for e in bad["events"]:
                if e["op"] == "unmount":
                    e["ok"] = False
            out["negative_controls"].append({"of": row["name"], "mutation": "own-p1 unmount marked failed",
                                             "rejected": rejected(supplement.own_p1, bad)})
        else:
            assert row["kind"] == "input_refusal", row["kind"]
            result = supplement.input_refusal(r)
        out["supplement"].append({"name": row["name"], "kind": row["kind"], "result": result})

    seen = set()
    for row in b.get("queries", []):
        o = json.loads(raw(row["observation"]).read_text())
        assert o["raw_artifact_sha256"] == sha(raw(row["trace"]))
        o["report_hex"] = raw(row["report"]).read_bytes().hex()
        result = boundary.check(o)
        out["queries"].append({"name": row["name"], "scope": row["scope"], "result": result})
        seen.add((row["name"], result["id"], result["exit"]))
        if result["id"] == "HOST_QUERY_FAILED":
            bad = copy.deepcopy(o)
            bad["exit"] = 3
            out["negative_controls"].append({"of": row["name"], "mutation": "HOST_QUERY_FAILED recorded as exit 3",
                                             "rejected": rejected(boundary.check, bad)})
    if b.get("queries"):
        names = {n: (i, x) for n, i, x in seen}
        assert names.get("host-query-initial-disk-length") == ("HOST_QUERY_FAILED", 1), names
        assert names.get("host-query-open-geometry") == ("HOST_QUERY_FAILED", 1), names
        assert names.get("host-query-neighbor-known-refusal", (None, 0))[1] == 3, names
    assert all(c["rejected"] for c in out["negative_controls"]), out["negative_controls"]
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    res = judge(a.bundle)
    a.out.write_text(json.dumps(res, indent=2) + "\n")
    print(f"{len(res['supplement'])} supplement, {len(res['queries'])} query rows judged; "
          f"{len(res['negative_controls'])} negative controls refused")
