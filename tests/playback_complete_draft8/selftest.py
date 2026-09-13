#!/usr/bin/env python3
"""P1-R6 package self-test with targeted named negative controls."""
from __future__ import annotations
import copy,json,shutil,subprocess,sys,tempfile
from pathlib import Path
import generate_fixture as gen, oracle
HERE=Path(__file__).resolve().parent; PRIOR=HERE.parent/"playback_draft8"
def fail(label,fn):
    try: fn()
    except (oracle.VerificationError,AssertionError,ValueError,KeyError,OSError,json.JSONDecodeError): print("CAUGHT",label); return
    raise AssertionError("negative control escaped: "+label)
def validate(obs,outs):
    r=oracle.validate(obs,outs)
    if not r["pass"]: raise oracle.VerificationError("PCM mismatch")
def runner_cmd(ev,cmd=None,source=None,timeout="3"):
    source=source or str(HERE/"_synthetic_adapter.py"); cmd=cmd or f"{sys.executable} {source}"
    return [sys.executable,str(HERE/"runner.py"),"--adapter-cmd",cmd,"--adapter-kind","synthetic","--adapter-id","verifier-p1-r6-public-contract-model-v1","--adapter-source",source,"--adapter-build","python3 source; verifier self-test","--adapter-timeout-seconds",timeout,"--source-commit","SELFTEST-DECLARED","--source-tree","SELFTEST-DECLARED","--evidence-dir",str(ev)]
def main():
    oracle.authenticate(); print("PASS authenticated DRAFT-8/WP-08/package and deterministic regeneration")
    subprocess.run([sys.executable,str(PRIOR/"selftest.py")],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE); print("PASS retained P1-R4 three-family + 18-control self-test")
    with tempfile.TemporaryDirectory(prefix="p1-r6-selftest-") as td_s:
        td=Path(td_s); out=td/"out"; out.mkdir(); subprocess.run([sys.executable,str(HERE/"_synthetic_adapter.py"),"--fixture-dir",str(HERE/"fixtures"),"--out-dir",str(out)],check=True,stdout=subprocess.PIPE)
        obs=json.loads((out/"observation.json").read_text()); outs={f:(out/n).read_bytes() for f,n in oracle.OUTPUTS.items()}; validate(obs,outs); print("PASS ten-family synthetic public-call/callback observation")
        def mut(label,edit):
            b=copy.deepcopy(obs); edit(b); fail(label,lambda:validate(b,outs))
        mut("empty-check ordering",lambda b:b["cases"]["empty_zero"]["calls"][4].update(at_end=False))
        mut("zero-rate endpoint drift",lambda b:b["cases"]["nonempty_zero"]["calls"][4].update(frame=1235))
        mut("INT32_MAX overshoot",lambda b:b["cases"]["one_intmax"]["calls"][4].update(frame=32768))
        mut("reverse-from-zero skipped frame",lambda b:b["cases"]["reverse_zero"]["calls"][3].update(rendered=0))
        mut("INT32_MIN position wrap",lambda b:b["cases"]["intmin"]["calls"][5].update(frame=0xffffffff))
        mut("scrub signed Q16.16 rate",lambda b:next(x for x in b["cases"]["scrub_forward"]["calls"][2:] if x["call"]=="tape_set_rate").update(rate_q16_16=297096))
        mut("scrub render count",lambda b:b["cases"]["scrub_forward"]["calls"][3].update(requested=127,rendered=127))
        mut("reverse scrub start",lambda b:b["cases"]["scrub_reverse"]["calls"][1].update(frame=gen.LONG_N-1))
        mut("service time advancing cadence",lambda b:b["cases"]["scrub_forward"]["calls"][2].update(more_work=True))
        mut("side switch refused while Playing",lambda b:b["cases"]["side_playing"]["calls"][6].update(result=5))
        mut("side position retained",lambda b:b["cases"]["side_playing"]["calls"][7].update(frame=gen.LONG_N))
        mut("side endpoint flag retained",lambda b:b["cases"]["side_playing"]["calls"][8].update(at_end=True))
        mut("side warm flag retained",lambda b:b["cases"]["side_playing"]["calls"][9].update(warm_start_used=True))
        mut("side rate lost",lambda b:b["cases"]["side_playing"]["calls"][6].update(rate_q16_16=0))
        bad=dict(outs); bad["side_playing"]=gen.pcm((gen.frame(gen.LONG_N-1),gen.frame(0))); fail("stale Side-A PCM after switch",lambda:validate(obs,bad))
        mut("callback I/O during render",lambda b:b["cases"]["side_idle"]["callbacks"].append({"call_index":6,"op":"read","lba":gen.BASE,"count":1,"rc":0}))

        ev=td/"evidence"; subprocess.run(runner_cmd(ev),check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE); subprocess.run([sys.executable,str(HERE/"replay.py"),str(ev)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE); print("PASS saved synthetic evidence offline replay")
        relabel=td/"relabel"; shutil.copytree(ev,relabel); p=relabel/"manifest.json"; m=json.loads(p.read_text()); m["adapter"]["kind"]="product"; p.write_text(json.dumps(m)); assert subprocess.run([sys.executable,str(HERE/"replay.py"),str(relabel)],stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode!=0; print("CAUGHT evidence kind relabel")
        changed=td/"changed"; shutil.copytree(ev,changed); p=changed/"output/scrub-forward.pcm"; d=bytearray(p.read_bytes()); d[0]^=1; p.write_bytes(d); assert subprocess.run([sys.executable,str(HERE/"replay.py"),str(changed)],stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode!=0; print("CAUGHT evidence tamper")
        nonzero=td/"nonzero.py"; nonzero.write_text("import sys;sys.exit(7)\n"); nev=td/"nonzero-ev"; assert subprocess.run(runner_cmd(nev,f"{sys.executable} {nonzero}",str(nonzero)),stdout=subprocess.PIPE).returncode==1; assert (nev/"output/adapter-exit.txt").read_text()=="7\n"; print("CAUGHT nonzero exit with diagnostics")
        sleeper=td/"sleep.py"; sleeper.write_text("import time;print('start',flush=True);time.sleep(2)\n"); tev=td/"timeout-ev"; assert subprocess.run(runner_cmd(tev,f"{sys.executable} {sleeper}",str(sleeper),"0.05"),stdout=subprocess.PIPE).returncode==1; assert (tev/"output/adapter-exit.txt").read_text()=="TIMEOUT\n"; print("CAUGHT timeout with diagnostics")
        retained=td/"retained"; retained.mkdir(); s=retained/"sentinel"; s.write_bytes(b"KEEP"); assert subprocess.run(runner_cmd(retained),stdout=subprocess.PIPE).returncode==2 and s.read_bytes()==b"KEEP"; print("PASS nonempty destination retained")
    saved=HERE/"evidence/p1-r6-synthetic"
    if saved.exists(): subprocess.run([sys.executable,str(HERE/"replay.py"),str(saved)],check=True); print("PASS checked-in synthetic replay")
    print("SELFTEST PASS: 10 families; 16 new behavioral controls; retained 18-control P1-R4 package; evidence controls")
    return 0
if __name__=="__main__": raise SystemExit(main())
