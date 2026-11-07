"""Synthetic decomposition tests only; no Product run or native acceptance."""
import ast,copy,hashlib,json,tempfile
from pathlib import Path
import qualification_supported as q
from retained import audit_retained,ignored_inputs

def reject(fn):
 try:fn()
 except (AssertionError,ValueError,KeyError,TypeError,OSError):return
 raise AssertionError('control survived')
def fixture(root,parts):
 natives={}
 for p in parts:
  d=root/('wp14-native-evidence-'+p);d.mkdir(parents=True);prefix='/synthetic/'+p+'/wp14-evidence/'
  data={'capture.raw':b'SYNTHETIC SAVED CAPTURE','dump.wav':b'SYNTHETIC DUMP','snapshot.img':b'SYNTHETIC SNAPSHOT','snapshot.img.blocks':b'SYNTHETIC BLOCKS','large.raw':b'SYNTHETIC INDEXED ONLY'}
  data['snapshot.img.extents.json']=json.dumps(dict(sha256=hashlib.sha256(data['snapshot.img']).hexdigest())).encode()
  data['large-artifacts.json']=json.dumps([dict(path=prefix+'large.raw',sha256=hashlib.sha256(data['large.raw']).hexdigest())]).encode()
  for name,raw in data.items():(d/name).write_bytes(raw)
  req=dict(case='synthetic-unit-only',platform=p,control=None,roundtrip=True,required_os_readme=True)
  req['request_sha256']=hashlib.sha256(json.dumps(req,sort_keys=True).encode()).hexdigest()
  res=dict(case=req['case'],platform=p,capture_origin='native-candidate',binary_sha256='2'*64,head_sha='1'*40,request_sha256=req['request_sha256'],control_applied=None,os_build='SYNTHETIC NOT A PRODUCT RUN',snapshot=prefix+'snapshot.img',dumps=dict(A=prefix+'dump.wav'),capture_artifacts=[dict(path=prefix+n,sha256=hashlib.sha256(raw).hexdigest()) for n,raw in data.items() if n not in ('snapshot.img','large.raw')])
  natives[p]=dict(results=[dict(request=req,response=res)])
 return natives

def main():
 checks=[];controls=[]
 # Prove the reused per-platform statements are unchanged, not a relaxed clone.
 old=ast.parse((Path(__file__).resolve().parent.parent/'wp14_r1/qualification.py').read_text(encoding='utf-8'));new=ast.parse(Path(q.__file__).read_text(encoding='utf-8'))
 get=lambda tree,name:next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
 ob=next(n for n in get(old,'audit').body if isinstance(n,ast.For));nb=next(n for n in get(new,'audit_platforms').body if isinstance(n,ast.For))
 assert ast.dump(ob)==ast.dump(nb)
 assert [ast.dump(n) for n in get(old,'audit').body[1:-1]]==[ast.dump(n) for n in get(new,'audit_platforms').body[1:-1]]
 checks.append('unchanged-original-per-platform-loop-AST')
 altered=copy.deepcopy(nb);altered.body.pop();assert ast.dump(ob)!=ast.dump(altered);controls.append('removed-per-platform-assertions')
 for parts in [('linux','windows'),('linux','macos','windows')]:
  assert q.parse_platforms(','.join(parts))==parts;q.validate_maps({x:{} for x in parts},{x:{} for x in parts},parts);checks.append('named-set-'+','.join(parts))
 for value in ['', 'windows','linux','macos','windows,linux','linux,linux,windows','linux,windows,macos','linux, windows','linux,other,windows',None]:reject(lambda value=value:q.parse_platforms(value));controls.append('invalid-list-'+str(value))
 for p in ('linux','windows'):
  reject(lambda p=p:q.validate_maps({x:{} for x in ('linux','windows') if x!=p},{x:{} for x in ('linux','windows')},('linux','windows')));controls.append('missing-map-'+p)
 reject(lambda:q.validate_maps(dict(linux={},windows={}),dict(linux={},windows={})));controls.append('default-still-needs-macos')
 # Full audit rejects omitted native cases after valid image metadata, without
 # substituting a Product response or weakening the original semantic oracle.
 images={p:dict(kind='candidate-image-cases',platform=p,head_sha='1'*40,cases=q.image_cases(),controls_killed=q.IMAGE_CONTROLS,full_c60=True) for p in ('linux','windows')}
 natives={p:dict(kind='native-candidate-cases',platform=p,head_sha='1'*40,os_build='SYNTHETIC',results=[]) for p in images}
 reject(lambda:q.audit_platforms(images,natives,'1'*40,('linux','windows')));controls.append('omitted-all-native-cases')
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);n=fixture(root,('linux','windows'));proof=audit_retained(n,root,('linux','windows'));assert len(proof)>10;checks.append('two-platform-real-saved-byte-authentication')
  for p in ('linux','windows'):
   changed=copy.deepcopy(n);changed[p]['results'][0]['response']['capture_artifacts'][0]['sha256']='0'*64;reject(lambda:audit_retained(changed,root,('linux','windows')));controls.append('mutated-retained-'+p)
   changed=copy.deepcopy(n);changed[p]['results']=[];reject(lambda:audit_retained(changed,root,('linux','windows')));controls.append('empty-results-'+p)
  for name,edit in [('large-index-hash',lambda r:r['response']['capture_artifacts'][-1].update(sha256='0'*64)),('snapshot-hash',lambda r:r['response'].update(snapshot='/synthetic/linux/wp14-evidence/missing.img')),('dump-missing',lambda r:r['response'].update(dumps=dict(A='/synthetic/linux/wp14-evidence/missing.wav'))),('path-escape',lambda r:r['response']['capture_artifacts'][0].update(path='/synthetic/linux/wp14-evidence/../escape'))]:
   changed=copy.deepcopy(n);edit(changed['linux']['results'][0]);reject(lambda:audit_retained(changed,root,('linux','windows')));controls.append(name)
  for name in ('large.raw','snapshot.img'):
   target=root/'wp14-native-evidence-linux'/name;raw=target.read_bytes();target.write_bytes(b'MUTATED LOGICAL BYTES');reject(lambda:audit_retained(n,root,('linux','windows')));target.write_bytes(raw);controls.append('logical-byte-mismatch-'+name)
  reject(lambda:audit_retained(n,root/'absent',('linux','windows')));controls.append('missing-named-artifact')
  extra=root/'wp14-native-evidence-macos';extra.mkdir();bundle=root/'bundle';bundle.mkdir();(bundle/'native-macos.json').write_text('malformed ignored bytes');assert ignored_inputs(bundle,root,('linux','windows'))==['native-macos.json','wp14-native-evidence-macos'];checks.append('unnamed-evidence-listed')
 assert checks and len(controls)>=20
 result=dict(mode='independent-oracle-selftest',checks=checks,controls_detected=controls,product_executed=False,accepted=False);print(json.dumps(result,indent=2));return result
if __name__=='__main__':main()
