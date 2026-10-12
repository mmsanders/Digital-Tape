"""Replay real captured provision writes at representative durability frontiers.

This checks ADR164 destructive provision outcomes, not WP10/media qualification
or an enlarged any-subset model. Payloads must be authenticated native capture.
"""
import hashlib
from pathlib import Path
from oracle import provision_order

def sha(data): return hashlib.sha256(data).hexdigest()

def payload(event):
    if 'data_hex' in event: data=bytes.fromhex(event['data_hex'])
    else:
        asset=Path(event['payload_path'])
        assert sha(asset.read_bytes())==event['payload_sha256']
        with asset.open('rb') as f:
            f.seek(event.get('payload_offset',0)); data=f.read(event['bytes'])
    assert len(data)==event['bytes']
    return data

def write(state,event):
    off=event['offset']; state[off:off+event['bytes']]=payload(event)

def replay_cuts(trace,baseline,new_mbr):
    provision_order(trace)
    assert len(baseline)==trace['target_bytes'] and len(new_mbr)==512
    assert baseline[:512] not in (bytes(512),new_mbr)
    durable=bytearray(baseline); pending=[]; phase=-1; rows=[]
    def emit(name,selected,allowed):
        state=bytearray(durable)
        for event in selected: write(state,event)
        sector=state[:512]
        outcome='unprovisioned' if sector==bytes(512) else 'new' if sector==new_mbr else 'old' if sector==baseline[:512] else 'invalid'
        assert outcome in allowed,(name,outcome,allowed)
        rows.append({'case':name,'outcome':outcome,'snapshot':bytes(state),'sha256':sha(state)})
    emit('before-first-write',[],{'old'})
    epoch=0
    for event in trace['events']:
        if event['kind']=='write':
            pending.append(event)
            if event['offset']==0: phase=0 if payload(event)==bytes(512) else 3
            elif event['offset']>=34816*512: phase=1
            else: phase=2
        elif event['kind']=='flush' and event['success']:
            allowed={'old','unprovisioned'} if phase==0 else {'unprovisioned','new'} if phase==3 else {'unprovisioned'}
            if pending:
                # Every actual successful flush epoch: none/all plus representative
                # first-/last-only persistence; no exhaustive 2^N claim.
                for label,subset in (('none',[]),('all',pending),('first',pending[:1]),('last',pending[-1:])):
                    emit('epoch-'+str(epoch)+'-'+label,subset,allowed)
                for w in pending: write(durable,w)
                pending=[]; epoch+=1
    assert not pending and durable[:512]==new_mbr
    emit('after-final-flush',[],{'new'})
    return rows
