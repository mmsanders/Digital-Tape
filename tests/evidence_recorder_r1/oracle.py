"""Independent evidence protocol checks; no recorder implementation."""
import hashlib,io,json,pathlib,re,zipfile
sha=lambda b:hashlib.sha256(b).hexdigest()
canon=lambda x:(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
REQUIRED={'request.json','input.bin','launch.json','stdout.bin','stderr.bin','exit.json','timing.json','result.json'}
def inventory(files):return {n:dict(bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())}
def check_complete(files,request):
 assert re.fullmatch('[a-z][a-z0-9-]{0,63}',request['case_id'])
 assert set(files)==REQUIRED|{'MANIFEST.json'}
 original={n:b for n,b in files.items() if n!='MANIFEST.json'}
 assert json.loads(files['MANIFEST.json'])==inventory(original),'final byte inventory mismatch'
 assert json.loads(files['request.json'])==request,'wrong external request identity'
 assert sha(files['input.bin'])==request['input_sha256']
 launch=json.loads(files['launch.json'])
 for k in ('argv','binary_sha256','source_commit','helper_sha256','nonce'):
  assert launch[k]==request[k],k+' identity'
 assert type(launch['pid']) is int and launch['pid']>0
 head,body=files['stdout.bin'].split(b'\n',1);head=json.loads(head)
 assert head==dict(pid=launch['pid'],nonce=request['nonce'],input_sha256=request['input_sha256'],input_bytes=len(files['input.bin']))
 mode=request['mode']
 expected_out=b'\x00\xffraw\n' if mode=='binary' else b'' if mode=='empty' else b'helper-output\n'
 expected_err=b'\x80diagnostic\n' if mode=='binary' else b'' if mode=='empty' else b'helper-diagnostic\n'
 assert body==expected_out and files['stderr.bin']==expected_err
 e=json.loads(files['exit.json']);assert type(e['code']) is int and e['code']==(7 if mode=='exit7' else 0)
 t=json.loads(files['timing.json'])
 assert all(type(t[k]) is int and t[k]>=0 for k in ('start_ns','end_ns','duration_ns','cpu_ns'))
 assert t['end_ns']>=t['start_ns'] and t['duration_ns']==t['end_ns']-t['start_ns'] and t['finalized'] is True
 r=json.loads(files['result.json'])
 assert r==dict(case_id=request['case_id'],evidence='complete',exit=e['code'],stdout_bytes=len(files['stdout.bin']),stderr_bytes=len(files['stderr.bin']))
 return 'COMPLETE_EVIDENCE'
def check_archive(raw,expected_files):
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  names=z.namelist();assert len(names)==len(set(names)),'duplicate archive member'
  assert all(not n.startswith('/') and '..' not in pathlib.PurePosixPath(n).parts and '\\' not in n and ':' not in n for n in names)
  assert set(names)==set(expected_files)|{'ARCHIVE-MANIFEST.json'}
  assert json.loads(z.read('ARCHIVE-MANIFEST.json'))==inventory(expected_files)
  for n,b in expected_files.items():assert z.read(n)==b
 return 'ARCHIVE_AUTHENTICATED'
