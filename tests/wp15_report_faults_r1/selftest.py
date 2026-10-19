import copy,json,hashlib,struct
from pathlib import Path
import id_inputs,tempfile
import oracle

def rejected(fn,x):
 try:fn(x)
 except (AssertionError,KeyError,ValueError):return
 raise AssertionError('fault control not detected')
def line(**r):return (json.dumps(r,separators=(',',':'))+'\n').encode()
def run():
 root=Path(__file__).parent
 for n,h in json.loads((root/'pins.json').read_text())['files'].items():assert hashlib.sha256((root/'spec'/n).read_bytes()).hexdigest()==h
 with tempfile.TemporaryDirectory()as tmp:
  for r in id_inputs.generate(Path(tmp)):
   b=(Path(r['folder'])/'x.wav').read_bytes();assert len(b)==52 and struct.unpack('<d',b[44:])[0]==r['value']
  assert struct.unpack('<f',struct.pack('<f',1e-300))[0]==0.0
  assert struct.unpack('<f',struct.pack('<f',1e-30))[0]>0.0
 records=[line(t='start',tool='ingest',version='test',nonce='0'*32),line(t='progress',step='publish',done=1,total=1),line(t='end',exit=0)]
 pair={'audio.wav':'a','manifest.json':'m'}
 base=dict(exit=0,pair=pair,report_hex=b''.join(records).hex(),foreign_before='f',foreign_after='f');oracle.baseline(base)
 total=0
 for kind,k in [('start',0),('middle',1),('end',2)]:
  for short in [0,1]:
   attempts=[dict(requested_hex=b.hex(),written=len(b),error=None)for b in records[:k+1]]
   attempts[-1].update(written=short,error='actual-OS-error'if not short else None)
   r=dict(exit=0,baseline_exit=0,stdout_hex=b'ordinary\n'.hex(),baseline_stdout_hex=b'ordinary\n'.hex(),pair=pair,baseline_pair=pair,foreign_before='f',foreign_after='f',sources_before='s',sources_after='s',unpublished_stage_after=[],baseline_stderr_hex=b''.hex(),stderr_hex=b'report diagnostic\n'.hex(),mechanism='compiled-writer-fault',claim='test-only',shipping=False,attempt_capture_complete=True,leaf_created_exclusive=True,attempts=attempts,report_hex=(b''.join(records[:k])+records[k][:short]).hex(),fault_position=kind)
   oracle.writes(r)
   for key,value in [('exit',1),('pair',{}),('foreign_after','changed'),('sources_after','changed'),('attempt_capture_complete',False),('stderr_hex',b'report diagnostic\nreport diagnostic\n'.hex()),('report_hex',b'fake'.hex()),('unpublished_stage_after',['stage'])]:
    x=copy.deepcopy(r);x[key]=value;rejected(oracle.writes,x);total+=1
   x=copy.deepcopy(r);x['attempts'].append(dict(requested_hex=records[-1].hex(),written=len(records[-1]),error=None));rejected(oracle.writes,x);total+=1
   x=copy.deepcopy(r);x['claim']='shipping-native';rejected(oracle.writes,x);total+=1
   if kind!='end':x=copy.deepcopy(r);x['fault_position']='end';rejected(oracle.writes,x);total+=1
 print(json.dumps({'scope':'AUTHORED synthetic writer-fault controls, not shipping/native receipts','admitted_neighbours':7,'detecting_mutations':total},indent=2))
if __name__=='__main__':run()
