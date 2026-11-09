"""Independent real-Git history fixtures for ADR206; never imports Product gates."""
import argparse,json,os,subprocess
from pathlib import Path
ENV=dict(os.environ,GIT_AUTHOR_NAME='Verification fixture',GIT_AUTHOR_EMAIL='fixture@example.invalid',GIT_COMMITTER_NAME='Verification fixture',GIT_COMMITTER_EMAIL='fixture@example.invalid',GIT_AUTHOR_DATE='2026-01-01T00:00:00+00:00',GIT_COMMITTER_DATE='2026-01-01T00:00:00+00:00')
def git(repo,*args):return subprocess.check_output(['git','-c','core.autocrlf=false',*args],cwd=repo,env=ENV,stderr=subprocess.DEVNULL).decode().strip()
def write(repo,path,value):
 p=repo/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding='utf-8')
def commit(repo,message):git(repo,'add','.');git(repo,'commit','-qm',message);return git(repo,'rev-parse','HEAD')
def manifest(repo,entries):write(repo,'tests/IMPORTS.json',json.dumps(dict(packages=entries),indent=2)+'\n')
def init(path):path.mkdir(parents=True);git(path,'init','-q','-b','main')
CASES=[('ordinary-import-before-implementation',True),('review-regression-with-attested-fix',True),('late-metadata-preserves-lineage',True),('unflagged-late-import',False),('missing-review-of',False),('short-review-of',False),('forged-review-of',False),('nonancestor-review-of',False),('stale-review-of',False),('preexisting-tree-edit',False),('previous-tree-edited',False),('no-later-correction',False),('correction-before-import',False),('simultaneous-import-fix',False),('ordinary-combined-import-implementation',False),('source-not-on-verifier-main',False),('attestation-absent',False),('attestation-forged',False),('attestation-not-on-main',False),('import-tree-mutated',False),('unrelated-late-import',False),('missing-publication-identity',False),('publication-order-not-attested',False),('unrelated-correction',False),('unrelated-earlier-late-import',False)]
def make(root,name,expected):
 d=root/name;p=d/'product';v=d/'verification';init(p);init(v)
 write(v,'tests/prior/run.py','assert True # previously published\n')
 if name=='preexisting-tree-edit':write(v,'tests/review_pkg/run.py','assert True # old package\n')
 vb=commit(v,'previous independent publication');prior_tree=git(v,'rev-parse','HEAD:tests/prior')
 prior=dict(path='tests/prior',tree=prior_tree,source_repo='mmsanders/digital-tape-verification',source_commit=vb)
 entries=[prior];write(p,'tests/prior/run.py','assert True # previously published\n')
 if name=='preexisting-tree-edit':
  write(p,'tests/review_pkg/run.py','assert True # old package\n');entries.append(dict(path='tests/review_pkg',tree=git(v,'rev-parse','HEAD:tests/review_pkg'),source_repo=prior['source_repo'],source_commit=vb))
 manifest(p,entries);base=commit(p,'base with prior immutable imports')
 ordinary=name in ('ordinary-import-before-implementation','ordinary-combined-import-implementation')
 reviewed=None
 if not ordinary:
  write(p,'firmware/bench/tool.py','value = 1 # held reviewed implementation\n');reviewed=commit(p,'reviewed implementation')
  if name=='stale-review-of':write(p,'engine/new.c','int unrelated = 1;\n');commit(p,'unreviewed behavior after reviewed head')
  if name=='correction-before-import':write(p,'firmware/bench/tool.py','value = 2 # premature correction\n');early_fix=commit(p,'correction before independent import');reviewed=early_fix
 if name=='nonancestor-review-of':nonancestor=git(p,'commit-tree',git(p,'rev-parse',base+'^{tree}'),'-m','unrelated nonancestor')
 if name=='unrelated-earlier-late-import':
  write(v,'tests/earlier/run.py','assert True\n');extra=commit(v,'earlier other independent publication');write(p,'tests/earlier/run.py','assert True\n');entries.append(dict(path='tests/earlier',tree=git(v,'rev-parse','HEAD:tests/earlier'),source_repo=prior['source_repo'],source_commit=extra));manifest(p,entries);commit(p,'unrelated earlier unflagged late import')
 if name=='source-not-on-verifier-main':git(v,'checkout','-qb','unpublished')
 write(v,'tests/review_pkg/run.py','assert True # NEW independent expectations\n');write(v,'tests/review_pkg/README.md','Reviewed Product '+str(reviewed)+'\n')
 publication=commit(v,'independent regression publication');tree=git(v,'rev-parse',publication+':tests/review_pkg')
 if name=='source-not-on-verifier-main':git(v,'checkout','-q','main')
 entry=dict(path='tests/review_pkg',tree=tree,source_repo=prior['source_repo'],source_commit=publication)
 entries=[e for e in entries if e['path']!=entry['path']]+[entry]
 write(p,'tests/review_pkg/run.py','assert True # NEW independent expectations\n');write(p,'tests/review_pkg/README.md','Reviewed Product '+str(reviewed)+'\n')
 if name=='previous-tree-edited':write(p,'tests/prior/run.py','assert False # forbidden edit\n')
 if name in ('simultaneous-import-fix','ordinary-combined-import-implementation'):write(p,'firmware/bench/tool.py','value = 2 # combined forbidden commit\n')
 
 if not ordinary and name!='late-metadata-preserves-lineage':entry['review_of']=reviewed
 manifest(p,entries);imported=commit(p,'independent import')
 fix=None
 if ordinary:
  if name!='ordinary-combined-import-implementation':write(p,'firmware/bench/tool.py','value = 2 # ordinary implementation after tests\n');fix=commit(p,'ordinary implementation')
 else:
  if name!='no-later-correction':
   if name=='unrelated-correction':write(p,'engine/unrelated.c','int unrelated = 2;\n')
   else:write(p,'firmware/bench/tool.py','value = 3 # corresponding corrective implementation\n')
   fix=commit(p,'corresponding correction')
  if name=='correction-before-import':fix=early_fix
  record=dict(source_repo=entry['source_repo'],source_commit=publication,source_path=entry['path'],tree=tree,review_of=nonancestor if name=='nonancestor-review-of' else reviewed,import_commit=imported,fix_commit=fix,reviewed_head=git(p,'rev-parse','HEAD'),publication_before_import_and_fix=name!='publication-order-not-attested',covered_paths=['firmware/bench/tool.py'])
  if name=='attestation-forged':record['review_of']=base
  if name=='attestation-not-on-main':git(v,'checkout','-qb','unpublished-attestation')
  if name!='attestation-absent':write(v,'attestations/reviews.json',json.dumps(dict(schema='verification/review-lineage/1',entries=dict(case=record)),indent=2))
  # For absent attestation make an independent metadata commit anyway.
  write(v,'PUBLICATION.txt',name);registry=commit(v,'independent corrected-head lineage attestation')
  if name=='attestation-not-on-main':git(v,'checkout','-q','main')
  entry.update(review_of=reviewed,review_fix=fix,review_attestation=dict(source_commit=registry,path='attestations/reviews.json',entry='case'))
  if name in ('unflagged-late-import','missing-review-of'):entry.pop('review_of')
  if name=='short-review-of':entry['review_of']=reviewed[:8]
  if name=='forged-review-of':entry['review_of']=base
  if name=='nonancestor-review-of':entry['review_of']=nonancestor
  if name=='missing-publication-identity':entry.pop('source_commit')
  if name=='attestation-absent':entry.pop('review_attestation')
  if name=='import-tree-mutated':write(p,'tests/review_pkg/run.py','assert False # changed imported expectation\n')
  if name=='unrelated-late-import':
   write(v,'tests/unrelated/run.py','assert True\n');extra=commit(v,'other independent package');write(p,'tests/unrelated/run.py','assert True\n');entries.append(dict(path='tests/unrelated',tree=git(v,'rev-parse','HEAD:tests/unrelated'),source_repo=prior['source_repo'],source_commit=extra))
  manifest(p,entries);commit(p,'protected final provenance metadata (no history rewrite)')
 case=dict(name=name,expect=0 if expected else 1,repo=str(p.resolve()),base=base,head=git(p,'rev-parse','HEAD'),verification_repo=str(v.resolve()),verification_main=git(v,'rev-parse','main'),manifest='tests/IMPORTS.json',reviewed=reviewed,import_commit=imported,fix=fix)
 (d/'CASE.json').write_text(json.dumps(case,indent=2)+'\n');return case

def generate(out):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);cases=[make(out,n,e) for n,e in CASES]
 for c in cases:
  git(Path(c['repo']),'fsck','--no-dangling');git(Path(c['verification_repo']),'fsck','--no-dangling')
 (out/'CASES.json').write_text(json.dumps(cases,indent=2)+'\n');return cases
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();rows=generate(a.out);print(json.dumps(dict(generated=len(rows),positive=sum(x['expect']==0 for x in rows),negative=sum(x['expect']!=0 for x in rows),product_gate_executed=False)))
