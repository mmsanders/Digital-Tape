"""Actual-shipping resource regression, INGEST-1/ADR186. Never opens a device."""
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
BASE='0e1ef2cb4f283eb876f08019222da5d3ac744ec30d49f020a2e87323f31bcac1'
SOURCE='d36663d1e4f05abaac699a6c14e0fa86724db9b4decdb8c96abe0c9d1f645821'
BOUNDS=[3,4,6,8,12,64,None]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def launched(binary,limit,argv,root,name):
    out=root/(name+'.stdout');err=root/(name+'.stderr')
    if sys.platform=='win32':
        import windows_job
        r=windows_job.run([binary,*argv],None if limit is None else limit*1024*1024,out,err,root)
    else:
        assert sys.platform.startswith('linux'),'No enforceable macOS method issued: explicit capability stop'
        cmd=([binary,*argv] if limit is None else ['prlimit',f'--as={limit*1024*1024}','--',binary,*argv])
        t=time.monotonic()
        with out.open('wb') as o,err.open('wb') as e:
            p=subprocess.run(cmd,cwd=root,stdout=o,stderr=e,timeout=30)
        r=dict(exit=p.returncode,timed_out=False,seconds=time.monotonic()-t,method='Linux RLIMIT_AS' if limit else 'unlimited')
    r.update(argv=[str(binary),*map(str,argv)],limit_mib=limit,stdout_sha256=sha(out),stderr_sha256=sha(err),stdout=out.read_text(errors='replace'),stderr=err.read_text(errors='replace'))
    return r

def judge(row,positive_pair):
    """Contract-only expectations; exact statuses remain visible even on failure."""
    load,c=row['load'],row['case'];bad=[]
    if load['exit']!=0 or load['timed_out'] or not load['stdout'].startswith('ingest '):return ['LOAD_CONTROL_FAILED: not tool-exhaustion evidence']
    if c['timed_out']:bad.append('case timeout')
    if not row['foreign_unchanged']:bad.append('foreign sentinel changed')
    if row['unexpected_entries']:bad.append('residual stage/unowned output entry')
    if c['exit']==0:
        if not row['pair'] or row['pair']!=positive_pair:bad.append('successful pair differs from unlimited shipping control')
    else:
        if c['exit']!=1:bad.append('resource failure must return exactly1 (abort/signal is red)')
        if row['dest_exists']:bad.append('failed operation published DEST')
        if not c['stderr'].startswith('ingest: '):bad.append('failure lacks tool diagnostic')
    return bad

def run(binary,expected,source,root,mode):
    assert sha(binary)==expected,'actual executable identity';assert sha(source)==SOURCE,'immutable admitted Stage1 source identity'
    assert not root.exists();root.mkdir(parents=True)
    music=root/'f0';music.mkdir();shutil.copyfile(source,music/'ordinary.wav')
    output=root/'output';output.mkdir();dest=output/'DEST';sentinel=output/'foreign';sentinel.write_bytes(b'FOREIGN SENTINEL - DO NOT MODIFY\n');sentinel_sha=sha(sentinel)
    rows=[]
    # Unlimited first binds success bytes for every successful limited row.
    for n,limit in enumerate([None,*[v for v in BOUNDS if v is not None]]):
        d=root/f'row-{n}';d.mkdir()
        load=launched(binary,limit,['--version'],d,'load')
        case=launched(binary,limit,['--out',str(dest),'--length','60',str(music)],d,'case')
        pair={p.name:sha(p) for p in dest.iterdir()} if dest.is_dir() else None
        if pair is not None and sorted(pair)!=['audio.wav','manifest.json']:pair=None
        unexpected=sorted(p.name for p in output.iterdir() if p.name not in ('DEST','foreign'))
        row=dict(limit_mib=limit,load=load,case=case,dest_exists=dest.exists(),pair=pair,unexpected_entries=unexpected,foreign_unchanged=sentinel.exists() and sha(sentinel)==sentinel_sha)
        rows.append(row)
        # Do not hide residuals to make the next row clean: keep each raw census.
        if dest.exists():shutil.move(str(dest),str(d/'published-DEST'))
        for p in output.iterdir():
            if p.name!='foreign':shutil.move(str(p),str(d/p.name))
    positive=rows[0]['pair'];assert rows[0]['case']['exit']==0 and positive,'unlimited admitted positive failed'
    for r in rows:r['violations']=judge(r,positive)
    six=next(r for r in rows if r['limit_mib']==6)
    result=dict(scope='actual shipping executable, full application path; Windows Server supplementary only',binary_sha256=expected,source_sha256=SOURCE,platform=sys.platform,mode=mode,rows=rows,contract_pass=not any(r['violations'] for r in rows))
    (root/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    if mode=='baseline-red':
        assert sys.platform=='win32' and expected==BASE
        assert six['load']['exit']==0 and six['case']['exit']==0xC0000409,'original red baseline not reproduced'
        assert not six['dest_exists'] and not six['unexpected_entries'] and six['foreign_unchanged']
        assert six['violations'] and not result['contract_pass'],'detector did not go red'
        assert any(r['limit_mib'] in (3,4) and r['case']['exit']==1 and not r['violations'] for r in rows),'adjacent bounded exit1 control absent'
        assert any(r['limit_mib'] in (8,12,64) and r['case']['exit']==0 and not r['violations'] for r in rows),'adjacent bounded positive absent'
        print('REPRODUCED real red shipping baseline:6MiB abort0xC0000409; detector rejects it; controls retained')
    else:
        assert result['contract_pass'],[(r['limit_mib'],r['violations']) for r in rows if r['violations']]
        assert any(r['case']['exit']==1 for r in rows),'no actual bounded exhaustion: capability stop, not PASS'
        print('PASS bounded shipping exhaustion regression; native/platform/full package holds remain')
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--binary',type=Path,required=True);a.add_argument('--sha256',required=True);a.add_argument('--source',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--mode',choices=['baseline-red','candidate'],default='candidate');v=a.parse_args();run(v.binary.resolve(),v.sha256,v.source.resolve(),v.out.resolve(),v.mode)
