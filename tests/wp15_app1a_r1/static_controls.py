"""Exercise Software's actual static G1 check against source mutations.

No device is opened: these are source-only injected functions in disposable copies.
The same File::open API on a private ordinary file must remain clean. This is
not a runtime G1 proof, a complete static analyzer, or permission to weaken a gate.
"""
import argparse,json,os,shutil,subprocess,tempfile
from pathlib import Path

def run(root,entry,command):
    results={}
    snippets={
      'ordinary-positive':'fn verification_g1_control() { let _ = std::fs::File::open("CONTROL_FILE"); }',
      'unix-read-negative':'fn verification_g1_control() { let target = "/dev/rdisk99"; let _ = std::fs::File::open(target); }',
      'windows-alias-negative':'fn verification_g1_control() { use std::fs::OpenOptions as Alias; let target = r"\\\\.\\PhysicalDrive99"; let _ = Alias::new().read(true).open(target); }',
      'partition-write-negative':'fn verification_g1_control() { let target = "/dev/disk99s1"; let _ = std::fs::OpenOptions::new().write(true).open(target); }',
    }
    for name,snippet in {'baseline':None,**snippets}.items():
        with tempfile.TemporaryDirectory(prefix='verification-g1-') as t:
            dst=Path(t)/'app';shutil.copytree(root,dst,ignore=shutil.ignore_patterns('.git','node_modules','target'))
            ordinary=Path(t)/'owned-control';ordinary.write_text('ordinary file only\n')
            if snippet:
                p=dst/entry;assert p.is_file();p.write_text(p.read_text()+'\n'+snippet.replace('CONTROL_FILE',str(ordinary))+'\n')
            env=dict(os.environ,APP_SOURCE_ROOT=str(dst));p=subprocess.run(command,cwd=dst,env=env,capture_output=True)
            results[name]={'exit':p.returncode,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')}
            assert (p.returncode==0)==(name in ('baseline','ordinary-positive')),(name,results[name])
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('entry');p.add_argument('--out',type=Path,required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();cmd=a.command
    if cmd[:1]==['--']:cmd=cmd[1:]
    assert cmd;r=run(a.root.resolve(),a.entry,cmd);a.out.write_text(json.dumps(r,indent=2)+'\n')
