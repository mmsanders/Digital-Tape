"""Execute the future gate against independent real histories, never a gate model."""
import argparse,json,subprocess,sys
from pathlib import Path
from generate import generate

def matches(code,expected):return (code==0)==(expected==0)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--gate',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--selftest',action='store_true');a=ap.parse_args();out=a.out.resolve();rows=generate(out/'histories')
 if a.selftest:
  assert not all(matches(0,c['expect']) for c in rows),'always-green harness control survived'
  assert not all(matches(1,c['expect']) for c in rows),'always-red harness control survived'
  result=dict(mode='history-fixture-selftest',generated=len(rows),positive=sum(c['expect']==0 for c in rows),negative=sum(c['expect']!=0 for c in rows),harness_controls=['always-green','always-red'],product_gate_executed=False)
 else:
  assert a.gate;observed=[]
  for c in rows:
   cmd=[sys.executable,'-B',str(a.gate.resolve()),'--repo',c['repo'],'--base',c['base'],'--head',c['head'],'--verification-repo',c['verification_repo'],'--verification-main',c['verification_main'],'--manifest',c['manifest']]
   p=subprocess.run(cmd,capture_output=True,text=True,timeout=60);observed.append(dict(case=c['name'],expected=c['expect'],exit=p.returncode,passed=matches(p.returncode,c['expect']),stderr=p.stderr[-800:]))
  result=dict(mode='actual-gate-history-replay',cases=observed,passed=all(c['passed'] for c in observed),product_gate_executed=True)
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0 if result.get('passed',True) else 1
if __name__=='__main__':raise SystemExit(main())
