"""Independent parser fixtures and explicit expected categories from APP-1A.

Not child-execution evidence. Stage2 must also exercise genuine outcomes.
"""
import copy,json
from oracle import I1,I2,M1,M2,M3,STEPS
NONCE='0123456789abcdef0123456789abcdef';VERSION='fixture-build-1';FOLDERS=['Music','More music']

def raw(rows):return (''.join(json.dumps(r,separators=(',',':'),ensure_ascii=False)+'\n' for r in rows)).encode()
def report(tool,exit,records=()):return [dict(t='start',tool=tool,version=VERSION,nonce=NONCE),*records,dict(t='end',exit=exit)]
def refusal(tool,id):
    r=dict(t='refusal',id=id,subject=None)
    if tool=='ingest':
        if id.startswith(('SOURCE_','ENTRY_')) or id=='IO_SOURCE':r['subject']='0/song.wav'
        if id.startswith('FOLDER_') or id=='IO_FOLDER':r['subject']='0'
        if id=='FOLDER_DUPLICATE':r['subject']='1';r['same_as']='0'
        if id in ('JOIN_PEAK','JOINED_PEAK'):r['subject']=['0/a.wav','1/b.wav'];r['dbtp']='-0.100000'
    if id in ('INGEST_TOO_LONG','TOO_LONG'):r.update(total_frames=158760001,capacity_frames=158760000,excess_frames=1)
    if id in ('DEVICE_OPEN_FAILED','CARDS_ENUM_UNAVAILABLE'):r['os_error']='native error'
    if id=='WAV_INVALID':r['reason']='riff'
    if id=='WAV_TRUNCATED':r['phase']='load'
    if id=='ENGINE':r.update(phase='provision',result='TAPE_ERR_GEOMETRY')
    if id=='IO':r.update(phase='verify',op='read_lba0')
    if id=='CARD_CHANGED':r.update(phase='load',os_error='native media change')
    if id=='VERIFY_FINDINGS':r['findings']=[dict(f='READ_ERROR',side='A',frame=0)]
    return r

def category(tool,id):
    if tool=='ingest':
        if id=='INGEST_TOO_LONG':return ['overage',1]
        if id=='SOURCE_PROTECTED':return ['protected','0/song.wav']
        if id in 'SOURCE_NOT_AUDIO ENTRY_NOT_REGULAR ENTRY_NESTED_FOLDER ENTRY_SYMLINK'.split():return ['folder-nonmusic','0/song.wav']
        if id in ('FOLDER_SYMLINK','FOLDER_EMPTY'):return ['folder-nonmusic','0']
        if id.startswith('SOURCE_') or id in ('IO_SOURCE','ENTRY_NAME_INVALID'):return ['unusable','0/song.wav']
        if id in ('FOLDER_NAME_COLLISION','FOLDER_NAME_NOT_UNICODE'):return ['unusable','0']
        return ['generic',None]
    if tool=='tapectl make':
        if id in ('TOO_LONG','ENGINE'):return ['card-small',None]
        if id in ('CARD_CHANGED','IO','DEVICE_OPEN_FAILED'):return ['card-interrupted',None]
        if id=='VERIFY_FINDINGS':return ['verify-finding',None]
        if id=='WAV_TRUNCATED':return ['music-changed',None]
        if id in M3:return ['card-refused',None]
        return ['make-generic',None]
    return ['generic',None]

