"""Harmless owned-input producer; never a recorder or Product test."""
import argparse,hashlib,json,os,pathlib,sys,time
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['text','binary','empty','exit7','wait'],required=True)
p.add_argument('--input',type=pathlib.Path,required=True);p.add_argument('--nonce',required=True)
p.add_argument('--ready',type=pathlib.Path);a=p.parse_args()
b=a.input.read_bytes()
header=dict(pid=os.getpid(),nonce=a.nonce,input_sha256=hashlib.sha256(b).hexdigest(),input_bytes=len(b))
sys.stdout.buffer.write((json.dumps(header,sort_keys=True)+'\n').encode());sys.stdout.buffer.flush()
if a.mode=='binary':out=b'\x00\xffraw\n';err=b'\x80diagnostic\n'
elif a.mode=='empty':out=err=b''
else:out=b'helper-output\n';err=b'helper-diagnostic\n'
sys.stdout.buffer.write(out);sys.stdout.buffer.flush();sys.stderr.buffer.write(err);sys.stderr.buffer.flush()
if a.mode=='wait':
 assert a.ready is not None
 with a.ready.open('xb') as f:f.write(b'READY\n')
 while True:time.sleep(.05)
sys.exit(7 if a.mode=='exit7' else 0)
