"""APP-1A S2/S3 independent observed-command predicates. No Product imports.
Facts/events are actual adapter observations; synthetic selftests confer no acceptance.
"""
import importlib.util,json,re
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'wp15_app1a_r1/oracle.py'
s=importlib.util.spec_from_file_location('app1a_existing_oracle',p);prior=importlib.util.module_from_spec(s);s.loader.exec_module(prior)

def device_events(r):
    assert r['trace_complete'] is True and r['observer'] in ('compiled-test','qualified-native')
    assert r['positive_control_seen'] is True,'unqualified absence'
    return [e for e in r['events'] if e.get('device') is True]

def no_device_mutation(events):
    for e in events:
        assert e['op'] not in ('write','unmount'),'device mutation'
        if e['op']=='open':assert e['access'] in ('none','read'),'write-mode open'

def cards(r):
    """Completed enumeration only. Exact raw layout never upgrades discovery safety."""
    assert r['exit']==0 and r['elevated'] is False
    no_device_mutation(device_events(r))
    expected={};unprobed=0
    for d in r['probes']:
        state=prior.candidate(d['facts'])
        if state=='unprobed':unprobed+=1
        elif state=='candidate':
            assert d['path'] not in expected,'repeated probe path'
            expected[d['path']]=d['facts']['bytes']
    raw=bytes.fromhex(r['stdout_hex']);assert raw.endswith(b'\n')
    rows=[json.loads(s,object_pairs_hook=prior.obj) for s in raw.decode('utf-8').splitlines()]
    assert rows and rows[-1]==dict(t='summary',offered=len(expected),unprobed=unprobed)
    assert type(rows[-1]['offered']) is int and type(rows[-1]['unprobed']) is int
    seen={}
    for v in rows[:-1]:
        assert set(v)=={'t','path','bytes'} and v['t']=='card'
        assert type(v['bytes']) is int and v['path'] not in seen
        seen[v['path']]=v['bytes']
    assert seen==expected,'wrong/refused/unknown disclosure'
    return {'offered':len(seen),'unprobed':unprobed}

def make_policy(f):
    """WP14 ordered known test facts; missing facts use its refusing seam defaults."""
    if not f.get('whole',False):return 'REFUSE_NOT_WHOLE_DEVICE'
    if not (f.get('removable',False) or f.get('sd_bus',False)) or f.get('virtual',False):return 'REFUSE_NOT_REMOVABLE'
    if f.get('bytes',0)>2**37:return 'REFUSE_TOO_LARGE'
    if f.get('holds_os',True):return 'REFUSE_SYSTEM_DISK'
    mounts=f.get('mounted',[])
    if mounts and not (mounts==[1] and f.get('exact_layout',False)):return 'REFUSE_FOREIGN_MOUNT'
    if mounts==[1] and f.get('exact_layout',False) and f.get('unmount_failed',False):return 'REFUSE_FOREIGN_MOUNT'
    if not f.get('erase_matches',False):return 'REFUSE_ERASE_NOT_CONFIRMED'
    return None

def report(r):
    v=prior.parse(bytes.fromhex(r['report_hex']),'tapectl make',r['version'],r['nonce'],r['exit'])
    assert v is not None,'unusable make report'
    return v['refusal']

def session(r):
    """Actual open/bind/phase journal, separate from optional report progress."""
    ev=device_events(r);expected=make_policy(r['facts']);terminal=report(r)
    if expected:
        assert r['exit']==3 and terminal and terminal['id']==expected
        own_failure=r['facts'].get('unmount_failed') and r['facts'].get('exact_layout') and r['facts'].get('mounted')==[1]
        if own_failure:
            assert terminal.get('unmount_failed') is True
            assert all(e.get('partition')==1 for e in ev if e['op']=='unmount')
            no_device_mutation([e for e in ev if e['op']!='unmount'])
        else:no_device_mutation(ev)
        assert not any(e['op']=='open' and e.get('role')=='authorized' for e in ev)
        assert r['foreign_before']==r['foreign_after'],'foreign mutation on refusal'
        return 'refused'
    opens=[e for e in ev if e['op']=='open' and e.get('role')=='authorized']
    assert len(opens)==1,'one retained authorized session required'
    authorized=opens[0];sid=authorized['session'];assert authorized['access']=='readwrite'
    pos=ev.index(authorized)
    no_device_mutation(ev[:pos])
    assert any(e['op']=='safety_pass' for e in ev[:pos]),'write session before safety'
    changed=False;phases=[];verify_null=False
    for e in ev[pos+1:]:
        if e['op']=='open':raise AssertionError('reopened path/session')
        if e['op']=='close':continue
        assert e['session']==sid,'different session'
        assert not changed,'continued after detected media change'
        if e['op']=='media_change':
            assert e['reason'] in ('removed','changed','disappeared')
            changed=True;assert r['exit']==1 and terminal and terminal['id']=='CARD_CHANGED'
            assert terminal['phase']==e['phase'] and terminal['os_error']==e['os_error']
            assert not r['stdout_after_change_hex'],'OK/findings after detected change'
        elif e['op']=='phase':
            phase=e['phase'];assert phase in ('provision','load','commit','verify')
            phases.append(phase)
            if phase=='verify':assert e['write_callback_null'] is True;verify_null=True
        elif e['op']=='write':assert not verify_null,'write callback during verify'
        elif e['op'] in ('read','flush'):pass
        elif e['op']=='bind':
            if e['phase']=='verify':assert e['write_callback_null'] is True;verify_null=True
        else:raise AssertionError('unknown journal operation')
    if r['exit']==0:
        assert terminal is None and not changed
        assert phases==['provision','load','commit','verify'] and verify_null
        assert r['equivalent_pair'] is True,'independent byte/output comparison missing'
    return 'changed' if changed else 'observed'

def equivalence(make_stdout,stage_stdout,make_exit,stage_exits,make_hash,standalone_hash):
    # Extract actual caller-owned identity; baseline provision reuses it via existing
    # --uuid/--epoch. This normalizes entropy, not permitted outcome/data bytes.
    m=re.match(rb'uuid ([0-9a-f]{32})\nepoch ([0-9]+)\n',make_stdout);assert m
    assert make_stdout==m.group(0)+b''.join(stage_stdout)
    assert len(stage_exits)==len(stage_stdout)==3
    first=0
    for i,e in enumerate(stage_exits):
        if first:assert e is None and stage_stdout[i]==b'', 'ran after failed stage'
        else:
            assert type(e) is int
            if e:first=e
    assert make_exit==first and make_hash==standalone_hash
    return (m.group(1).decode(),int(m.group(2)))

def parent_binding(r):
    """Elevated report/cleanup substitution boundary, not a new ingest policy."""
    assert r['foreign_before']==r['foreign_after']
    if r['substituted']:
        assert r['exit']!=0 and not r['device_work']
        assert not r['foreign_leaf_created'] and not r['foreign_deleted']
    else:assert r['exclusive_leaf'] and r['parent_identity_bound']
