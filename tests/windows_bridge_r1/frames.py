"""Pre-code563 exact optional snapshot-frame projection. No Product execution."""
import argparse, copy, json, re
from pathlib import Path

C=158760000
CASES=[
 dict(id='empty',events=['snapshot'],want=None),
 dict(id='checking',events=['begin-A','snapshot'],want=None),
 dict(id='success',events=['begin-A','current-success-88200','snapshot'],want=88200),
 dict(id='new-check-clears',events=['begin-A','current-success-88200','begin-B','snapshot'],want=None),
 dict(id='one-frame-over',events=['begin-A','current-valid-overage-1','snapshot'],want=C+1),
 dict(id='other-overage',events=['begin-A','current-valid-overage-8467200','snapshot'],want=C+8467200),
 dict(id='max-safe-overage',events=['begin-A','current-valid-overage-max-safe','snapshot'],want=9007199254740991),
 dict(id='bad-report',events=['begin-A','wrong-nonce-overage','snapshot'],want=None),
 dict(id='generic-failure',events=['begin-A','current-generic-failure','snapshot'],want=None),
 dict(id='missing-pair',events=['begin-A','exit0-no-pair-with-count','snapshot'],want=None),
 dict(id='progress-not-count',events=['begin-A','progress-100-percent','snapshot'],want=None),
 dict(id='stale',events=['begin-A','begin-B','A-success','snapshot'],want=None),
 dict(id='duplicate',events=['begin-A','current-success-88200','duplicate-overage','snapshot'],want=88200),
 dict(id='reset',events=['begin-A','current-success-88200','start-over','snapshot'],want=None),
 dict(id='cancelled',events=['begin-A','start-over','cancelled-A-success','snapshot'],want=None),
 dict(id='label-retains',events=['begin-A','current-success-88200','set-label','snapshot'],want=88200),
]

def qualify(r,head):
    assert re.fullmatch('[0-9a-f]{40}',head) and r['source_head']==head
    assert r['evidence_class']=='production bridge / controlled order' and r['raw_refs'] and r['adapter_ref']
    assert r['rows']=={c['id']:c['want'] for c in CASES}
    assert not r['inverse_bar_reconstruction'] and not r['progress_as_frames'] and not r['native_ui']
    assert r['actual_snapshot_refs'] and r['accepted_gate_refs'] and r['typed_outcome_refs']
    return 'ONLY current exact optional snapshot-frame projection; no native/INGEST acceptance'

def controls():
    good=dict(source_head='a'*40,evidence_class='production bridge / controlled order',raw_refs=['SYNTHETIC'],adapter_ref='SYNTHETIC',rows={c['id']:c['want'] for c in CASES},
              inverse_bar_reconstruction=False,progress_as_frames=False,native_ui=False,actual_snapshot_refs=['SYNTHETIC'],accepted_gate_refs=['SYNTHETIC'],typed_outcome_refs=['SYNTHETIC'])
    qualify(good,'a'*40)
    for key,value in [('success',2),('new-check-clears',88200),('one-frame-over',C),('other-overage',C+1),('stale',88200),('duplicate',C+1),('reset',88200),('missing-pair',88200),('max-safe-overage',9007199254740992)]:
        bad=copy.deepcopy(good);bad['rows'][key]=value
        try:qualify(bad,'a'*40)
        except AssertionError:continue
        raise AssertionError('exact-frame causal control survived: '+key)
    print('PASS exact-frame/current-result/reset/overage causal controls; ZERO Product/child/UI execution')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--emit',action='store_true');p.add_argument('--input',type=Path);p.add_argument('--candidate');a=p.parse_args()
    if a.emit:print(json.dumps(CASES,indent=2))
    elif a.input:print(qualify(json.loads(a.input.read_text(encoding='utf-8-sig')),a.candidate))
    else:controls()
