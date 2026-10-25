"""318 pre-code app poll/report/card-line expectations. No Product/device imports."""
import argparse,copy,importlib.util,json,re
from pathlib import Path,PureWindowsPath
path=Path(__file__).resolve().parents[1]/'wp15_app1a_r1/oracle.py'
spec=importlib.util.spec_from_file_location('accepted_app1a',path)
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
OLD='82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9'
ENGINE='d96b4245e04d74078f8938744b1394c3018516f7'
NONCE='a'*32;VERSION='tapectl-wp15-s2+'+'b'*12
GENERIC='Something went wrong. Nothing else on your computer was changed.'
SCHEDULES={
 'regular':dict(ticks=[0,1999,2000,3000,4000,5000],terminal_before=[3000],making=[],stopped=[],started=[2000,5000]),
 'slow':dict(ticks=[2000,4000,6000,7000,8000,9000],terminal_before=[7000],making=[],stopped=[],started=[2000,9000]),
 'making':dict(ticks=[2000,4000,6000],terminal_before=[],making=[2000,4000],stopped=[],started=[6000]),
 'stopped':dict(ticks=[2000,4000],terminal_before=[],making=[],stopped=[2000,4000],started=[])}
def lines(rows):return ''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows)
def report(exit=0,nonce=NONCE,version=VERSION,refusal=False):
    rows=[dict(t='start',tool='tapectl cards',version=version,nonce=nonce)]
    if refusal:rows.append(dict(t='refusal',id='CARDS_ENUM_UNAVAILABLE',subject=None,os_error='MODEL_QUERY_ERROR'))
    return lines(rows+[dict(t='end',exit=exit)])
def output(sizes=(),unprobed=0):return lines([dict(t='card',path='MODEL-DISK-'+str(i),bytes=n) for i,n in enumerate(sizes)]+[dict(t='summary',offered=len(sizes),unprobed=unprobed)])
CASES=[
 dict(id='zero',exit=0,stdout=output(),report=report()),
 dict(id='one64',exit=0,stdout=output([64000000000]),report=report()),
 dict(id='round-up',exit=0,stdout=output([63600000000]),report=report()),
 dict(id='round-down',exit=0,stdout=output([64400000000]),report=report()),
 dict(id='binary-limit-decimal-display',exit=0,stdout=output([2**37]),report=report()),
 dict(id='multiple',exit=0,stdout=output([64000000000,32000000000]),report=report()),
 dict(id='zero-unprobed',exit=0,stdout=output([],3),report=report()),
 dict(id='one-plus-unprobed',exit=0,stdout=output([64000000000],2),report=report()),
 dict(id='enum-unavailable',exit=1,stdout=output([64000000000]),report=report(1,refusal=True)),
 dict(id='wrong-nonce-failure',exit=1,stdout=output([64000000000]),report=report(1,nonce='c'*32,refusal=True)),
 dict(id='wrong-version-failure',exit=1,stdout='',report=report(1,version='wrong',refusal=True)),
 dict(id='partial-report-failure',exit=1,stdout='',report=report(1,refusal=True).rstrip('\n')),
 dict(id='unknown-report-id',exit=1,stdout='',report=report(1,refusal=True).replace('CARDS_ENUM_UNAVAILABLE','UNISSUED_ID')),
 dict(id='valid-stdout-missing-report',exit=0,stdout=output([64000000000]),report=''),
 dict(id='valid-stdout-wrong-nonce',exit=0,stdout=output([64000000000]),report=report(nonce='c'*32)),
 dict(id='missing-summary',exit=0,stdout=lines([dict(t='card',path='MODEL-DISK',bytes=64000000000)]),report=report()),
 dict(id='summary-mismatch',exit=0,stdout=output([64000000000]).replace('"offered":1','"offered":2'),report=report()),
 dict(id='partial-summary',exit=0,stdout=output([64000000000]).rstrip('\n'),report=report()),
 dict(id='duplicate-path',exit=0,stdout=output([64000000000,32000000000]).replace('MODEL-DISK-1','MODEL-DISK-0'),report=report()),
 dict(id='invalid-capacity',exit=0,stdout=output([True]),report=report()),
 dict(id='unknown-output-record',exit=0,stdout=lines([dict(t='refused',path='PRIVATE-REFUSED-DISK')])+output(),report=report()),
 dict(id='usage-stale-output',exit=2,stdout=output([64000000000]),report=''),
 dict(id='no-child-exit',exit=None,stdout=output([64000000000]),report=''),
]
def stdout(s):
    assert s and s.endswith('\n')
    rows=[json.loads(x,object_pairs_hook=prior.obj) for x in s.splitlines()]
    summary=rows[-1];assert list(summary)==['t','offered','unprobed'] and summary['t']=='summary'
    prior.integer(summary['offered']);prior.integer(summary['unprobed'])
    cards=[];paths=set()
    for r in rows[:-1]:
        assert list(r)==['t','path','bytes'] and r['t']=='card'
        assert isinstance(r['path'],str) and r['path'] and '\0' not in r['path'] and r['path'] not in paths
        paths.add(r['path']);prior.integer(r['bytes']);assert r['bytes']>0
        cards.append(r['bytes'])
    assert len(cards)==summary['offered']
    return cards,summary['unprobed']
