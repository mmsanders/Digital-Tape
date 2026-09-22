#!/usr/bin/env python3
from __future__ import annotations
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from oracle import SENTINEL,check,make_cases,synth_observation

ROOT=Path(__file__).resolve().parent

def expect_fail(case,obs,label):
    errors=check(case,obs)
    if not errors:
        raise AssertionError("negative control escaped: "+label)
    print("CAUGHT",label,"=>",errors[0])

def case_by_id(cases,cid):
    return cases[cid]

def main():
    cases={c.id:c for c in make_cases()}
    if len(cases)!=34:
        raise AssertionError("expected 34 isolated cases")
    for case in cases.values():
        obs=synth_observation(case)
        errors=check(case,obs)
        if errors: raise AssertionError((case.id,errors))
        print("PASS conforming",case.id)

    tell=case_by_id(cases,"NM-BEFORE-TELL")
    obs=synth_observation(tell)
    bad=copy.deepcopy(obs); bad["calls"][-1]["result"]="TAPE_OK"
    expect_fail(tell,bad,"tell before mount succeeded")
    bad=copy.deepcopy(obs); bad["calls"][-1]["out_frame_after"]=0
    expect_fail(tell,bad,"tell sentinel overwritten before mount")

    tell_after=case_by_id(cases,"NM-AFTER-TELL")
    obs_after=synth_observation(tell_after)
    bad=copy.deepcopy(obs_after); bad["calls"][-1]["out_frame_after"]=0
    expect_fail(tell_after,bad,"tell sentinel overwritten after unmount")

    seek=case_by_id(cases,"NM-AFTER-SEEK")
    obs=synth_observation(seek)
    bad=copy.deepcopy(obs); bad["calls"][-1]["result"]="TAPE_OK"
    expect_fail(seek,bad,"seek after unmount succeeded")
    bad=copy.deepcopy(obs); bad["calls"]=[c for c in bad["calls"] if not (c.get("phase")=="setup" and c.get("fn")=="tape_unmount")]
    expect_fail(seek,bad,"after-case omitted setup unmount")
    bad=copy.deepcopy(obs); bad["calls"][1],bad["calls"][2]=bad["calls"][2],bad["calls"][1]
    expect_fail(seek,bad,"after-case setup order wrong")

    arm=case_by_id(cases,"NM-BEFORE-ARM")
    obs=synth_observation(arm)
    bad=copy.deepcopy(obs); bad["calls"]=[c for c in bad["calls"] if c.get("phase")!="probe"]
    expect_fail(arm,bad,"target omitted")
    bad=copy.deepcopy(obs); bad["calls"].append(copy.deepcopy(bad["calls"][-1]))
    expect_fail(arm,bad,"duplicate probe")
    bad=copy.deepcopy(obs); bad["calls"][-1]["fn"]="tape_commit"
    expect_fail(arm,bad,"wrong target")

    # Callback counters are diagnostic only; WP-06h does not separately specify
    # a zero-callback acceptance rule.
    diagnostic=copy.deepcopy(obs)
    diagnostic["calls"][-1]["src_callbacks"]=3
    diagnostic["calls"][-1]["src_writes"]=1
    if check(arm,diagnostic):
        raise AssertionError("oracle invented a zero-callback WP-06h requirement")

    # Product runner must reject synthetic evidence.
    with tempfile.TemporaryDirectory(prefix="wp06h-runner-control-") as td:
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
            "--case","NM-BEFORE-TELL","--log",str(log)
        ])
        if r.returncode==0:
            raise AssertionError("runner accepted synthetic adapter")
        if "non-product adapter refused" not in log.read_text():
            raise AssertionError("synthetic evidence rejected for wrong reason")
        print("CAUGHT synthetic product evidence")

    print("PASS all WP-06h not-mounted self-tests")

if __name__=="__main__":
    main()
