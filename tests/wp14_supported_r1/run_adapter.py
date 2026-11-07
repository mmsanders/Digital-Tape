"""Candidate adapter contract replay. Requires actual complete two-platform artifacts."""
import argparse,copy,json,os,shutil,subprocess,sys
from pathlib import Path
from retained import audit_retained

def agrees(code,positive,usage=False):return code==(0 if positive else 64) if positive or usage else code not in (0,64)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--adapter',type=Path,required=True);ap.add_argument('--bundle',type=Path,required=True);ap.add_argument('--captures',type=Path,required=True);ap.add_argument('--head',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);cases=[]
 def run(name,platforms='linux,windows',positive=False,usage=False,edit=None):
  d=out/name;d.mkdir();b=d/'bundle';b.mkdir();c=d/'captures'
  # Hard links preserve large immutable input bytes without copying campaigns.
  # Every mutated entry is replaced via a new file, never written through a link.
  shutil.copytree(a.captures,c,copy_function=os.link)
  for p in ('linux','windows'):
   for kind in ('image','native'):shutil.copyfile(a.bundle/(kind+'-'+p+'.json'),b/(kind+'-'+p+'.json'))
  if edit:edit(b,c)
  cmd=[sys.executable,'-B',str(a.adapter.resolve()),'--head',a.head,'--captures',str(c),'--relocations',str(d/'relocations.json'),str(b)]
  if platforms=='__missing__':cmd+=['--platforms']
  elif platforms is not None:cmd+=['--platforms',platforms]
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=1800);ok=agrees(r.returncode,positive,usage);doc={}
  if positive:
   try:doc=json.loads(r.stdout);ok=ok and doc['kind']=='evidence-completeness' and doc['accepted'] is False and doc['platforms']==['linux','windows'] and doc['deferred']==['macos'] and (d/'relocations.json').is_file() and bool(json.loads((d/'relocations.json').read_text()))
   except (ValueError,KeyError,OSError):ok=False
   if ok:
    try:
     native={p:json.loads((b/('native-'+p+'.json')).read_text()) for p in ('linux','windows')};expected=audit_retained(native,c,('linux','windows'));actual=json.loads((d/'relocations.json').read_text())
     for proof in expected:
      matches=[r for r in actual if (r.get('platform'),r.get('original'),r.get('sha256'))==(proof['platform'],proof['original'],proof['sha256'])]
      assert matches and all(Path(r['retained']).resolve()==Path(proof['retained']).resolve() for r in matches),'missing or wrong relocation proof'
    except (AssertionError,ValueError,KeyError,TypeError,OSError):ok=False
   if name=='unnamed-listed':ok=ok and {'image-macos.json','native-macos.json','wp14-native-evidence-macos'}<=set(doc.get('ignored',[]))
  cases.append(dict(case=name,exit=r.returncode,passed=ok,stderr=r.stderr[-500:]))
 def unlink(path,root):
  assert path.resolve().is_relative_to(root.resolve());path.unlink()
 def json_edit(b,p,fn):
  path=b/('native-'+p+'.json');v=json.loads(path.read_text());fn(v);path.write_text(json.dumps(v),encoding='utf-8')
 def move_artifact(c,p):
  source=c/('wp14-native-evidence-'+p);target=c/('UNNAMED-'+p)
  assert source.resolve().is_relative_to(c.resolve()) and target.resolve().is_relative_to(c.resolve());source.rename(target)
 def corrupt(b,c,p):
  doc=json.loads((b/('native-'+p+'.json')).read_text());original=doc['results'][0]['response']['capture_artifacts'][0]['path'];tail=original.replace('\\','/').split('/wp14-evidence/',1)[1];target=c/('wp14-native-evidence-'+p)/tail
  assert target.resolve().is_relative_to(c.resolve());new=target.with_name(target.name+'.V394-mutant');new.write_bytes(b'V394 MUTATED SAVED BYTES');new.replace(target)
 def unnamed(b,c):
  for k in ('image','native'):(b/(k+'-macos.json')).write_text('invalid ignored data')
  (c/'wp14-native-evidence-macos').mkdir(exist_ok=True)
 run('complete-two-platform',positive=True);run('unnamed-listed',positive=True,edit=unnamed);run('default-requires-macos',platforms=None)
 for value in ('','windows','linux','macos','windows,linux','linux,linux,windows','linux,windows,macos','linux,other,windows'):
  # Argument validation must happen before evidence loading, with usage64.
  run('usage-'+str(len(cases)),platforms=value,usage=True)
 for p in ('linux','windows'):
  for kind in ('image','native'):run('missing-'+kind+'-'+p,edit=lambda b,c,p=p,kind=kind:unlink(b/(kind+'-'+p+'.json'),b))
  run('missing-artifact-'+p,edit=lambda b,c,p=p:move_artifact(c,p))
  run('retained-mismatch-'+p,edit=lambda b,c,p=p:corrupt(b,c,p))
  run('empty-results-'+p,edit=lambda b,c,p=p:json_edit(b,p,lambda v:v.update(results=[])))
 run('usage-missing-argument',platforms='__missing__',usage=True)
 run('empty-image-json',edit=lambda b,c:(b/'image-linux.json').write_text('{}'))
 run('removed-windows-case',edit=lambda b,c:json_edit(b,'windows',lambda v:v['results'].pop(0)))
 run('malformed-native-json',edit=lambda b,c:(b/'native-windows.json').write_text('{'))
 assert not agrees(0,False) and not agrees(1,True) and not agrees(2,False,True)
 result=dict(mode='actual-adapter-replay',cases=cases,passed=all(c['passed'] for c in cases),predicate_controls=3,accepted=False)
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
