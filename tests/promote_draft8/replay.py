#!/usr/bin/env python3
"""Offline replay of hash-bound promote tranche evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import oracle

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence")
    a = ap.parse_args()
    ev = Path(a.evidence)

    try:
        m = json.loads((ev / "manifest.json").read_text())
        oracle.req(m.get("schema") == "promote-draft8-evidence-v1", "evidence schema")
        oracle.req(str(m.get("product_commit", "")).strip(), "missing product commit")
        oracle.req(str(m.get("verifier_commit", "")).strip(), "missing verifier commit")
        for rel, digest in m["files"].items():
            p = ev / rel
            oracle.req(p.is_file() and oracle.shafile(p) == digest, "evidence hash mismatch " + rel)
        actual = {
            p.relative_to(ev).as_posix()
            for p in ev.rglob("*")
            if p.is_file() and p.name != "manifest.json"
        }
        oracle.req(actual == set(m["files"]), "unbound/missing evidence file")

        got_specs = oracle.verify_spec_dir(ev / "input" / "spec")
        oracle.req(got_specs == m.get("spec_hashes"), "spec manifest mismatch")
        oracle.req(m["oracle_sha256"] == oracle.shafile(ev / "input/package/oracle.py"), "oracle evidence identity")
        oracle.req(m["runner_sha256"] == oracle.shafile(ev / "input/package/runner.py"), "runner evidence identity")
        oracle.req(m["replay_sha256"] == oracle.shafile(ev / "input/package/replay.py"), "replay evidence identity")
        oracle.req(m["oracle_sha256"] == oracle.shafile(HERE / "oracle.py"), "local oracle identity")
        oracle.req(m["replay_sha256"] == oracle.shafile(HERE / "replay.py"), "local replay identity")

        cases = {c.id: c for c in oracle.make_cases()}
        replayed = {"pass": True, "cases": {}}
        for cid, case in cases.items():
            execution = m["executions"][cid]
            oracle.req(
                execution["outcome"] == "exited" and execution["exit_code"] == 0,
                cid + " execution not successful",
            )
            cdir = ev / "output" / cid
            oracle.req((cdir / "adapter-exit.txt").read_text() == "0\n", cid + " exit record")
            inp = oracle.Media.decode((cdir / "input.vo08").read_bytes())
            oracle.req(inp == case.pre, cid + " input fixture mismatch")
            obs = json.loads((cdir / "observation.json").read_text())
            oracle.req(obs.get("adapter_kind") == m["adapter"]["kind"], cid + " adapter kind mismatch")
            oracle.req(obs.get("adapter_id") == m["adapter"]["id"], cid + " adapter id mismatch")
            errors = oracle.validate_observation(case, (cdir / "output.vo08").read_bytes(), obs)
            replayed["cases"][cid] = {"pass": not errors, "errors": errors}
            if errors:
                replayed["pass"] = False

        saved = json.loads((ev / "result.json").read_text())
        oracle.req(saved == replayed, "saved result mismatch")
        oracle.req(replayed["pass"], "oracle mismatch")
        print("REPLAY PASS", ev)
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, oracle.VerificationError) as e:
        print("REPLAY FAIL:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
