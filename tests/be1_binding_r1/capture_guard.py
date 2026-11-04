"""Fake-port execution boundary. Never imports pyserial or connects to a device."""
import base64
import json
import os
from pathlib import Path
import runpy
import sys
import types

helper,config,out,log=map(lambda v:Path(v).resolve(),sys.argv[1:])
cfg=json.loads(config.read_text(encoding='utf-8'))
data=base64.b64decode(cfg['bytes']);offset=0;calls=0;opened=[];writes=[]

class FakeSerial:
    def __init__(self,port=None,*a,**kw):
        assert port=='V382_FAKE_ONLY','Only simulator port is allowed'
        opened.append(port);self.timeout=kw.get('timeout');self.is_open=True
    @property
    def in_waiting(self):return min(cfg['fragment'],len(data)-offset)
    def read(self,n=1):
        global offset,calls
        calls+=1
        assert calls<1000000,'Unbounded fake-port read loop'
        end=min(len(data),offset+min(n,cfg['fragment']))
        part=data[offset:end];offset=end
        return part
    def readinto(self,b):
        part=self.read(len(b));b[:len(part)]=part;return len(part)
    def readline(self):
        raw=bytearray()
        while offset<len(data):
            raw.extend(self.read(1))
            if raw.endswith(b'\n'):break
        return bytes(raw)
    def write(self,b):
        writes.append(bytes(b).hex());raise AssertionError('No command is sent in these ready cases')
    def flush(self):pass
    def reset_input_buffer(self):assert offset==0
    def close(self):self.is_open=False
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

serial=types.ModuleType('serial');serial.Serial=FakeSerial;serial.SerialException=OSError
sys.modules['serial']=serial
violations=[];active=True
def audit(event,args):
    if not active:return
    bad=event.startswith(('socket.','subprocess.')) or event in ('ctypes.dlopen','os.system','os.remove','os.rename')
    if event=='open':
        name,mode,flags=args
        if not isinstance(name,(str,bytes,os.PathLike)):bad=True
        else:
            path=Path(os.fsdecode(name)).resolve()
            writing=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            roots=(helper.parent,config.parent,Path(sys.base_prefix).resolve(),Path(os.__file__).resolve().parent)
            bad=(writing and path!=out) or (not writing and not any(path==r or r in path.parents for r in roots))
    if bad:
        violations.append(event);raise PermissionError('V382 fake-port confinement')
sys.dont_write_bytecode=True;sys.addaudithook(audit)
sys.argv=[str(helper),'--port','V382_FAKE_ONLY','--out',str(out),'--until-digest','--timeout','0.1']
rc=0
try:runpy.run_path(str(helper),run_name='__main__')
except SystemExit as exc:rc=exc.code if isinstance(exc.code,int) else 1
except BaseException as exc:rc=97;violations.append(repr(exc))
finally:
    active=False
    log.write_text(json.dumps(dict(violations=violations,ports=opened,command_writes=writes,read_calls=calls))+'\n',encoding='utf-8')
raise SystemExit(rc)