def expected(c):
    parsed=prior.parse(c['report'].encode(),'tapectl cards',VERSION,NONCE,c['exit']) if type(c['exit']) is int else None
    selected=parsed['refusal']['id'] if parsed and parsed['refusal'] else None
    if c['exit']!=0:return dict(line=GENERIC,offered=None,unprobed=None,id_specific=selected,make_enabled=False)
    if parsed is None:return dict(line=GENERIC,offered=None,unprobed=None,id_specific=None,make_enabled=False)
    try:cards,unprobed=stdout(c['stdout'])
    except (AssertionError,ValueError,KeyError,IndexError,TypeError):return dict(line=GENERIC,offered=None,unprobed=None,id_specific=None,make_enabled=False)
    # Actual exit remains unchanged; NEW discovery hint also requires current report binding.
    line='Put a card in.' if not cards else ('Leave just one card in the computer.' if len(cards)>1 else 'Card ready ('+str((cards[0]+500000000)//1000000000)+' GB).')
    return dict(line=line,offered=len(cards),unprobed=unprobed,id_specific=None,make_enabled=False)
def below(p,root):return PureWindowsPath(p).is_absolute() and PureWindowsPath(root) in PureWindowsPath(p).parents
def qualify(r,head):
    assert re.fullmatch('[0-9a-f]{40}',head) and r['source_head']==head
    assert r['evidence_class']=='production discovery integration / controlled order' and r['raw_refs'] and r['adapter_ref']
    assert r['rows']=={c['id']:expected(c) for c in CASES}
    assert not r['native_ui'] and not r['live_enumeration'] and not r['shipping_fake_switch'] and not r['stderr_selected_outcome']
    q=r['child'];assert re.fullmatch('[0-9a-f]{64}',q['sha256']) and q['sha256']!=OLD
    assert re.fullmatch('[0-9a-f]{40}',q['source']) and q['version']=='tapectl-wp15-s2+'+q['source'][:12]
    assert q['engine_tree']==ENGINE and q['test_build'] is False and q['build_refs'] and q['accepted_source_crosswalk']
    req=r['request'];assert req['shell'] is False and req['elevated'] is False
    assert PureWindowsPath(req['exe']).parent==PureWindowsPath(req['executable_dir']) and PureWindowsPath(req['exe']).is_absolute()
    argv=req['argv'];assert len(argv)==6 and argv[:2]==[req['exe'],'cards']
    for flag,value in [('--report',req['report']),('--report-nonce',req['nonce'])]:assert argv.count(flag)==1 and argv[argv.index(flag)+1]==value
    assert re.fullmatch('[0-9a-f]{32}',req['nonce']) and below(req['job'],req['private_root']) and below(req['report'],req['job'])
    assert req['cwd']==req['job'] and req['nonce_ref'] and req['actual_command_ref']
    t=r['poll'];assert t['nominal_interval_ms']==2000 and t['max_concurrent']==1 and t['timeout_ms']==10000
    assert t['busy_tick_new_workers']==0 and t['making_tick_new_workers']==0 and t['stopped_tick_new_workers']==0
    assert t['stale_emissions']==t['duplicate_emissions']==0 and not t['ui_waits_for_child']
    assert t['timeout_order']==['invalidate-current','cancel','child-terminal','remove-owned-job']
    assert t['shutdown_order']==['stop-polls','invalidate-current','cancel','child-terminal','remove-owned-job']
    assert t['replacement_order']==['old-child-terminal','old-owned-cleanup','new-worker-start']
    assert t['current_result_refs'] and t['timer_worker_refs'] and t['actual_trace_refs']
    assert t['schedules']=={k:v['started'] for k,v in SCHEDULES.items()}
    assert len(t['request_nonces'])>=3 and len(set(t['request_nonces']))==len(t['request_nonces'])
    assert all(re.fullmatch('[0-9a-f]{32}',n) for n in t['request_nonces'])
    assert len(t['request_reports'])==len(set(t['request_reports']))==len(t['request_nonces'])
    assert r['valid_music_label_one_hint_make_enabled'] is False
    assert r['displayed_paths']==r['lists']==r['external_cleanup_calls']==[] and not r['app_device_calls'] and not r['make_or_elevation_calls']
    assert r['source_before']==r['source_after'] and r['foreign_before']==r['foreign_after']
    assert r['accepted_parser_reuse_refs'] and r['card_line_actual_render_refs'] and r['failure_clears_hint']
    return 'ONLY covered discovery integration component; no live metadata/native/G1/S3/Make/fullAPP clearance'
def fixture():
    private=r'C:\MODEL\appdata';job=private+r'\jobs\poll';exe=r'C:\MODEL\bundle\tapectl.exe'
    return dict(source_head='a'*40,evidence_class='production discovery integration / controlled order',raw_refs=['SYNTHETIC'],adapter_ref='SYNTHETIC',rows={c['id']:expected(c) for c in CASES},native_ui=False,live_enumeration=False,shipping_fake_switch=False,stderr_selected_outcome=False,
      child=dict(sha256='1'*64,source='b'*40,version=VERSION,engine_tree=ENGINE,test_build=False,build_refs=['SYNTHETIC'],accepted_source_crosswalk=['SYNTHETIC']),
      request=dict(shell=False,elevated=False,exe=exe,executable_dir=r'C:\MODEL\bundle',argv=[exe,'cards','--report',job+r'\control\report.jsonl','--report-nonce',NONCE],report=job+r'\control\report.jsonl',nonce=NONCE,private_root=private,job=job,cwd=job,nonce_ref='SYNTHETIC',actual_command_ref='SYNTHETIC'),
      poll=dict(nominal_interval_ms=2000,max_concurrent=1,timeout_ms=10000,busy_tick_new_workers=0,making_tick_new_workers=0,stopped_tick_new_workers=0,stale_emissions=0,duplicate_emissions=0,ui_waits_for_child=False,
       timeout_order=['invalidate-current','cancel','child-terminal','remove-owned-job'],shutdown_order=['stop-polls','invalidate-current','cancel','child-terminal','remove-owned-job'],replacement_order=['old-child-terminal','old-owned-cleanup','new-worker-start'],current_result_refs=['SYNTHETIC'],timer_worker_refs=['SYNTHETIC'],actual_trace_refs=['SYNTHETIC'],schedules={k:v['started'] for k,v in SCHEDULES.items()},request_nonces=['1'*32,'2'*32,'3'*32],request_reports=['SYNTHETIC1','SYNTHETIC2','SYNTHETIC3']),
      valid_music_label_one_hint_make_enabled=False,displayed_paths=[],lists=[],external_cleanup_calls=[],app_device_calls=False,make_or_elevation_calls=False,source_before='s',source_after='s',foreign_before='f',foreign_after='f',accepted_parser_reuse_refs=['SYNTHETIC'],card_line_actual_render_refs=['SYNTHETIC'],failure_clears_hint=True)
def controls():
    r=fixture();qualify(r,'a'*40)
    for change in [lambda q:q['rows']['round-up'].update(line='Card ready (63 GB).'),lambda q:q['rows']['enum-unavailable'].update(offered=1),lambda q:q['child'].update(sha256=OLD),lambda q:q['poll'].update(max_concurrent=2),lambda q:q['poll'].update(stale_emissions=1),lambda q:q['poll'].update(shutdown_order=['remove-owned-job','cancel']),lambda q:q['poll'].update(request_nonces=['1'*32]*3),lambda q:q['poll']['schedules'].update(slow=[2000,4000]),lambda q:q.update(valid_music_label_one_hint_make_enabled=True),lambda q:q.update(displayed_paths=['PRIVATE-DISK']),lambda q:q.update(app_device_calls=True),lambda q:q['request'].update(shell=True),lambda q:q.update(shipping_fake_switch=True),lambda q:q.update(stderr_selected_outcome=True)]:
        bad=copy.deepcopy(r);change(bad)
        try:qualify(bad,'a'*40)
        except AssertionError:continue
        raise AssertionError('discovery causal control survived')
    assert expected(CASES[13])['offered'] is None and expected(CASES[14])['offered'] is None
    assert expected(CASES[9])['id_specific'] is None
    print('PASS discovery integration/exit/report/poll/rounding/disabled-Make causal controls; ZERO Product/device/UI execution')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--emit',action='store_true');p.add_argument('--input',type=Path);p.add_argument('--candidate');a=p.parse_args()
    if a.emit:print(json.dumps(dict(cases=CASES,schedules=SCHEDULES,nonce=NONCE,model_report_version=VERSION,events=['ticks while idle/busy/Making/stopped','current/stale/duplicate completion','timeout/terminal/cleanup/replacement','shutdown'],runtime_admission='NONE; exact new child and live metadata source/pin/command preflight pending'),indent=2))
    elif a.input:print(qualify(json.loads(a.input.read_text(encoding='utf-8-sig')),a.candidate))
    else:controls()
