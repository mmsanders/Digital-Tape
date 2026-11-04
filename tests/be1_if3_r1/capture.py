"""IF/3 capture binding with fake ports/clocks. Never opens a real device."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from capture_cases import catalog

HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()

def execute(helper,c,out):
    out.mkdir(parents=True,exist_ok=False)
    config=out/'stimulus.json';capture=out/'capture.raw';log=out/'audit.json'
    config.write_text(json.dumps(c),encoding='utf-8')
    before=base64.b64decode(c['preexisting']) if 'preexisting' in c else None
    if before is not None:capture.write_bytes(before)
    p=subprocess.run([sys.executable,'-B',str(HERE/'capture_worker.py'),str(helper.resolve()),str(config.resolve()),str(capture.resolve()),str(log.resolve())],
      capture_output=True,timeout=10)
    facts=json.loads(log.read_text(encoding='utf-8'))
    assert not facts['violations'],facts['violations']
    assert p.returncode==c['exit'],('exit',p.returncode,c['exit'],p.stderr.decode(errors='replace'))
    if c['usage']:
        assert not facts['events'],'Serial import/open before usage acceptance'
        assert (capture.read_bytes()==before) if before is not None else not capture.exists()
        assert not p.stdout.strip(),'Usage refusal must not emit a capture summary'
    else:
        expected=base64.b64decode(c['expected']);assert capture.read_bytes()==expected,'Raw bytes were changed, lost or over-read'
        lines=p.stdout.decode('utf-8').splitlines();assert len(lines)==1,'Expected exactly one JSON summary'
        summary=json.loads(lines[0])
        fields=dict(tool='bench_capture.py',version='BE1-IF/3',port=c['port'],command=c['send'],out=str(capture.resolve()),
                    bytes=len(expected),sha256=sha(expected),stop=c['stop'],exit=c['exit'])
        for k,v in fields.items():assert summary[k]==v,('summary',k,summary[k],v)
        opens=[x for x in facts['events'] if x[0]=='open'];assert opens==[['open',c['port'],115200,0.05]]
        if c.get('error')!='open':assert facts['events'][-1]==['close'],'Port not closed'
        resets=[x for x in facts['events'] if x[0]=='reset'];writes=[x for x in facts['events'] if x[0]=='write']
        if c['send'] is not None and c.get('error')!='open':
            assert len(resets)==len(writes)==1
            assert writes[0][1]==(c['send'].encode('ascii')+b'\n').hex()
        else:assert not resets and not writes
        if 'elapsed_min' in c:assert facts['elapsed']>=c['elapsed_min']
        if 'elapsed_max' in c:assert facts['elapsed']<=c['elapsed_max']
    assert set(x.name for x in out.iterdir())<=set(('stimulus.json','capture.raw','audit.json')),'Unexpected file'
    return dict(case=c['name'],passed=True,exit=p.returncode,fake_reads=facts['reads'],elapsed=facts['elapsed'])

def double_source(c,mutation=''):
    # This double follows catalogued lengths/spans, not a general serial parser.
    # Only harness self-test receives these constants; Product gets no expectations.
    source='''import base64,hashlib,json,sys,time
from pathlib import Path
C=CASE
out=Path(sys.argv[sys.argv.index('--out')+1])
if C['usage']:raise SystemExit(64)
import serial
port=None
f=out.open('xb')
stop='timeout';rc=3
started=time.monotonic()
try:
 port=serial.Serial(C['port'],baudrate=115200,timeout=0.05)
 if C['send'] is not None:
  port.reset_input_buffer()
  port.write(C['send'].encode('ascii')+b'\\n')
  port.flush()
 started=time.monotonic()
 timeout=C['timeout']
 if timeout is None:timeout=600 if C['mode']=='--until-digest' else 10 if C['mode']=='--until-info' else None
 received=0
 while True:
  if timeout is not None and time.monotonic()-started>=timeout:
   stop='timeout';rc=0 if C['mode']=='--until-interrupt' else 3;break
  n=1
  for start,end,kind in C['spans']:
   if start<=received<end:n=end-received;break
  part=port.read(n)
  if not part:continue
  f.write(part);f.flush();received+=len(part)
  if C['stop'] in ('digest','info','err') and received==len(base64.b64decode(C['expected'])):
   stop=C['stop'];rc=0;break
 AFTER_LOOP
except (serial.SerialException,OSError):stop='port_error';rc=4
except KeyboardInterrupt:stop='interrupt';rc=0 if C['mode']=='--until-interrupt' else 130
finally:
 f.close()
 if port is not None:port.close()
raw=out.read_bytes()
MUTATE
summary=dict(tool='bench_capture.py',version='BE1-IF/3',port=C['port'],command=C['send'],out=str(out),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),stop=stop,exit=rc)
SUMMARY_MUTATE
print(json.dumps(summary))
raise SystemExit(rc)
'''
    source=source.replace('CASE',repr(copy.deepcopy(c))).replace('AFTER_LOOP','pass').replace('MUTATE','pass')
    # Replace the separate longer placeholder first (the generic replacement above
    # intentionally leaves SUMMARY_pass, which is unambiguous).
    source=source.replace('SUMMARY_pass','pass')
    if mutation=='truncate':source=source.replace('raw=out.read_bytes()',"raw=out.read_bytes()[:-1];out.write_bytes(raw)")
    if mutation=='newline':source=source.replace('raw=out.read_bytes()',"raw=out.read_bytes().replace(b'\\r\\n',b'\\n');out.write_bytes(raw)")
    if mutation=='erase-partial':source=source.replace('raw=out.read_bytes()',"raw=b'';out.write_bytes(raw)")
    if mutation=='metadata':source=source.replace('print(json.dumps(summary))',"summary['bytes']=0\nprint(json.dumps(summary))")
    if mutation=='no-reset':source=source.replace('port.reset_input_buffer()','pass')
    if mutation=='wrong-send':source=source.replace("+b'\\n'","+b'\\r\\n'")
    if mutation=='early-deadline':source=source.replace('started=time.monotonic()','started=0.0')
    if mutation=='no-close':source=source.replace('if port is not None:port.close()','if port is not None:pass')
    if mutation=='early-import':source='import serial\n'+source
    if mutation=='empty-is-EOF':source=source.replace('if not part:continue','if not part:break')
    if mutation=='over-read':source=source.replace('part=port.read(n)','part=port.read(4096)')
    return source

def selftest(out):
    cs=catalog();assert len({c['name'] for c in cs})==len(cs)
    stub=out/'double.py';observations=[]
    for c in cs:
        stub.write_text(double_source(c),encoding='utf-8')
        observations.append(execute(stub,c,out/c['name']))
    controls=[]
    for mutation,name in [('truncate','digest-fragmented'),('newline','digest-fragmented'),('erase-partial','partial-line'),
      ('metadata','digest-fragmented'),('no-reset','send-info'),('wrong-send','send-info'),
      ('early-deadline','deadline-starts-after-send'),('no-close','info-terminates'),
      ('early-import','send-empty'),('empty-is-EOF','empty-and-short-reads-continue'),('over-read','digest-fragmented')]:
        c=next(v for v in cs if v['name']==name)
        stub.write_text(double_source(c,mutation),encoding='utf-8')
        try:execute(stub,c,out/('control-'+mutation))
        except AssertionError:controls.append(mutation)
        else:raise AssertionError('Undetected capture control: '+mutation)
    return dict(mode='harness-selftest-only',product_executed=False,cases=observations,controls_detected=controls,physical_run=False)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--helper',type=Path);ap.add_argument('--selftest',action='store_true');ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    if a.selftest:assert not a.helper;result=selftest(out)
    else:
        assert a.helper and a.helper.is_file();observations=[]
        for c in catalog():
            try:observations.append(execute(a.helper,c,out/c['name']))
            except Exception as e:observations.append(dict(case=c['name'],passed=False,error=repr(e)))
        result=dict(mode='candidate-fake-port-execution',helper_sha256=sha(a.helper.read_bytes()),cases=observations,
          passed=all(c['passed'] for c in observations),physical_run=False)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}));return 0 if result.get('passed',True) else 1

if __name__=='__main__':raise SystemExit(main())
