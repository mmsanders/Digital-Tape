import copy,hashlib,json
from pathlib import Path
import cases,oracle,shell_oracle,parser_runner

def run():
    root=Path(__file__).parent;pins=json.loads((root/'pins.json').read_text())
    for name,want in pins['files'].items():assert hashlib.sha256((root/'spec'/name).read_bytes()).hexdigest()==want
    rows=cases.corpus();assert len({c['name'] for c in rows})==len(rows)
    valid=invalid=0
    for c in rows:
        r=oracle.parse(bytes.fromhex(c['raw_hex']),c['tool'],c['version'],c['nonce'],c['exit'],c['folders'])
        assert (r is not None)==c['valid'],c['name']
        assert list(oracle.message(c['tool'],c['exit'],r,c['pair']))==c['message'],c['name']
        if c['valid']:
            valid+=1
        else:invalid+=1
    base=dict(whole=True,removable_or_sd=True,nonvirtual=True,bytes=64000000000,not_system_boot_swap=True,mounts=[])
    assert oracle.candidate(base)=='candidate'
    discoveries=1
    for k in base:
        f=dict(base);f[k]=None;assert oracle.candidate(f)=='unprobed';discoveries+=1
    for k in ['whole','removable_or_sd','nonvirtual','not_system_boot_swap']:
        f=dict(base);f[k]=False;assert oracle.candidate(f)=='refused';discoveries+=1
    for n,want in [(2**37,'candidate'),(2**37+1,'refused')]:assert oracle.candidate(dict(base,bytes=n))==want;discoveries+=1
    p=dict(style='MBR',p1_type=14,p1_start=2048,p1_sectors=32768,p2_type=218,p2_start=34816,p2_end_bytes=base['bytes'],p3=False,p4=False)
    own=dict(base,mounts=[1],partition_view=p);assert oracle.candidate(own)=='candidate';discoveries+=1
    for k,v in p.items():
        q=dict(p);q[k]=None;assert oracle.candidate(dict(own,partition_view=q))=='unprobed';discoveries+=1
        q=dict(p);q[k]=not v if type(v) is bool else 'wrong' if isinstance(v,str) else v+1
        assert oracle.candidate(dict(own,partition_view=q))=='refused';discoveries+=1
    assert oracle.candidate(dict(own,mounts=[1,2]))=='refused';discoveries+=1
    # Discovery facts cannot distinguish a byte-invalid MBR from valid raw bytes.
    # Exact make rejection must be tested independently at the WP14 boundary.
    assert oracle.candidate(dict(own,raw_layout_valid=False))=='candidate';discoveries+=1
    assert oracle.label_append('é'*16,'x')=='é'*16
    assert oracle.label_append('','é'*16)=='é'*16
    assert oracle.label_append('','é'*17)==''
    assert oracle.label_append('a'*31,'💿')=='a'*31
    assert oracle.label_append('','💿'*8)=='💿'*8
    assert oracle.label_append('','\ud800')==''
    s=dict(window_count=1,state='Ready',lists=[],label='Music',make_enabled=True,check_current=True,check_success=True,pair_present=True,candidate_count=1,app_elevated=False)
    shell_oracle.snapshot(s);shell_controls=1
    for k,v in [('window_count',2),('lists',['a.wav']),('label','é'*17),('app_elevated',True),('candidate_count',2),('check_current',False),('pair_present',False)]:
        try:shell_oracle.snapshot(dict(s,**{k:v}))
        except AssertionError:pass
        else:raise AssertionError(('undetected shell mutant',k))
        shell_controls+=1
    for values in [[0,.4,.8,1],[]]:shell_oracle.progress(values);shell_controls+=1
    for values in [[0,.8,.4],[0,float('nan')],[1.1]]:
        try:shell_oracle.progress(values)
        except AssertionError:pass
        else:raise AssertionError('progress mutant')
        shell_controls+=1
    # Mount B failure does not prevent reading the independently mounted A side.
    oracle.findings([dict(f='MOUNT',side='B',result='TAPE_ERR_CRC'),dict(f='READ_ERROR',side='A',frame=0)])
    expected=[dict(valid=c['valid'],message=c['message']) for c in rows];parser_runner.compare(rows,expected)
    bad=copy.deepcopy(expected);i=next(i for i,c in enumerate(rows) if not c['valid'] and c['exit']!=0);bad[i]['message']=['protected','0/wrong.wav']
    try:parser_runner.compare(rows,bad)
    except AssertionError:pass
    else:raise AssertionError('invalid report selected an ID-specific message without detection')
    result=dict(scope='AUTHORED/SYNTHETIC; no Product acceptance',parser_inputs=len(rows),valid=valid,rejected=invalid,discovery_controls=discoveries,label_controls=6,shell_predicate_controls=shell_controls,invalid_message_selector_control='REJECTED after honest adapter baseline',closed_id_examples=sum(len(v) for t in oracle.IDS.values() for v in t.values()))
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':run()
