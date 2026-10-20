"""Independent S4 predicates over actual test-driver snapshots, not a UI implementation.

Driver captures these observations from the real app/OS. A JSON assertion alone
does not establish real UI events/process attribution; raw evidence is mandatory.
"""
import math

def snapshot(s):
    assert s['window_count']==1
    assert s['state'] in ('Empty','Ready','Making','Done','Problem')
    assert s['lists']==[], 'no music/folder/card enumeration widgets'
    assert isinstance(s['label'],str) and len(s['label'].encode('utf-8'))<=32
    if s['state']=='Empty':assert not s['make_enabled']
    if s['state']=='Ready':
        assert s['make_enabled']==bool(s['label'] and s['check_current'] and s['check_success'] and s['pair_present'] and s['candidate_count']==1)
    if s['state'] in ('Done','Problem'):assert s['sentence'] and s['action'] in ('Make another','Start over')
    if s['state']=='Problem':assert s['show_details_copyable']
    if s['state']=='Making':
        assert s['progress_bar_count']==1
        assert s['cancel_enabled']==(not s['make_started'])
    assert not s['app_elevated']

def child(c):
    assert c['actual_executable_sha256']==c['bundled_executable_sha256']
    assert c['tool'] in ('ingest','tapectl cards','tapectl make')
    assert c['elevated']==(c['tool']=='tapectl make')
    if c['tool']=='ingest':
        assert c['length_seconds']==3600
        assert c['folders']==c['ordered_accepted_drops']
        assert c['dest_under_private_parent'] and c['control_under_private_parent']
        assert c['report_outside_dest_stage_sources_card']
    assert c['nonce_is_current'] and c['version_matches_bundled']

def progress(values):
    assert all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in values)
    assert all(a<=b for a,b in zip(values,values[1:]))

def atomic_drop(before,after,gesture):
    if any(x['kind']!='folder' for x in gesture):
        assert after['accepted_drops']==before['accepted_drops']
        assert after['child_count']==before['child_count']
        assert after['app_event']=='DROP_NOT_FOLDER'

def success(exit,pair,report_says_success):
    # Report data cannot authorize success; exact process and pair are authoritative.
    return exit==0 and pair
