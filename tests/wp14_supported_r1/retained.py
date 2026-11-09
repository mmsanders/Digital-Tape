"""Independent named-artifact byte oracle; no devices, decompression or acceptance."""
import hashlib,json
from pathlib import Path
from qualification_supported import parse_platforms
from native import capture_identity

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for b in iter(lambda:stream.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def audit_retained(natives,captures,platforms=None,resolver=None):
 parts=parse_platforms(','.join(platforms)) if platforms is not None else parse_platforms()
 assert set(natives)==set(parts),'named native evidence missing'
 roots={p:(Path(captures)/('wp14-native-evidence-'+p)).resolve() for p in parts}
 assert all(r.is_dir() for r in roots.values()),'named retained artifact missing'
 proof=[];bound={}
 def bind(original,expected,p):
  assert isinstance(original,str) and '/wp14-evidence/' in original.replace('\\','/'),'invalid retained path'
  suffix=original.replace('\\','/').split('/wp14-evidence/',1)[1];path=(roots[p]/suffix).resolve()
  assert path.is_relative_to(roots[p]),'retained path escape'
  if resolver is not None and not path.is_file():resolver(path)
  assert path.resolve().is_relative_to(roots[p]),'restored retained path escape'
  assert path.is_file(),'retained file missing'
  assert sha(path)==expected,'retained hash mismatch'
  assert original not in bound or bound[original]==path,'ambiguous original path'
  bound[original]=path;proof.append(dict(platform=p,original=original,retained=str(path),sha256=expected));return path
 for p in parts:
  rows=natives[p]['results'];assert isinstance(rows,list) and rows,'empty or malformed native results'
  for row in rows:
   req,res=row['request'],row['response'];capture_identity(req,res)
   artifacts=res['capture_artifacts'];assert isinstance(artifacts,list) and artifacts
   captured={}
   for a in artifacts:
    assert a['path'] not in captured,'duplicate retained path'
    bind(a['path'],a['sha256'],p);captured[a['path']]=a['sha256']
   for original in list(captured):
    if original.replace('\\','/').endswith('/large-artifacts.json'):
     index=json.loads(bound[original].read_text(encoding='utf-8'));assert isinstance(index,list)
     for a in index:
      assert a['path'] not in captured or captured[a['path']]==a['sha256'],'conflicting retained hash'
      bind(a['path'],a['sha256'],p);captured[a['path']]=a['sha256']
   if req.get('required_os_readme'):
    original=res['snapshot'];meta=original+'.extents.json';blocks=original+'.blocks'
    assert meta in captured and blocks in captured,'snapshot retained metadata missing'
    expected=json.loads(bound[meta].read_text(encoding='utf-8'))['sha256'];bind(original,expected,p)
   if req.get('roundtrip'):
    assert isinstance(res['dumps'],dict) and res['dumps'],'roundtrip dump missing'
    for original in res['dumps'].values():
     assert original in captured,'dump not authenticated';bind(original,captured[original],p)
 return proof

def ignored_inputs(bundle,captures,platforms):
 named=set(parse_platforms(','.join(platforms)));ignored=[]
 for p in set(('linux','macos','windows'))-named:
  if Path(bundle).is_dir():
   for item in Path(bundle).iterdir():
    if any(item.name.endswith('-'+p+ext) for ext in ('.json','.stderr','.json.zst')):ignored.append(item.name)
  name='wp14-native-evidence-'+p
  if (Path(captures)/name).exists():ignored.append(name)
 return sorted(ignored)
