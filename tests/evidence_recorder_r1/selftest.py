"""Method controls only: synthetic receipts and actual harmless helper bytes.

Does not implement or qualify Software's recorder. All temporary data is owned.
"""
import copy,io,json,pathlib,subprocess,sys,tempfile,zipfile,warnings
from cases import corpus
from oracle import canon,sha,inventory,check_complete,check_archive

ROOT=pathlib.Path(__file__).resolve().parent
def seal(f):
 f={k:v for k,v in f.items() if k!='MANIFEST.json'}
 return dict(f,**{'MANIFEST.json':canon(inventory(f))})
def fixture():
 # Deliberately synthetic, never represented as a captured child receipt.
 b=b'owned input\n';r=dict(case_id='synthetic',mode='text',input_sha256=sha(b),argv=['synthetic-helper'],binary_sha256='a'*64,source_commit='b'*40,helper_sha256=sha((ROOT/'helper.py').read_bytes()),nonce='synthetic-nonce')
 h=dict(pid=123,nonce=r['nonce'],input_sha256=sha(b),input_bytes=len(b))
 out=canon(h)+b'helper-output\n';err=b'helper-diagnostic\n'
 f={'input.bin':b,'request.json':canon(r),'launch.json':canon(dict(r,pid=123)),
 'stdout.bin':out,'stderr.bin':err,'exit.json':canon(dict(code=0)),
 'timing.json':canon(dict(start_ns=10,end_ns=20,duration_ns=10,cpu_ns=4,finalized=True)),
 'result.json':canon(dict(case_id='synthetic',evidence='complete',exit=0,stdout_bytes=len(out),stderr_bytes=len(err)))}
 return seal(f),r
def zipped(f,extra=None,duplicate=False):
 b=io.BytesIO()
 with warnings.catch_warnings():
  warnings.simplefilter('ignore',UserWarning)
  with zipfile.ZipFile(b,'w',zipfile.ZIP_STORED) as z:
   for n,v in f.items():z.writestr(n,v)
   z.writestr('ARCHIVE-MANIFEST.json',canon(inventory(f)))
   if extra:z.writestr(extra,b'bad')
   if duplicate:z.writestr(next(iter(f)),b'bad')
 return b.getvalue()
def rejects(call):
 try:call()
 except (AssertionError,KeyError,ValueError,zipfile.BadZipFile):return
 raise AssertionError('negative control admitted')

def main():
 rows=corpus();assert len({r['name'] for r in rows})==32
 f,r=fixture();assert check_complete(f,r)=='COMPLETE_EVIDENCE'
 names=[]
 for name in [x['name'] for x in rows if x['kind']=='actual-positive-copy-corruption']:
  m=copy.deepcopy(f)
  if name=='changed-stdout':m['stdout.bin']+=b'changed'
  elif name=='truncated-stderr':m['stderr.bin']=m['stderr.bin'][:-1]
  elif name=='missing-exit':del m['exit.json']
  elif name=='missing-input':del m['input.bin']
  elif name=='stale-timing-checksum':
   t=json.loads(m['timing.json']);t['cpu_ns']+=1;m['timing.json']=canon(t)
  elif name in ('wrong-argv','wrong-binary','wrong-source','wrong-input-identity','wrong-nonce','wrong-pid'):
   k={'wrong-argv':'argv','wrong-binary':'binary_sha256','wrong-source':'source_commit','wrong-input-identity':'input_sha256','wrong-nonce':'nonce','wrong-pid':'pid'}[name]
   target='request.json' if k=='input_sha256' else 'launch.json'
   d=json.loads(m[target]);d[k]=['different'] if k=='argv' else 124 if k=='pid' else 'different';m[target]=canon(d)
  elif name=='unlisted-case-file':m['unlisted']=b'extra'
  elif name=='incomplete-promoted':del m['timing.json']
  elif name=='wrong-stream-count':
   d=json.loads(m['result.json']);d['stdout_bytes']+=1;m['result.json']=canon(d)
  elif name=='negative-timing':
   d=json.loads(m['timing.json']);d['cpu_ns']=-1;m['timing.json']=canon(d)
  else:raise AssertionError(name)
  # Semantic mutations must survive internal checksum repair, unlike stale hash.
  if name!='stale-timing-checksum':m=seal(m)
  rejects(lambda:check_complete(m,r));names.append(name)
 assert check_archive(zipped(f),f)=='ARCHIVE_AUTHENTICATED'
 for name,b in [('archive-extra',zipped(f,extra='extra')),('archive-duplicate',zipped(f,duplicate=True)),('archive-traversal',zipped(f,extra='../escape')),('archive-truncated',zipped(f)[:-25])]:
  rejects(lambda:check_archive(b,f));names.append(name)
 actual=[]
 with tempfile.TemporaryDirectory(prefix='verification252-helper-',dir=ROOT) as tmp:
  p=pathlib.Path(tmp)/'input.bin';p.write_bytes('owned \u03bb input\n'.encode())
  for mode in ('text','binary','empty','exit7'):
   nonce='stage1-helper-'+mode
   a=[sys.executable,'-B',str(ROOT/'helper.py'),'--mode',mode,'--input',str(p),'--nonce',nonce]
   proc=subprocess.run(a,capture_output=True,timeout=5)
   head,body=proc.stdout.split(b'\n',1);h=json.loads(head)
   assert h['pid']>0 and h['nonce']==nonce and h['input_sha256']==sha(p.read_bytes()) and h['input_bytes']==len(p.read_bytes())
   assert body==(b'\x00\xffraw\n' if mode=='binary' else b'' if mode=='empty' else b'helper-output\n')
   assert proc.stderr==(b'\x80diagnostic\n' if mode=='binary' else b'' if mode=='empty' else b'helper-diagnostic\n')
   assert proc.returncode==(7 if mode=='exit7' else 0);actual.append(mode)
 print(json.dumps(dict(scope='STAGE1 METHOD ONLY; recorder acceptance pending',frozen_cases=len(rows),synthetic_positive=1,synthetic_rejected=names,actual_harmless_helper_modes=actual),sort_keys=True))

if __name__=='__main__':main()
