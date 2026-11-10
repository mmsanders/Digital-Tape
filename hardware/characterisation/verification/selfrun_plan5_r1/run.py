"""Real declared CLI runner, with separate verifier-oracle selftest mode."""
import argparse,copy,json,re,subprocess,sys
from pathlib import Path
from fixtures import *
from oracle import evaluate,agrees
import plan_cli

def invoke(judge,args,cwd):
 q=subprocess.run([sys.executable,str(judge.resolve()),*args],cwd=cwd,capture_output=True,text=True)
 return q

def write_case(work,p,rows,build=None,serial_edit=lambda raw:raw):
 work.mkdir(parents=True,exist_ok=True);_,_,card,b,photo=fixture();build=build or b
 (work/'photo.bin').write_bytes(photo);(work/'firmware.hex').write_bytes(HEX);(work/'build.json').write_text(json.dumps(build),encoding='utf-8');(work/'plan.json').write_text(json.dumps(p),encoding='utf-8');(work/'card.json').write_text(json.dumps(card),encoding='utf-8')
 header='BUILD '+json.dumps(dict(firmware_build=BUILD,timer='SYNTHETIC MCU',timer_hz=150000000),separators=(',',':'))+'\n'
 mapped=''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows).encode()
 raw=('SYNTHETIC BOOT NOT REAL CARD DATA\n'+header).encode()+b''.join(b'ATOM '+line+b'\n' for line in mapped.splitlines())
 raw=serial_edit(raw);(work/'serial.log').write_bytes(raw)
 lines=[line[:-1] if line.endswith(b'\r') else line for line in raw.split(b'\n')[:-1]]
 mapped=b''.join(line[5:]+b'\n' for line in lines if line.startswith(b'ATOM '))
 # Delete only known prior synthetic outputs; stale files must not masquerade as new results.
 for name in ('verdict.json','run.jsonl','created-plan.json','extended-plan.json'):
  f=work/name
  if f.exists():f.unlink()
 return raw,mapped

def serial_cases():
 return [
 ('CRLF-normalization',lambda b:b.replace(b'\n',b'\r\n'),True),
 ('row-JSON-spacing-preserved',lambda b:b.replace(b'\"iteration\":',b'\"iteration\" : ',1),True),
 ('debug-text-retained',lambda b:b+b'ignored debug\n',True),
 ('final-untagged-fragment-ignored',lambda b:b+b'partial debug',True),
 ('invalid-UTF8',lambda b:b+b'\xff\n',False),
 ('missing-BUILD',lambda b:b''.join(x+b'\n' for x in b.splitlines() if not x.startswith(b'BUILD ')),False),
 ('duplicate-BUILD',lambda b:b+b.splitlines()[1]+b'\n',False),
 ('BUILD-after-first-ATOM',lambda b:b'\n'.join([b.splitlines()[0],b.splitlines()[2],b.splitlines()[1],*b.splitlines()[3:]])+b'\n',False),
 ('truncated-ATOM',lambda b:b[:-1],False),
 ('truncated-BUILD',lambda b:b+b'BUILD {}',False),
 ('tag-without-space',lambda b:b+b'ATOM{}\n',False),
 ('tag-extra-space',lambda b:b+b'ATOM  {}\n',False),
 ('malformed-tagged-JSON',lambda b:b+b'ATOM {\n',False),
 ('tagged-array',lambda b:b+b'ATOM []\n',False),
 ('duplicate-JSON-key',lambda b:b.replace(b'"vcard_off_mv":0',b'"vcard_off_mv":0,"vcard_off_mv":0',1),False),
 ('wrong-BUILD-identity',lambda b:b.replace(BUILD.encode(),b'2'*40,1),False),
 ('BUILD-unknown-key',lambda b:b.replace(b'"timer_hz":150000000',b'"timer_hz":150000000,"waiver":true',1),False),
 ('BUILD-boolean-clock',lambda b:b.replace(b'"timer_hz":150000000',b'"timer_hz":true',1),False),
 ('BUILD-zero-clock',lambda b:b.replace(b'"timer_hz":150000000',b'"timer_hz":0',1),False),
 ]

