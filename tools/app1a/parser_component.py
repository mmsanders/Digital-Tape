#!/usr/bin/env python3
"""Software498 transport: fixed independent reports -> actual production modules.

No device/query journal is fabricated: query matrix rows supply report bytes only.
The unchanged independent parser predicates judge those bytes. This is pure parser
evidence, never execution of the matrix's OS/device/continuation observations.
"""
import argparse,hashlib,importlib.util,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/wp15_app1a_r1'))
import cases,parser_runner

def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--adapter',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);start=time.monotonic()
 rows=cases.corpus()
 # The extension imports its own immutable prior oracle in isolation.
 q=load('query_oracle','tests/wp15_boundary_query_r1/oracle.py')
 # cases.py uses `from oracle import PHASES`; isolate that import from APP cases.
 prior=sys.modules.get('oracle');sys.modules['oracle']=q
 qm=load('query_cases','tests/wp15_boundary_query_r1/cases.py')
 if prior is None:del sys.modules['oracle']
 else:sys.modules['oracle']=prior
 query=[]
 for c in qm.matrix():
  parsed=q.parse_report(bytes.fromhex(c['report_hex']),c['version'],c['nonce'],c['exit'])
  query.append(dict(name='query-report:'+c['id'],tool='tapectl make',version=c['version'],nonce=c['nonce'],exit=c['exit'],folders=[],pair=False,raw_hex=c['report_hex'],valid=parsed is not None,message=list(q.message(c['exit'],parsed))))
 failures=[];counts={}
 for name,rs in [('app',rows),('query-report',query)]:
  stdin=(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in rs)).encode()
  p=subprocess.run([a.adapter],input=stdin,capture_output=True)
  (out/(name+'-stdin.jsonl')).write_bytes(stdin);(out/(name+'-stdout.jsonl')).write_bytes(p.stdout);(out/(name+'-stderr.txt')).write_bytes(p.stderr)
  got=[json.loads(l) for l in p.stdout.splitlines()]
  try:
   assert p.returncode==0,(name,p.returncode)
   parser_runner.compare(rs,got)
  except AssertionError as e:failures.append(str(e))
  for c,r in zip(rs,got):
   if r.get('valid')!=c['valid'] or r.get('message')!=c['message']:
    failures.append(dict(name=c['name'],expected=dict(valid=c['valid'],message=c['message']),actual=r))
  counts[name]=dict(inputs=len(rs),outputs=len(got),exit=p.returncode)
 identity={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'host/app/src/report.rs',ROOT/'host/app/src/messages.rs',ROOT/'host/app/parser-component/src/main.rs',ROOT/'host/app/parser-component/Cargo.toml',ROOT/'host/app/parser-component/Cargo.lock',Path(__file__)]}
 result=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sources=identity,adapter_sha256=sha(Path(a.adapter)),counts=counts,failures=failures,result='FAIL' if failures else 'PASS',scope='627 synthetic APP parser reports (281 ingest +346 cards/make) and49 query report schemas/fallbacks only; zero actual query/native/child/S3 evidence',execution_wall_seconds=time.monotonic()-start)
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
 files={p.name:sha(p) for p in out.iterdir() if p.is_file()};(out/'SHA256SUMS.json').write_text(json.dumps(files,indent=2)+'\n')
 print(json.dumps(result,indent=2));return bool(failures)
if __name__=='__main__':sys.exit(main())
