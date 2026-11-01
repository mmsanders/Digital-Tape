"""Independent 332 command/capture predicates and pre-code production case index.
No Product imports, process execution or expected-trace production.
"""
import copy,json
from receipts import sha

# IDs are frozen obligations, not claimed Product runs. README defines originals.
CASES={
 'C01':'Windows command CREATE_NO_WINDOW; harmless child GetConsoleWindow == 0',
 'C02':'Test-only removed flag, same console-attached runner: child console != 0',
 'C03':'Exit0: exact argv/cwd/env/stdin, raw streams/report, canonical pair and reaping',
 'C04':'Exit2 refusal: exact report/streams/exit, no delivered pair; cleanup after wait',
 'C05':'Missing executable: child-not-launched, no invented PID/wait; failed outcome/cleanup',
 'C06':'Cancellation: killed child actually waited/reaped, no later publication accepted',
 'C07':'Teardown during child: join/wait/cleanup before session end, no live helper remains',
 'C08':'OFF and ON same child outcome/argv/cwd/env/streams/report/pair and GUI state',
 'C09':'No flag / value / duplicate / path argument: OFF, zero diagnostic sink calls or files',
 'C10':'Fresh exclusive private session/marker; preserve old/foreign files byte-identically',
 'C11':'Occupied session/marker/record/blob leaf: fail closed, never overwrite foreign bytes',
 'C12':'Root/control/session reparse or parent identity substituted: no write through replacement',
 'C13':'Reset/stale in-flight result: exact old work generation, cancel/reap, stale-dropped, cleanup',
 'C14':'Queued work cancelled before admission: work-skipped, no invented launch/cleanup',
 'C15':'Ingress route native-event / tauri-command / controlled-test honest at real boundary',
 'C16':'Rejected and no-change drops retain reason/Next; no job or child invented',
 'C17':'Original report/stdout/stderr/manifest retained only after wait, before job deletion',
 'C18':'Audio streamed hash/length/frames before cleanup; no audio or music bytes copied',
 'C19':'Malformed or wrong-nonce original report retained unchanged, receipt incomplete',
 'C20':'Unknown source/OS build/process creation identity stays unknown and incomplete',
 'C21':'JSONL UTF8 line including LF <=65536 bytes, boundary accepted; next byte stops sink',
 'C22':'Blob <=4194304 bytes boundary accepted; next byte missing/incomplete, no truncation',
 'C23':'All marker/records/blobs <=16777216 bytes; aggregate exhaustion stops collection',
 'C24':'Create/short-write/full-volume/record/blob/footer failure: incomplete if possible, stop',
 'C25':'Sink failures leave actual child outcomes, reaping, stale decision and cleanup unchanged',
 'C26':'Reset/close retain own diagnostic session only; no startup enumeration or deletion',
 'C27':'Wrong PID/nonce/generation/seq/hash/dropped wait/early cleanup fail receipt oracle',
 'C28':'Source and release bundle: no shipping probe/fake flag/export/env/default-on authority',
}

def command(actual,expected,windows=True):
    """Actual Command/probe observation, compared to caller-owned fixture inputs."""
    assert actual['exe']==expected['exe']
    assert actual['argv']==[expected['exe'],'--report',expected['report'],'--report-nonce',expected['nonce'],'--out',expected['dest'],'--length','3600','--']+expected['folders']
    assert actual['cwd']==expected['job_dir'] and actual['env_sha256']==expected['env_sha256']
    assert actual['stdin']=='null' and actual['stdout']=='piped' and actual['stderr']=='piped'
    if windows:assert actual['creation_flags']==0x08000000

def parity(off,on):
    # Timing/PIDs/receipt files differ; production inputs and outcomes may not.
    fields=['exe_sha256','argv','cwd','env_sha256','exit','stdout_sha256','stderr_sha256','report_sha256','manifest_sha256','audio_sha256','audio_bytes','total_frames','state','cleanup','reaped']
    assert set(off)==set(on)==set(fields) and off==on and off['reaped'] is True

def controls():
    e=dict(exe='owned/probe.exe',report='owned/report',nonce='a'*32,dest='owned/DEST',folders=['owned/Music'],job_dir='owned/job',env_sha256='b'*64)
    a=dict(exe=e['exe'],argv=[e['exe'],'--report',e['report'],'--report-nonce',e['nonce'],'--out',e['dest'],'--length','3600','--']+e['folders'],cwd=e['job_dir'],env_sha256=e['env_sha256'],stdin='null',stdout='piped',stderr='piped',creation_flags=0x08000000)
    command(a,e)
    for field,value in [('exe','foreign'),('argv',a['argv'][:-1]),('cwd','foreign'),('env_sha256','c'*64),('stdin','inherit'),('stdout','inherit'),('stderr','null'),('creation_flags',0)]:
        b=copy.deepcopy(a);b[field]=value
        try:command(b,e)
        except AssertionError:continue
        raise AssertionError('command mutation survived: '+field)
    p=dict(exe_sha256='a',argv=['probe'],cwd='job',env_sha256='b',exit=0,stdout_sha256='c',stderr_sha256='d',report_sha256='e',manifest_sha256='f',audio_sha256='g',audio_bytes=48,total_frames=1,state='ready',cleanup='removed',reaped=True)
    parity(p,p)
    for field in p:
        q=copy.deepcopy(p);q[field]=None
        try:parity(p,q)
        except AssertionError:continue
        raise AssertionError('parity mutation survived: '+field)
    assert len(CASES)==28 and all(CASES.values())
    print('PASS8 command +16 parity causal negatives;28 frozen production obligations; ZERO Product/process execution')
if __name__=='__main__':
    import sys
    if '--catalog' in sys.argv:print(json.dumps(CASES,indent=2))
    else:controls()
