#!/usr/bin/env python3
"""Authenticate and replay READ-1 observations across the ADR-171 metadata repair.

Original manifests and executed head are preserved. This is an identity binding,
not a newly executed campaign, independent disposition or gate waiver.
"""
import argparse,hashlib,importlib.util,json,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ORIGINAL='dfe426d4569a53c64558ca84e24cb41881521821'
ENGINE='d96b4245e04d74078f8938744b1394c3018516f7'
ASSET='4a626ca4605780287d03aca211de9a45250700bae857143800113bc715179add'
REPAIRED='63098ee78ab67a0e12e9f414d2ad467276a77a8d'
TAG='evidence-read1-'+ORIGINAL

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def run(args,**kwargs):subprocess.run(list(map(str,args)),check=True,**kwargs)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    head=git('rev-parse','HEAD');assert git('rev-parse','HEAD:engine')==ENGINE
    assert git('rev-parse','HEAD:tests/playback_readonly_r1')==REPAIRED
    run(['gh','release','download',TAG,'--repo','mmsanders/Digital-Tape','--pattern','evidence.tar.gz','--dir',out])
    archive=out/'evidence.tar.gz';assert sha(archive)==ASSET
    original=out/'original';original.mkdir()
    with tarfile.open(archive) as tar:tar.extractall(original,filter='data')
    p=json.loads((original/'provenance.json').read_text());assert p['product_commit']==ORIGINAL and p['engine_tree']==ENGINE
    for path,expected in p['sources'].items():assert sha(ROOT/path)==expected,path
    # Engine tree covers all engine headers; adapter tree is byte-identical.
    assert git('rev-parse',ORIGINAL+':tests/playback_readonly_adapter')==git('rev-parse','HEAD:tests/playback_readonly_adapter')
    diff=git('diff','--name-only',ORIGINAL,'HEAD','--','tests/playback_readonly_r1').splitlines()
    assert diff==['tests/playback_readonly_r1/INPUTS.json','tests/playback_readonly_r1/authority/acceptance.md']
    old=json.loads(git('show',ORIGINAL+':tests/playback_readonly_r1/INPUTS.json'))
    new=json.loads((ROOT/'tests/playback_readonly_r1/INPUTS.json').read_text())
    new.pop('authority_copy_repair');new['sha256'].pop('authority/acceptance.md');assert new==old
    spec=importlib.util.spec_from_file_location('binding',ROOT/'tests/playback_readonly_adapter/qualify.py')
    binding=importlib.util.module_from_spec(spec);spec.loader.exec_module(binding)
    # Keep the original canonical build location to authenticate binaries,
    # including debug/source paths, instead of normalizing away binary drift.
    canonical=Path('/home/runner/work/_temp/read1')
    comparisons={}
    for name,observed in [('instrumented',True),('shipping',False)]:
        exe,lib,_,_=binding.build(ROOT,canonical/'build'/name,observed)
        for kind,path in [('library',lib),('adapter',exe)]:
            key=('adapter_sha256' if name=='instrumented' and kind=='adapter' else
                 name+'_'+kind+'_sha256')
            actual=sha(path);assert actual==p[key],key
            comparisons[key]=actual
    package=ROOT/'tests/playback_readonly_r1'
    run([sys.executable,'-B',package/'check_pins.py'])
    # These manifests retain their original actual execution identity.
    run([sys.executable,'-B',package/'qualification.py','--run',original/'run','--controls',original/'controls',
         '--product-commit',ORIGINAL,'--engine-tree',ENGINE])
    run([sys.executable,'-B',package/'absence.py','--shipping',original/'shipping-absence.json',
         '--leak-control',original/'leak-absence.json','--product-commit',ORIGINAL,'--engine-tree',ENGINE])
    run([sys.executable,'-B',package/'runner.py','--replay',original/'run/observations.jsonl.gz','--out',out/'corrected-oracle-replay'])
    before=json.loads((original/'run/manifest.json').read_text())
    replay=json.loads((out/'corrected-oracle-replay/manifest.json').read_text())
    assert before['cases']==replay['cases']
    result={'kind':'actual-original-observations-bound-by-exact-identities','candidate_commit':head,'engine_tree':ENGINE,
            'executed_commit':ORIGINAL,'original_run':37799314742,'original_release_tag':TAG,'archive_sha256':ASSET,
            'corrected_import_tree':REPAIRED,'original_provenance_sha256':sha(original/'provenance.json'),
            'original_run_manifest_sha256':sha(original/'run/manifest.json'),
            'original_control_manifest_sha256':sha(original/'controls/manifest.json'),
            'observation_sha256':before['observation_sha256'],'control_sha256':json.loads((original/'controls/manifest.json').read_text())['observations_sha256'],
            'binary_comparisons':comparisons,'canonical_cases':len(before['cases']),
            'corrected_oracle_replay_cases_identical':True,'new_full_campaign_executed':False,
            'independent_disposition':'required; this binding grants no acceptance or retained-regression waiver'}
    (out/'binding.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
