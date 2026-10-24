"""Independent component expectations; synthetic outcomes are never real child facts."""
import argparse
import copy
import importlib.util
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('jobs_oracle',ROOT/'wp15_app1a_r1/oracle.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
VERSION='0.1.1 INGEST-1 arithmetic-profile INGEST1-AP4'
NONCE='a'*32


def report(exit=0,refusal=None,nonce=NONCE,version=VERSION):
    rows=[dict(t='start',tool='ingest',version=version,nonce=nonce)]
    if refusal:rows.append(dict(t='refusal',id=refusal,subject='0'))
    rows.append(dict(t='end',exit=exit))
    return '\n'.join(json.dumps(r,separators=(',',':')) for r in rows)+'\n'


def expected(case):
    parsed=oracle.parse(case['report'].encode(),'ingest',VERSION,NONCE,case['exit'],['Music'])
    category=oracle.message('ingest',case['exit'],parsed,case['pair'])[0]
    return dict(view='Ready' if case['exit']==0 and case['pair'] else 'Problem',category=category,
                total_frames=88200 if case['exit']==0 and case['pair'] else None,
                details=case['stderr'],make_enabled=False)


CASES=[
    dict(id='positive',exit=0,pair=True,report=report(),stderr=''),
    dict(id='missing-pair',exit=0,pair=False,report=report(),stderr='pair missing'),
    dict(id='nonzero-with-pair-and-stale-success',exit=1,pair=True,report=report(),stderr='IO_FOLDER'),
    dict(id='empty-folder',exit=2,pair=False,report=report(2,'FOLDER_EMPTY'),stderr='actual details'),
    dict(id='stderr-is-not-id',exit=1,pair=False,report='',stderr='FOLDER_EMPTY'),
    dict(id='wrong-nonce-paired-exit0',exit=0,pair=True,report=report(nonce='b'*32),stderr='warning'),
    dict(id='wrong-version-nonzero',exit=2,pair=False,report=report(2,'FOLDER_EMPTY',version='wrong'),stderr='details'),
    dict(id='partial-final-line',exit=2,pair=False,report=report(2,'FOLDER_EMPTY').rsplit('\n',2)[0]+'\n{"t":"end"',stderr='details'),
]


def deliveries(events):
    generation=0;active=None;state=dict(view='Empty',category=None,total_frames=None,details='',make_enabled=False)
    outputs=[]
    for e in events:
        if e['op']=='begin':
            generation+=1;active=e['job'];state=dict(view='Checking',category=None,total_frames=None,details='',make_enabled=False)
        elif e['op']=='start-over':
            generation+=1;active=None;state=dict(view='Empty',category=None,total_frames=None,details='',make_enabled=False)
        elif e['op']=='complete':
            if e['generation']==generation and e['job']==active and not e.get('cancelled'):
                state=expected(CASES[e['case']]);active=None
        else:raise AssertionError('unissued operation')
        outputs.append(dict(generation=generation,active_job=active,visible=copy.deepcopy(state)))
    return outputs


SEQUENCES={
    'new-drop-supersedes': [dict(op='begin',job='A'),dict(op='begin',job='B'),
        dict(op='complete',job='A',generation=1,case=0),dict(op='complete',job='B',generation=2,case=3)],
    'start-over-supersedes': [dict(op='begin',job='A'),dict(op='start-over'),dict(op='complete',job='A',generation=1,case=0)],
    'wrong-job-same-generation': [dict(op='begin',job='A'),dict(op='complete',job='other',generation=1,case=0),dict(op='complete',job='A',generation=1,case=0)],
    'duplicate-completion': [dict(op='begin',job='A'),dict(op='complete',job='A',generation=1,case=0),dict(op='complete',job='A',generation=1,case=3)],
    'cancelled-stale': [dict(op='begin',job='A'),dict(op='start-over'),dict(op='complete',job='A',generation=1,case=0,cancelled=True)],
}


def qualify(r,candidate):
    assert re.fullmatch('[0-9a-f]{40}',candidate)
    assert r['source_head']==candidate and r['scope']=='backend lifecycle only' and r['raw_refs']
    assert not r['elevated'] and not r['shipping_test_switch'] and not r['make_enabled']
    assert r['state_rows']=={c['id']:expected(c) for c in CASES}
    assert r['delivery_rows']=={name:deliveries(events) for name,events in SEQUENCES.items()}
    own=r['ordinary_job_files']
    assert own['exclusive_second_create_refused'] and own['collision_bytes_unchanged']
    assert own['control_out_distinct'] and own['under_app_private_root'] and own['report_outside_sources_dest_stage']
    assert own['own_completed_job_removed'] and own['own_superseded_job_removed']
    assert own['foreign_sibling_unchanged'] and own['source_bytes_unchanged'] and own['sentinel_bytes_unchanged']
    assert own['raw_refs'] and own['no_external_cleanup']
    real=r['real_runner']
    assert real['pinned_original_s1'] and real['current_nonce_version_exit_end_bound'] and real['actual_source_runner']
    assert real['binary_sha256']=='3895f3f356c91b8a9fe870c33694da64bf2765df308bef118d657c1be4bb9a20'
    assert real['child_source']=='35b23cacae886d9b3693b7104f581d8646ea5667' and real['report_version']==VERSION
    assert real['p0_exit']==0 and real['p0_exact_pair_frames']==88200 and real['p1_exit']==2 and real['p1_id']=='FOLDER_EMPTY'
    assert real['p1_no_dest'] and real['raw_refs'] and not real['fake_child']
    return 'ONLY actual raw-reviewed backend lifecycle and real runner scope; no UI/native acceptance'


def selftest():
    expected_rows=[expected(c) for c in CASES]
    assert expected_rows[0]['view']=='Ready' and expected_rows[1]['view']=='Problem'
    assert expected_rows[2]['category']=='generic' and expected_rows[4]['category']=='generic'
    assert expected_rows[5]['view']=='Ready' and expected_rows[6]['category']=='generic' and expected_rows[7]['category']=='generic'
    for name,events in SEQUENCES.items():
        rows=deliveries(events)
        if name=='new-drop-supersedes':assert rows[1]['visible']==rows[2]['visible'] and rows[-1]['visible']['category']=='folder-nonmusic'
        elif name in ['start-over-supersedes','cancelled-stale']:assert rows[-1]['visible']['view']=='Empty'
        elif name=='wrong-job-same-generation':assert rows[1]['visible']['view']=='Checking' and rows[-1]['visible']['view']=='Ready'
        else:assert rows[-1]['visible']==rows[-2]['visible']
    # Causal neighbouring traces demonstrate precisely what stale/duplicate gates detect.
    wrong=copy.deepcopy(SEQUENCES['new-drop-supersedes']);wrong[2]['job']='B';wrong[2]['generation']=2
    assert deliveries(wrong)[2]['visible']!=deliveries(SEQUENCES['new-drop-supersedes'])[2]['visible']
    no_pair=copy.deepcopy(CASES[0]);no_pair['pair']=False;assert expected(no_pair)!=expected(CASES[0])
    wrong_exit=copy.deepcopy(CASES[0]);wrong_exit['exit']=1;assert expected(wrong_exit)!=expected(CASES[0])
    print('PASS independent lifecycle/report/exit/pair and stale/duplicate causal models; ZERO Product/child/UI execution')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path);p.add_argument('--candidate');p.add_argument('--emit',action='store_true');a=p.parse_args()
    if a.emit:print(json.dumps(dict(state_cases=CASES,sequences=SEQUENCES),indent=2))
    elif a.input:print(qualify(json.loads(a.input.read_text()),a.candidate))
    else:selftest()
