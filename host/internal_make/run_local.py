"""ONE approved finite ordinary-file composition/reference matrix. Preserve every STOP."""
import argparse,ctypes,hashlib,importlib.util,json,os,shutil,subprocess,sys,time
from ctypes import wintypes as w
from pathlib import Path
SIZE=20972032
CASES=['positive','initial-query-failure','unknown-safety','policy-refusal','provision-failure','load-failure','verify-failure','media-change','media-remove','query-failure']
FIXTURE='48f1b3c7ce7fe27a90469364f841803087a9d274a4af9a4ec8ee195a2846ac18'
METHOD_BLOBS={'tests/windows_make_core_r1/README.md':'4a54f725dab57d591d032c8ccb3e30eb22754d10','tests/windows_make_core_r1/oracle.py':'0d1e56c04c8edd1d9324001068915b45626af0b7','tests/wp14_r1/oracle.py':'90b8a79114ebb645db3403bcdfa6f605d84228b4','tests/windows_make_port_r1/README.md':'8bd2870d5a744d9d086a3291ec4fcfa98fb7df34','tests/windows_make_port_r1/admission.py':'e1d9d9a1a7fd8841037e2227258fb89272a2c044'}

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def load_module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')

class Standard(ctypes.Structure):
 _fields_=[('AllocationSize',ctypes.c_longlong),('EndOfFile',ctypes.c_longlong),('NumberOfLinks',w.DWORD),('DeletePending',w.BYTE),('Directory',w.BYTE)]
class Info(ctypes.Structure):
 _fields_=[('attributes',w.DWORD),('created',w.FILETIME),('accessed',w.FILETIME),('written',w.FILETIME),('volume',w.DWORD),('size_hi',w.DWORD),('size_lo',w.DWORD),('links',w.DWORD),('index_hi',w.DWORD),('index_lo',w.DWORD)]

def ordinary_facts(p,ordinary):
 ordinary(p)
 kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 kernel.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,w.LPVOID,w.DWORD,w.DWORD,w.HANDLE];kernel.CreateFileW.restype=w.HANDLE
 kernel.GetFileInformationByHandle.argtypes=[w.HANDLE,ctypes.POINTER(Info)]
 kernel.GetFileInformationByHandleEx.argtypes=[w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD]
 kernel.GetFinalPathNameByHandleW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,w.DWORD]
 kernel.CloseHandle.argtypes=[w.HANDLE]
 handle=kernel.CreateFileW(str(p),0x80,7,None,3,0x80,None)
 assert handle not in (None,w.HANDLE(-1).value),'STOP ordinary attributes open'
 try:
  info=Info();standard=Standard();final=ctypes.create_unicode_buffer(32768)
  assert kernel.GetFileInformationByHandle(handle,ctypes.byref(info))
  assert kernel.GetFileInformationByHandleEx(handle,1,ctypes.byref(standard),ctypes.sizeof(standard))
  n=kernel.GetFinalPathNameByHandleW(handle,final,len(final),0);assert 0<n<len(final)
  canonical=final.value.removeprefix('\\\\?\\')
  assert os.path.normcase(canonical)==os.path.normcase(str(p.resolve()))
  assert not info.attributes & (0x200|0x400|0x10)
  assert standard.EndOfFile==SIZE and standard.AllocationSize>=SIZE and not standard.Directory
  return dict(identity=f'{info.volume:08x}:{info.index_hi:08x}:{info.index_lo:08x}',canonical=canonical,
              ordinary_owned=True,reparse=False,sparse=False,bytes=standard.EndOfFile,
              allocated_bytes=standard.AllocationSize,initial_sha256=sha(p),open_mode='existing',truncate=False,
              attributes=info.attributes,links=info.links)
 finally:assert kernel.CloseHandle(handle)