def corpus():
    out=[]
    def add(name,tool,exit,rows=None,data=None,valid=True,message=None,pair=False):
        if not valid:
            message=['success',None] if exit==0 and (tool!='ingest' or pair) else ['make-generic' if tool=='tapectl make' and exit!=0 else 'generic',None]
        out.append(dict(name=name,tool=tool,version=VERSION,nonce=NONCE,exit=exit,folders=FOLDERS,pair=pair,raw_hex=(raw(rows) if data is None else data).hex(),valid=valid,message=message))
    for tool,groups in [('ingest',[(1,I1),(2,I2)]),('tapectl make',[(1,M1),(2,M2),(3,M3)]),('tapectl cards',[(1,['CARDS_ENUM_UNAVAILABLE']),(2,['USAGE'])])]:
        for exit,ids in groups:
            for id in ids:
                rows=report(tool,exit,[refusal(tool,id)]);add(tool+':'+id,tool,exit,rows,message=category(tool,id))
                # Each closed-ID input has its own real byte mutation.
                bad=copy.deepcopy(rows);bad[1]['id']='UNKNOWN_'+id;add(tool+':'+id+':unknown',tool,exit,bad,valid=False)
                bad=copy.deepcopy(rows);bad[1]['subject']='/foreign/path';add(tool+':'+id+':subject',tool,exit,bad,valid=False)
    for tool in STEPS:
        rows=report(tool,0);add(tool+':no-progress',tool,0,rows,message=['success',None],pair=True)
        add(tool+':final-partial-ignored',tool,0,data=raw(rows)+b'{"t":',message=['success',None],pair=True)
        for field,value in [('tool','wrong'),('version','old-build'),('nonce','f'*32)]:
            bad=copy.deepcopy(rows);bad[0][field]=value;add(tool+':stale-'+field,tool,0,bad,valid=False)
        add(tool+':missing-end',tool,0,rows[:-1],valid=False)
        add(tool+':mismatched-exit',tool,1,rows,valid=False)
        add(tool+':extra-end',tool,0,rows+[rows[-1]],valid=False)
        add(tool+':unknown-record',tool,0,rows[:1]+[dict(t='mystery')]+rows[1:],valid=False)
        add(tool+':blank-line',tool,0,data=raw(rows[:1])+b'\n'+raw(rows[1:]),valid=False)
        add(tool+':duplicate-key',tool,0,data=raw(rows).replace(b'"t":"end"',b'"t":"end","t":"end"'),valid=False)
        add(tool+':spaced-json',tool,0,data=raw(rows).replace(b'"t":"end"',b'"t": "end"'),valid=False)
        add(tool+':invalid-utf8',tool,0,data=raw(rows)+b'\xff\n',valid=False)
        add(tool+':empty',tool,0,data=b'',valid=False)
        steps=STEPS[tool]
        records=[dict(t='progress',step=s,done=0,total=0) for s in steps]
        add(tool+':ordered-sparse',tool,0,report(tool,0,records),message=['success',None],pair=True)
        for done,total in [(True,1),(-1,1),(2,1),(2**53,2**53),(1.0,2)]:
            add(tool+':bad-counter-'+str(done)+'-'+str(total),tool,0,report(tool,0,[dict(t='progress',step=steps[0],done=done,total=total)]),valid=False)
        for name,values in [('regression',[(1,2),(0,2)]),('changed-total',[(1,2),(2,3)]),('known-to-unknown',[(1,2),(1,0)])]:
            add(tool+':'+name,tool,0,report(tool,0,[dict(t='progress',step=steps[0],done=d,total=n) for d,n in values]),valid=False)
        add(tool+':unknown-to-known',tool,0,report(tool,0,[dict(t='progress',step=steps[0],done=0,total=0),dict(t='progress',step=steps[0],done=1,total=2)]),message=['success',None],pair=True)
        if len(steps)>1:add(tool+':step-return',tool,0,report(tool,0,[records[0],records[1],records[0]]),valid=False)
    r=refusal('ingest','INGEST_TOO_LONG')
    for e in [1,44100,44101,8467200]:
        v=dict(r,total_frames=158760000+e,excess_frames=e)
        add('overage-'+str(e),'ingest',2,report('ingest',2,[v]),message=['overage',(e+44099)//44100])
    for key,value in [('excess_frames',0),('excess_frames',2),('total_frames',True),('capacity_frames',-1)]:
        v=dict(r);v[key]=value;add('bad-overage-'+key+str(value),'ingest',2,report('ingest',2,[v]),valid=False)
    for s in ['2/song.wav','00/song.wav','0/../song.wav','0/','/song.wav','0/e\u0301.wav']:
        v=refusal('ingest','SOURCE_CORRUPT');v['subject']=s;add('bad-logical-'+s,'ingest',2,report('ingest',2,[v]),valid=False)
    v=refusal('ingest','SOURCE_CORRUPT');v['subject']='0/é.wav';add('NFC-name','ingest',2,report('ingest',2,[v]),message=['unusable','0/é.wav'])
    add('success-needs-pair','ingest',0,report('ingest',0),message=['generic',None])
    add('exit-never-overridden','ingest',2,report('ingest',2),message=['generic',None])
    v=refusal('tapectl make','WAV_TRUNCATED')
    add('make-diagnostic-not-selector','tapectl make',2,report('tapectl make',2,[dict(t='stderr',text='CARD_CHANGED REFUSE_SYSTEM_DISK'),v,dict(t='stderr',text='different words')]),message=['music-changed',None])
    add('two-terminal','ingest',2,report('ingest',2,[r,r]),valid=False)
    add('progress-after-terminal','ingest',2,report('ingest',2,[r,dict(t='progress',step='publish',done=1,total=1)]),valid=False)
    for reason in 'open riff fmt pcm channels rate bits align data chunk'.split():
        v=refusal('tapectl make','WAV_INVALID');v['reason']=reason
        add('wav-reason-'+reason,'tapectl make',2,report('tapectl make',2,[v]),message=['make-generic',None])
    for phase in ('safety','provision','load','commit','verify'):
        v=refusal('tapectl make','CARD_CHANGED');v['phase']=phase
        add('changed-phase-'+phase,'tapectl make',1,report('tapectl make',1,[v]),message=['card-interrupted',None])
    for phase in ('provision','capacity','load','commit'):
        v=refusal('tapectl make','ENGINE');v['phase']=phase;v['result']='TAPE_ERR_IO'
        add('engine-io-'+phase,'tapectl make',1,report('tapectl make',1,[v]),message=['card-interrupted',None])
    for op in ('entropy','read_lba0','clear_lba0','write_p1','build_mbr','write_mbr'):
        v=refusal('tapectl make','IO');v.update(phase='provision',op=op)
        add('provision-io-'+op,'tapectl make',1,report('tapectl make',1,[v]),message=['make-generic' if op in ('entropy','build_mbr') else 'card-interrupted',None])
    fs=[dict(f='MBR_LAYOUT'),dict(f='PARTITION_TYPE'),dict(f='PARTITION_TRUNCATED'),dict(f='MOUNT',side='B',result='TAPE_ERR_CRC'),dict(f='NEEDS_REPAIR'),dict(f='SIDE_B_DEGRADED'),dict(f='READ_ERROR',side='A',frame=1)]
    v=refusal('tapectl make','VERIFY_FINDINGS');v['findings']=fs
    add('all-findings-order','tapectl make',1,report('tapectl make',1,[v]),message=['verify-finding',None])
    for name,bad in [('unknown',[dict(f='UNISSUED')]),('out-of-order',list(reversed(fs))),('failed-mount-read',[dict(f='MOUNT',side='A',result='TAPE_ERR_CRC'),dict(f='READ_ERROR',side='A',frame=0)]),('bad-frame',[dict(f='READ_ERROR',side='A',frame=True)]),('bad-result',[dict(f='MOUNT',side='A',result='TAPE_ERR_MADE_UP')]),('repeat-frame',[dict(f='READ_ERROR',side='A',frame=1)]*2),('duplicate-layout',[dict(f='MBR_LAYOUT')]*2)]:
        v=refusal('tapectl make','VERIFY_FINDINGS');v['findings']=bad
        add('findings-'+name,'tapectl make',1,report('tapectl make',1,[v]),valid=False)
    # Remove every required terminal field independently.
    positives=list(out)
    for c in positives:
        if not c['valid']:continue
        rr=[json.loads(x) for x in bytes.fromhex(c['raw_hex']).splitlines() if x and x!=b'{"t":']
        terminal=next((i for i,x in enumerate(rr) if x.get('t')=='refusal'),None)
        if terminal is None:continue
        for key in list(rr[terminal]):
            bad=copy.deepcopy(rr);del bad[terminal][key]
            add(c['name']+':missing-'+key,c['tool'],c['exit'],bad,valid=False)
    return out

if __name__=='__main__':print(json.dumps(corpus(),indent=2,ensure_ascii=False))
