#!/usr/bin/env python3
"""Run VT8-001 public-operation observations against an external mechanical adapter."""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path
from oracle import Media, check, make_cases, HASHES

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--adapter',type=Path,required=True)
    ap.add_argument('--log',type=Path,required=True)
    ap.add_argument('--timeout',type=int,default=60)
    a=ap.parse_args(); adapter=a.adapter.resolve()
    if not adapter.is_file(): ap.error('adapter executable missing')
    a.log.parent.mkdir(parents=True,exist_ok=True)
    failures=0
    with a.log.open('w') as log, tempfile.TemporaryDirectory(prefix='vt8-ops-') as td:
        log.write(json.dumps({'kind':'provenance','adapter':str(adapter),
            'adapter_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest(),
            'spec_hashes':HASHES,'cases':2})+'\n')
        for c in make_cases():
            inp=Path(td)/(c.id+'.in'); out=Path(td)/(c.id+'.out'); inp.write_bytes(c.pre.encode())
            rec={'id':c.id,'operation':c.operation,'pre_sha256':hashlib.sha256(inp.read_bytes()).hexdigest()}
            try:
                r=subprocess.run([str(adapter),c.id,str(inp),str(out)],capture_output=True,text=True,timeout=a.timeout)
                rec.update(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
                if r.returncode!=0 or not out.is_file(): errs=['adapter failed or omitted output media']; events=[]
                else:
                    obs=json.loads(r.stdout); events=obs['events']; post=Media.decode(out.read_bytes())
                    errs=check(c,post,events); rec['post_sha256']=hashlib.sha256(out.read_bytes()).hexdigest()
            except Exception as e:
                errs=['adapter observation malformed: '+str(e)]; events=[]
            rec['errors']=errs; rec['status']='FAIL' if errs else 'PASS'; rec['events']=events
            log.write(json.dumps(rec)+'\n'); log.flush(); failures += bool(errs)
            if errs: print(c.id+': FAIL: '+'; '.join(errs))
        print(f'2 cases; {failures} failed; see {a.log}')
    return 1 if failures else 0
if __name__=='__main__': raise SystemExit(main())