def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--source',required=True)
 p.add_argument('--receipt',type=Path,required=True);p.add_argument('--method',type=Path,required=True)
 p.add_argument('--context-method',type=Path,required=True);p.add_argument('--fixture',type=Path,required=True)
 p.add_argument('--tool-context',required=True);a=p.parse_args()
 context=load_module('owned_context',a.context_method.absolute()/'context.py')
 base=a.receipt.absolute();context.ordinary(base.parent,True);assert not base.exists();base.mkdir()
 receipt=dict(source_head=a.source,scope='internal-file-composition',start_ns=time.time_ns(),verdict='STOP',matrix_attempts=0,children=[])
 session=base/'SESSION.private.json';deadline=time.monotonic()+600
 def save():dump(session,receipt)
 save()
 try:
  receipt['context']=context.current(a.tool_context);save();context.admit(receipt['context'])
  method=a.method.absolute()
  for name,pin in METHOD_BLOBS.items():
   data=(method/name).read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==pin
  core=load_module('frozen_core',method/'tests/windows_make_core_r1/oracle.py')
  admission=load_module('frozen_port',method/'tests/windows_make_port_r1/admission.py')
  bundle=a.bundle.absolute();context.ordinary(bundle,True)
  build=json.loads((bundle/'BUILD.json').read_text(encoding='utf-8-sig'))
  assert build['source_head']==a.source and build['reference_source']=='bf2381c9c187c14ce65cc501b13f9eb512c99693'
  assert build['method']=='a901272c91c781c9278c4abe6e36d68bcfa5fb79' and build['port_addendum']=='420e5cf3172376c5edeb95aeb73733c84a83d201'
  assert build['executions']==0
  for name in ['reference.exe','composition.exe']:
   context.ordinary(bundle/name);assert sha(bundle/name)==build['binaries'][name]
  fixture=a.fixture.absolute();context.ordinary(fixture);assert sha(fixture)==FIXTURE
  receipt['build']=build;receipt['fixture']=str(fixture);receipt['fixture_sha256']=FIXTURE
  receipt['driver_sha256']=sha(Path(__file__));receipt['method_files']={str(x.relative_to(method)):sha(x) for x in method.rglob('*') if x.is_file() and '__pycache__' not in x.parts}
  receipt['free_before']=shutil.disk_usage(base).free
  assert receipt['free_before']>=20*SIZE+1024**3,'STOP twin profile plus1GiB headroom required'
  sentinel=base/'foreign-sentinel.txt';sentinel.write_bytes(b'UNCHANGED\n');sentinel_hash=sha(sentinel)
  work=base/'matrix';work.mkdir();twins={}
  # Fresh owned files, written in full. No truncate/sparse/create-image API.
  zero=bytes(1024*1024)
  for case in CASES:
   twins[case]=[]
   for mode in ['reference','composition']:
    path=work/f'{case}.{mode}.img'
    with path.open('xb') as f:
     remaining=SIZE
     while remaining:
      data=zero[:min(len(zero),remaining)];assert f.write(data)==len(data);remaining-=len(data)
     f.flush();os.fsync(f.fileno())
    fact=ordinary_facts(path,context.ordinary);assert fact['initial_sha256']==admission.ZERO
    twins[case].append(fact)
  receipt['twins_before']=twins;receipt['free_after_materialization']=shutil.disk_usage(base).free;save()
  assert receipt['free_after_materialization']>=1024**3
  for case in CASES:
   admission.qualify(dict(twins=twins[case],calls_hport_os_create=False,sparse_ioctl=False,device_branch=False,
    same_uuid_epoch_input_fault=True,source_sentinel_unchanged=sha(fixture)==FIXTURE and sha(sentinel)==sentinel_hash,
    retained_session_closed_by_owner_only=True,fault_closes_retained_handle=False,fault_rule_shared_with_reference=True))
  receipt['matrix_attempts']=1;save()
  for mode in ['reference','composition']:
   argv=[str(bundle/(mode+'.exe')),str(work),str(fixture)]
   child=dict(mode=mode,argv=argv,cwd=str(work),start_ns=time.time_ns(),forced_cleanup=False);receipt['children'].append(child);save()
   with (base/(mode+'.supervisor.stdout')).open('xb') as out,(base/(mode+'.supervisor.stderr')).open('xb') as err:
    remaining=deadline-time.monotonic();assert remaining>0,'STOP overall600s deadline'
    proc=subprocess.Popen(argv,cwd=work,stdin=subprocess.DEVNULL,stdout=out,stderr=err);child['pid']=proc.pid;save()
    try:child['exit']=proc.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
     child['forced_cleanup']=True;proc.kill();child['exit']=proc.wait(timeout=10)
    except BaseException:
     child['forced_cleanup']=True;proc.kill();child['exit']=proc.wait(timeout=10);raise
   child['end_ns']=time.time_ns();save();assert child['exit']==0 and not child['forced_cleanup'],'STOP actual adapter'
  rows=[];fault_records={}
  for case in CASES:
   data={};events={};outputs={};hashes={}
   for mode in ['reference','composition']:
    prefix=work/f'{case}.{mode}';data[mode]=json.loads(Path(str(prefix)+'.result.json').read_text())
    assert data[mode]['source_head']==a.source and data[mode]['case']==case and data[mode]['mode']==mode
    events[mode]=[json.loads(line) for line in Path(str(prefix)+'.events.jsonl').read_text().splitlines()]
    outputs[mode]=Path(str(prefix)+'.stdout.bin').read_bytes();image=Path(str(prefix)+'.img')
    now=ordinary_facts(image,context.ordinary);assert now['identity']==twins[case][0 if mode=='reference' else 1]['identity']
    assert all(e['file_id']==now['identity'] for e in events[mode] if 'file_id' in e)
    hashes[mode]=now['initial_sha256']
   rc=data['composition']['exit'];assert rc==data['reference']['exit']
   assert hashes['composition']==hashes['reference'] and outputs['composition']==outputs['reference']
   faults={mode:[e for e in events[mode] if e.get('fault_injected')] for mode in events}
   if case in ['provision-failure','load-failure','verify-failure']:
    assert all(len(faults[m])==1 for m in faults)
    keys=('phase','op','offset','length','ordinal','result','os_error_code')
    assert {k:faults['composition'][0][k] for k in keys}=={k:faults['reference'][0][k] for k in keys}
    assert faults['composition'][0]['result']!=0 and faults['composition'][0]['os_error_code']!=0
   else:assert not any(faults.values())
   fault_records[case]=faults
   terminal_events=[e for e in events['composition'] if e['op'] in ['phase-failure','media-change','query-failure']]
   after=bool(terminal_events and len(outputs['composition'])!=terminal_events[-1]['stdout_position'])
   row=dict(case=case,scope='internal-file-composition',backend='ordinary-file',observer='compiled-callbacks',raw_refs=[f'matrix/{case}.composition.events.jsonl',f'matrix/{case}.reference.events.jsonl',f'matrix/{case}.composition.result.json',f'matrix/{case}.reference.result.json','SESSION.private.json'],shipping_image_flag=False,shipping_make_enabled=False,elevated=receipt['context']['token_elevated'],source_unchanged=sha(fixture)==FIXTURE,foreign_sentinel_unchanged=sha(sentinel)==sentinel_hash,external_io=False,required_initial_query_ok=case!='initial-query-failure',required_facts_known=case!='unknown-safety',policy_facts={'whole':case!='policy-refusal'},events=events['composition'],terminal=data['composition']['terminal'],exit=rc,open_attempt_count=data['composition']['open_attempt_count'],normal_output_after_terminal=after,identity_inputs_equal=True,composition_exit=rc,baseline_exit=data['reference']['exit'],composition_stdout_hex=outputs['composition'].hex(),baseline_stdout_hex=outputs['reference'].hex(),composition_image_sha256=hashes['composition'],baseline_image_sha256=hashes['reference'])
   core.check(row);rows.append(row)
  dump(base/'faults.private.json',fault_records);dump(base/'trace.private.json',dict(source_head=a.source,rows=rows))
  receipt['verdict']='PRODUCER frozen component predicates PASS; independent299 disposition pending'
  receipt['source_unchanged']=sha(fixture)==FIXTURE;receipt['sentinel_unchanged']=sha(sentinel)==sentinel_hash
  assert receipt['source_unchanged'] and receipt['sentinel_unchanged']
 except BaseException as error:
  receipt['error']=repr(error);raise
 finally:
  receipt['end_ns']=time.time_ns();save()
  inventory=[]
  for path in sorted(base.rglob('*')):
   if path.is_file() and path.name!='INVENTORY.private.json':inventory.append(dict(path=path.relative_to(base).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
  dump(base/'INVENTORY.private.json',dict(closed=True,files=inventory))

if __name__=='__main__':main()
