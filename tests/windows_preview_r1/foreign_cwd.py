"""Preview foreign-cwd process receipt. No UIAutomation/input or fake app API."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'windows_app_start_r2'))
from context import ROUTE,current,admit,ordinary
CHILD='3895f3f356c91b8a9fe870c33694da64bf2765df308bef118d657c1be4bb9a20'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def run(a):
    assert re.fullmatch('[0-9a-f]{40}',a.source) and re.fullmatch('[0-9a-f]{64}',a.app_sha)
    ordinary(a.work.parent,True);assert not a.work.exists();a.work.mkdir();ordinary(a.work,True)
    r=dict(scope='process supervision only; actual UI facts must come from Computer Use',context=None,
           source_head=a.source,app_sha256=a.app_sha,argv=[],ui='UNEXECUTED',forced_cleanup=False)
    def save(): (a.work/'session.private.json').write_text(json.dumps(r,indent=2)+'\n')
    p=None
    try:
        r['context']=current(a.tool_context);save();admit(r['context'])
        ordinary(a.bundle,True);ordinary(a.launch_cwd,True);ordinary(a.bundle/'digital-tape.exe');ordinary(a.bundle/'ingest.exe');assert not a.launch_cwd.samefile(a.bundle)
        assert sha(a.bundle/'digital-tape.exe')==a.app_sha and sha(a.bundle/'ingest.exe')==CHILD
        build=json.loads((a.bundle/'BUILD.json').read_text(encoding='utf-8-sig'));assert build['source_head']==a.source
        assert sorted(p.name for p in a.launch_cwd.iterdir())==['foreign.txt'] and (a.launch_cwd/'foreign.txt').read_bytes()==b'UNCHANGED\n';r['foreign_before']=sha(a.launch_cwd/'foreign.txt');r['build_sha256']=sha(a.bundle/'BUILD.json');r['cwd']=str(a.launch_cwd);r['start_utc_ns']=time.time_ns();save()
        with (a.work/'stdout.bin').open('xb') as out,(a.work/'stderr.bin').open('xb') as err:
            p=subprocess.Popen([str(a.bundle/'digital-tape.exe')],cwd=a.launch_cwd,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
            r['pid']=p.pid;save();deadline=time.monotonic()+240
            while p.poll() is None and time.monotonic()<deadline and not (a.work/'stop.request').exists():time.sleep(.25)
            if p.poll() is None:r['forced_cleanup']=True;p.kill()
            r['exit']=p.wait(timeout=5)
    except BaseException as e:r['error']=repr(e);raise
    finally:
        if p is not None and p.poll() is None:r['forced_cleanup']=True;p.kill();p.wait(timeout=5)
        r['end_utc_ns']=time.time_ns()
        try: r['foreign_cwd_preserved']=(sorted(p.name for p in a.launch_cwd.iterdir())==['foreign.txt'] and (a.launch_cwd/'foreign.txt').read_bytes()==b'UNCHANGED\n') if r.get('foreign_before') else None
        except OSError as e: r['foreign_cwd_preserved']=False;r['foreign_observation_error']=repr(e)
        for name in ['stdout.bin','stderr.bin']:
            f=a.work/name
            if f.exists():r[name]=dict(bytes=f.stat().st_size,sha256=sha(f))
        save()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--launch-cwd',type=Path,required=True);p.add_argument('--source',required=True);p.add_argument('--app-sha',required=True);p.add_argument('--tool-context',choices=[ROUTE],required=True)
    a=p.parse_args();a.bundle=a.bundle.absolute();a.work=a.work.absolute();a.launch_cwd=a.launch_cwd.absolute();run(a)
