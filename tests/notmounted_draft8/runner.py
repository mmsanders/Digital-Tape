#!/usr/bin/env python3
"""Run verifier-owned WP-06h expectations against the verifier product probe."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from oracle import Media,SPEC_SHA256,check,make_cases

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--adapter",type=Path,required=True)
    p.add_argument("--log",type=Path,required=True)
    p.add_argument("--case")
    p.add_argument("--timeout",type=int,default=30)
    a=p.parse_args(argv)
    adapter=a.adapter.resolve()
    if not adapter.is_file(): p.error("adapter executable does not exist")
    cases=make_cases()
    if a.case: cases=[c for c in cases if c.id==a.case]
    if not cases: p.error("no matching cases")
    a.log.parent.mkdir(parents=True,exist_ok=True)
    failures=0
    with a.log.open("w") as log,tempfile.TemporaryDirectory(prefix="wp06h-") as td:
        log.write(json.dumps({
            "kind":"provenance",
            "adapter":str(adapter),
            "adapter_sha256":hashlib.sha256(adapter.read_bytes()).hexdigest(),
            "spec_sha256":SPEC_SHA256,
            "cases":len(cases),
        },sort_keys=True)+"\n")
        for case in cases:
            inp=Path(td)/(case.id+".vo08")
            out=Path(td)/(case.id+".out.vo08")
            payload=case.pre.encode(); inp.write_bytes(payload)
            rec={"id":case.id,"fixture_sha256":hashlib.sha256(payload).hexdigest()}
            errors=[]
            try:
                r=subprocess.run([str(adapter),case.id,str(inp),str(out)],
                                 capture_output=True,text=True,timeout=a.timeout)
                rec.update(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
                if r.returncode:
                    errors.append("adapter process failed")
                else:
                    obs=json.loads(r.stdout)
                    if obs.get("adapter_kind")!="product":
                        errors.append("non-product adapter refused")
                    if not out.is_file():
                        errors.append("adapter did not produce output envelope")
                    else:
                        # Decode only to authenticate the adapter's output envelope.
                        # WP-06h does not add an unstated media-identity criterion.
                        Media.decode(out.read_bytes())
                        rec["output_sha256"]=hashlib.sha256(out.read_bytes()).hexdigest()
                    errors.extend(check(case,obs))
            except (OSError,subprocess.TimeoutExpired,ValueError,json.JSONDecodeError,KeyError,TypeError) as exc:
                rec["exception"]=str(exc)
                errors.append("missing/malformed observation or adapter failure")
            rec["errors"]=errors
            rec["status"]="FAIL" if errors else "PASS"
            log.write(json.dumps(rec,sort_keys=True)+"\n"); log.flush()
            if errors:
                failures+=1
                print(case.id+": FAIL: "+"; ".join(errors[:4]))
            else:
                print(case.id+": PASS")
    print(f"{len(cases)} cases; {failures} failed; see {a.log}")
    return 1 if failures else 0

if __name__=="__main__":
    sys.exit(main())
