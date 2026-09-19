#!/usr/bin/env python3
"""Offline replay of hash-bound P1-R6 evidence."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import oracle
HERE=Path(__file__).resolve().parent
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("evidence"); a=ap.parse_args(); ev=Path(a.evidence)
    try:
        m=json.loads((ev/"manifest.json").read_text()); oracle.req(m.get("schema")=="playback-complete-draft8-evidence-v1","evidence schema"); oracle.req(m.get("assignment")=="P1-R6-V","assignment")
        for k,v in m["files"].items(): oracle.req((ev/k).is_file() and oracle.shafile(ev/k)==v,"evidence hash mismatch "+k)
        actual={p.relative_to(ev).as_posix() for p in ev.rglob("*") if p.is_file() and p.name!="manifest.json"}; oracle.req(actual==set(m["files"]),"unbound/missing evidence file")
        oracle.req(m["execution"]["outcome"]=="exited" and m["execution"]["exit_code"]==0,"execution not successful"); oracle.req((ev/"output/adapter-exit.txt").read_text()=="0\n","exit record")
        obs=json.loads((ev/"output/observation.json").read_text()); oracle.req(obs["adapter"]["kind"]==m["adapter"]["kind"] and obs["adapter"]["id"]==m["adapter"]["id"],"adapter identity mismatch")
        for f in ("source","build"): oracle.req(str(m["adapter"].get(f,"")).strip(),"missing adapter "+f)
        oracle.req(m["package_manifest_sha256"]==oracle.shafile(ev/"input/package/package.json"),"package identity")
        oracle.req(m["oracle_sha256"]==oracle.shafile(ev/"input/package/oracle.py"),"oracle identity")
        outputs={f:(ev/"output"/n).read_bytes() for f,n in oracle.OUTPUTS.items()}; result=oracle.validate(obs,outputs); oracle.req(result["pass"],"oracle mismatch")
        saved=json.loads((ev/"result.json").read_text()); oracle.req(saved==dict(result,error=None),"saved result mismatch")
        print("REPLAY PASS",ev); return 0
    except (OSError,ValueError,KeyError,json.JSONDecodeError,oracle.VerificationError) as e: print("REPLAY FAIL:",e,file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
