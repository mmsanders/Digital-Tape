#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ENGINE=ROOT/"engine"
BUILD=ROOT/"build"/"engine"/"src"
LIB=ROOT/"build"/"engine"/"libtape.a"
PKG=ROOT/"tests"/"embedded_readiness_draft8"
VERIFIER_TREE="46c8aa37f1f882e6a371fae7cdb5b96a28ada109"
VERIFIER_PUBLICATION="82847985cd41e2b4b2fc086079ead7e5f2f7669e"
IMPORT_COMMIT="7bdfddb73cfa8e2021719a506eb02ceeaf2663bb"
PRODUCT_BASE="92d6a3402d4908322c191bd3464011ae97f94114"
FORBIDDEN={"malloc","calloc","realloc","reallocarray","free","aligned_alloc","posix_memalign","memalign","valloc","pvalloc","strdup","strndup"}
PERMITTED={("dev_read","read","engine/src/dev.h"),("dev_write","write","engine/src/dev.h"),("dev_flush","flush","engine/src/dev.h")}
NODE=re.compile(r'node:\s*\{\s*title:\s*"([^"]+)"\s*label:\s*"([^"]*)"(.*?)\}',re.S)
EDGE=re.compile(r'edge:\s*\{\s*sourcename:\s*"([^"]+)"\s+targetname:\s*"([^"]+)"')
BYTES=re.compile(r'\\n(\d+)\s+bytes\s+\((static|dynamic|dynamic,bounded)\)')

class Fail(RuntimeError): pass

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def git(*args): return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()

