"""Actual pinned executable S1 smoke/ownership/no-flag regressions (host only).

Supply one independently authenticated admitted Stage1 audio source. This does not
replace the full ADAPTER.md matrix or AP4 math. Never opens a block device.
"""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
import oracle

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(binary,sha,version,source,work):
    assert binary.is_file() and digest(binary)==sha
    assert source.is_file() and not work.exists();work.mkdir(parents=True)
    inp=work/'music';inp.mkdir();shutil.copyfile(source,inp/'song.wav')
    empty=work/'empty';empty.mkdir();sentinel=work/'foreign';sentinel.write_bytes(b'FOREIGN MUST SURVIVE\n')
    nonce='0123456789abcdef0123456789abcdef';results=[]
    def invoke(name,folder,flags=(),expected=0):
        d=work/name;d.mkdir();dest=work/'shared-dest';argv=[str(binary),'--out',str(dest),'--length','3600',*flags,str(folder)]
        p=subprocess.run(argv,capture_output=True);(d/'stdout').write_bytes(p.stdout);(d/'stderr').write_bytes(p.stderr)
        record=dict(name=name,argv=argv,binary_sha256=sha,version=version,exit=p.returncode,stdout_sha256=digest(d/'stdout'),stderr_sha256=digest(d/'stderr'))
        (d/'process.json').write_text(json.dumps(record,indent=2)+'\n');results.append(record)
        assert p.returncode==expected,(name,p.returncode,p.stderr)
        assert sentinel.read_bytes()==b'FOREIGN MUST SURVIVE\n'
        if expected!=0:assert not dest.exists(),name
        else:shutil.move(str(dest),str(d/'dest')) # snapshot pair; reuse the SAME CLI DEST for stdout equivalence
        return d,p
    a,p=invoke('no-flag',inp)
    assert sorted(x.name for x in (a/'dest').iterdir())==['audio.wav','manifest.json']
    control=work/'control';control.mkdir();report=control/'success.jsonl'
    b,q=invoke('reported',inp,['--report',str(report),'--report-nonce',nonce])
    assert p.stdout==q.stdout and p.stderr==q.stderr
    for name in ('audio.wav','manifest.json'):assert digest(a/'dest'/name)==digest(b/'dest'/name)
    parsed=oracle.parse(report.read_bytes(),'ingest',version,nonce,q.returncode,['music']);assert parsed is not None
    r=control/'empty.jsonl';d,p=invoke('empty-refusal',empty,['--report',str(r),'--report-nonce',nonce],2)
    parsed=oracle.parse(r.read_bytes(),'ingest',version,nonce,p.returncode,['empty']);assert parsed and parsed['refusal']['id']=='FOLDER_EMPTY'
    assert set(x.name for x in d.iterdir())=={'stdout','stderr','process.json'},'stage/output created on refusal'
    # Bad report syntax never creates its requested leaf.
    for name,flags in [('missing-nonce',['--report',str(control/'missing')]),('missing-report',['--report-nonce',nonce]),('upper-nonce',['--report',str(control/'upper'),'--report-nonce','A'*32]),('short-nonce',['--report',str(control/'short'),'--report-nonce','0']),('repeat-report',['--report',str(control/'repeat'),'--report',str(control/'repeat2'),'--report-nonce',nonce])]:
        before=set(control.iterdir());invoke(name,empty,flags,2);assert set(control.iterdir())==before
    for name,kind in [('existing-leaf','ordinary'),('link-leaf','link'),('dangling-leaf','dangling')]:
        r=control/name
        if kind=='ordinary':r.write_bytes(b'EXISTING\n')
        else:
            target=sentinel if kind=='link' else work/'never-created'
            try:r.symlink_to(target)
            except OSError as e:
                results.append(dict(name=name,status='UNEXECUTED',os_error=str(e)));continue
        before=r.read_bytes() if kind=='ordinary' else os.readlink(r)
        invoke(name,inp,['--report',str(r),'--report-nonce',nonce],1)
        assert (r.read_bytes() if kind=='ordinary' else os.readlink(r))==before
        assert not (work/'never-created').exists()
    r=work/'missing-parent'/'report';invoke('create-failure',inp,['--report',str(r),'--report-nonce',nonce],1);assert not r.exists()
    (work/'RESULT.json').write_text(json.dumps(dict(scope='actual bounded S1 process tests, not overall acceptance',source_sha256=digest(source),results=results),indent=2)+'\n')
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--ingest',type=Path,required=True);p.add_argument('--sha256',required=True);p.add_argument('--version',required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args();r=run(a.ingest.resolve(),a.sha256,a.version,a.source.resolve(),a.work.resolve());print(len(r),'actual process rows; retain RESULT.json and all raw files')
