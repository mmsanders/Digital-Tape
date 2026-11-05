"""V390: complete loader boundary must convert malformed supplied input to problems."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path

def refused(value):return isinstance(value,(tuple,list)) and len(value)==3 and isinstance(value[2],list) and bool(value[2])
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--judge',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--record-known-findings',action='store_true');a=ap.parse_args()
 raw=a.judge.read_bytes();digest=hashlib.sha256(raw).hexdigest()
 if a.record_known_findings:assert digest=='61896c2dcfc5b11e1b786d52a6eaa6975291ac86189eb978e0ea0df8c25c237b'
 s=importlib.util.spec_from_file_location('loader_review_candidate',a.judge.resolve());m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 (out/'shape.json').write_text('{}');(out/'deep.json').write_text('['*10000+'0'+']'*10000)
 cases=[]
 for name,path in [('ordinary-invalid-object',out/'shape.json'),('missing-file',out/'missing.json'),('NUL-manifest-path',str(out/'input')+'\0.json'),('deep-json',out/'deep.json')]:
  try:
   value=m.load_manifest(path,out);cases.append(dict(case=name,passed=refused(value),problems=value[2]))
  except Exception as e:cases.append(dict(case=name,passed=False,exception=repr(e)))
 # The setup gate must suppress proof/credit while retaining observed damage.
 spec=importlib.util.spec_from_file_location('review390_fixtures',Path(__file__).resolve().parent.parent/'rig_records_r1/fixtures.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
 _,mp,ev,h=f.write_bundle(out/'damage',digest,lambda x:x['controls']['E0'].update(result='fail'))
 plans,rows=f.run_fixture(h);rows[0]['readback_hex']=(f.pattern(0)[:256]+f.pattern(1)[256:]).hex();rows[1]['readback_hex']='aa'*512
 for off in f.OFFSETS:rows[2]['neighbours'][off]='ff'*512
 actual=m.judge(plans,rows,manifest=m.load_manifest(mp,ev))
 damage_ok=(actual['verdict']=='FAIL' and bool(actual['problems']) and actual['qualifying']==0 and actual['completed_write_reverted']==[] and actual['torn_iterations']==[1] and actual['corrupt_iterations']==[2] and sorted(actual['neighbour_damage'])==sorted([[3,o] for o in f.OFFSETS]) and actual['damage_on_non_qualifying']==[1,2,3])
 cases.append(dict(case='invalid-setup-retains-damage',passed=damage_ok,observed={k:actual[k] for k in ('verdict','qualifying','completed_write_reverted','torn_iterations','corrupt_iterations','neighbour_damage','damage_on_non_qualifying')}))
 assert refused((None,None,['invalid'])) and not refused((None,None,[])) and not refused(None)
 failed=sorted(x['case'] for x in cases if not x['passed']);ok=failed==['NUL-manifest-path','deep-json'] if a.record_known_findings else not failed
 result=dict(judge_sha256=digest,cases=cases,failed=failed,controls_detected=2,harness_success=ok,clearance=False,physical_run=False)
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result));return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
