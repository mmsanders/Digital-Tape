#!/usr/bin/env python3
"""Frozen missing coordinates through unchanged55552ad fault/remount/model code.

Added transport: argv/syscall/raw capture, exact baseline/prefix authentication,
equivalent-projection deduplication, original cold-command selector and cost stops.
No original source, model, fault, state oracle or input is modified.
"""
import argparse,gzip,hashlib,importlib.util,json,os,re,resource,shlex,shutil,subprocess,sys,time,zipfile,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PKG=ROOT/'tests/wp10_missing_faults_r1';NEWPKG=ROOT/'tests/fault_cost_r2'
def sha(b):return hashlib.sha256(b).hexdigest()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--retained',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--judge',type=Path,required=True);a=ap.parse_args();assert not a.out.exists();a.out.mkdir(parents=True)
 start=time.monotonic();plan=json.loads((NEWPKG/'PLAN.json').read_text());basecat=json.loads((PKG/'BASELINE.json').read_text());
 for row in plan['rows']:
  row['estimated_cpu_seconds']=row['reserved_cpu_seconds'];row['estimated_compressed_bytes']=row['reserved_bytes']
 plan['rows_original25']=25
 def cpu():
  x=resource.getrusage(resource.RUSAGE_SELF);y=resource.getrusage(resource.RUSAGE_CHILDREN);return x.ru_utime+x.ru_stime+y.ru_utime+y.ru_stime+600 # conservative complete build/mechanics reserve
 gate_index=0;active_row=None
 def allocated(root):
  return sum(getattr(p.stat(),'st_blocks',0)*512 for p in root.rglob('*') if p.is_file())
 def reserve(seconds=10,extra=0):
  nonlocal gate_index
  completion_seconds=132 if active_row is not None else 60
  completion_bytes=32*1024**2 if active_row is not None else 16*1024**2
  used=allocated(a.out.parent);used_cpu=cpu()
  fact=dict(index=gate_index,cpu_including_build_reserve=used_cpu,workspace_allocated_bytes=used,
    next_seconds=seconds,next_bytes=extra,completion_seconds=completion_seconds,completion_bytes=completion_bytes,
    active_row=active_row,max_cpu_seconds=7200,max_bytes=2*1024**3)
  gp=a.out/'gates';gp.mkdir(exist_ok=True);(gp/(f'{gate_index:05d}.json')).write_text(json.dumps(fact,sort_keys=True)+'\n');gate_index+=1
  assert used_cpu+seconds+completion_seconds<=7200,'CPU cap: stop before next invocation'
  assert used+extra+completion_bytes<2*1024**3,'all working/evidence allocated storage cap'

 def put(name,b):
  p=a.out/name;p.parent.mkdir(parents=True,exist_ok=True)
  if not p.exists():p.write_bytes(b)
  else:assert p.read_bytes()==b,'refuse evidence overwrite'
  return name
 def js(name,obj):return put(name,(json.dumps(obj,indent=1,sort_keys=True)+'\n').encode())
 sys.path.insert(0,str(a.source/'tools/wp10-narrow'));import s467_load as L
 rl=L.rl;SD=L.sd
 original_oracle=load('original210_fault_oracle',a.source/'tests/wp10_narrow_supplement_r1/oracle.py')
 provenance=load('new241_provenance',PKG/'oracle.py')
 sys.path.insert(0,str(a.judge));judge=load('original199_load_state',a.judge/'load_rows.py')
 binary=rl.TAPECTL;native_sha=sha(binary.read_bytes());original_tapectl=rl.tapectl;counter=0
 records=[]
 recorder=load('cleared_recorder',ROOT/'host/evidence-recorder/recorder.py')
 assert sha((ROOT/'host/evidence-recorder/recorder.py').read_bytes())=='eb3597ad4ff378d2d140e116b659be467489c03ec77d60f24a2ecb91ccec7cf2'
 source_candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 def capture(args,env=None,cwd=None):
  nonlocal counter
  reserve();i=counter;counter+=1;rel=f'commands/{i:05d}';p=Path(args[1]);before=sha(p.read_bytes()) if p.exists() else None
  target=a.out/rel;target.parent.mkdir(parents=True,exist_ok=True)
  native=target/'native';target.mkdir();syscall=native/'syscalls.txt';specific=dict(env or {})
  assert all(k.startswith('TAPECTL_') for k in specific),specific.keys()
  argv=[str(Path(shutil.which('strace')).resolve()),'-f','-qq','-yy','-s','512','-e','trace=openat,lseek,write,pwrite64,fsync,fdatasync','-o',str(syscall),str(binary),*args]
  payload=dict(domain_dir=str(native),argv=argv,binary_sha256=sha(Path(argv[0]).read_bytes()),source='55552ad4fe57e99827ab8eb016044d0486017877',
    inputs={str(binary):native_sha,**({str(p):before} if before else {})},environment=specific,cwd=str(cwd) if cwd else None)
  payload_path=a.out/(f'request-{i:05d}.json');js(payload_path.name,payload)
  name=f'command-{i:05d}';nonce=hashlib.sha256(os.urandom(32)).hexdigest();stage=a.out/'recorder'/'incoming'/name/'input.bin'
  request=dict(case_id=name,argv=[str(Path(sys.executable).resolve()),'-B',str(ROOT/'host/fault-cost/adapter.py'),'--input',str(stage),'--nonce',nonce],
    input_sha256=sha(payload_path.read_bytes()),binary_sha256=sha(Path(sys.executable).resolve().read_bytes()),helper_sha256=sha((ROOT/'host/fault-cost/adapter.py').read_bytes()),source_commit=source_candidate,nonce=nonce,mode='text')
  js(f'recorder-request-{i:05d}.json',request)
  recorder.record(a.out/'recorder',request,payload_path)
  recorder.validate_case(a.out/'recorder'/'cases'/name,request)
  code=json.loads((native/'EXIT.json').read_bytes())['code']
  stdout=(native/'stdout.bin').read_bytes();stderr=(native/'stderr.bin').read_bytes()
  result=subprocess.CompletedProcess([str(binary),*args],code,stdout.decode(),stderr.decode())
  trace=Path(specific['TAPECTL_TEST_TRACE']) if 'TAPECTL_TEST_TRACE' in specific else None
  if trace and trace.exists():put(rel+'/seam.json',trace.read_bytes())
  wav=None
  if args[0]=='dump':
   q=Path(args[args.index('-o')+1])
   if q.exists():wav=sha(q.read_bytes());put('pcm/'+wav+'.wav',q.read_bytes())
  rec=dict(argv=[str(binary),*args],proxy_argv=argv,environment=specific,exit=code,input_before_sha256=before,input_after_sha256=sha(p.read_bytes()) if p.exists() else None,wav_sha256=wav,seam=rel+'/seam.json' if trace and trace.exists() else None,syscalls=rel+'/native/syscalls.txt',recorder_request=f'recorder-request-{i:05d}.json')
  js(rel+'/PROCESS.json',rec);records.append(rec);return result
 rl.tapectl=capture
 temp=a.out.parent/'software514-private';temp.mkdir(exist_ok=False);w=rl.make_worker(temp)
 pristine=w.base.read_bytes();assert sha(pristine)==plan['initial_sha256'];put('initial.img.gz',gzip.compress(pristine,6))
 voice=rl.SOURCE.read_bytes();assert sha(voice)==plan['source_wav_sha256'];put('source.wav',voice)
 with zipfile.ZipFile(a.retained/'load1.zip') as z:original=gzip.decompress(z.read('load/part-001-02/traces/'+plan['original_complete_trace_sha256']+'.jsonl.gz'))
 assert sha(original)==plan['original_complete_trace_sha256'];baseline=[json.loads(x) for x in original.splitlines()];put('original-baseline.jsonl',original)
 class Out:
  def put(self,n,b):return put(n,b)
  def put_json(self,n,o):return js(n,o)
 o=Out();normal_cache={};rows=[];stop=None
 def normalize(seam):
  out=[];wi=fi=0
  for e in seam['events']:
   if e['kind']=='write':
    assert e['bytes']==512 and e['offset']%512==0 and len(bytes.fromhex(e['data_hex']))==512
    out.append(dict(t='W',id=wi,call=wi,lba=e['offset']//512,ack=bool(e['ok']),phase='op',hex=e['data_hex']));wi+=1
   elif e['kind']=='flush':out.append(dict(t='F',ord=fi,ok=bool(e['success']),phase='op'));fi+=1
  return out
 # Actual allocated build/mechanics workspace gate; no fault if already over.
 assert allocated(a.out.parent)<=128*1024**2,'build/mechanics workspace exceeds128MiB; zero new faults'
 # At most one licensed complete positive, through the unchanged route.
 reserve(60,16*1024**2);_,pos=L.run_fault(o,w,temp,'none',None,pristine,sha(voice))
 positive=json.loads((a.out/'faults/none/seam-trace.json').read_text());assert normalize(positive)==baseline
 assert judge.check(pos['post_failure_remount'])=='new/new'
 js('POSITIVE.json',dict(native_binary_sha256=native_sha,complete_events=405,writes=353,barriers=52,record='faults/none/record.json'))
 assert cpu()-600<=60,'positive exceeded60CPU-seconds; stop before first fault'
 assert allocated(a.out.parent)<=144*1024**2,'build/positive workspace exceeded128+16MiB; stop before first fault'
 # Carry prior selected command contexts by original projection hash; do not replay them.
 with zipfile.ZipFile(a.retained/'return.zip') as z:
  for n in z.namelist():
   if n.startswith('stage3/commands/') and n.endswith('/original-remount.json'):
    q=json.loads(z.read(n));normal_cache[q['projection_sha256']]=dict(observation=q,state=judge.check(q),carried=True,origin=n)
 for row in plan['rows']:
  active_row=dict(kind=row['kind'],ordinal=row['ordinal']);reserve(row['reserved_cpu_seconds'],row['reserved_bytes']);t0=cpu();storage0=allocated(a.out.parent);files0={p for p in a.out.rglob('*') if p.is_file()};c0=len(records)
  try:
   name,rec=L.run_fault(o,w,temp,row['kind'],row['ordinal'],pristine,sha(voice));original_oracle.host_fault(rec)
   raw=json.loads((a.out/f'faults/{name}/seam-trace.json').read_text());trace=normalize(raw)
   assert len(trace)==row['trace_index']+1 and trace[:-1]==baseline[:row['trace_index']]
   canonical=b''.join(json.dumps(e,sort_keys=True).encode()+b'\n' for e in trace[:-1]);assert sha(canonical)==row['successful_prefix_sha256']
   bars=[e['ord'] for e in trace[:-1] if e['t']=='F' and e['ok']];assert bars==row['prior_successful_barriers']
   attempt=trace[-1];assert attempt['t']==('W' if row['kind']=='write' else 'F')
   if row['kind']=='write':assert attempt['lba']==row['lba'] and sha(bytes.fromhex(attempt['hex']))==row['payload_sha256'] and not attempt['ack']
   else:assert not attempt['ok']
   syscall=(a.out/records[c0]['syscalls']).read_text();pattern=r'(?:lseek|pwrite64|write)\(-1[^\n]*= -1 EBADF[^\n]*' if row['kind']=='write' else r'(?:fsync|fdatasync)\(-1[^\n]*= -1 EBADF[^\n]*'
   hit=re.findall(pattern,syscall);assert hit,'missing actual failed OS return; no summary-only claim'
   # Carried model retains attempted failed-call eligibility (conservative), while
   # working reconstruction uses only confirmed visible effects. Neither is a
   # physical persistence observation or a new no-write crash oracle.
   dev=SD.replay(pristine,trace);working=b''.join(dev.working.get(i,bytes(512)) for i in range(len(pristine)//512))
   after=gzip.decompress((a.out/f'faults/{name}/image-after.img.gz').read_bytes());assert working==after and sha(after)==rec['image_after_sha256']
   durable=SD.materialize(dev,[],len(pristine)//512);touched=sorted({e.lba for e in dev.events})
   mode,plans=SD.plans(dev.events);unique={};order_digest=hashlib.sha256()
   for p in plans:
    order=p['landing_order'];order_digest.update(SD._canon(order)+b'\n')
    # Exact last-write-per-LBA equivalence before materializing a whole image.
    by={e.id:e for e in dev.events};effect={by[i].lba:by[i].data for i in order};sig=tuple(sorted((l,sha(b)) for l,b in effect.items()))
    if sig in unique:continue
    image=SD.projection(dev,order,durable,touched);h=sha(image);unique[sig]=dict(image_sha256=h,landing_order=order)
    if h not in normal_cache:
     reserve();obs=rl.remount(w,temp,('load','voice.wav'),image);state=judge.check(obs)
     js('projections/'+h+'/observation.json',obs);normal_cache[h]=dict(observation=obs,state=state,carried=False)
   assert len(plans)==row['model_order_class_bound'] and len(unique)<=row['projection_bound'],'actual model differs from issued two-class bound'
   byhash={p['image_sha256']:p for p in unique.values()};first={};selected={}
   for h in sorted(byhash):
    item=normal_cache[h];first.setdefault(item['state'],h)
    needs=any(e.get('needs_repair') for k in ('verify','dump_A','dump_B') for e in item['observation'][k]['engine'] if e['kind']=='engine_info')
    if needs:selected.setdefault(h,[]).append('needs_repair')
   for state,h in first.items():selected.setdefault(h,[]).append('first '+state)
   for h in selected:
    image=SD.projection(dev,byhash[h]['landing_order'],durable,touched);assert sha(image)==h
    put('projections/'+h+'/projection.img.gz',gzip.compress(image,6))
   state=judge.check(rec['post_failure_remount']);assert sha(rl.SOURCE.read_bytes())==sha(voice)
   proof=dict(requested=dict(kind=row['kind'],ordinal=row['ordinal']),fault_fired=rec['fault_fired'],exit=rec['exit'],initial_sha256=sha(pristine),source_wav_sha256=sha(voice),successful_prefix_sha256=sha(canonical),prior_successful_barriers=bars,history_complete=trace[:-1]==baseline[:row['trace_index']],setup_preserved=sha(pristine)==plan['initial_sha256'],failure_actual_return_bytes=0,failure_os_error=hit,attempted_bytes=row['attempted_bytes'],raw_bound=True,carried199_state_pass=all(judge.check(normal_cache[h]['observation']) for h in byhash),source_before_sha256=sha(voice),source_after_sha256=sha(rl.SOURCE.read_bytes()))
   provenance.check(proof,row)
   compressed=sum(len(zlib.compress(p.read_bytes(),6)) for p in a.out.rglob('*') if p.is_file() and p not in files0)
   result=dict(coordinate=dict(kind=row['kind'],ordinal=row['ordinal']),status='executed; independent disposition pending',original_record=f'faults/{name}/record.json',provenance=proof,actual_syscall_return=-1,actual_syscall_error='EBADF',confirmed_landed_bytes=0,working_reconstruction_sha256=sha(working),model=mode,model_orders=len(plans),model_orders_sha256=order_digest.hexdigest(),projections=list(byhash.values()),selected=selected,working_state=state,actual_cpu_seconds=cpu()-t0,new_compressed_bytes=compressed)
   rows.append(result);js(f'faults/{name}/NEW241.json',result)
   result['new_allocated_working_bytes']=max(0,allocated(a.out.parent)-storage0)
   js(f'faults/{name}/COST255.json',dict(actual_cpu_seconds=result['actual_cpu_seconds'],new_allocated_working_bytes=result['new_allocated_working_bytes'],reserved_cpu_seconds=row['reserved_cpu_seconds'],reserved_bytes=row['reserved_bytes']))
   if result['actual_cpu_seconds']>row['reserved_cpu_seconds'] or result['new_allocated_working_bytes']>row['reserved_bytes']:
    stop='actual row exceeded original conservative reservation; stop before next row and return actual cost';break
  except Exception as e:
   stop=repr(e);js('STOP.json',dict(coordinate=row,error=stop,commands_started=counter,actual_cpu_seconds=cpu()));break
  finally:pass
 result=dict(source='55552ad4fe57e99827ab8eb016044d0486017877',original443=plan['original443'],engine_tree=plan['engine_tree'],method_tree='f9083b328dbff20fa5dfc746b9b5b87045b40f6e',recorder_clearance='87e94160f62922a06346d00dc69f4dfcda987328',native_binary_sha256=native_sha,scheduled=4,executed=len(rows),remaining=plan['rows'][len(rows):],stop=stop,cpu_seconds_including_600_build_reserve=cpu(),wall_seconds=time.monotonic()-start,old39_replayed=False,full443_accepted=False)
 js('LEDGER.json',rows);js('RESULT.json',result);js('FILES.json',{p.relative_to(a.out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in a.out.rglob('*') if p.is_file()})
 archive=a.out.parent/'software514-exact-return.zip'
 with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in a.out.rglob('*'):
   if p.is_file():z.write(p,p.relative_to(a.out).as_posix())
 print(json.dumps(result,indent=2));print('ARCHIVE',archive.stat().st_size,sha(archive.read_bytes()))
if __name__=='__main__':main()
