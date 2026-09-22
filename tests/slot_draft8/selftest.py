#!/usr/bin/env python3
from __future__ import annotations
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from oracle import Media,check,make_cases,synth_observation

def expect_fail(case,post,obs,label):
    errors=check(case,post,obs)
    if not errors:
        raise AssertionError("negative control escaped: "+label)
    print("CAUGHT",label,"=>",errors[0])

def mutate_call(obs,fn,**changes):
    out=copy.deepcopy(obs)
    next(c for c in out["calls"] if c.get("fn")==fn).update(changes)
    return out

ROOT=Path(__file__).resolve().parent

def main():
    cases={c.id:c for c in make_cases()}
    for case in cases.values():
        post,obs=synth_observation(case)
        errors=check(case,post,obs)
        if errors: raise AssertionError((case.id,errors))
        print("PASS conforming",case.id)

    mut=cases["WP36-SRC-MUTATORS-B"]
    post,obs=synth_observation(mut)
    bad=copy.deepcopy(obs); bad["events"].append({"op":"write","lba":0,"count":1})
    expect_fail(mut,post,bad,"write observation")
    expect_fail(mut,post,mutate_call(obs,"tape_get_info",writable=True),"writable true")
    expect_fail(mut,post,mutate_call(obs,"tape_reset_side_b",result="TAPE_OK"),"reset accepted")
    expect_fail(mut,post,mutate_call(obs,"tape_feed",result="TAPE_ERR_READ_ONLY"),"feed precedence")

    play=cases["WP36-SRC-A"]
    post,obs=synth_observation(play)
    missing=copy.deepcopy(obs)
    missing["calls"]=[c for c in missing["calls"] if c.get("fn")!="tape_render"]
    expect_fail(play,post,missing,"missing render")
    expect_fail(play,post,mutate_call(obs,"tape_service",result="TAPE_ERR_IO"),"service failure")

    repair=cases["WP36-SRC-REPAIR-A"]
    post,obs=synth_observation(repair)
    expect_fail(repair,post,mutate_call(obs,"tape_get_info",needs_repair=False),"repair hidden")
    bad=copy.deepcopy(obs); bad["events"].append({"op":"flush","lba":0,"count":0})
    expect_fail(repair,post,bad,"repair flush")
    mutated=Media(post.blocks,post.primary,bytes([1])+post.mirror[1:],post.slots)
    expect_fail(repair,mutated,obs,"media mutation")

    # Negative control for the assertion/crash observation path: any adapter
    # process failure must make runner.py fail the case.
    with tempfile.TemporaryDirectory(prefix="wp36-runner-control-") as td:
        fake=Path(td)/"fail_adapter.py"
        fake.write_text("#!/usr/bin/env python3\\nraise SystemExit(134)\\n")
        os.chmod(fake,0o755)
        log=Path(td)/"run.jsonl"
        r=subprocess.run([
            sys.executable,str(ROOT/"runner.py"),"--adapter",str(fake),
            "--case","WP36-SRC-A","--log",str(log)
        ])
        if r.returncode==0:
            raise AssertionError("runner accepted crashing adapter")
        print("CAUGHT adapter assertion/crash exit")

    print("PASS all WP-36 source-slot self-tests")

if __name__=="__main__":
    main()
