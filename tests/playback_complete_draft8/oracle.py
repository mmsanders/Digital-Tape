#!/usr/bin/env python3
"""Independent oracle for P1-R6 boundary, exact scrub, and side-switch behavior."""
from __future__ import annotations
import gzip, hashlib, json
from pathlib import Path
import generate_fixture as gen

HERE=Path(__file__).resolve().parent
SPEC={"tapefs-v1.md":"3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb","engine-api.md":"537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1","acceptance.md":"7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7"}
WP08="ff519e960ed3db6e401baebd12f33d5527f83f0e4dfec12484f498470198a96a"
OUTPUTS={"one_intmax":"one-intmax.pcm","reverse_zero":"reverse-zero.pcm","intmin":"intmin.pcm","scrub_forward":"scrub-forward.pcm","scrub_reverse":"scrub-reverse.pcm","side_playing":"side-playing.pcm","side_idle":"side-idle.pcm"}
class VerificationError(Exception): pass
def req(x,m):
    if not x: raise VerificationError(m)
def sha(b): return hashlib.sha256(b).hexdigest()
def shafile(p): return sha(p.read_bytes())
def authenticate(root=HERE):
    m=json.loads((root/"package.json").read_text()); req(m["schema"]=="playback-complete-draft8-package-v1","package schema")
    for n,h in SPEC.items(): req(shafile(root/"spec"/n)==h,"spec hash mismatch "+n)
    req(shafile(root/"input/WP-08.md")==WP08,"WP-08 hash mismatch")
    for n,r in m["generated_files"].items():
        p=root/n; req(p.is_file(),"missing generated "+n); req(len(p.read_bytes())==r["bytes"] and shafile(p)==r["sha256"],"generated hash mismatch "+n)
    gen.check(gen.generated()[1]); return m
def c(call,name,result=0,**fields):
    req(call.get("call")==name and call.get("result")==result,"bad "+name)
    for k,v in fields.items(): req(call.get(k)==v,f"{name}.{k}")
def status(call,at_end,at_start): c(call,"tape_status",at_end=at_end,at_start=at_start)
def tell(call,n): c(call,"tape_tell",frame=n)
def info(call,total,warm=False): c(call,"tape_get_info",total_frames=total,warm_start_used=warm)
def callbacks(case,calls):
    ev=case.get("callbacks"); req(isinstance(ev,list) and ev,"callbacks missing")
    mount=service=0
    for e in ev:
        i=e.get("call_index"); req(isinstance(i,int) and 0<=i<len(calls),"callback index")
        name=calls[i].get("call"); req(name in ("tape_mount","tape_service"),"I/O during "+str(name))
        req(e.get("op")=="read" and e.get("rc")==0 and e.get("count",0)>0,"callback record")
        mount += name=="tape_mount"; service += name=="tape_service"
    req(mount>0,"mount callbacks absent")
    if any(x.get("call")=="tape_service" for x in calls): req(service>0,"service callbacks absent")
def service_seq(calls,p):
    start=p
    while p<len(calls) and calls[p].get("call")=="tape_service":
        c(calls[p],"tape_service",block_budget=1024); req(isinstance(calls[p].get("more_work"),bool),"service more_work"); p+=1
        if not calls[p-1]["more_work"]: break
    req(p>start and calls[p-1]["more_work"] is False,"service incomplete"); return p
def simple(case,names):
    calls=case["calls"]; req([x.get("call") for x in calls]==names,"call order"); callbacks(case,calls); return calls
def expected_outputs():
    return {
      "one_intmax":gen.pcm((gen.frame(0),)),
      "reverse_zero":gen.pcm((gen.frame(0),)),
      "intmin":gen.pcm((gen.frame(1),)),
      "scrub_forward":(HERE/"candidate/scrub-forward.pcm").read_bytes(),
      "scrub_reverse":(HERE/"candidate/scrub-reverse.pcm").read_bytes(),
      "side_playing":gen.pcm((gen.frame(gen.LONG_N-1),gen.frame(0,1))),
      "side_idle":gen.pcm((gen.frame(0,1),)),
    }
