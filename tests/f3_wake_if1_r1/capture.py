"""New F3 payload through the unchanged helper, exclusively injected fake port."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from checker_cases import fixture,SHA
FAKE=r"""
import os,json
from pathlib import Path
class SerialException(Exception):pass
class Serial:
 def __init__(self,port,baudrate,timeout):
  assert port=='SYNTHETIC-PORT' and baudrate==115200 and timeout==0.05
  self.data=Path(os.environ['V405_RAW']).read_bytes();self.offset=0;self.calls=['open']
 def reset_input_buffer(self):self.calls.append('reset')
 def write(self,b):assert b==b'sleep\n';self.calls.append('write-sleep-LF');return len(b)
 def flush(self):self.calls.append('flush')
 def read(self,n):
  assert 1<=n<=4096
  if self.offset>=len(self.data):raise KeyboardInterrupt()
  b=self.data[self.offset:self.offset+min(n,7)];self.offset+=len(b);return b
 def close(self):
  self.calls.append('close');Path(os.environ['V405_CALLS']).write_text(json.dumps(self.calls))
"""

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--helper',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False);(a.out/'serial.py').write_text(FAKE,encoding='utf-8');obs=[]
 for name,partial in [('complete-F3-lines-retained',False),('partial-WAKE-still-retained',True)]:
  _,f=fixture(provenance='simulated',session='simulation');raw=f['capture.log'];raw=raw[:-11] if partial else raw
  inp=a.out/(name+'.input');capture=a.out/(name+'.raw');calls=a.out/(name+'.calls');inp.write_bytes(raw)
  env=dict(os.environ,PYTHONPATH=str(a.out.resolve()),V405_RAW=str(inp.resolve()),V405_CALLS=str(calls.resolve()),PYTHONDONTWRITEBYTECODE='1')
  q=subprocess.run([sys.executable,'-B',str(a.helper.resolve()),'--port','SYNTHETIC-PORT','--out',str(capture.resolve()),'--send','sleep','--until-interrupt','--timeout','120'],env=env,capture_output=True,text=True)
  try:r=json.loads(q.stdout);sequence=json.loads(calls.read_text());good=q.returncode==0 and capture.read_bytes()==raw and r.get('bytes')==len(raw) and r.get('sha256')==SHA(raw) and r.get('command')=='sleep' and r.get('stop')=='interrupt' and sequence==['open','reset','write-sleep-LF','flush','close']
  except (ValueError,OSError):good=False;r={'stderr':q.stderr,'stdout':q.stdout}
  obs.append(dict(case=name,passed=good,observed=r))
 result=dict(mode='actual-unchanged-helper-new-payload-fake-port',cases=obs,passed=all(c['passed'] for c in obs),candidate_executed=True,physical_run=False,accepted=False)
 (a.out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='cases'}));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
