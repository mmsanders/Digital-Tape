#!/usr/bin/env python3
from __future__ import annotations
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from oracle import Media,check,make_cases,synth_observation

ROOT=Path(__file__).resolve().parent

def expect_fail(case,post,obs,label):
    errors=check(case,post,obs)
    if not errors:
        raise AssertionError("negative control escaped: "+label)
    print("CAUGHT",label,"=>",errors[0])

def mutate_call(obs,fn,**changes):
    out=copy.deepcopy(obs)
    next(c for c in out["calls"] if c.get("fn")==fn).update(changes)
    return out

def main():
    cases={c.id:c for c in make_cases()}
    for case in cases.values():
        post,obs=synth_observation(case)
        errors=check(case,post,obs)
        if errors: raise AssertionError((case.id,errors))
        print("PASS conforming",case.id)

    arm=cases["W06A-ARM"]
    post,obs=synth_observation(arm)
    bad=copy.deepcopy(obs); bad["events"].append({"op":"write","lba":8,"count":1})
    expect_fail(arm,post,bad,"dev_write observed")
    expect_fail(arm,post,mutate_call(obs,"tape_get_info",writable=True),"writable true")
    expect_fail(arm,post,mutate_call(obs,"tape_get_info",version_minor=0),"minor zero")
    bad=copy.deepcopy(obs); bad["device_write_nonnull"]=False
    expect_fail(arm,post,bad,"device write callback NULL")
    bad=copy.deepcopy(obs); bad["event_overflow"]=True
    expect_fail(arm,post,bad,"callback trace overflow")
    expect_fail(arm,post,mutate_call(obs,"tape_mount",side="A"),"wrong side")
    expect_fail(arm,post,mutate_call(obs,"tape_arm",result="TAPE_OK"),"arm accepted")
    reset=cases["W06A-RESET-B"]; rpost,robs=synth_observation(reset)
    expect_fail(reset,rpost,mutate_call(robs,"tape_reset_side_b",result="TAPE_OK"),"reset accepted")
    # Flush-only activity is recorded but is not an independent WP-06a failure:
    # the issued acceptance criterion is zero dev_write calls.
    flush_only=copy.deepcopy(obs); flush_only["events"].append({"op":"flush","lba":0,"count":0})
    if check(arm,post,flush_only):
        raise AssertionError("oracle invented a zero-flush WP-06a requirement")
    missing=copy.deepcopy(obs)
    missing["calls"]=[c for c in missing["calls"] if c.get("fn")!="tape_arm"]
    expect_fail(arm,post,missing,"arm omitted")

    feed=cases["W06A-FEED"]
    post,obs=synth_observation(feed)
    expect_fail(feed,post,mutate_call(obs,"tape_feed",result="TAPE_ERR_READ_ONLY"),"feed precedence")

    for cid in ("W06A-REPAIR-INVALID","W06A-REPAIR-STALE"):
        case=cases[cid]; post,obs=synth_observation(case)
        expect_fail(case,post,mutate_call(obs,"tape_get_info",needs_repair=False),cid+" repair hidden")

    case=cases["W06A-REPAIR-INVALID"]
    post,obs=synth_observation(case)
    mutated=Media(post.blocks,post.primary,bytes([1])+post.mirror[1:],post.slots)
    expect_fail(case,mutated,obs,"media mutation")

    # The product runner must reject the synthetic adapter even when its
    # verifier expectations are otherwise conforming.
    with tempfile.TemporaryDirectory(prefix="wp06a-runner-control-") as td:
        wrapper=Path(td)/"synthetic"
        wrapper.write_text(
            "#!/usr/bin/env python3\n"
            "import runpy, sys\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            f"runpy.run_path({str(ROOT/'_synthetic_adapter.py')!r}, run_name='__main__')\n"
        )
        os.chmod(wrapper,0o755)
        log=Path(td)/"run.jsonl"
        r=subprocess.run([
            sys.executable,str(ROOT/"runner.py"),"--adapter",str(wrapper),
            "--case","W06A-ARM","--log",str(log)
        ])
        if r.returncode==0:
            raise AssertionError("runner accepted synthetic adapter")
        if "non-product adapter refused" not in log.read_text():
            raise AssertionError("synthetic-adapter negative control failed for wrong reason")
        print("CAUGHT synthetic product evidence")

    print("PASS all WP-06a writability self-tests")

if __name__=="__main__":
    main()
