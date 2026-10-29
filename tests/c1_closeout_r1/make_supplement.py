"""Correct two verifier routing defects without modifying published package bytes."""
import copy, importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('c1_s3_immutable',ROOT/'wp15_cards_make_r1/oracle.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

def own_p1(r):
    f=r['facts'];events=old.device_events(r)
    assert f.get('mounted')==[1] and f.get('exact_layout') is True
    assert old.make_policy(f) is None
    opens=[i for i,e in enumerate(events) if e['op']=='open' and e.get('role')=='authorized']
    assert len(opens)==1
    unmounts=[e for e in events[:opens[0]] if e['op']=='unmount']
    assert len(unmounts)==1 and unmounts[0]['partition']==1 and unmounts[0].get('ok') is True
    # Validate everything except the one lawful unmount with the immutable judge.
    x=copy.deepcopy(r)
    prefix=True; filtered=[]
    for e in x['events']:
        if e['op']=='open' and e.get('role')=='authorized':prefix=False
        if prefix and e['op']=='unmount':continue
        filtered.append(e)
    x['events']=filtered
    return old.session(x)

def input_refusal(r):
    assert r['exit']==2
    terminal=old.report(r);assert terminal and terminal['id']=='LABEL_INVALID'
    assert not old.device_events(r), 'label admission must precede device work'
    assert r['foreign_before']==r['foreign_after']
    return 'input-refused-before-device'

def controls():
    def report():
        return ''.join(json.dumps(v,separators=(',',':'))+'\n' for v in [dict(t='start',tool='tapectl make',version='unit',nonce='0'*32),dict(t='end',exit=0)]).encode().hex()
    events=[dict(op='safety_pass',device=True),dict(op='unmount',device=True,partition=1,ok=True),dict(op='open',device=True,role='authorized',access='readwrite',session='s')]
    events += [dict(op='phase',device=True,session='s',phase=p,write_callback_null=p=='verify') for p in ('provision','load','commit','verify')]
    r=dict(facts=dict(whole=True,removable=True,bytes=64_000_000_000,holds_os=False,mounted=[1],exact_layout=True,erase_matches=True),events=events,exit=0,report_hex=report(),version='unit',nonce='0'*32,trace_complete=True,observer='compiled-test',positive_control_seen=True,equivalent_pair=True,foreign_before='same',foreign_after='same')
    own_p1(r)
    for field,value in [('partition',2),('partition',0),('ok',False)]:
        bad=copy.deepcopy(r);bad['events'][1][field]=value
        try:own_p1(bad)
        except AssertionError:pass
        else:raise AssertionError('foreign unmount survived')
    bad=copy.deepcopy(r);bad['events'].insert(1,dict(op='write',device=True))
    try:own_p1(bad)
    except AssertionError:pass
    else:raise AssertionError('early write survived')
    return 'lawful-own-p1 admitted; two foreign unmounts, failed unmount and early write rejected'

if __name__=='__main__':print(controls())
