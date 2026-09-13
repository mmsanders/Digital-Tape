#!/usr/bin/env python3
"""Synthetic public-contract model for verifier plumbing only; never product evidence."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import oracle, generate_fixture as gen

def call(name,result=0,**kw): return {"call":name,"result":result,**kw}
def finish(calls): return [{"call_index":0,"op":"read","lba":0,"count":1,"rc":0}]+[{"call_index":i,"op":"read","lba":gen.BASE,"count":1,"rc":0} for i,x in enumerate(calls) if x["call"]=="tape_service"]
def boundary(mount_fixture,rate,seek=None):
    c=[call("tape_mount",side="A",resume_frame=0,warm=None)]
    if seek is not None:c.append(call("tape_seek",frame=seek))
    c += [call("tape_set_rate",rate_q16_16=rate),call("tape_service",block_budget=1024,more_work=False),call("tape_render",requested=2,rendered=1),call("tape_tell",frame=1 if mount_fixture=="one" else 0),call("tape_status",at_end=mount_fixture=="one",at_start=mount_fixture!="one"),call("tape_unmount")]
    return {"fixture":mount_fixture,"calls":c,"callbacks":finish(c)}
def scrub(reverse=False):
    c=[call("tape_mount",side="A",resume_frame=0,warm=None)]
    if reverse:c.append(call("tape_seek",frame=gen.LONG_N))
    for rate,count in zip(gen.RATES,gen.COUNTS):
        c += [call("tape_set_rate",rate_q16_16=-rate if reverse else rate),call("tape_service",block_budget=1024,more_work=False)]
        while count: n=min(128,count); c.append(call("tape_render",requested=n,rendered=n)); count-=n
    c.append(call("tape_unmount")); return {"fixture":"long","calls":c,"callbacks":finish(c)}
def side(playing):
    c=[call("tape_mount",side="A",resume_frame=0,warm=None)]
    if playing:c += [call("tape_seek",frame=gen.LONG_N-1),call("tape_set_rate",rate_q16_16=65536),call("tape_service",block_budget=1024,more_work=False),call("tape_render",requested=2,rendered=1),call("tape_status",at_end=True,at_start=False)]
    else:c += [call("tape_set_rate",rate_q16_16=0)]
    c += [call("tape_set_side",side="B",rate_q16_16=65536 if playing else 0),call("tape_tell",frame=0),call("tape_status",at_end=False,at_start=False),call("tape_get_info",total_frames=gen.SIDE_B_N,warm_start_used=False)]
    if not playing:c += [call("tape_set_rate",rate_q16_16=65536)]
    c += [call("tape_render",6,requested=1,rendered=0),call("tape_service",block_budget=1024,more_work=False),call("tape_render",requested=1,rendered=1),call("tape_unmount")]
    return {"fixture":"long","calls":c,"callbacks":finish(c)}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--fixture-dir",required=True); ap.add_argument("--out-dir",required=True); a=ap.parse_args(); out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    basic=lambda fixture,rate,status:[call("tape_mount",side="A",resume_frame=0,warm=None),call("tape_set_rate",rate_q16_16=rate),call("tape_render",requested=4,rendered=0),call("tape_tell",frame=status[2]),call("tape_status",at_end=status[0],at_start=status[1]),call("tape_unmount")]
    cases={}
    for fam,fixture,rate,st in (("empty_zero","empty",0,(True,False,0)),("empty_nonzero","empty",65536,(True,False,0))): c=basic(fixture,rate,st); cases[fam]={"fixture":fixture,"calls":c,"callbacks":finish(c)}
    c=[call("tape_mount",side="A",resume_frame=0,warm=None),call("tape_seek",frame=1234),call("tape_set_rate",rate_q16_16=0),call("tape_render",requested=4,rendered=0),call("tape_tell",frame=1234),call("tape_status",at_end=False,at_start=False),call("tape_unmount")]; cases["nonempty_zero"]={"fixture":"long","calls":c,"callbacks":finish(c)}
    cases.update(one_intmax=boundary("one",2147483647),reverse_zero=boundary("long",-65536),intmin=boundary("long",-2147483648,1),scrub_forward=scrub(),scrub_reverse=scrub(True),side_playing=side(True),side_idle=side(False))
    obs={"schema":"playback-complete-draft8-observation-v1","wp08_sha256":oracle.WP08,"adapter":{"kind":"synthetic","id":"verifier-p1-r6-public-contract-model-v1"},"cases":cases}
    (out/"observation.json").write_text(json.dumps(obs,indent=2,sort_keys=True)+"\n")
    for fam,name in oracle.OUTPUTS.items():(out/name).write_bytes(oracle.expected_outputs()[fam])
    print("synthetic P1-R6 observation written"); return 0
if __name__=="__main__": raise SystemExit(main())
