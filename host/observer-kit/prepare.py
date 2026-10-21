"""Owned-file packaging and ordinary probe dry-run only. No target/capture APIs."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time

import probe


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--source',required=True)
    p.add_argument('--validate-retained',action='store_true',help='Finish offline checks from original child receipts; NEVER relaunch')
    a=p.parse_args();out=Path(os.path.abspath(a.out))
    if not a.validate_retained:out.mkdir()
    runtime=Path(sys.executable).resolve().parent
    image=out/'probe-235.exe'
    if not a.validate_retained:
        shutil.copyfile(sys.executable,image)
        shutil.copyfile(Path(__file__).with_name('probe.py'),out/'probe.py')
    def sha(b):return hashlib.sha256(b).hexdigest()
    def js(name,obj):(out/name).write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
    required=[runtime/'python312.dll']
    assert all(x.is_file() for x in required),'known existing runtime DLL unavailable; stop, no hunt'
    # Inventory this KNOWN existing runtime, no alternate provider discovery.
    known=[runtime/'python.exe',*required]
    for n in ('python3.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt'):
        if (runtime/n).is_file():known.append(runtime/n)
    for folder in ('DLLs','Lib'):
        base=runtime/folder
        if base.is_dir():
            known.extend(x for x in base.rglob('*') if x.is_file() and 'site-packages' not in x.parts and '__pycache__' not in x.parts and x.suffix in ('.py','.pyd','.dll','.zip'))
    inventory={x.relative_to(runtime).as_posix():dict(bytes=x.stat().st_size,sha256=sha(x.read_bytes())) for x in sorted(set(known))}
    if a.validate_retained:
        assert json.loads((out/'RUNTIME-INVENTORY.json').read_bytes())==inventory,'existing runtime identity changed'
    else:js('RUNTIME-INVENTORY.json',inventory)
    env=os.environ.copy();env['PYTHONHOME']=str(runtime);env['PATH']=str(runtime)+os.pathsep+env.get('PATH','');env.pop('PYTHONPATH',None)
    if a.validate_retained:
        launch=json.loads((out/'LAUNCH.json').read_bytes())
        assert launch['source']==a.source and launch['exit']==0
        nonce=launch['argv'][-1]
        assert launch['image_sha256']==sha(image.read_bytes())
    else:
        nonce=os.urandom(16).hex()
        argv=[str(image),'-S','-B',str(out/'probe.py'),'--dry-run','--nonce',nonce]
        start=time.monotonic_ns();cpu=time.process_time_ns()
        with (out/'dry-stdout.bin').open('xb') as stdout,(out/'dry-stderr.bin').open('xb') as stderr:
            child=subprocess.Popen(argv,env=env,stdout=stdout,stderr=stderr)
            code=child.wait(timeout=5)
        end=time.monotonic_ns()
        launch=dict(argv=argv,pid=child.pid,parent_pid=os.getpid(),exit=code,source=a.source,
           image_sha256=sha(image.read_bytes()),runtime_root=str(runtime),environment_overrides=dict(PYTHONHOME=str(runtime),PATH_prefix=str(runtime),PYTHONPATH='removed'),
           start_ns=start,end_ns=end,duration_ns=end-start,parent_cpu_ns=time.process_time_ns()-cpu,
           cpu_accounting='parent CPU measured; child included in conservative600CPU-second reservation, no wall/CPU substitution')
        js('LAUNCH.json',launch)
        assert code==0,'known copied-image route failed; retain logs, no repair/provider hunt'
    actual=json.loads((out/'dry-stdout.bin').read_bytes())
    assert actual['pid']==launch['pid'] and actual['parent_pid']==launch['parent_pid'] and actual['nonce']==nonce
    normalize=lambda path:os.path.normcase(os.path.abspath(path))
    assert actual['image_name']=='probe-235.exe' and normalize(actual['image'])==normalize(image)
    assert actual['image_sha256']==sha(image.read_bytes()) and actual['pointer_bits']==struct.calcsize('P')*8
    assert not actual['ctypes_imported'] and actual['native_target_calls']==actual['token_probes']==actual['capture_launches']==0
    js('DRY-RUN.json',actual)
    config=dict(mode='PREPARATION_ONLY',synthetic=True,native_calls=0,token_probes=0,capture_launches=0,
       helper_image='probe-235.exe',pointer_bits=64,observer_sha256=probe.OBSERVER,filter_sha256=probe.FILTER,
       nonce='a'*32,owned=r'C:\owned\fixture.bin',missing=r'C:\owned\missing.bin')
    config.update({key:True for key in probe.FLAGS});config['cases']=[]
    for name,target,access in probe.ROWS:
        path=config['owned'] if target=='owned' else config['missing'] if target=='missing' else r'\\.\NUL' if target=='nul' else '\\\\.\\DTVerify235_'+config['nonce']
        config['cases'].append(dict(id=name,path=path,access=access,share=7,disposition=3,flags=128,security_null=True,template_null=True,attempts=1))
    js('SYNTHETIC.json',config)
    assert probe.validate(config)=='SYNTHETIC_READINESS_CONTROLS_ONLY'
    mutations=[]
    for key,value in [('helper_image','python.exe'),('pointer_bits',16),('observer_sha256','0'*64),('filter_sha256','0'*64),('native_calls',1),('token_probes',1),('capture_launches',1),('synthetic',False),('nonce','')]:
        m=copy.deepcopy(config);m[key]=value;mutations.append((key,m))
    for key in probe.FLAGS:
        m=copy.deepcopy(config);m[key]=False;mutations.append((key,m))
    for key,value in [('path',r'\\.\PhysicalDrive0'),('path',r'\\?\Volume{unissued}'),('path',r'\\.\OtherDosName'),('path',r'C:\owned\..\outside'),('access',0x40000000),('share',0),('disposition',2),('flags',0x40000000),('attempts',2)]:
        m=copy.deepcopy(config);m['cases'][0][key]=value;mutations.append(('case-'+key,m))
    controls=[]
    for i,(name,mutation) in enumerate(mutations):
        file=out/f'negative-{i:02d}.json';file.write_text(json.dumps(mutation,indent=2)+'\n',encoding='utf-8')
        try:probe.validate(mutation)
        except ValueError as e:controls.append(dict(name=name,recipe=file.name,rejected=True,error=str(e)))
        else:raise AssertionError('actual offline validator admitted '+name)
    assert len(controls)==28
    js('CONTROLS.json',dict(scope='ACTUAL OFFLINE VALIDATOR on clearly SYNTHETIC inputs',positive=True,rejected=controls,native_calls=0,capture_launches=0,token_probes=0))
    js('PAYLOAD-INVENTORY.json',{x.name:dict(bytes=x.stat().st_size,sha256=sha(x.read_bytes())) for x in (image,out/'probe.py')})
    print(json.dumps(dict(image='probe-235.exe',image_sha256=sha(image.read_bytes()),actual_dry_run=True,controls_rejected=28,
       native_calls=0,capture_launches=0,token_probes=0,source=a.source,readiness='independent256 pending')))


if __name__=='__main__':main()