def validate(obs,outputs):
    authenticate(); req(obs.get("schema")=="playback-complete-draft8-observation-v1","observation schema")
    req(obs.get("wp08_sha256")==WP08,"observation WP-08 identity"); req(obs.get("adapter",{}).get("kind") in ("synthetic","product"),"adapter kind")
    cases=obs.get("cases",{}); required=("empty_zero","empty_nonzero","nonempty_zero","one_intmax","reverse_zero","intmin","scrub_forward","scrub_reverse","side_playing","side_idle")
    req(set(cases)==set(required),"case set")

    x=simple(cases["empty_zero"],["tape_mount","tape_set_rate","tape_render","tape_tell","tape_status","tape_unmount"])
    c(x[1],"tape_set_rate",rate_q16_16=0); c(x[2],"tape_render",requested=4,rendered=0); tell(x[3],0); status(x[4],True,False)
    x=simple(cases["empty_nonzero"],["tape_mount","tape_set_rate","tape_render","tape_tell","tape_status","tape_unmount"])
    c(x[1],"tape_set_rate",rate_q16_16=65536); c(x[2],"tape_render",requested=4,rendered=0); tell(x[3],0); status(x[4],True,False)
    x=simple(cases["nonempty_zero"],["tape_mount","tape_seek","tape_set_rate","tape_render","tape_tell","tape_status","tape_unmount"])
    c(x[1],"tape_seek",frame=1234); c(x[2],"tape_set_rate",rate_q16_16=0); c(x[3],"tape_render",requested=4,rendered=0); tell(x[4],1234); status(x[5],False,False)

    for fam,rate,seek,total in (("one_intmax",2147483647,None,1),("reverse_zero",-65536,None,gen.LONG_N),("intmin",-2147483648,1,gen.LONG_N)):
        calls=cases[fam]["calls"]; callbacks(cases[fam],calls); p=0; c(calls[p],"tape_mount",side="A",resume_frame=0,warm=None); p+=1
        if seek is not None: c(calls[p],"tape_seek",frame=seek); p+=1
        c(calls[p],"tape_set_rate",rate_q16_16=rate); p=service_seq(calls,p+1); c(calls[p],"tape_render",requested=2,rendered=1); p+=1
        tell(calls[p],1 if fam=="one_intmax" else 0); p+=1; status(calls[p],fam=="one_intmax",fam!="one_intmax"); p+=1; c(calls[p],"tape_unmount"); req(p==len(calls)-1,"boundary trailing calls")

    for fam,rates,start in (("scrub_forward",gen.RATES,0),("scrub_reverse",tuple(-x for x in gen.RATES),gen.LONG_N)):
        calls=cases[fam]["calls"]; callbacks(cases[fam],calls); p=0; c(calls[p],"tape_mount",side="A",resume_frame=0,warm=None); p+=1
        if start: c(calls[p],"tape_seek",frame=start); p+=1
        for rate,count in zip(rates,gen.COUNTS):
            c(calls[p],"tape_set_rate",rate_q16_16=rate); p=service_seq(calls,p+1)
            remaining=count
            while remaining:
                n=min(128,remaining); c(calls[p],"tape_render",requested=n,rendered=n); remaining-=n; p+=1
        c(calls[p],"tape_unmount"); req(p==len(calls)-1,"scrub trailing calls")

    for fam,playing in (("side_playing",True),("side_idle",False)):
        calls=cases[fam]["calls"]; callbacks(cases[fam],calls); p=0; c(calls[p],"tape_mount",side="A",resume_frame=0,warm=None); p+=1
        if playing:
            c(calls[p],"tape_seek",frame=gen.LONG_N-1); p+=1; c(calls[p],"tape_set_rate",rate_q16_16=65536); p=service_seq(calls,p+1); c(calls[p],"tape_render",requested=2,rendered=1); p+=1; status(calls[p],True,False); p+=1
        else: c(calls[p],"tape_set_rate",rate_q16_16=0); p+=1
        c(calls[p],"tape_set_side",side="B",rate_q16_16=65536 if playing else 0); p+=1; tell(calls[p],0); p+=1; status(calls[p],False,False); p+=1; info(calls[p],gen.SIDE_B_N,False); p+=1
        if not playing: c(calls[p],"tape_set_rate",rate_q16_16=65536); p+=1
        c(calls[p],"tape_render",result=6,requested=1,rendered=0); p=service_seq(calls,p+1); c(calls[p],"tape_render",requested=1,rendered=1); p+=1; c(calls[p],"tape_unmount"); req(p==len(calls)-1,"side trailing calls")

    exp=expected_outputs(); verdict={"pass":True,"families":{}}
    for fam,name in OUTPUTS.items():
        req(fam in outputs,"missing output "+fam); ok=outputs[fam]==exp[fam]; verdict["families"][fam]={"match":ok,"expected_sha256":sha(exp[fam]),"actual_sha256":sha(outputs[fam]),"frames":len(outputs[fam])//4}; verdict["pass"] &= ok
    return verdict
