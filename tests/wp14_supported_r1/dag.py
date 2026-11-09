"""ADR206 required supported census DAG checks (PyYAML BaseLoader)."""
import argparse,copy,hashlib,json,os,subprocess,sys
from pathlib import Path
import yaml

def needs(job):
 n=job.get('needs',[]);return [n] if isinstance(n,str) else n

def failures(workflow):
 jobs=workflow.get('jobs',{});bad=[]
 if 'wp14-package-census' not in jobs:return ['missing required census job']
 census=jobs['wp14-package-census'];text=str(census.get('steps',[]))
 checks={'census-required':'wp14-package-census' in needs(jobs.get('qualification',{})), 'package-dependency':'wp14-package' in needs(census), 'two-platform-flag':'--platforms linux,windows' in text, 'retained-inputs':'--captures' in text and '--relocations' in text and 'wp14-native-evidence-' in text, 'completeness-call':'census.py' in text, 'git-identity':'a8_identity.py' in text, 'census-not-tolerated':census.get('continue-on-error','false')!='true' and 'continue-on-error' not in text, 'aggregate-always':'always()' in jobs.get('qualification',{}).get('if','')}
 legs=jobs.get('wp14-package',{}).get('strategy',{}).get('matrix',{}).get('include',[])
 checks['supported-legs']={x.get('platform') for x in legs}=={'linux','windows'}
 for k,v in checks.items():
  if not v:bad.append(k)
 return bad

def selftest():
 wf=dict(jobs={'wp14-package':dict(strategy=dict(matrix=dict(include=[dict(platform='linux'),dict(platform='windows')]))),'wp14-package-census':dict(needs=['wp14-package'],steps=[dict(run='census.py --platforms linux,windows --captures wp14-native-evidence-* --relocations relocations.json; a8_identity.py')]),'qualification':dict(needs=['wp14-package','wp14-package-census'],**{'if':'always()'})})
 assert not failures(wf);controls=[]
 for name,edit in [('missing-census',lambda w:w['jobs'].pop('wp14-package-census')),('unrequired-census',lambda w:w['jobs']['qualification'].update(needs=['wp14-package'])),('no-package-dependency',lambda w:w['jobs']['wp14-package-census'].update(needs=[])),('git-only',lambda w:w['jobs']['wp14-package-census'].update(steps=[dict(run='a8_identity.py')])),('macos-required',lambda w:w['jobs']['wp14-package']['strategy']['matrix']['include'].append(dict(platform='macos'))),('unexpected-skip',lambda w:w['jobs']['qualification'].update(**{'if':'success()'})),('tolerated-census',lambda w:w['jobs']['wp14-package-census'].update(**{'continue-on-error':'true'}))]:
  w=copy.deepcopy(wf);edit(w);assert failures(w);controls.append(name)
 return dict(mode='DAG-selftest-only',positive=True,controls=controls,product_executed=False)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--selftest',action='store_true');ap.add_argument('--product',type=Path);a=ap.parse_args()
 if a.selftest:print(json.dumps(selftest()));return 0
 assert a.product;root=a.product.resolve();wf=yaml.load((root/'.github/workflows/ci.yml').read_text(encoding='utf-8'),Loader=yaml.BaseLoader);bad=failures(wf)
 manual=root/'.github/workflows/wp14-macos-manual.yml';expected=(Path(__file__).parent/'MANUAL-SHA256').read_text().strip()
 if not manual.is_file() or hashlib.sha256(manual.read_bytes()).hexdigest()!=expected:bad.append('original manual workflow bytes changed')
 members=needs(wf['jobs']['qualification']);rows=[]
 for state in ('success','failure','cancelled','missing','skipped'):
  results={n:dict(result='success') for n in members};results.setdefault('changes',dict(result='success'))
  if state=='missing':results.pop('wp14-package-census',None)
  else:results['wp14-package-census']=dict(result=state)
  env=dict(os.environ,LANE='qualification',NEEDS=json.dumps(results),DOCS_ONLY='false',QUALIFY='true',QUALIFY_JOBS=',')
  r=subprocess.run([sys.executable,'-B',str(root/'tools/ci/lane-verdict.py')],env=env,capture_output=True,text=True);ok=r.returncode==(0 if state=='success' else 1);rows.append(dict(state=state,passed=ok))
  if not ok:bad.append('actual aggregate '+state)
 print(json.dumps(dict(failed=bad,lane_cli=rows,accepted=False)));return 1 if bad else 0
if __name__=='__main__':raise SystemExit(main())
