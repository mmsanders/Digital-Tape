"""V392: declared judge CLI rejects deep plan/results with exit2, no traceback."""
import argparse,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('cli_review_fixtures',Path(__file__).resolve().parent.parent/'rig_records_r1/fixtures.py');f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
def agrees(rc,stderr,positive,report):
 return rc==(0 if positive else 2) and 'Traceback' not in stderr and (not positive or report.get('verdict')=='PASS')
def exercise(judge,out):
 out.mkdir(parents=True,exist_ok=False);raw=judge.read_bytes();_,mp,ev,h=f.write_bundle(out/'setup',f.sha(raw));plans,rows=f.run_fixture(h)
 plan=out/'valid-plan.json';plan.write_text(json.dumps(plans[0]),encoding='utf-8');results=out/'valid-results.jsonl';results.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
 deep=out/'deep.json';deep.write_text('['*10000+'0'+']'*10000+'\n');cases=[]
 for name,pp,rp,positive in [('valid',plan,results,True),('deep-plan',deep,results,False),('deep-results',plan,deep,False)]:
  report=out/(name+'-report.json');p=subprocess.run([sys.executable,'-B',str(judge),'judge','--plan',str(pp),'--results',str(rp),'--manifest',str(mp),'--evidence',str(ev),'--json',str(report)],capture_output=True,text=True,timeout=60)
  r=json.loads(report.read_text()) if report.exists() else {};cases.append(dict(case=name,exit=p.returncode,stderr=p.stderr[-600:],passed=agrees(p.returncode,p.stderr,positive,r)))
 return cases

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--judge',type=Path,required=True);ap.add_argument('--negative-judge',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 actual=exercise(a.judge.resolve(),out/'candidate');negative=exercise(a.negative_judge.resolve(),out/'old-negative');negative_failed=sorted(x['case'] for x in negative if not x['passed'])
 assert negative_failed==['deep-plan','deep-results'] and negative[0]['passed'],negative
 assert not agrees(0,'',False,{}) and not agrees(2,'Traceback',False,{}) and not agrees(2,'',True,{})
 result=dict(cases=actual,negative_cases=negative,negative_cases_detected=negative_failed,predicate_controls=3,judge_sha256=f.sha(a.judge.read_bytes()),negative_sha256=f.sha(a.negative_judge.read_bytes()),passed=all(x['passed'] for x in actual),physical_run=False)
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
