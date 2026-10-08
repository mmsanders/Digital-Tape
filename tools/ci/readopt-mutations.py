#!/usr/bin/env python3
"""Execute ADR-172's baseline, benign and seven causal behavior mutations."""
import argparse,importlib.util,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('epoch',ROOT/'tests/playback_regression_epoch/check.py')
epoch=importlib.util.module_from_spec(spec);spec.loader.exec_module(epoch)
def command(tree,argv,log):
    r=subprocess.run(list(map(str,argv)),cwd=tree,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    log.write_text(r.stdout);print(str(log),r.returncode,flush=True)
    return r.returncode,r.stdout
def git(tree,*args):return subprocess.check_output(['git',*args],cwd=tree,text=True).strip()
def golden(tree,out):
    rc,text=command(tree,['bash','-e','-c','make -C engine all && make -C host && make -C tests all && cd tests/golden && sha256sum -c SHA256SUMS'],out/'golden-build.log')
    if rc:raise RuntimeError('golden build or fixture authentication failed')
    return command(tree,['tools/ci/run-golden.sh'],out/'golden-behavior.log')
def transport(tree,out):
    rc,_=command(tree,['make','-C','tests/transport_adapter','all'],out/'transport-build.log')
    if rc:raise RuntimeError('transport build failed')
    return command(tree,[sys.executable,'-B','tests/transport_adapter/run_product.py','--evidence',out/'transport-evidence'],out/'transport-behavior.log')
def suites(tree,out,mutation=None):
    rows=[]
    for name in epoch.load()['suites']:
        dest=out/name
        argv=[sys.executable,'-B',tree/'tools/readopt-binding.py','--suite',name,'--out',dest]
        if mutation:argv+=['--mutation',mutation]
        rc,log=command(tree,argv,out/(name+'.log'))
        r=json.loads((dest/'binding-result.json').read_text());rows.append(r)
        if rc:raise RuntimeError('baseline/benign suite failed: '+name)
    return rows
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    report={'mutations':[]};m=epoch.load()
    baseline=out/'baseline';baseline.mkdir()
    rows=suites(ROOT,baseline)
    rc,_=golden(ROOT,baseline)
    trc,_=transport(ROOT,baseline)
    report.update(baseline_behavior_pass=rc==0 and trc==0 and all(r['behavior_pass'] for r in rows),
                  baseline_raw_pass=all(r['raw_pass'] for r in rows),
                  baseline_selection_pass=all(r['selection_pass'] for r in rows))
    if not all(report[k] for k in ['baseline_behavior_pass','baseline_raw_pass','baseline_selection_pass']):
        raise RuntimeError('unmutated baseline is not green')
    try:
        names=['00-benign-comment']+[n for n in m['mutation_patches'] if n!='00-benign-comment']
        for name in names:
            pin=m['mutation_patches'][name]
            dest=out/name;dest.mkdir()
            with tempfile.TemporaryDirectory(prefix='readopt-mutation-') as d:
                tree=Path(d)/'tree'
                subprocess.run(['git','worktree','add','--detach',tree,'HEAD'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
                try:
                    subprocess.run(['git','apply',ROOT/pin['path']],cwd=tree,check=True)
                    subprocess.run(['git','-c','user.name=mutation-gate','-c','user.email=mutation-gate@localhost','commit','-qam','deliberate '+name],cwd=tree,check=True)
                    selection=epoch.select(tree,'record-package',name,m)
                    (dest/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
                    (dest/'actual-commit.txt').write_text(git(tree,'cat-file','commit','HEAD')+'\n')
                    with (dest/'actual-engine.tar').open('wb') as f:
                        subprocess.run(['git','archive','HEAD','engine'],cwd=tree,stdout=f,check=True)
                    if name=='00-benign-comment':
                        rows=suites(tree,dest,name);rc,_=golden(tree,dest);trc,_=transport(tree,dest)
                        report.update(benign_behavior_pass=rc==0 and trc==0 and all(r['behavior_pass'] for r in rows),
                                      benign_raw_pass=all(r['raw_pass'] for r in rows),
                                      benign_selection_pass=all(r['selection_pass'] for r in rows))
                        continue
                    rc,log=golden(tree,dest)
                    oracle='tests/golden/MANIFEST';assertion=next((l for l in log.splitlines() if l.strip().startswith('FAIL  ') and 'case' not in l),None)
                    if rc and not assertion:
                        assertion=next((l for l in log.splitlines() if l.strip().startswith('FAIL  ')),None)
                    if not rc:
                        trc,tlog=transport(tree,dest)
                        if trc:
                            assertion=next((l for l in tlog.splitlines() if l.strip().startswith('FAIL')),None)
                            if not assertion:raise RuntimeError('no actual transport oracle assertion for '+name)
                            oracle='tests/transport_adapter/run_product.py'
                    if not rc and not assertion:
                        # These are the unchanged original full behavioral suites.
                        # Raw mismatches and binding/build failures cannot count.
                        for suite in ['record-package',*[s for s in m['suites'] if s!='record-package']]:
                            sub=dest/suite
                            argv=[sys.executable,'-B',tree/'tools/readopt-binding.py','--suite',suite,'--out',sub,'--mutation',name]
                            _,_=command(tree,argv,dest/(suite+'.log'))
                            result=json.loads((sub/'binding-result.json').read_text())
                            if not result['selection_pass'] or not result['build_pass'] or result.get('failure_kind')=='binding':
                                raise RuntimeError('mutation failed provenance/build: '+name+' '+suite)
                            if not result['behavior_pass']:
                                behavior=(sub/'behavior.log').read_text()
                                assertion=next((l for l in behavior.splitlines() if l.strip().startswith('FAIL') or 'AssertionError:' in l),None)
                                if not assertion:raise RuntimeError('no actual oracle assertion for '+name)
                                oracle=str(m['suites'][suite]['adapter_root'])+'/run_product.py';break
                    if not assertion:raise RuntimeError('behavior mutation survived: '+name)
                    report['mutations'].append({'mutation':name,'selection_pass':True,'build_pass':True,'failure_kind':'behavior',
                        'oracle':oracle,'assertion':assertion,'actual_commit':selection['actual_commit'],
                        'actual_engine':selection['actual_engine'],'actual_root_tree':selection['actual_root_tree']})
                finally:
                    subprocess.run(['git','worktree','remove','--force',tree],cwd=ROOT,check=True)
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        census=epoch.mutation_census(report,m)
        (out/'census.json').write_text(json.dumps(census,indent=2)+'\n');print(json.dumps(census))
    finally:(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
