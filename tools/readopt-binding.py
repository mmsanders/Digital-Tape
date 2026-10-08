#!/usr/bin/env python3
"""Mechanical ADR-172 sequencing; all expectations remain in published packages."""
import argparse, hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'tests/playback_regression_epoch'
spec = importlib.util.spec_from_file_location('epoch', PACKAGE/'check.py')
epoch = importlib.util.module_from_spec(spec); spec.loader.exec_module(epoch)

def execute(argv, log, env=None):
    r = subprocess.run(list(map(str, argv)), cwd=ROOT, env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(r.stdout); print(r.stdout, end='', flush=True)
    return r.returncode

def replay_record(old, fresh_media, out):
    # The historical JSONL stores media hashes, not media bytes. Fresh canonical
    # media can transport the old post-media only if its full hash matches the
    # immutable old hash. Use original independent fixtures and verdict functions.
    module_path = ROOT/'tests/record_adapter/run_product.py'
    spec = importlib.util.spec_from_file_location('record_binding',module_path)
    record = importlib.util.module_from_spec(spec);spec.loader.exec_module(record)
    rows = {x['case']:x for x in json.loads('['+','.join(old.decode().splitlines())+']')}
    verdicts=[]
    for cid, pre, audit, verdict in record.plan():
        r=rows[cid];data=(fresh_media/(cid+'.out.vo08')).read_bytes()
        if hashlib.sha256(pre.encode()).hexdigest()!=r['input_sha256']:
            raise RuntimeError('historical input media transport hash')
        if hashlib.sha256(data).hexdigest()!=r['output_sha256']:
            raise RuntimeError('historical post-media transport hash')
        errors=list(audit())+list(verdict(record.Media.decode(data),r['observation']['events'],r['observation']['calls']))
        if errors:raise RuntimeError('historical unchanged record oracle: '+str(errors))
        verdicts.append({'case':cid,'oracle_errors':errors,'post_media_sha256':r['output_sha256']})
    (out/'old-record-replay.json').write_text(json.dumps(verdicts,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',required=True)
    p.add_argument('--out',required=True);p.add_argument('--mutation')
    p.add_argument('--old-retained',type=Path)
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    m=epoch.load();pin=m['suites'][a.suite];adapter=ROOT/pin['adapter_root']
    result={'suite':a.suite,'selection_pass':False,'build_pass':False,
            'behavior_pass':False,'raw_pass':False,'old_replay_pass':False}
    def save(): (out/'binding-result.json').write_text(json.dumps(result,indent=2)+'\n')
    try:
        selection=epoch.select(ROOT,a.suite,a.mutation,m);result.update(selection)
        result['selection_pass']=True
        (out/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
        old_dir=a.old_retained or ROOT/pin['old']['path']
        old=epoch.authenticate(a.suite,old_dir,'old',m)
        env=dict(os.environ,PRODUCT_COMMIT=selection['actual_commit'])
        if a.suite!='record-package':
            rc=execute([sys.executable,'-B',adapter/'run_product.py','--replay',old_dir,
                        '--out',out/'old-replay'],out/'old-replay.log',env)
            if rc:raise RuntimeError('historical unchanged behavior replay failed')
            result['old_replay_pass']=True
        if execute(['make','-C',ROOT/'engine','all'],out/'engine-build.log'):
            raise RuntimeError('engine build failed')
        if execute(['make','-C',adapter,'all'],out/'adapter-build.log'):
            raise RuntimeError('adapter build failed')
        result['build_pass']=True
        argv=[sys.executable,'-B',adapter/'run_product.py','--evidence',out/'fresh']
        if a.suite=='record-package':argv+=['--workdir',out/'media']
        rc=execute(argv,out/'behavior.log',env)
        result['behavior_pass']=rc==0
        result['oracle']=str(adapter/'run_product.py')
        result['behavior_exit']=rc
        if rc:
            result['failure_kind']='behavior'
            result['assertion_log']='behavior.log'
            return 1
        fresh=out/'fresh/observations.jsonl'
        if not fresh.exists():fresh=fresh.with_suffix('.jsonl.gz')
        try:
            raw=epoch.regenerate(fresh,a.suite,selection,m)
            result['raw_pass']=True;result['regeneration']=raw
        except AssertionError as e:
            result['raw_failure']=str(e)
            if not a.mutation:raise
        # Mutant raw differences are diagnostic only. The original oracle above
        # must catch a behavioral violation; no raw/provenance failure counts.
        if a.suite=='record-package' and not a.mutation:
            replay_record(old,out/'media',out);result['old_replay_pass']=True
        elif a.suite=='record-package' and a.mutation=='00-benign-comment':
            replay_record(old,out/'media',out);result['old_replay_pass']=True
        if not a.mutation and not result['raw_pass']:return 1
        return 0
    except Exception as e:
        result['failure_kind']='binding';result['error']=str(e)
        print('BINDING FAILURE:',e);return 1
    finally:save()
if __name__=='__main__':sys.exit(main())
