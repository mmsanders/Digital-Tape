"""A252 conforming helper: success means domain receipts committed, not native PASS."""
import argparse,hashlib,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
sha=lambda b:hashlib.sha256(b).hexdigest()
def emit(p,v):
 with p.open('xb') as f:f.write((json.dumps(v,sort_keys=True)+'\n').encode())
def limits():
 resource.setrlimit(resource.RLIMIT_CPU,(4,4))
 resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--nonce',required=True);a=p.parse_args()
 raw=a.input.read_bytes();sys.stdout.buffer.write((json.dumps(dict(pid=os.getpid(),nonce=a.nonce,input_sha256=sha(raw),input_bytes=len(raw)),sort_keys=True)+'\n').encode());sys.stdout.buffer.flush()
 req=json.loads(raw);out=Path(req['domain_dir']);out.mkdir()
 emit(out/'REQUEST.json',dict(request=req,recorder_nonce=a.nonce,recorder_input_sha256=sha(raw),adapter_pid=os.getpid()))
 assert sha(Path(req['argv'][0]).read_bytes())==req['binary_sha256']
 for name,h in req['inputs'].items():assert sha(Path(name).read_bytes())==h
 env=dict(os.environ);env.update(req['environment']);start=time.monotonic_ns();used=resource.getrusage(resource.RUSAGE_CHILDREN)
 with (out/'stdout.bin').open('xb') as so,(out/'stderr.bin').open('xb') as se:
  child=subprocess.Popen(req['argv'],stdout=so,stderr=se,env=env,cwd=req['cwd'],start_new_session=True,preexec_fn=limits)
  emit(out/'LAUNCH.json',dict(argv=req['argv'],pid=child.pid,group=child.pid,source=req['source'],binary_sha256=req['binary_sha256'],start_ns=start))
  timeout=False
  try:code=child.wait(timeout=4)
  except subprocess.TimeoutExpired:
   timeout=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait(timeout=.3)
 cpu=resource.getrusage(resource.RUSAGE_CHILDREN)
 emit(out/'EXIT.json',dict(code=code,timeout=timeout,end_ns=time.monotonic_ns(),native_cpu_seconds=cpu.ru_utime+cpu.ru_stime-used.ru_utime-used.ru_stime))
 emit(out/'MANIFEST.json',{f.name:dict(bytes=f.stat().st_size,sha256=sha(f.read_bytes())) for f in sorted(out.iterdir()) if f.is_file()})
 assert not timeout and code>=0,'native timeout/signal; preserve incomplete recorder, no retry'
 # A returned native error is a completed observation for original domain oracles.
 sys.stdout.buffer.write(b'helper-output\n');sys.stderr.buffer.write(b'helper-diagnostic\n')
if __name__=='__main__':main()