def run(args,check=True,cwd=ROOT):
    p=subprocess.run(args,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if check and p.returncode: raise Fail(f"command failed ({p.returncode}): {' '.join(args)}\n{p.stdout}")
    return p.stdout

def version(tool):
    s=run([tool,"--version"],check=False).strip()
    if not s: raise Fail(f"missing version output: {tool}")
    return s.splitlines()[0]

def build(raw):
    out=[]
    for cmd in (["make","-C","engine","clean"],["make","-C","engine","all"]):
        out.append("$ "+" ".join(cmd)+"\n")
        p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        out.append(p.stdout)
        if p.returncode:
            (raw/"build.log").write_text("".join(out))
            raise Fail("product engine build failed")
    text="".join(out)
    (raw/"build.log").write_text(text)
    if "-fstack-usage" not in text or "-fcallgraph-info=su,da" not in text:
        raise Fail("normal product build did not emit required stack/callgraph metadata")
    if "-flto" in text: raise Fail("LTO present; complete equivalent per-object attribution not implemented")

def probe(raw):
    exe=raw/"instance-size-probe"
    cmd=[os.environ.get("CC","cc"),"-std=c99","-Iengine/include",str(PKG/"instance_size_probe.c"),str(LIB),"-o",str(exe)]
    p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (raw/"instance-size-probe.build.log").write_text("$ "+" ".join(cmd)+"\n"+p.stdout)
    if p.returncode: raise Fail("verifier-owned instance probe did not link")
    s=run([str(exe)]).strip()
    (raw/"instance-size-probe.output.txt").write_text(s+"\n")
    try: return int(s)
    except ValueError as e: raise Fail(f"bad instance probe output {s!r}") from e

def parse_sections(text):
    rows={}
    rx=re.compile(r"^\s*\[\s*(\d+)\]\s+(\S+)\s+(\S+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s*(.*)$")
    for line in text.splitlines():
        m=rx.match(line)
        if not m: continue
        rest=m.group(8).split()
        flags=rest[0] if rest and re.fullmatch(r"[A-Z]+",rest[0]) else ""
        rows[int(m.group(1))]={"name":m.group(2),"type":m.group(3),"size":int(m.group(6),16),"flags":flags}
    if not rows: raise Fail("could not parse readelf -SW")
    return rows

def parse_symbols(text):
    rows=[]
    rx=re.compile(r"^\s*\d+:\s+([0-9A-Fa-f]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*(.*)$")
    for line in text.splitlines():
        m=rx.match(line)
        if m: rows.append({"size":int(m.group(2)),"type":m.group(3),"ndx":m.group(6),"name":m.group(7).strip()})
    if not rows: raise Fail("could not parse readelf -sW")
    return rows

def data_sec(n):
    return not (n==".data.rel.ro" or n.startswith(".data.rel.ro.")) and (n==".data" or n.startswith(".data.") or n==".sdata" or n.startswith(".sdata."))
def bss_sec(n): return n==".bss" or n.startswith(".bss.") or n==".sbss" or n.startswith(".sbss.")
def ro_sec(n): return n==".rodata" or n.startswith(".rodata.") or n==".srodata" or n.startswith(".srodata.") or n==".data.rel.ro" or n.startswith(".data.rel.ro.")
def normsym(n):
    n=n.split("@",1)[0]
    return n[1:] if n.startswith("_") and not n.startswith("__") else n

def objects(raw):
    od=raw/"objects"; od.mkdir()
    src=sorted((ENGINE/"src").glob("*.c"))
    expected=[BUILD/(p.stem+".o") for p in src]
    actual=sorted(BUILD.glob("*.o"))
    if [x.name for x in expected]!=[x.name for x in actual]: raise Fail("engine object inventory mismatch")
    members=[x for x in run(["ar","t",str(LIB)]).splitlines() if x]
    (raw/"archive-members.txt").write_text("\n".join(members)+"\n")
    if members!=[x.name for x in expected]: raise Fail("archive member inventory mismatch")
    data=bss=ro=0; forbidden=[]; mutable=[]; common=[]; ro_count=0; undef=set(); defined=set(); census=[]
    for obj in expected:
        sec=run(["readelf","-SW",str(obj)])
        sym=run(["readelf","-sW",str(obj)])
        un=run(["nm","--undefined-only","--format=posix",str(obj)],check=False)
        de=run(["nm","--defined-only","--format=posix",str(obj)],check=False)
        sz=run(["size","-A","-d",str(obj)])
        rel=run(["objdump","-r",str(obj)],check=False)
        for suffix,text in [("readelf-sections",sec),("readelf-symbols",sym),("nm-u",un),("nm-defined",de),("size-A",sz),("objdump-r",rel)]:
            (od/f"{obj.name}.{suffix}.txt").write_text(text)
        sections=parse_sections(sec)
        d=sum(x["size"] for x in sections.values() if data_sec(x["name"]))
        b=sum(x["size"] for x in sections.values() if bss_sec(x["name"]))
        r=sum(x["size"] for x in sections.values() if ro_sec(x["name"]))
        data+=d; bss+=b; ro+=r
        census.append({"object":obj.name,"data_bytes":d,"bss_bytes":b,"rodata_bytes":r,"sections":[{"index":i,**x} for i,x in sorted(sections.items())]})
        for line in un.splitlines():
            p=line.split()
            if len(p)>=2:
                name=normsym(p[0]); undef.add(name)
                if name in FORBIDDEN: forbidden.append({"object":obj.name,"symbol":name})
        for line in de.splitlines():
            p=line.split()
            if len(p)>=2 and p[1] in {"T","t"}: defined.add(p[0])
        for s in parse_symbols(sym):
            if s["ndx"]=="UND": continue
            if s["ndx"]=="COM":
                common.append({"object":obj.name,"symbol":s["name"],"section":"COMMON","size":s["size"]}); continue
            if s["type"] not in {"OBJECT","TLS"}: continue
            try: idx=int(s["ndx"])
            except ValueError: continue
            q=sections.get(idx)
            if q is None: raise Fail(f"{obj.name}: missing section {idx} for {s['name']}")
            if "A" not in q["flags"]: continue
            readonly=ro_sec(q["name"]) or "W" not in q["flags"]
            if readonly: ro_count+=1
            else: mutable.append({"object":obj.name,"symbol":s["name"],"type":s["type"],"section":q["name"],"size":s["size"]})
    (raw/"per-object-section-census.json").write_text(json.dumps(census,indent=2,sort_keys=True)+"\n")
    (raw/"undefined-symbols.json").write_text(json.dumps(sorted(undef),indent=2)+"\n")
    (raw/"engine-state-symbols.json").write_text(json.dumps({"mutable_symbols":mutable,"common_symbols":common,"read_only_object_symbol_count":ro_count},indent=2,sort_keys=True)+"\n")
    return {"objects":expected,"data":data,"bss":bss,"rodata":ro,"forbidden":sorted(forbidden,key=lambda x:(x["object"],x["symbol"])),"mutable":sorted(mutable,key=lambda x:(x["object"],x["symbol"])),"common":sorted(common,key=lambda x:(x["object"],x["symbol"])),"ro_count":ro_count,"undef":undef,"defined":defined}

def strip_c(text):
    out=list(text); i=0; state="code"; quote=""
    while i<len(out):
        c=out[i]; n=out[i+1] if i+1<len(out) else ""
        if state=="code":
            if c=="/" and n=="/": out[i]=out[i+1]=" "; i+=2; state="line"; continue
            if c=="/" and n=="*": out[i]=out[i+1]=" "; i+=2; state="block"; continue
            if c in {'"',"'"}: quote=c; out[i]=" "; i+=1; state="str"; continue
            i+=1
        elif state=="line":
            if c=="\n": state="code"
            else: out[i]=" "
            i+=1
        elif state=="block":
            if c=="*" and n=="/": out[i]=out[i+1]=" "; i+=2; state="code"
            else:
                if c!="\n": out[i]=" "
                i+=1
        else:
            if c=="\\":
                out[i]=" "
                if i+1<len(out):
                    if out[i+1]!="\n": out[i+1]=" "
                    i+=2
                else: i+=1
            elif c==quote: out[i]=" "; i+=1; state="code"
            else:
                if c!="\n": out[i]=" "
                i+=1
    return "".join(out)

def sources(raw):
    paths=sorted(list((ENGINE/"src").glob("*.c"))+list((ENGINE/"src").glob("*.h"))+list((ENGINE/"include").glob("*.h")))
    inv=[]; stripped={}
    for p in paths:
        rel=p.relative_to(ROOT).as_posix(); inv.append({"path":rel,"sha256":sha(p)}); stripped[rel]=strip_c(p.read_text())
    (raw/"engine-source-sha256.json").write_text(json.dumps(inv,indent=2,sort_keys=True)+"\n")
    return inv,stripped

def indirect(raw,stripped,obj):
    permitted=[]; violations=[]; ambiguous=[]; members=[]
    typedefs=set()
    for code in stripped.values():
        typedefs.update(m.group(1) for m in re.finditer(r"\btypedef\b[^;]{0,800}\(\s*\*\s*([A-Za-z_]\w*)\s*\)\s*\(",code,re.S))
    fpvars=set()
    if typedefs:
        rx=re.compile(r"\b(?:"+"|".join(re.escape(x) for x in sorted(typedefs))+r")\s+([A-Za-z_]\w*)\b")
        for code in stripped.values(): fpvars.update(m.group(1) for m in rx.finditer(code))
    for path,code in stripped.items():
        for m in re.finditer(r"(?:->|\.)\s*([A-Za-z_]\w*)\s*\(",code):
            member=m.group(1); line=code.count("\n",0,m.start())+1
            prev=list(re.finditer(r"\b(dev_read|dev_write|dev_flush)\s*\(",code[:m.start()]))
            wrapper=prev[-1].group(1) if prev else None
            row={"path":path,"line":line,"member":member,"wrapper":wrapper}; members.append(row)
            if (wrapper,member,path) in PERMITTED: permitted.append(row)
            else: violations.append({**row,"expression":f"member-call {member}()"})
        for var in sorted(fpvars):
            for m in re.finditer(rf"\b{re.escape(var)}\s*\(",code):
                violations.append({"path":path,"line":code.count("\n",0,m.start())+1,"expression":f"function-pointer variable {var}()"})
    # Function-address relocation backstop.
    for o in obj["objects"]:
        section=None
        for line in (raw/"objects"/f"{o.name}.objdump-r.txt").read_text().splitlines():
            m=re.match(r"RELOCATION RECORDS FOR \[(.+)\]:",line)
            if m: section=m.group(1); continue
            m=re.match(r"^[0-9A-Fa-f]+\s+R_\S+\s+(\S+)",line)
            if not m or not section: continue
            if not any(section.startswith(x) for x in (".data",".rodata",".sdata",".init_array",".fini_array",".ctors",".dtors")): continue
            target=re.sub(r"[+-]0x[0-9A-Fa-f]+$","",m.group(1))
            if target.startswith(".text") or target in obj["defined"]:
                violations.append({"object":o.name,"section":section,"target":m.group(1),"expression":"engine function address stored in data"})
    uniq={(x["wrapper"],x["member"],x["path"]):x for x in permitted}
    permitted=[uniq[k] for k in sorted(uniq)]
    seen={(x["wrapper"],x["member"],x["path"]) for x in permitted}
    if seen!=PERMITTED: ambiguous.append({"reason":"exact frozen callback-site set not reproduced","observed":sorted([list(x) for x in seen])})
    report={"analysis_complete":not ambiguous,"function_pointer_typedefs":sorted(typedefs),"function_pointer_variables":sorted(fpvars),"member_call_expressions":members,"permitted_callback_sites":permitted,"violations":violations,"ambiguous_or_unresolved":ambiguous}
    (raw/"indirect-call-scan.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    return report

def stack(raw,obj,ind):
    sd=raw/"stack"; sd.mkdir()
    cis=sorted(BUILD.glob("*.ci")); sus=sorted(BUILD.glob("*.su"))
    expected=[x.stem for x in obj["objects"]]; unresolved=[]
    if [x.stem for x in cis]!=expected: unresolved.append({"reason":"callgraph inventory mismatch","expected":expected,"actual":[x.stem for x in cis]})
    if [x.stem for x in sus]!=expected: unresolved.append({"reason":"stack-usage inventory mismatch","expected":expected,"actual":[x.stem for x in sus]})
    frames={}; kinds={}; origins={}; edges={}; declared=set()
    for p in cis:
        shutil.copy2(p,sd/p.name); text=p.read_text(errors="replace")
        for m in NODE.finditer(text):
            name,label,tail=m.group(1),m.group(2),m.group(3)
            if "ellipse" in tail: declared.add(name)
            b=BYTES.search(label)
            if b:
                if name in origins and origins[name]!=p.name: unresolved.append({"reason":"duplicate callgraph title","function":name,"objects":[origins[name],p.name]})
                frames[name]=max(frames.get(name,0),int(b.group(1))); kinds[name]=b.group(2); origins[name]=p.name
        for e in EDGE.finditer(text): edges.setdefault(e.group(1),set()).add(e.group(2))
    for p in sus: shutil.copy2(p,sd/p.name)
    if not frames: unresolved.append({"reason":"no function frames parsed"})
    dynamic=sorted(n for n,k in kinds.items() if k=="dynamic")
    external=[]
    for src,targets in sorted(edges.items()):
        for dst in sorted(targets):
            if dst in frames: continue
            nd=normsym(dst)
            if dst in obj["defined"] or nd in obj["defined"]: unresolved.append({"edge":f"{src} -> {dst}","reason":"engine target lacks frame"})
            elif nd in obj["undef"] or dst in declared: external.append({"caller":src,"callee":dst})
            else: unresolved.append({"edge":f"{src} -> {dst}","reason":"unclassified callgraph target"})
    colour={}; cycles=[]
    def walk(n,path):
        colour[n]=1; path.append(n)
        for q in sorted(edges.get(n,())):
            if q not in frames: continue
            if colour.get(q,0)==1: cycles.append(path[path.index(q):]+[q])
            elif colour.get(q,0)==0: walk(q,path)
        path.pop(); colour[n]=2
    for n in sorted(frames):
        if colour.get(n,0)==0: walk(n,[])
    memo={}
    def cost(n,active):
        if n in memo:return memo[n]
        if n in active:return (0,[n])
        active.add(n); best=0; chain=[]
        for q in sorted(edges.get(n,())):
            if q not in frames: continue
            c,ch=cost(q,active)
            if c>best:best,chain=c,ch
        active.remove(n); memo[n]=(frames[n]+best,[n]+chain); return memo[n]
    maxb=0; maxp=[]
    if not cycles:
        for n in sorted(frames):
            c,ch=cost(n,set())
            if c>maxb:maxb,maxp=c,ch
    excluded=[{"wrapper":x["wrapper"],"member":x["member"],"path":x["path"]} for x in ind["permitted_callback_sites"]]
    report={"analysis_complete":not dynamic and not unresolved and not cycles,"max_path_bytes":maxb,"max_path":maxp,"dynamic_or_unknown_frames":dynamic,"unresolved_internal_edges":unresolved,"recursive_cycles":cycles,"excluded_external_callback_edges":excluded,"external_direct_leaf_edges":external,"function_frames":[{"function":n,"bytes":frames[n],"kind":kinds[n],"origin":origins[n]} for n in sorted(frames)]}
    (raw/"stack-analysis.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    return report

def manifest(root):
    rows=[]
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name!="manifest.json": rows.append({"path":p.relative_to(root).as_posix(),"bytes":p.stat().st_size,"sha256":sha(p)})
    (root/"manifest.json").write_text(json.dumps({"files":rows},indent=2,sort_keys=True)+"\n")

def main():
    a=argparse.ArgumentParser(); a.add_argument("--evidence",type=Path,required=True); ns=a.parse_args()
    ev=ns.evidence if ns.evidence.is_absolute() else ROOT/ns.evidence
    if ev.exists(): shutil.rmtree(ev)
    raw=ev/"raw"; raw.mkdir(parents=True)
    try:
        vt=git("rev-parse","HEAD:tests/embedded_readiness_draft8")
        if vt!=VERIFIER_TREE: raise Fail(f"verifier tree mismatch {vt}")
        head=git("rev-parse","HEAD"); pc=os.environ.get("PRODUCT_COMMIT") or head
        if pc!=head: raise Fail(f"workspace/head mismatch PRODUCT_COMMIT={pc} HEAD={head}")
        pt=git("rev-parse","HEAD^{tree}")
        versions={"cc":version(os.environ.get("CC","cc")),"nm":version("nm"),"readelf":version("readelf"),"size":version("size"),"objdump":version("objdump"),"ar":version("ar"),"make":version("make"),"python_source_scanner":sys.version.splitlines()[0]}
        (raw/"tool-versions.json").write_text(json.dumps(versions,indent=2,sort_keys=True)+"\n")
        build(raw); inst=probe(raw); obj=objects(raw); inv,stripped=sources(raw); ind=indirect(raw,stripped,obj); st=stack(raw,obj,ind)
        evidence={"format":"WP13-EMBEDDED-EVIDENCE-1","provenance":{"product_commit":pc,"product_tree":pt,"product_base":PRODUCT_BASE,"verifier_import_commit":IMPORT_COMMIT,"verifier_publication":VERIFIER_PUBLICATION,"verifier_tree":vt,"engine_makefile_sha256":sha(ENGINE/"Makefile"),"tool_versions":versions,"engine_source_inventory_count":len(inv),"engine_object_count":len(obj["objects"])},"ram":{"data_bytes":obj["data"],"bss_bytes":obj["bss"],"tape_instance_size_bytes":inst,"summed_bytes":obj["data"]+obj["bss"]+inst},"rodata":{"rodata_bytes":obj["rodata"]},"allocator":{"scan_complete":True,"forbidden_references":obj["forbidden"]},"stack":st,"indirect_calls":{"analysis_complete":ind["analysis_complete"],"permitted_callback_sites":[{"wrapper":x["wrapper"],"member":x["member"],"path":x["path"]} for x in ind["permitted_callback_sites"]],"violations":ind["violations"],"ambiguous_or_unresolved":ind["ambiguous_or_unresolved"]},"engine_state":{"symbol_scan_complete":True,"mutable_symbols":obj["mutable"],"common_symbols":obj["common"],"read_only_object_symbol_count":obj["ro_count"]}}
        ep=ev/"evidence.json"; rp=ev/"result.json"; ep.write_text(json.dumps(evidence,indent=2,sort_keys=True)+"\n")
        cmd=[sys.executable,str(PKG/"runner.py"),"--evidence",str(ep),"--result",str(rp)]
        rr=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (ev/"runner.log").write_text("$ "+" ".join(cmd)+"\n"+rr.stdout)
        prov={"product_commit":pc,"product_tree":pt,"product_base":PRODUCT_BASE,"import_commit":IMPORT_COMMIT,"verifier_publication":VERIFIER_PUBLICATION,"verifier_tree":vt,"evidence_sha256":sha(ep),"result_sha256":sha(rp) if rp.is_file() else "MISSING","runner_exit":rr.returncode,"raw_build_log_sha256":sha(raw/"build.log"),"source_inventory_sha256":sha(raw/"engine-source-sha256.json")}
        (ev/"PROVENANCE.json").write_text(json.dumps(prov,indent=2,sort_keys=True)+"\n"); manifest(ev)
        print(f"product_commit={pc}\nproduct_tree={pt}\nverifier_import_commit={IMPORT_COMMIT}\nverifier_tree={vt}")
        print(f"ram_data_bytes={obj['data']}\nram_bss_bytes={obj['bss']}\ntape_instance_size_bytes={inst}\nram_summed_bytes={obj['data']+obj['bss']+inst}\nrodata_bytes={obj['rodata']}")
        print(f"allocator_forbidden_refs={len(obj['forbidden'])}\nstack_max_path_bytes={st['max_path_bytes']}\nstack_max_path={' -> '.join(st['max_path'])}\nstack_dynamic_or_unknown={len(st['dynamic_or_unknown_frames'])}\nstack_unresolved_internal_edges={len(st['unresolved_internal_edges'])}\nstack_recursive_cycles={len(st['recursive_cycles'])}")
        print(f"indirect_permitted={len(ind['permitted_callback_sites'])}\nindirect_violations={len(ind['violations'])}\nindirect_ambiguous={len(ind['ambiguous_or_unresolved'])}\nmutable_symbols={len(obj['mutable'])}\ncommon_symbols={len(obj['common'])}\nread_only_object_symbol_count={obj['ro_count']}")
        print(f"evidence_sha256={prov['evidence_sha256']}\nresult_sha256={prov['result_sha256']}\nrunner_exit={rr.returncode}")
        return rr.returncode
    except Exception as e:
        (ev/"COLLECTION-FAILURE.txt").write_text(f"{type(e).__name__}: {e}\n"); manifest(ev); print(f"COLLECTION FAILURE: {e}",file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
