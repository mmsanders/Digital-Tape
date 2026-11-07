"""Fake serial/clock and IO audit for an IF/3 helper. No real serial import."""
import base64
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import time
import types

helper,config,out,log=map(lambda x:Path(x).resolve(),sys.argv[1:])
c=json.loads(config.read_text(encoding='utf-8'))
wire=base64.b64decode(c['wire']);offset=0;clock=0.0;reads=0;events=[];violations=[];active=True
delivered=bytearray();reset=False;written=False;flushed=False

class PortError(OSError):pass

class FakeSerial:
    def __init__(self,port,baudrate=115200,timeout=0.05):
        events.append(['open',port,baudrate,timeout])
        assert port==c['port'] and baudrate==115200 and timeout==0.05
        if c.get('error')=='open':raise PortError('injected open failure')
    def reset_input_buffer(self):
        global reset
        events.append(['reset']);assert not written and not delivered;reset=True
    def write(self,b):
        global written,clock
        events.append(['write',bytes(b).hex()]);assert reset and c['send'] is not None
        assert bytes(b)==c['send'].encode('ascii')+b'\n';written=True
        clock+=c.get('send_delay',0)
        if c.get('error')=='write':raise PortError('injected write failure')
        return len(b)
    def flush(self):
        global flushed
        events.append(['flush']);assert written;flushed=True
        if c.get('error')=='flush':raise PortError('injected flush failure')
    def read(self,n):
        global offset,reads,clock
        reads+=1;assert reads<10000,'Unbounded read loop'
        if c['send'] is not None:assert reset and written and flushed,'Read before send/flush'
        else:assert not reset and not written,'Reset/write without --send'
        # A new read may not hide an unflushed previous chunk.
        if delivered:assert out.read_bytes()==bytes(delivered),'Received bytes not flushed before next read'
        if 'terminal_end' in c:assert offset<c['terminal_end'],'Read after completed stop line'
        assert isinstance(n,int) and n>0
        allowed=1
        for start,end,kind in c['spans']:
            if start<=offset<end:allowed=end-offset;break
        assert n<=allowed,('Over-read protocol element',n,allowed,offset)
        if c.get('interrupt_after') is not None and offset>=c['interrupt_after']:raise KeyboardInterrupt()
        if c.get('error')=='read' and offset>=c.get('error_after',0):raise PortError('injected read failure')
        clock+=c['tick']
        if reads in c['empty_reads']:return b''
        end=min(len(wire),offset+min(n,c['fragment']))
        part=wire[offset:end];offset=end;delivered.extend(part)
        return part
    def close(self):events.append(['close'])

serial=types.ModuleType('serial');serial.Serial=FakeSerial;serial.SerialException=PortError
class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def find_spec(self,name,path=None,target=None):
        if name=='serial':events.append(['import-serial']);return importlib.util.spec_from_loader(name,self)
    def create_module(self,spec):return serial
    def exec_module(self,module):pass
sys.modules.pop('serial',None);sys.meta_path.insert(0,Loader())

def now():return clock
def sleep(seconds):
    global clock
    assert seconds>=0;clock+=seconds
time.monotonic=now;time.perf_counter=now;time.time=now;time.sleep=sleep

def audit(event,args):
    if not active:return
    bad=event.startswith(('socket.','subprocess.')) or event in ('ctypes.dlopen','ctypes.dlsym','os.system','os.remove','os.rename','os.mkdir','os.rmdir','os.link','os.symlink')
    if event=='open':
        name,mode,flags=args
        if not isinstance(name,(str,bytes,os.PathLike)):bad=True
        else:
            p=Path(os.fsdecode(name)).resolve();writing=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            roots=(helper.parent,Path(sys.base_prefix).resolve(),Path(os.__file__).resolve().parent)
            bad=(writing and p!=out) or (not writing and p!=out and not any(p==r or r in p.parents for r in roots))
    if bad:violations.append([event,str(args)]);raise PermissionError('IF3 fake-port confinement')

args=[str(helper),'--port',c['port'],'--out',str(out)]
if c['mode'] is not None:args.append(c['mode'])
if c['send'] is not None:args.extend(['--send',c['send']])
if c['timeout'] is not None:args.extend(['--timeout',str(c['timeout'])])
args.extend(c.get('extra_args',[]));sys.argv=args
sys.dont_write_bytecode=True;sys.addaudithook(audit);rc=0
try:runpy.run_path(str(helper),run_name='__main__')
except SystemExit as e:rc=e.code if isinstance(e.code,int) else 1
except BaseException as e:rc=97;violations.append(['uncaught',repr(e)])
finally:
    active=False
    log.write_text(json.dumps(dict(events=events,violations=violations,elapsed=clock,reads=reads,
      delivered_sha256=hashlib.sha256(delivered).hexdigest(),delivered_bytes=len(delivered)))+'\n',encoding='utf-8')
raise SystemExit(rc)
