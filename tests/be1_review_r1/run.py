"""V388 review regressions: continuous-input deadlines and resolved bundle bounds."""
import argparse
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import hashlib

HERE=Path(__file__).resolve().parent
PREV=HERE.parent/'be1_binding_r1';IF3=HERE.parent/'be1_if3_r1'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
f=load('review_fixture_support',PREV/'fixtures.py');caps=load('review_capture_catalog',IF3/'capture_cases.py')
sha=lambda b:hashlib.sha256(b).hexdigest()
GAPS={'digest-continuous-input-deadline','info-continuous-input-deadline','interrupt-continuous-input-deadline','outside-bundle-alias','criterion-list','supersede-list'}

def retained(raw,facts):return len(raw)==facts['delivered_bytes'] and sha(raw)==facts['delivered_sha256']
def alias_agrees(rc,overall,violations):return not violations and rc==2 and overall=='INVALID'

def deadline_agrees(rc,summary,facts,raw,wire,timeout,continuous):
    expected_exit=0 if summary.get('stop')=='timeout' and summary.get('exit')==0 else 3
    if continuous:
        return (rc==expected_exit and summary.get('stop')=='timeout' and facts['elapsed']<=timeout+0.05+1e-6
          and 0<len(raw)<len(wire) and wire.startswith(raw) and summary.get('bytes')==len(raw)
          and summary.get('sha256')==sha(raw))
    return rc==0 and summary.get('stop') in ('digest','info') and raw==wire

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--checker',type=Path,required=True);ap.add_argument('--helper',type=Path,required=True)
    ap.add_argument('--golden',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--record-known-findings',action='store_true');a=ap.parse_args()
    checker=a.checker.resolve();helper=a.helper.resolve();golden=a.golden.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    hashes=dict(checker=sha(checker.read_bytes()),helper=sha(helper.read_bytes()))
    if a.record_known_findings:
        assert hashes==dict(checker='657ba23e822cad6b1e44f6919285bd5801b52268c2e3fca9aa5efb0530bd0fce',helper='f12c209772b04e659f89979de3d6785c5ea608e4c8741a8d509b23372edcfe6a')
    observations=[]
    for mode,wire in [('--until-digest',caps.DIGEST),('--until-info',caps.INFO),('--until-interrupt',caps.DIGEST)]:
        for continuous in ([False,True] if mode!='--until-interrupt' else [True]):
            name=mode[8:]+('-continuous-input-deadline' if continuous else '-before-deadline-positive')
            d=out/name;d.mkdir();c=copy.deepcopy(caps.catalog()[0]);timeout=0.03 if continuous else 1.0
            c.update(mode=mode,wire=base64.b64encode(wire).decode(),expected=base64.b64encode(wire).decode(),timeout=timeout,tick=0.01 if continuous else 0.001,empty_reads=[])
            config=d/'stimulus.json';config.write_text(json.dumps(c),encoding='utf-8')
            rawpath=d/'capture.raw';audit=d/'audit.json'
            p=subprocess.run([sys.executable,'-B',str(IF3/'capture_worker.py'),str(helper),str(config),str(rawpath),str(audit)],capture_output=True,text=True,timeout=10)
            facts=json.loads(audit.read_text());raw=rawpath.read_bytes() if rawpath.exists() else b''
            try:
                summary=json.loads(p.stdout);correct_code=0 if mode=='--until-interrupt' else 3
                passed=deadline_agrees(p.returncode,summary,facts,raw,wire,timeout,continuous)
                if continuous:passed=passed and p.returncode==correct_code
                passed=passed and not facts['violations'] and retained(raw,facts)
            except (ValueError,KeyError):summary={};passed=False
            observations.append(dict(case=name,passed=passed,exit=p.returncode,summary=summary,elapsed=facts['elapsed'],configured_timeout=timeout,bytes=len(raw),violations=facts['violations']))
    # All outside bytes are synthetic task-owned fixtures. Windows uses a directory
    # junction and Linux a symlink; no deletion/moving or real external data is used.
    refs=f.references(golden);m,payloads=f.base(refs);bundle=out/'bundle';bundle.mkdir();outside=out/'outside';outside.mkdir()
    first=f.CASES[0];outside_file=outside/'quiet.serial';outside_file.write_bytes(payloads[first+'.serial'])
    for path,raw in payloads.items():(bundle/path).write_bytes(raw)
    m['observations'][0]['transcript']='linked/quiet.serial'
    m['files']=[dict(path=p,sha256=sha(raw),bytes=len(raw)) for p,raw in payloads.items()]
    m['files'].append(dict(path='linked/quiet.serial',sha256=sha(outside_file.read_bytes()),bytes=outside_file.stat().st_size))
    (bundle/'manifest.json').write_text(json.dumps(m),encoding='utf-8');link=bundle/'linked'
    if os.name=='nt':
        quote=lambda v:"'"+str(v).replace("'","''")+"'"
        subprocess.run(['powershell','-NoProfile','-Command','New-Item -ItemType Junction -Path '+quote(link)+' -Target '+quote(outside)+' | Out-Null'],check=True,capture_output=True)
    else:link.symlink_to(outside,target_is_directory=True)
    report=out/'alias-report.json';audit=out/'alias-audit.json'
    p=subprocess.run([sys.executable,'-B',str(PREV/'guard.py'),str(checker),str(bundle),str(report),str(golden),str(audit)],capture_output=True,text=True,timeout=30)
    violations=json.loads(audit.read_text());r=json.loads(report.read_text()) if report.exists() else {}
    observations.append(dict(case='outside-bundle-alias',passed=alias_agrees(p.returncode,r.get('overall'),violations),
      exit=p.returncode,overall=r.get('overall'),violations=violations))
    for name in ('criterion-list','supersede-list'):
        m,payloads=f.base(refs);d=out/name;d.mkdir()
        if name=='criterion-list':m['observations'][0]['criterion']=[]
        else:m['observations'][0].update(superseded_by=[],supersede_reason='malformed reference')
        m['files']=[dict(path=k,sha256=sha(v),bytes=len(v)) for k,v in payloads.items()]
        for path,raw in payloads.items():(d/path).write_bytes(raw)
        (d/'manifest.json').write_text(json.dumps(m),encoding='utf-8')
        report=out/(name+'-report.json');audit=out/(name+'-audit.json')
        p=subprocess.run([sys.executable,'-B',str(PREV/'guard.py'),str(checker),str(d),str(report),str(golden),str(audit)],capture_output=True,text=True,timeout=30)
        violations=json.loads(audit.read_text());r=json.loads(report.read_text()) if report.exists() else {}
        observations.append(dict(case=name,passed=alias_agrees(p.returncode,r.get('overall'),violations),exit=p.returncode,overall=r.get('overall'),violations=violations))
    # Known correct observations and altered outputs qualify the new predicates.
    partial=b'SHA';facts=dict(elapsed=0.03);summary=dict(stop='timeout',exit=3,bytes=3,sha256=sha(partial))
    assert deadline_agrees(3,summary,facts,partial,caps.DIGEST,0.03,True)
    assert not deadline_agrees(0,dict(summary,stop='digest',bytes=len(caps.DIGEST),sha256=sha(caps.DIGEST)),dict(elapsed=0.91),caps.DIGEST,caps.DIGEST,0.03,True)
    assert not deadline_agrees(3,dict(summary,sha256='0'*64),facts,partial,caps.DIGEST,0.03,True)
    assert not deadline_agrees(3,summary,dict(elapsed=0.2),partial,caps.DIGEST,0.03,True)
    assert retained(partial,dict(delivered_bytes=3,delivered_sha256=sha(partial)))
    assert not retained(partial[:-1],dict(delivered_bytes=3,delivered_sha256=sha(partial)))
    assert alias_agrees(2,'INVALID',[]) and not alias_agrees(0,'CONSISTENT',[])
    assert not alias_agrees(2,'INVALID',['outside read was attempted'])
    failed={o['case'] for o in observations if not o['passed']};success=(failed==GAPS) if a.record_known_findings else not failed
    result=dict(mode='authenticated-known-findings' if a.record_known_findings else 'candidate-regressions',hashes=hashes,cases=observations,failed=sorted(failed),controls_detected=6,harness_success=success,candidate_clearance=False,physical_run=False)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='cases'}));return 0 if success else 1

if __name__=='__main__':raise SystemExit(main())
