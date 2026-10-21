"""Operation predicates on already bound subset observations. No projection replay.

Run each family in its own process: original standalone verifier packages use
unqualified module names. Only Verification modules are imported. No Product code.
"""
import argparse,collections,copy,gzip,hashlib,json,struct,sys,zlib
from functools import lru_cache
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FAMILIES={'core':'crash_core_draft8','promote':'promote_draft8','dup':'format_dup_identity_draft8','respool':'respool_full_draft8'}
def sha(b):return hashlib.sha256(b).hexdigest()
def canon(o):return json.dumps(o,sort_keys=True,separators=(',',':')).encode()
def lines(p):return [json.loads(l) for l in p.read_text().splitlines() if l]
@lru_cache(64)
def initial(p):
    b=gzip.decompress(Path(p).read_bytes());assert sha(b)==Path(p).name[:-7];return b
@lru_cache(32)
def trace_file(p):return gzip.decompress(Path(p).read_bytes())
def trace(part,r):
    q=r['trace'];key=q.get('reference_trace_sha256',q['trace_sha256']);raw=trace_file(str(part/'traces'/(key+'.jsonl.gz')));assert sha(raw)==key
    es=[json.loads(x) for x in raw.splitlines()]
    if q['stored']!='whole':
        es=es[:q['prefix_records']];cut=q['cut_record'];n=q['unacknowledged_cut_call_units']
        if n:
            for e in es[-n:]:
                assert e['t']=='W' and e['call']==cut.get('call');e['ack']=False
        es.append(cut)
        assert sha(b''.join(json.dumps(e,sort_keys=True).encode()+b'\n' for e in es))==q['trace_sha256']
    return es
def snap(meta,ref):
    s=copy.deepcopy(meta[ref['metadata_snapshot_sha256']]);s.update({k:v for k,v in ref.items() if k!='metadata_snapshot_sha256'});return s