def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--selftest',action='store_true');g.add_argument('--judge',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False);obs=[]
 for case in cases():
  p,rows,_,_,_=fixture();case['edit'](p,rows)
  expected=evaluate(p,rows);assert agrees(expected,case['wanted']),case['name']
  if a.selftest:actual=expected;good=True
  else:
   work=a.out/'work';raw,mapped=write_case(work,p,rows)
   q=invoke(a.judge,['judge','--plan','plan.json','--serial','serial.log','--build-record','build.json','--hex','firmware.hex','--run-jsonl','run.jsonl','--json','verdict.json'],work)
   f=work/'verdict.json';actual=json.loads(f.read_text()) if f.exists() else {'refused':q.stderr[-500:]}
   # Strict NaN/Infinity input refusals may have no verdict; they must exit2 without traceback.
   strict_refusal=any(label in case['name'] for label in ('-nan','-inf')) and q.returncode==2 and 'Traceback' not in q.stderr
   good=(agrees(actual,case['wanted']) and q.returncode==(0 if case['wanted']['verdict']=='PASS' else 2)) or strict_refusal
   if good and actual.get('verdict')=='PASS':
    good=all(actual.get(k)==p[k] for k in ('method','run_id','plan_digest','card_model','card_unit','firmware_build','hex_sha256','t_sched_us')) and not actual.get('problems') and actual.get('qualification_scope')=='spi-characterisation' and actual.get('residual_limits')==RESIDUAL and actual.get('serial_sha256')==SHA(raw) and actual.get('run_jsonl_sha256')==SHA(mapped) and actual.get('build_record_sha256')==SHA((work/'build.json').read_bytes()) and (work/'run.jsonl').read_bytes()==mapped
  obs.append(dict(case=case['name'],expected=case['wanted'],passed=good,observed=actual))
 controls=[]
 for v in ('PASS','FAIL'):
  assert any(x['expected']['verdict']!=v for x in obs);controls.append('blanket-'+v)
 for name,change in [('erase-completed-OLD',lambda x:x.update(completed_before_old=[])),('gate-null-CID',lambda x:x.update(verdict='FAIL')),('drop-CID-diagnostic',lambda x:x.update(cid_disagreements=[])),('hide-qualifying-damage',lambda x:x.update(torn_iterations=[]))]:
  detected=False
  for observed in obs:
   v=copy.deepcopy(observed['observed']);change(v)
   if not agrees(v,observed['expected']):detected=True;break
  assert detected,name;controls.append(name)
 if not a.selftest:
  work=a.out/'work'
  for name,edit,positive in serial_cases():
   p,r,_,_,_=fixture();raw,mapped=write_case(work,p,r,serial_edit=edit)
   q=invoke(a.judge,['judge','--plan','plan.json','--serial','serial.log','--build-record','build.json','--hex','firmware.hex','--run-jsonl','run.jsonl','--json','verdict.json'],work)
   actual=json.loads((work/'verdict.json').read_text()) if (work/'verdict.json').exists() else {}
   good=q.returncode==(0 if positive else 2) and 'Traceback' not in q.stderr
   if positive:good=good and actual.get('verdict')=='PASS' and actual.get('serial_sha256')==SHA(raw) and actual.get('run_jsonl_sha256')==SHA(mapped) and (work/'run.jsonl').read_bytes()==mapped
   else:good=good and actual.get('verdict','FAIL')=='FAIL'
   obs.append(dict(case=name,passed=good,observed=actual))
  # Independent hash bindings: change bytes/records only after serial/plan construction.
  for name,edit in [('hex-bytes-mismatch',lambda w:(w/'firmware.hex').write_bytes(HEX+b'X')),('build-record-hash-mismatch',lambda w:(w/'build.json').write_text(json.dumps(dict(firmware_build=BUILD,hex_sha256='0'*64)))),('build-record-source-mismatch',lambda w:(w/'build.json').write_text(json.dumps(dict(firmware_build='2'*40,hex_sha256=SHA(HEX)))) )]:
   p,r,_,_,_=fixture();write_case(work,p,r);edit(work);q=invoke(a.judge,['judge','--plan','plan.json','--serial','serial.log','--build-record','build.json','--hex','firmware.hex','--json','verdict.json'],work);obs.append(dict(case=name,passed=q.returncode==2 and 'Traceback' not in q.stderr))
  # The raw serial path may not be bypassed with legacy --results.
  p,r,_,_,_=fixture();write_case(work,p,r);(work/'input.jsonl').write_bytes(b'')
  q=invoke(a.judge,['judge','--plan','plan.json','--results','input.jsonl','--build-record','build.json','--hex','firmware.hex','--json','verdict.json'],work);obs.append(dict(case='v5-refuses-pre-normalized-results',passed=q.returncode==2 and 'Traceback' not in q.stderr))
 if not a.selftest:
  for field,value in [('t_sched_us',201),('block',2000000),('card_model',dict(brand_line='OTHER',capacity_label='64 GB',part_number=None,photos=[]))]:
   p,r,_,_,_=fixture();p[field]=value;work=a.out/'work';write_case(work,p,r);q=invoke(a.judge,['judge','--plan','plan.json','--serial','serial.log','--build-record','build.json','--hex','firmware.hex','--json','verdict.json'],work);obs.append(dict(case='plan-digest-tamper-'+field,passed=q.returncode==2 and 'Traceback' not in q.stderr))
  for version in (3,4):
   p,r,_,_,_=fixture();work=a.out/'work';write_case(work,p,r);legacy=dict(p,plan_version=version);(work/'legacy.json').write_text(json.dumps(legacy));q=invoke(a.judge,['judge','--plan','plan.json','--plan','legacy.json','--serial','serial.log','--build-record','build.json','--hex','firmware.hex','--json','verdict.json'],work);obs.append(dict(case='mixed-v5-v'+str(version),passed=q.returncode==2 and 'Traceback' not in q.stderr))
  obs.extend(plan_cli.run(a.judge,a.out/'work',invoke,write_case))
 result=dict(declared_plan_cases=len(plan_cli.cases())+5,declared_serial_cases=len(serial_cases())+4,declared_plan_integrity_cases=5,mode='independent-oracle-selftest' if a.selftest else 'actual-declared-plan5-judge-CLI',cases=obs,controls_detected=controls,passed=all(x['passed'] for x in obs),candidate_executed=not a.selftest,accepted=False,physical_run=False)
 (a.out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='cases'}));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
