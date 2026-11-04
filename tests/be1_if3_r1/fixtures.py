"""IF/3-only, independently authored saved-evidence cases. All bytes synthetic."""
import copy
import json
from pathlib import Path
from support import previous as old


def catalog(refs):
    result=[]
    def add(name,edit=lambda m,f:None,state='NOT_RUN',codes=(),exit=0,physical=False,criterion='F5',overall=None):
        m,f=old.base(refs);m['session']['id']='IF3-SYNTHETIC-'+name
        old.add_f5(m,f);edit(m,f)
        result.append(dict(name=name,manifest=m,payloads=f,expected=dict(criterion=criterion,state=state,
          codes=list(codes),exit=exit,physical_run=physical,complete=False,
          overall=overall or ('INVALID' if exit==2 else 'MISMATCH' if exit==1 else 'NOT_RUN'))))
    def f5(m):return next(o for o in m['observations'] if o['criterion']=='F5')
    add('missing-witness-only',codes=['f5_witness_missing'])
    add('no-transcript',lambda m,f:f5(m).update(transcript=None),codes=['f5_transcript_missing','f5_witness_missing'])
    add('no-card',lambda m,f:f5(m).update(card_before=None,card_after=None),codes=['f5_card_identity_missing','f5_witness_missing'])
    add('no-verify',lambda m,f:f5(m).update(verify_command=None,verify_stdout=None,verify_exit=None),codes=['f5_verify_missing','f5_witness_missing'])
    for field,value in [('manufacturer','DIFFERENT'),('part_number','OTHER'),('capacity_bytes',64000000001),('revision','OTHER'),('cid','a'*32)]:
        add('card-change-'+field,lambda m,f,field=field,value=value:f5(m)['card_after'].update({field:value}),
            state='MISMATCH',codes=['f5_card_identity_changed','f5_witness_missing'],exit=1)
    add('unknown-cid-is-not-qualified',codes=['f5_cid_unknown','f5_witness_missing'])
    findings=[b'MBR_LAYOUT\n',b'PARTITION_TYPE\n',b'PARTITION_TRUNCATED\n',b'MOUNT BAD_MAGIC\n',
              b'NEEDS_REPAIR\n',b'SIDE_B_DEGRADED\n',b'READ_ERROR SIDE A FRAME 2\n']
    for i,raw in enumerate(findings):
        for rc in (0,1):
            add(f'verify-finding-{i}-exit{rc}',lambda m,f,raw=raw,rc=rc:(f.update({'verify.txt':raw}),f5(m).update(verify_exit=rc)),
                state='MISMATCH',codes=['f5_verify_findings','f5_witness_missing'],exit=1)
    add('verify-OK-nonzero',lambda m,f:f5(m).update(verify_exit=1),state='MISMATCH',codes=['f5_verify_findings','f5_witness_missing'],exit=1)
    add('verify-malformed-no-witness',lambda m,f:f.update({'verify.txt':b'probably fine\n'}),state='INVALID',codes=['f5_verify_malformed','f5_witness_missing'],exit=2)
    add('failed-verify-no-transcript',lambda m,f:(f5(m).update(transcript=None,verify_exit=1)),state='MISMATCH',codes=['f5_transcript_missing','f5_verify_findings','f5_witness_missing'],exit=1)
    add('failed-verify-no-card',lambda m,f:f5(m).update(card_before=None,verify_exit=1),state='MISMATCH',codes=['f5_card_identity_missing','f5_verify_findings','f5_witness_missing'],exit=1)
    add('malformed-transcript-plus-verify-fail',lambda m,f:(f.update({'controls.serial':b'UNKNOWN RAW LINE\n'}),f5(m).update(verify_exit=1)),
        state='INVALID',codes=['line_unknown','f5_verify_findings','f5_witness_missing'],exit=2)
    add('truncated-transcript-plus-verify-fail',lambda m,f:(f.update({'controls.serial':b'PLAY 0'}),f5(m).update(verify_exit=1)),
        state='INVALID',codes=['transcript_truncated','f5_verify_findings','f5_witness_missing'],exit=2)
    add('play-failed-with-missing-sequence',lambda m,f:f.update({'controls.serial':b'PLAY FAILED -1\n'}),
        state='MISMATCH',codes=['f5_play_failed','f5_sequence_missing','f5_witness_missing'],exit=1)
    add('render-failed-with-missing-verify',lambda m,f:(f.update({'controls.serial':f['controls.serial']+b'RENDER FAILED\n'}),f5(m).update(verify_command=None,verify_stdout=None,verify_exit=None)),
        state='MISMATCH',codes=['f5_play_failed','f5_verify_missing','f5_witness_missing'],exit=1)
    def markers(m,f,present=('play_stop','removal','verify')):
        # Deliberately self-reported markers exercise parsing, never a real witness.
        m['session']['kind']='physical'
        f5(m).update(provenance='actual',witness=dict(name='SIMULATED-NOT-MICHAEL',
          statement='Parser fixture only; no hardware or witnessing occurred',present_for=list(present)))
    add('self-reported-marker-f5-consistency',markers,state='CONSISTENT',codes=['f5_cid_unknown'],physical=True)
    for missing in ('play_stop','removal','verify'):
        add('witness-marker-missing-'+missing,lambda m,f,missing=missing:markers(m,f,[x for x in ('play_stop','removal','verify') if x!=missing]),
            codes=['f5_witness_missing'],physical=True)
    add('witness-marker-missing-verify-failed',lambda m,f:(markers(m,f,['play_stop']),f5(m).update(verify_exit=1)),
        state='MISMATCH',codes=['f5_witness_missing','f5_verify_findings'],exit=1,physical=True)
    add('simulation-cannot-have-witness',lambda m,f:f5(m).update(witness=dict(name='SIMULATED',statement='not a witness',present_for=['play_stop','removal','verify'])),
        state='INVALID',codes=['witness_on_simulation'],exit=2,criterion=None)
    def retry(m,f,invalid=False,requested=False):
        o=m['observations'][0];raw=f[o['transcript']]
        later=copy.deepcopy(o);later.update(id='retry-good',sequence=20,transcript='retry-good.serial')
        f[later['transcript']]=raw
        f[o['transcript']]=raw.rstrip(b'\r\n') if invalid else raw.replace(raw.split()[1],b'0'*64)
        o.update(superseded_by=later['id'],supersede_reason='Retain the failed simulated attempt')
        m['observations'].append(later)
        if requested:m['requested']=['F2']
    for invalid in (False,True):
        for unrequested in (False,True):
            name=f'retry-retains-{invalid}-{unrequested}'
            add(name,lambda m,f,invalid=invalid,unrequested=unrequested:retry(m,f,invalid,unrequested),criterion='F1',state='CONSISTENT',
                codes=['transcript_truncated' if invalid else 'f1_digest_mismatch'],exit=2 if invalid else 1)
            result[-1]['expected']['retained']=[dict(id=old.CASES[0],state='INVALID' if invalid else 'MISMATCH')]
    def chain(m,f):
        retry(m,f,True)
        second=m['observations'][-1];third=copy.deepcopy(second)
        third.update(id='retry-third',sequence=21,transcript='retry-third.serial')
        f[third['transcript']]=f[second['transcript']]
        raw=f[second['transcript']];f[second['transcript']]=raw.replace(raw.split()[1],b'0'*64)
        second.update(superseded_by='retry-third',supersede_reason='Second failure retained')
        m['observations'].append(third)
    add('retry-chain-worst-retained-error',chain,criterion='F1',state='CONSISTENT',codes=['transcript_truncated','f1_digest_mismatch'],exit=2)
    result[-1]['expected']['retained']=[dict(id=old.CASES[0],state='INVALID'),dict(id='retry-good',state='MISMATCH')]
    def retry_f5(m,f):
        o=f5(m);later=copy.deepcopy(o);later.update(id='f5-retry',sequence=41,transcript='controls-retry.serial')
        f['controls-retry.serial']=f['controls.serial'];o.update(verify_exit=1,superseded_by='f5-retry',supersede_reason='Retained verify failure')
        m['observations'].append(later)
    add('f5-retry-no-witness-still-retains-failure',retry_f5,codes=['f5_verify_findings','f5_witness_missing'],exit=1)
    result[-1]['expected']['retained']=[dict(id='f5',state='MISMATCH')]
    def retry_f2(m,f):
        old.add_f2(m,f);o=m['observations'][-1]
        later=copy.deepcopy(o);later.update(id='f2-retry',sequence=51,transcript='info-retry.serial')
        f[later['transcript']]=f['info.serial'];f['info.serial']=f['info.serial'].replace(b'water 8192',b'water 8196')
        o.update(superseded_by='f2-retry',supersede_reason='Retained stack excess')
        m['observations'].append(later)
    add('f2-retry-retains-stack-excess',retry_f2,criterion='F2',state='CONSISTENT',codes=['f2_stack_exceeds'],exit=1)
    result[-1]['expected']['retained']=[dict(id='f2',state='MISMATCH')]
    def image(m,f,path='firmware.hex',raw=b'V382 SIMULATED FIRMWARE\n'):
        f[path]=raw
    add('firmware-path-positive',image,criterion='F1',state='CONSISTENT')
    add('firmware-exact-path-conflict-rehashed',lambda m,f:image(m,f,raw=b'DIFFERENT SIMULATED IMAGE\n'),criterion=None,state='MISMATCH',codes=['candidate_conflict'],exit=1)
    for path in ('sub/firmware.hex','firmware.HEX','another.hex'):
        add('not-image-'+path.replace('/','_'),lambda m,f,path=path:image(m,f,path,b'DIFFERENT SIMULATED IMAGE\n'),criterion='F1',state='CONSISTENT')
    for label in ('declared-only','measured-only','role-key'):
        add('firmware-'+label,image,criterion=None,state='INVALID' if label=='role-key' else 'MISMATCH',
            codes=['field_unknown'] if label=='role-key' else ['candidate_conflict','file_digest_mismatch'],exit=2 if label=='role-key' else 1)
        result[-1]['wire']=label
    return result


def materialize(c,directory):
    m=old.materialize(c,directory);directory=Path(directory)
    firmware=next((v for v in m['files'] if v['path']=='firmware.hex'),None)
    wire=c.get('wire')
    if wire=='declared-only':firmware['sha256']='0'*64
    if wire=='measured-only':(directory/'firmware.hex').write_bytes(b'DIFFERENT ACTUAL FILE BYTES\n')
    if wire=='role-key':firmware['role']='firmware_hex'
    (directory/'manifest.json').write_text(json.dumps(m,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return m
