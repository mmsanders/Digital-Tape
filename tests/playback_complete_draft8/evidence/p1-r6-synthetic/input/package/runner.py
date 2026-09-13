#!/usr/bin/env python3
"""Execute an adapter and retain hash-bound P1-R6 playback evidence."""
from __future__ import annotations
import argparse,json,shlex,shutil,subprocess,tempfile
from pathlib import Path
import oracle
HERE=Path(__file__).resolve().parent
def shafile(p): return oracle.shafile(p)
def hashes(root): return {p.relative_to(root).as_posix():shafile(p) for p in sorted(root.rglob("*")) if p.is_file() and p.name!="manifest.json"}
def fresh(p):
    if p.exists():
        if not p.is_dir() or any(p.iterdir()): raise oracle.VerificationError("evidence destination is nonempty or not a directory")
    else:p.mkdir(parents=True)
def copy_package(dst):
    for n in ("package.json","generate_fixture.py","oracle.py","runner.py","replay.py","ADAPTER.md","COVERAGE.md","README.md"):
        shutil.copy2(HERE/n,dst/n)
    for d in ("spec","input","fixtures","candidate"): shutil.copytree(HERE/d,dst/d)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--adapter-cmd",required=True); ap.add_argument("--adapter-kind",choices=("synthetic","product"),required=True); ap.add_argument("--adapter-id",required=True); ap.add_argument("--adapter-source",required=True); ap.add_argument("--adapter-build",required=True); ap.add_argument("--adapter-timeout-seconds",type=float,default=90); ap.add_argument("--source-commit",required=True); ap.add_argument("--source-tree",required=True); ap.add_argument("--evidence-dir",required=True); a=ap.parse_args()
    try:
        oracle.authenticate(); ev=Path(a.evidence_dir); fresh(ev)
        for label,v in (("cmd",a.adapter_cmd),("id",a.adapter_id),("source",a.adapter_source),("build",a.adapter_build),("commit",a.source_commit),("tree",a.source_tree)): oracle.req(v.strip(),"missing provenance "+label)
        oracle.req(a.adapter_timeout_seconds>0,"bad timeout")
    except (oracle.VerificationError,OSError) as e: print("RUNNER FAIL:",e); return 2
    (ev/"output").mkdir(); (ev/"input/package").mkdir(parents=True); copy_package(ev/"input/package")
    execution={"outcome":"exited","exit_code":None,"timeout_seconds":a.adapter_timeout_seconds}
    with tempfile.TemporaryDirectory(prefix="p1-r6-playback-") as td_s:
        td=Path(td_s); out=td/"out"; out.mkdir()
        cmd=shlex.split(a.adapter_cmd)+["--fixture-dir",str(HERE/"fixtures"),"--out-dir",str(out)]
        try:
            p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=a.adapter_timeout_seconds); execution["exit_code"]=p.returncode; stdout,stderr=p.stdout,p.stderr; exit_text=f"{p.returncode}\n"
        except subprocess.TimeoutExpired as e:
            execution["outcome"]="timeout"; stdout=e.stdout or b""; stderr=e.stderr or b""; exit_text="TIMEOUT\n"
        (ev/"output/stdout.txt").write_bytes(stdout); (ev/"output/stderr.txt").write_bytes(stderr); (ev/"output/adapter-exit.txt").write_text(exit_text)
        result={"pass":False,"families":{}}
        if execution["outcome"]=="timeout": result["error"]="adapter timeout"
        elif execution["exit_code"]!=0: result["error"]=f"adapter exit {execution['exit_code']}"
        else:
            needed=["observation.json",*oracle.OUTPUTS.values()]; missing=[n for n in needed if not (out/n).is_file()]
            if missing: result["error"]="missing outputs: "+", ".join(missing)
            else:
                for n in needed: shutil.copy2(out/n,ev/"output"/n)
                try:
                    obs=json.loads((out/"observation.json").read_text()); oracle.req(obs.get("adapter",{}).get("kind")==a.adapter_kind,"adapter kind mismatch"); oracle.req(obs.get("adapter",{}).get("id")==a.adapter_id,"adapter id mismatch")
                    outputs={f:(out/n).read_bytes() for f,n in oracle.OUTPUTS.items()}; result=oracle.validate(obs,outputs); result["error"]=None
                except (oracle.VerificationError,ValueError,KeyError,json.JSONDecodeError) as e: result={"pass":False,"families":{},"error":str(e)}
        (ev/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    sf=Path(a.adapter_source); source_file={"path":str(sf),"sha256":shafile(sf)} if sf.is_file() else None
    manifest={"schema":"playback-complete-draft8-evidence-v1","assignment":"P1-R6-V","source_commit":a.source_commit,"source_tree":a.source_tree,"package_manifest_sha256":shafile(HERE/"package.json"),"oracle_sha256":shafile(HERE/"oracle.py"),"runner_sha256":shafile(HERE/"runner.py"),"replay_sha256":shafile(HERE/"replay.py"),"adapter":{"kind":a.adapter_kind,"id":a.adapter_id,"command":a.adapter_cmd,"source":a.adapter_source,"source_file":source_file,"build":a.adapter_build},"execution":execution,"files":hashes(ev)}
    (ev/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n"); print("PASS" if result["pass"] else "FAIL","P1-R6 playback evidence",ev); return 0 if result["pass"] else 1
if __name__=="__main__": raise SystemExit(main())
