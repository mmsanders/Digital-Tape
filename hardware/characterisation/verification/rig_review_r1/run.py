"""Versioned review regressions: no proof without setup, and loader never raises."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

spec=importlib.util.spec_from_file_location('published_rig_records',Path(__file__).resolve().parent.parent/'rig_records_r1'/'fixtures.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
GAPS={'failed-E0-has-no-completion-proof','missing-manifest-has-no-completion-proof',
      'repointed-bytes-have-no-completion-proof','wrong-card-has-no-completion-proof',
      'NUL-ref-is-a-problem-not-exception','huge-out-of-window-integer-is-a-problem-not-exception'}

def proof_agrees(actual,authenticated):
    return actual['verdict']=='FAIL' and bool(actual['problems']) and actual['qualifying']==(1000 if authenticated else 0) and actual['completed_write_reverted']==([1001] if authenticated else []) and actual['torn_iterations']==[]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--judge',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--record-known-findings',action='store_true');a=ap.parse_args()
    raw=a.judge.read_bytes()
    import hashlib
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if a.record_known_findings:assert blob=='03382e6ec422a06048514122db0c2b4557ae46ba','Historical mode is pinned; never candidate clearance'
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('rig_review_candidate',a.judge.resolve());m=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=m;spec.loader.exec_module(m)
    observations=[]
    def attempt(name,action):
        try:
            observed,passed=action();observations.append(dict(case=name,observed=observed,passed=passed))
        except Exception as exc:observations.append(dict(case=name,observed=dict(exception=repr(exc)),passed=False))
    for name,setup in [('valid-setup-OLD-is-reverted','valid'),('failed-E0-has-no-completion-proof','failed'),
                       ('missing-manifest-has-no-completion-proof','none'),('repointed-bytes-have-no-completion-proof','bytes'),
                       ('wrong-card-has-no-completion-proof','card')]:
        def run(name=name,setup=setup):
            edit=(lambda x:x['controls']['E0'].update(result='fail')) if setup=='failed' else (lambda x:None)
            _,mp,ev,h=f.write_bundle(out/name,f.sha(raw),edit)
            plans,rows=f.run_fixture(h);rows[-1]['readback_hex']=f.pattern(1000).hex()
            if setup=='bytes':mp.write_bytes(mp.read_bytes()+b' \n')
            loaded=None if setup=='none' else m.load_manifest(mp,ev)
            if setup=='card':
                plans[0].update(sku='OTHER',revision='OTHER',card_cid='2'*32)
                plans[0]['plan_digest']=f.plan_digest(plans[0])
                for r in rows:r.update(sku='OTHER',revision='OTHER',card_cid='2'*32,card_cid_after_cut='2'*32,plan_digest=plans[0]['plan_digest'])
            actual=m.judge(plans,rows,manifest=loaded)
            observed={k:actual[k] for k in ('verdict','problems','qualifying','completed_write_reverted','torn_iterations')}
            return observed,proof_agrees(actual,setup=='valid')
        attempt(name,run)
    for name,edit in [('NUL-ref-is-a-problem-not-exception',lambda x:x['host_script'].update(path='host.py\0')),
                      ('huge-out-of-window-integer-is-a-problem-not-exception',lambda x:x['thresholds_measured']['a_falling_v'].__setitem__(0,10**500))]:
        def run(name=name,edit=edit):
            _,mp,ev,h=f.write_bundle(out/name,f.sha(raw),edit)
            loaded=m.load_manifest(mp,ev)
            good=isinstance(loaded,(tuple,list)) and len(loaded)==3 and isinstance(loaded[2],list) and bool(loaded[2])
            return dict(problems=loaded[2] if good else repr(loaded)),good
        attempt(name,run)
    good=dict(verdict='FAIL',problems=['completion reverted'],qualifying=1000,completed_write_reverted=[1001],torn_iterations=[])
    assert proof_agrees(good,True) and not proof_agrees(good,False)
    invalid=dict(good,qualifying=0,completed_write_reverted=[])
    assert proof_agrees(invalid,False) and not proof_agrees(invalid,True)
    assert not proof_agrees(dict(invalid,qualifying=1000),False)
    assert not proof_agrees(dict(good,torn_iterations=[1001]),True)
    failed={o['case'] for o in observations if not o['passed']}
    passed=(failed==GAPS) if a.record_known_findings else not failed
    report=dict(mode='authenticated-known-findings' if a.record_known_findings else 'candidate-regressions',
      judge_git_blob=blob,judge_sha256=f.sha(raw),cases=observations,failed=sorted(failed),
      proof_predicate_controls_detected=4,harness_success=passed,candidate_clearance=False,physical_run=False)
    (out/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'}));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
