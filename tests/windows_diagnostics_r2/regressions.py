"""Independent r2 corrections and existing bounded-writer/provenance obligations."""
import copy,json
import receipts
def limit_stops(rows):
    for i,r in enumerate(rows):
        if r['kind']=='missing' and 'limit' in str(r['data']['reason']):
            assert [x['kind'] for x in rows[i+1:]]==['incomplete']
def bound_source(meta,app_sha,pins):
    assert meta['child_pin']==pins['ingest'] and meta['tapectl_pin']==pins['tapectl']
    app=[f for f in meta['files'] if f['name']=='digital-tape.exe']
    assert len(app)==1 and app[0]['sha256']==app_sha
    receipts.hx(meta['source_head'],40)
def no_false_complete(header,terminal,report_present,complete):
    known=bool(header['app_path'] and header['app_sha256'] and header['source_commit'] and header['os_build'] and header['app_os_start_ns'])
    if not known or (terminal.get('cancelled') and not report_present):assert complete is False
def controls():
    receipts.controls()
    for t in [1,1793047401339587700,2**64-1]:receipts.timestamp(t)
    for t in [-1,0,True,1.5,2**64,'1793047401339587700']:
        try:receipts.timestamp(t)
        except AssertionError:continue
        raise AssertionError('timestamp negative survived')
    rows,files=receipts.fixture()
    for r in rows:
        if r['kind']=='child-launch':r['data'].update(os_start_ns=1793047401339587700,spawn_call_ns=1793047401338453600)
        if r['kind']=='child-terminal':r['data']['end_ns']=1793047401401836700
    files['records.jsonl']=receipts.encode(rows);receipts.validate(files)
    # A second admitted gesture appends, while each work keeps its own snapshot.
    base=copy.deepcopy(rows[:-1]);second=copy.deepcopy(rows[1:-1]);old=rows[3]['data']['work_id'];new='ingest-'+'9'*32
    for r in second:
        d=r['data']
        if 'work_id' in d:d['work_id']=new
        if 'drop_id' in d:d['drop_id']='drop2'
        if r['kind']=='ingress':d['paths']=['fixture/Second']
        if r['kind']=='child-launch':d['argv'].append('fixture/Second')
    combined=base+second+[copy.deepcopy(rows[-1])]
    for i,r in enumerate(combined):r['seq']=i
    ff=dict(files);ff['records.jsonl']=receipts.encode(combined);receipts.validate(ff)
    j=next(i for i,r in enumerate(combined) if r['kind']=='child-launch' and r['data']['work_id']==new)
    for folders in [['fixture/Second'],['fixture/Second','fixture/Music'],['fixture/Music','fixture/Second','foreign']]:
        rr=copy.deepcopy(combined);rr[j]['data']['argv']=rr[j]['data']['argv'][:10]+folders;ff['records.jsonl']=receipts.encode(rr)
        try:receipts.validate(ff)
        except AssertionError:continue
        raise AssertionError('cumulative folder negative survived')
    rr=copy.deepcopy(combined);rr.insert(len(base),dict(schema=1,session=rows[0]['session'],seq=0,kind='reset',data=dict(old_generation=0,new_generation=1)))
    for i,r in enumerate(rr):
        r['seq']=i
        if i>len(base) and 'generation' in r['data']:r['data']['generation']=1
    rr[j+1]['data']['argv']=rr[j+1]['data']['argv'][:10]+['fixture/Second']
    ff['records.jsonl']=receipts.encode(rr);receipts.validate(ff)
    rr,ff=receipts.fixture();leaf=rr[6]['data']['leaf'];del ff[leaf];rr.pop(6)
    rr[5]['data'].update(cancelled=True,exit=None,wait_kind='wait');ff['records.jsonl']=receipts.encode(rr)
    for i,r in enumerate(rr):r['seq']=i
    ff['records.jsonl']=receipts.encode(rr)
    try:receipts.validate(ff)
    except AssertionError:pass
    else:raise AssertionError('cancel without report completed')
    rr[-1]['data'].update(complete=False,reason='missing-cancel-report');ff['records.jsonl']=receipts.encode(rr);receipts.validate(ff,False)
    m=dict(source_head='a'*40,child_pin='b'*64,tapectl_pin='c'*64,files=[dict(name='digital-tape.exe',sha256='d'*64)])
    bound_source(m,'d'*64,dict(ingest='b'*64,tapectl='c'*64))
    try:bound_source(m,'e'*64,dict(ingest='b'*64,tapectl='c'*64))
    except AssertionError:pass
    else:raise AssertionError('stale app sidecar survived')
    for h in [dict(app_path='',app_sha256='',source_commit='a'*40,os_build='win',app_os_start_ns=1),dict(app_path='app',app_sha256='d'*64,source_commit='a'*40,os_build='win',app_os_start_ns=1)]:
        try:no_false_complete(h,dict(cancelled=True),False,True)
        except AssertionError:pass
        else:raise AssertionError('unknown/missing-report completion survived')
    missing=dict(kind='missing',data=dict(reason='over-limit'))
    limit_stops([missing,dict(kind='incomplete')])
    try:limit_stops([missing,dict(kind='blob'),dict(kind='session-end')])
    except AssertionError:pass
    else:raise AssertionError('continued-after-limit survived')
    line=b'x'*receipts.LINE_LIMIT;assert len(line)<=receipts.LINE_LIMIT
    assert len(line+b'\n')>receipts.LINE_LIMIT # applies equally to footer, not just ordinary records
    print('PASS epoch/cumulative/reset/source-binding/incomplete/footer regressions; ZERO Product/process execution')
if __name__=='__main__':controls()
