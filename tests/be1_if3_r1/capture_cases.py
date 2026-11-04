"""Saved fake-port stimuli and expected IF/3 exits, independent of helper code."""
import base64
import struct

DIGEST=b'SHA256 '+b'0'*64+b' FRAMES 0 RESULT 0\r\n'
INFO=b'INFO state 1 instance 191600 reserve 191600 card_blocks 100000 p2_base 34816 p2_blocks 65184 stack_high_water 8192 underruns 0\r\n'

def catalog():
    out=[]
    def add(name,raw=b'',mode='--until-digest',stop='digest',rc=0,**kw):
        c=dict(name=name,wire=base64.b64encode(raw).decode(),expected=base64.b64encode(raw).decode(),
          mode=mode,stop=stop,exit=rc,fragment=1,tick=0.001,timeout=0.25,empty_reads=[],port='V3_FAKE:UNCHANGED',
          send=None,spans=[],usage=False)
        c.update(kw);out.append(c);return c
    add('digest-fragmented',DIGEST,fragment=7,timeout=1)
    add('digest-LF',DIGEST.replace(b'\r\n',b'\n'),timeout=1)
    add('empty-and-short-reads-continue',DIGEST,fragment=3,empty_reads=[1,3,7],timeout=1)
    add('digest-stops-on-ERR',b'ERR unknown command\r\n',stop='err')
    add('info-terminates',INFO,mode='--until-info',stop='info',timeout=1)
    add('info-FATAL',b'FATAL instance 9 > reserve 8\r\n',mode='--until-info',stop='info')
    add('info-ERR',b'ERR usage or no mounted card\r\n',mode='--until-info',stop='err')
    add('digest-ignores-info',INFO+DIGEST,timeout=1)
    add('info-ignores-digest',DIGEST+INFO,mode='--until-info',stop='info',timeout=1)
    c=add('nothing-read-after-stop',DIGEST+b'UNWANTED TAIL\n',timeout=1)
    c.update(expected=base64.b64encode(DIGEST).decode(),terminal_end=len(DIGEST))
    payload=(DIGEST+b'ERR unknown command\nINFO false\n')
    payload+=b'\0'*((-len(payload))%4)
    prefix=b'PCM\r\n';count=struct.pack('<I',len(payload)//4);zero=struct.pack('<I',0)
    raw=prefix+count+payload+zero+DIGEST
    spans=[[len(prefix),len(prefix)+4,'count'],[len(prefix)+4,len(prefix)+4+len(payload),'pcm'],
           [len(prefix)+4+len(payload),len(prefix)+8+len(payload),'count']]
    add('stream-framing-with-digest-ERR-info-in-PCM',raw,spans=spans,fragment=19,timeout=1)
    add('stream-count-byte-fragments',raw,spans=spans,fragment=1,timeout=1)
    add('stream-empty-reads-inside-count',raw,spans=spans,fragment=3,empty_reads=[7,9,13],timeout=1)
    for name,data,sp in (
      ('partial-line',b'SHA256 partial',[]),
      ('partial-count',prefix+b'\x03\x00',[[len(prefix),len(prefix)+4,'count']]),
      ('partial-pcm',prefix+struct.pack('<I',3)+b'\x00\xff\x0a',[[len(prefix),len(prefix)+4,'count'],[len(prefix)+4,len(prefix)+16,'pcm']]),
      ('missing-zero-terminator',prefix+struct.pack('<I',1)+b'\x00'*4,[[len(prefix),len(prefix)+4,'count'],[len(prefix)+4,len(prefix)+8,'pcm'],[len(prefix)+8,len(prefix)+12,'count']]),
      ('missing-digest-after-zero',prefix+zero,[[len(prefix),len(prefix)+4,'count']]),
    ):
        add(name,data,stop='timeout',rc=3,spans=sp)
    add('info-timeout-keeps-partial',b'INFO par',mode='--until-info',stop='timeout',rc=3)
    add('digest-default-600',b'P',stop='timeout',rc=3,timeout=None,tick=200,elapsed_min=600,elapsed_max=800)
    add('info-default-10',b'P',mode='--until-info',stop='timeout',rc=3,timeout=None,tick=4,elapsed_min=10,elapsed_max=14)
    add('interrupt-timeout-keeps-bytes',b'AB',mode='--until-interrupt',stop='timeout',timeout=0.2,tick=0.05)
    for mode,rc in [('--until-digest',130),('--until-info',130),('--until-interrupt',0)]:
        add('ctrl-C-'+mode[8:],b'AB',mode=mode,stop='interrupt',rc=rc,interrupt_after=2)
    add('interrupt-default-has-no-timeout',b'AB',mode='--until-interrupt',stop='interrupt',timeout=None,
        tick=10000,interrupt_after=2,elapsed_min=20000)
    for stage in ('open','read','write','flush'):
        data=b'AB' if stage=='read' else b''
        add('port-error-'+stage,data,stop='port_error',rc=4,error=stage,
            error_after=2,send='info' if stage in ('write','flush') else None)
    for name,line in [('send-one','x'),('send-info','info'),('send-63','x'*63)]:
        add(name,INFO,mode='--until-info',stop='info',send=line,timeout=1)
    add('deadline-starts-after-send',INFO,mode='--until-info',stop='info',send='info',send_delay=1000,timeout=1)
    add('reset-discards-pre-send-bytes',INFO,mode='--until-info',stop='info',send='info',
        before_send=base64.b64encode(b'STALE\r\n').decode(),timeout=1)
    for name,line in [('send-empty',''),('send-64','x'*64),('send-non-ascii','caf\u00e9'),('send-CR','x\r'),('send-LF','x\n'),('send-NUL','x\0')]:
        add(name,rc=64,stop=None,send=line,usage=True)
    for value in (0,-1):add('timeout-invalid-'+str(value),rc=64,stop=None,timeout=value,usage=True)
    add('no-mode',rc=64,stop=None,mode=None,usage=True)
    add('multiple-modes',rc=64,stop=None,extra_args=['--until-info'],usage=True)
    add('unknown-option',rc=64,stop=None,extra_args=['--not-an-option'],usage=True)
    add('existing-output-never-overwritten',rc=64,stop=None,preexisting=base64.b64encode(b'EARLIER EVIDENCE\r\n').decode(),usage=True)
    return out