def raw_snapshot(raw,template):
    get=lambda l,n=1:raw[l*512:(l+n)*512]
    s=dict(primary_hex=get(0).hex(),mirror_hex=raw[-512:].hex(),block_count=len(raw)//512)
    for k,v in template.items():
        if k=='format':s[k]=v
        elif k=='slots':s[k]={n:get(l,2).hex() for n,l in [('A0',8),('A1',136),('B0',264),('B1',392)]}
        elif k=='slot_prefix_hex':s[k]=[get(l,2).hex() for l in (8,136,264,392)]
        elif k=='chunk_sha256':s[k]={c:sha(get(2048+int(c)*1024,1024)) for c in v}
        elif k=='chunk0_hex':s[k]={c:get(2048+int(c)*1024).hex() for c in v}
        elif k.endswith('_header_hex') or k.endswith('_entries_hex'):
            n=k[:2].upper();base={'A0':8,'A1':136,'B0':264,'B1':392}[n];s[k]=get(base+(1 if '_entries_' in k else 0)).hex()
        elif k in ('a0_head_hex','b0_head_hex'):s[k]=get(8 if k[0]=='a' else 264).hex()
    return s

def core_check(s,o,pre,scenario,hist):
    import media,fixture
    family,variant,seed=scenario;p=media.logical_fingerprint(s,requested_side='A');assert p['mount_result']=='TAPE_OK',p
    sb=media.inspect_snapshot(pre,requested_side='A')['superblock']['selected'];old=media.logical_fingerprint(pre,requested_side='A')
    assert p['sb_generation']>=sb['generation'],'selected stale generation'
    assert p['a_entries']==old['a_entries'] and p['a_sequence']==old['a_sequence'],'A index changed'
    # All Side-A owned chunks, including live B references below H, are protected.
    for c in range(sb['a_high_water']):assert s['chunk_sha256'][str(c)]==pre['chunk_sha256'][str(c)],('A-owned data changed',c)
    if family=='record_commit':
        assert p['b_entries'] in [[(0,0,131072)],fixture.expected_record_post_entries(variant)]
        assert p['b_sequence'] in (20,21)
        if p['b_sequence']==21:assert p['b_entries']==fixture.expected_record_post_entries(variant)
        else:assert p['b_entries']==[(0,0,131072)]
        setup=[e for e in hist if e['t']=='W' and e.get('phase')=='setup' and e['lba']==4096]
        if setup:
            expected=bytes.fromhex(pre['chunk0_first_hex'])[:4] if variant=='overdub' else bytes(4)
            assert bytes.fromhex(setup[-1]['hex'])[:4]==expected,'prepared first PCM frame'
    elif family=='reset_b':
        if variant=='healthy':assert (p['b_sequence'],p['b_entries']) in [(20,[(1,0,131072)]),(21,[(0,0,131072)])]
        elif p['degraded_b']:assert p['b_error'] in ('TAPE_ERR_INCONSISTENT','TAPE_ERR_NO_VALID_INDEX')
        else:assert p['b_sequence'] in (500,501) and p['b_entries']==[(0,0,131072)]
        assert s['chunk_sha256']==pre['chunk_sha256'],'reset wrote chunk data'
    else:
        assert p['sb_generation'] in (10,11) and p['a_high_water']==3
        assert p['promote_stage']==(1 if p['sb_generation']==10 else 0)
        assert p['b_sequence']>=old['b_sequence'],'stage caller rolled back the live B index'
        if variant!='respool':assert p.get('b_entries')==[(2,0,131072)]
        else:
            e=p['b_entries'];assert len(e)==1 and e[0][1:]==(0,131072)
            c=e[0][0];assert c in (2,3,4)
            assert s['chunk_sha256'][str(c)]==pre['chunk_sha256']['2'],'respool live B content'
    actual=o['remount_result'];pred=media.inspect_snapshot(s,requested_side=o['side'])['mount_result'];assert actual==pred
    return {'mount':pred,'generation':p['sb_generation'],'stage':p['promote_stage'],'a':p['a_entries'],'b':p.get('b_entries'),'b_sequence':p.get('b_sequence'),'degraded':p['degraded_b']}

def promote_check(s,o,pre,scenario,hist):
    import media,fixture
    a=media.inspect_snapshot(s,'A');b=media.inspect_snapshot(s,'B');assert a['mount_result']=='TAPE_OK'
    assert b['mount_result']=='TAPE_OK'
    selected=a['sb']['selected'];old=media.select_superblock(pre)['selected'];assert selected['sb_generation']>=old['sb_generation'],'closure rollback'
    before=media.inspect_snapshot(pre,'A')
    if old['promote_stage']==1 and before.get('resume_rows') in ([2],[3]):
        assert not any(e['t']=='W' and e.get('phase')=='op' and 2048<=e['lba']<s['block_count']-1 for e in hist),'resume at8/9 repeated a data copy'
    media.require_unique_structural_sequences(s)
    if selected['promote_stage']==1:assert len(a['resume_rows'])==1
    allowed_a={sha(fixture.OLD_A_BLOCK),sha(fixture.PROMOTED_BLOCK),sha(b'')}
    ad,bd=media.render_sha256(s,'A'),media.render_sha256(s,'B')
    assert ad in allowed_a and bd==sha(fixture.PROMOTED_BLOCK),'timeline corrupted'
    ae=a['A']['selected']['entries'];be=b['B']['selected']['entries'];H=selected['a_high_water'];S=selected['promote_staging_chunk']
    if selected['promote_stage']==1:
        assert S in (0,3) and H==S+1
        assert a['A']['selected']['total_frames']==128 and b['B']['selected']['total_frames']==128
        meaning={1:'RESUME-step5',2:'RESUME-step8-no-copy',3:'RESUME-step9'}[a['resume_rows'][0]]
    else:
        assert S==0
        if ad==sha(fixture.OLD_A_BLOCK):
            assert H==2 and ae==[(0,0,128)] and be in [[(1,0,64),(2,0,64)],[(3,0,128)]];meaning='FRESH-A-fallback-B-old-or-phase1'
        elif ad==sha(b''):
            assert H==0 and ae==[] and be==[(0,0,128)];meaning='FRESH-first-use'
        else:
            assert H==1 and ae==be==[(0,0,128)];meaning='NOTHING-TO-DO-complete-or-decline'
    assert o['actual_mount_A']==a['mount_result'] and o['actual_mount_B']==b['mount_result']
    assert o['actual_audio_A_sha256']==ad and o['actual_audio_B_sha256']==bd
    return {'generation':selected['sb_generation'],'stage':selected['promote_stage'],'H':selected['a_high_water'],'resume':a.get('resume_rows',[]),'permitted_row':meaning,'a':ad,'b':bd}

def dup_check(s,o,pre,scenario,hist):
    import media,fixture
    # Reuse the issued DRAFT10 raw classification algorithm; never its old
    # ordinal-based persistence planner. It handles actual restored second bases.
    import importlib.util
    if not hasattr(dup_check,'D10'):
        spec=importlib.util.spec_from_file_location('residue_pins_independent',ROOT/'tests/wp10_residue_d10/pins.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);dup_check.D10=module.M
    M=dup_check.D10
    init={'P':bytes.fromhex(pre['primary_hex']),'M':bytes.fromhex(pre['mirror_hex'])}
    step1=M.step1_ops(init);sbops=[x for x in step1 if x[0]=='w'];n=s['block_count'];lbas={'P':0,'M':n-1}
    expected=[(lbas[x[1]],x[2]) for x in sbops]+[(n-1,fixture.final_superblock(scenario[0])),(0,fixture.final_superblock(scenario[0]))]
    actual=[];prior_barrier=True;completed_step1=not sbops;pending=[];durable={};first_identity=False
    for e in hist:
        if e.get('phase')!='op':continue
        if e['t']=='W':
            l=e['lba'];data=bytes.fromhex(e['hex'])
            if l in (0,n-1):
                assert len(actual)<len(expected) and (l,data)==expected[len(actual)],'wrong invalidation/identity target or bytes'
                assert prior_barrier,'superblock role crossed without successful barrier'
                if len(actual)==len(sbops):
                    first_identity=True
                    required={136:bytes(512),392:bytes(512),8:fixture.final_index_heads(scenario[0])[0],264:fixture.final_index_heads(scenario[0])[1]}
                    if scenario[0]=='dup':
                        entry=struct.pack('<III',0,0,100)+bytes(500);required.update({9:entry,265:entry})
                    assert all(durable.get(k)==v for k,v in required.items()),'identity before durable new index state'
                actual.append((l,data));prior_barrier=False
            else:assert completed_step1,'data/index write before step1 barrier complete'
            if e['ack']:pending.append((l,data))
        elif e['t']=='F' and e['ok']:
            durable.update(pending);pending=[];prior_barrier=True
            if len(actual)>=len(sbops):completed_step1=True
    p=media.inspect_snapshot(s);result=p['mount_result'];actual=o['actual_remount_result']
    assert actual==result or result=='TAPE_ERR_BAD_MAGIC' and actual=='TAPE_ERR_CRC'
    allowed={'TAPE_OK','TAPE_ERR_BAD_MAGIC','TAPE_ERR_CRC','TAPE_ERR_INCOMPLETE','TAPE_ERR_VERSION','TAPE_ERR_INCONSISTENT'}
    assert result in allowed,(scenario,result)
    out={'mount':result}
    if result=='TAPE_OK':
        op=scenario[0];fresh=(fixture.FRESH_FORMAT_UUID if op=='format' else fixture.FRESH_DUP_UUID).hex()
        uuid=p['selected_uuid'];assert uuid==o['actual_selected_uuid'];out['identity']='fresh' if uuid==fresh else 'old'
        if uuid==fresh:
            sb=p['superblock']['selected'];assert sb['generation']==1 and sb['promote_stage']==0 and sb['a_high_water']==(0 if op=='format' else 1)
            assert p['a0']['raw']==(fixture.FORMAT_A0 if op=='format' else fixture.DUP_A0)
            assert p['b0']['raw']==(fixture.FORMAT_B0 if op=='format' else fixture.DUP_B0)
        else:
            assert uuid in (fixture.OLD_UUID_A.hex(),fixture.OLD_UUID_B.hex())
            assert s['a0_head_hex']==pre['a0_head_hex'] and s['b0_head_hex']==pre['b0_head_hex'],'old identity over new indices'
            # No durable data/index work may coexist with old mounted identity.
            changed=False
            for e in hist:
                if e['t']=='W' and e.get('phase')=='op' and e['lba'] not in (0,s['block_count']-1):changed=True
                if changed and e['t']=='F' and e['ok']:raise AssertionError('old identity after destructive data barrier')
    return out

def respool_check(s,o,pre,scenario,hist):
    import fixture,oracle
    B=fixture.BASE;m=fixture.from_compact(s);p=fixture.from_compact(pre);sb=B.select_sb(m)
    assert sb==B.select_sb(p),'respool changed superblock'
    live=B.live_slot(m,1);oldlive=B.live_slot(p,1);assert live is not None and oldlive is not None
    entries=B.parse_entries(m.slots[live]);oldentries=B.parse_entries(p.slots[oldlive])
    seq=B.structural_sequence(m.slots[live]);oldseq=B.structural_sequence(p.slots[oldlive]);maximum=B.cartridge_sequence(p)
    if seq==oldseq:assert entries==oldentries;layout='initial'
    else:
        assert seq in (maximum+1,maximum+2),'unexpected new sequence'
        if scenario[0]=='no_lower_run':
            assert seq==maximum+1 and entries==[(10,0,10)];layout='decline-pass1'
        else:
            assert len(oldentries)==1 and oldentries[0] in ((10,0,262144),(12,0,262144))
            first=12 if oldentries[0][0]==10 else 10
            if seq==maximum+1:assert entries==[(first,0,262144)];layout='pass1'
            else:assert first==12 and entries==[(10,0,262144)];layout='pass2'
    assert m.slots[:2]==p.slots[:2],'A indices changed'
    assert o['actual_remount_result']=='TAPE_OK'
    oracle._validate_remount_info(m,o)
    return {'layout':layout,'sequence':seq,'sideA_metadata_preserved':True,'audio_execution':'not retained in remount; trace copy/live-range proof reviewed separately'}

def main(root,family,out):
    sys.path.insert(0,str(ROOT/'tests'/FAMILIES[family]))
    check={'core':core_check,'promote':promote_check,'dup':dup_check,'respool':respool_check}[family]
    folders={'core':['core','core-respool'],'promote':['promote'],'dup':['dup'],'respool':['respool-v3','respool-decline']}[family]
    result={'family':family,'scope':'new operation predicates only; prior exact binding/model/PCM facts carry; no full replay','rows':{},'failures':[],'causal_controls':{}}
    exemplars=[];precache={};control_raw=None
    for bundle in sorted(root.glob('wp10-subset-*')):
      if not bundle.is_dir():continue
      for f in folders:
       for part in sorted((bundle/f).glob('part-*')):
        meta={r['snapshot_sha256']:r['snapshot'] for r in lines(part/'snapshots.jsonl')}
        obs={(r['projection_sha256'],r['remount_key']):r for r in lines(part/'remounts.jsonl')};seen=set()
        for r in lines(part/'runs.jsonl'):
         if 'trace' not in r:continue
         row='/'.join(r['scenario']);stats=result['rows'].setdefault(row,{'runs':0,'contexts':0,'bases':set(),'states':collections.Counter()});stats['runs']+=1;stats['bases'].add(r['base'])
         hist=None
         for q in r['projections']:
          key=(r['initial_sha256'],q['image_sha256'],r['remount_key'],row)
          if key in seen:continue
          seen.add(key);o=obs[(q['image_sha256'],r['remount_key'])];s=snap(meta,o['image_snapshot'])
          pk=(r['initial_sha256'],tuple(sorted(s)))
          if pk not in precache:
              raw=initial(str(part/'initial'/(r['initial_sha256']+'.img.gz')));pre=raw_snapshot(raw,s)
              if family=='core':pre['chunk0_first_hex']=raw[2048*512:2048*512+512].hex()
              precache[pk]=pre
          pre=precache[pk]
          try:
           if hist is None:hist=trace(part,r) if family in ('dup','core','promote') else []
           v=check(s,o,pre,r['scenario'],hist)
           if r.get('label')=='complete' and r['base']=='fixture':
               if family=='promote':
                   import oracle as PO
                   PO._validate_terminal_promoted(s)
               elif family=='dup':assert v.get('identity')=='fresh'
               elif family=='core':
                   if r['scenario'][0]=='record_commit':assert v['b_sequence']==21
                   elif r['scenario'][0]=='reset_b':assert v['b_sequence']==(501 if r['scenario'][1]=='degraded_equal' else 21)
                   else:
                       assert v['generation']==11 and v['stage']==0
                       if r['scenario'][1]=='respool':assert v['b'][0][0]>=3
               else:assert v['layout']!='initial'
               stats['complete_fixture_controls']=stats.get('complete_fixture_controls',0)+1
           stats['contexts']+=1;stats['states'][canon(v).decode()]+=1
           if control_raw is None:control_raw=initial(str(part/'initial'/(r['initial_sha256']+'.img.gz')))
           if len(exemplars)<100:exemplars.append((s,o,pre,r['scenario'],hist))
          except Exception as e:result['failures'].append({'bundle':bundle.name,'part':part.name,'row':row,'base':r['base'],'image':q['image_sha256'],'error':str(e),'type':type(e).__name__})
    for row,s in result['rows'].items():s['bases']=sorted(s['bases']);s['states']=dict(s['states'])
    # Actual-byte/observation mutation after an honest positive, never new Product outcomes.
    if exemplars:
      s,o,pre,sc,h=exemplars[0];bad=copy.deepcopy(s);bo=copy.deepcopy(o)
      if family=='core':
        chunk=bytearray(control_raw[2048*512:(2048+1024)*512]);chunk[0]^=1;bad['chunk_sha256']['0']=sha(chunk)
      elif family=='promote':
        # Change actual retained live chunk bytes, not a summary verdict.
        for c,v in bad['chunk0_hex'].items():bad['chunk0_hex'][c]=bytes([bytes.fromhex(v)[0]^1]).hex()+v[2:]
      elif family=='dup':
        for k in ('primary_hex','mirror_hex'):
          b=bytearray.fromhex(bad[k]);b[20:36]=bytes.fromhex('101112131415161718191a1b1c1d1e1f');struct.pack_into('<I',b,508,zlib.crc32(b[:508]));bad[k]=b.hex()
        bo['actual_selected_uuid']='101112131415161718191a1b1c1d1e1f'
      else:bad['slot_prefix_hex'][0]='00'*1024
      try:check(bad,bo,pre,sc,h)
      except Exception as e:result['causal_controls']['actual-byte-mutant']='REJECTED: '+str(e)
      else:result['causal_controls']['actual-byte-mutant']='UNDETECTED'
    out.write_text(json.dumps(result,indent=2)+'\n');print(family,'contexts',sum(s['contexts'] for s in result['rows'].values()),'failures',len(result['failures']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('family',choices=FAMILIES);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.root,a.family,a.out)
