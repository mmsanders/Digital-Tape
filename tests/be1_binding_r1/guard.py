"""Run an offline Python checker with observable, denied external side effects."""
import json
import os
from pathlib import Path
import runpy
import sys

checker, bundle, report, golden, log = map(lambda x:Path(x).resolve(),sys.argv[1:])
allowed = (checker.parent, golden, bundle, Path(sys.base_prefix).resolve(), Path(os.__file__).resolve().parent)
violations=[]
active=True

def under(path, root):
    return path == root or root in path.parents

def deny(event, detail):
    violations.append(dict(event=event,detail=str(detail)))
    raise PermissionError('V382 offline confinement: '+event)

def audit(event,args):
    if not active:
        return
    if event.startswith('socket.') or event.startswith('subprocess.') or event in (
       'os.system','os.exec','os.posix_spawn','os.spawn','os.fork','ctypes.dlopen','ctypes.dlsym',
       'os.remove','os.rename','os.rmdir','os.mkdir','os.link','os.symlink','os.chmod','os.truncate'):
        deny(event,args)
    if event == 'import' and str(args[0]).split('.')[0] == 'serial':
        deny(event,'serial')
    if event == 'open':
        name,mode,flags=args
        if not isinstance(name,(str,bytes,os.PathLike)):
            deny(event,'raw file descriptor')
        path=Path(os.fsdecode(name)).resolve()
        write=bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if write and path != report:
            deny(event,'write '+str(path))
        if not write and not (path == report or any(under(path,r) for r in allowed)):
            deny(event,'read '+str(path))

sys.dont_write_bytecode=True
sys.addaudithook(audit)
sys.argv=[str(checker),'--offline',str(bundle),'--out',str(report),'--golden',str(golden)]
code=0
try:
    runpy.run_path(str(checker),run_name='__main__')
except SystemExit as exc:
    code=exc.code if isinstance(exc.code,int) else 1
except BaseException as exc:
    code=97
    violations.append(dict(event='uncaught',detail=repr(exc)))
finally:
    active=False
    log.write_text(json.dumps(violations,indent=2)+'\n',encoding='utf-8')
raise SystemExit(code)
