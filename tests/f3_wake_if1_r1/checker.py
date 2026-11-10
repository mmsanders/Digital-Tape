"""Bound single-build CLI/flags tests; report-layout/multi-build scopes reserved."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from checker_cases import cases,fixture,SHA

GUARD = r"""
import os,sys,types,runpy
from pathlib import Path
script=Path(sys.argv[1]).resolve();bundle=Path(sys.argv[2]).resolve();report=Path(sys.argv[3]).resolve()
serial=types.ModuleType('serial')
def noport(*a,**k):raise RuntimeError('AUDIT_VIOLATION: physical port forbidden')
serial.Serial=noport;serial.SerialException=RuntimeError;sys.modules['serial']=serial
sys.path.insert(0,str(script.parent));sys.argv=[str(script),'--offline',str(bundle),'--out',str(report)]
def audit(event,args):
 if event in ('socket.__new__','socket.connect','subprocess.Popen','os.system'):
  print('AUDIT_VIOLATION '+event,file=sys.stderr);raise RuntimeError('offline checker side effect')
 if event=='open' and not isinstance(args[0],int):
  p=Path(args[0]).resolve();mode=args[1];flags=args[2] or 0;write=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)) or isinstance(mode,str) and any(c in mode for c in 'wax+')
  if write:allowed=p==report and bool(flags&os.O_EXCL)
  else:allowed=p==script or bundle in p.parents or Path(sys.base_prefix) in p.parents or p.suffix in ('.py','.pyc','.pyd','.dll','.so')
  if not allowed:
   print('AUDIT_VIOLATION file '+str(p),file=sys.stderr);raise RuntimeError('offline file boundary')
sys.addaudithook(audit);runpy.run_path(str(script),run_name='__main__')
"""

def materialize(d,m,files):
 d.mkdir(parents=True,exist_ok=False)
 for name,raw in files.items():
  p=d/name;assert d.resolve() in p.resolve().parents;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
 m['files']=[dict(path=k,sha256=SHA(v),bytes=len(v)) for k,v in sorted(files.items())]
 (d/'manifest.json').write_text(json.dumps(m,sort_keys=True),encoding='utf-8')

def snapshot(d):return {str(p.relative_to(d)):SHA(p.read_bytes()) for p in d.rglob('*') if p.is_file()}

def run(checker,out):
 guard=out/'offline_guard.py';guard.write_text(GUARD,encoding='utf-8');obs=[]
 for c in cases():
  m,f=fixture(**c['setup']);c['edit'](m,f);bundle=out/c['name'];materialize(bundle,m,f);before=snapshot(bundle);report=out/(c['name']+'.json')
  q=subprocess.run([sys.executable,'-B',str(guard.resolve()),str(checker.resolve()),str(bundle.resolve()),str(report.resolve())],capture_output=True,text=True)
  try:r=json.loads(report.read_text());valid=True
  except (ValueError,OSError):r={};valid=False
  good=q.returncode==c['exit'] and valid and r.get('accepted') is False and 'Traceback' not in q.stderr and 'AUDIT_VIOLATION' not in q.stderr and snapshot(bundle)==before
  if c['reason']:good=good and c['reason'] in json.dumps(r)
  # This flag reflects declared fixture provenance, never an actually performed check.
  want_physical=m['session']['kind']=='physical' and any(o['provenance']=='actual' for o in m['observations'])
  good=good and isinstance(r.get('physical_run'),bool) and (want_physical or r['physical_run'] is False)
  if want_physical and c['exit'] in (0,1):good=good and r['physical_run'] is True
  obs.append(dict(case=c['name'],expected_exit=c['exit'],exit=q.returncode,passed=good,report=r,stderr=q.stderr[-500:]))
 # Exclusive output and inside-bundle usage are explicitly inherited from BE1.
 for name,inside in [('existing-output',False),('output-inside-bundle',True)]:
  m,f=fixture(provenance='simulated',session='simulation');bundle=out/name;materialize(bundle,m,f);report=bundle/'REPORT.json' if inside else out/(name+'.json');report.write_bytes(b'SENTINEL') if not inside else None
  q=subprocess.run([sys.executable,'-B',str(guard.resolve()),str(checker.resolve()),str(bundle.resolve()),str(report.resolve())],capture_output=True,text=True)
  good=q.returncode==64 and (not report.exists() if inside else report.read_bytes()==b'SENTINEL') and 'AUDIT_VIOLATION' not in q.stderr
  obs.append(dict(case=name,expected_exit=64,exit=q.returncode,passed=good))
 return obs

def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--selftest',action='store_true');g.add_argument('--checker',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 if a.selftest:
  obs=[]
  for c in cases():
   m,f=fixture(**c['setup']);c['edit'](m,f);materialize(a.out/c['name'],m,f)
   assert all(SHA((a.out/c['name']/x['path']).read_bytes())==x['sha256'] for x in m['files'])
   obs.append(dict(case=c['name'],expected_exit=c['exit'],passed=True))
  assert any(c['exit']==0 for c in cases()) and any(c['exit']==1 for c in cases()) and any(c['exit']==2 for c in cases())
 else:obs=run(a.checker,a.out)
 result=dict(mode='fixture-materialization-only' if a.selftest else 'actual-single-build-offline-CLI',cases=obs,passed=all(x['passed'] for x in obs),candidate_executed=not a.selftest,accepted=False,physical_run=False,reserved=['multi-build-association','new-state-precedence-and-report-layout','clock-changed-host-simulation-seam','production/control-ELF-symbol-proof'])
 (a.out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='cases'}));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
