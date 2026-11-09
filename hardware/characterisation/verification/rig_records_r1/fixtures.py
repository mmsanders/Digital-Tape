"""Rig correction-1 synthetic manifest/plan/row fixtures. No measurements."""
import copy
import hashlib
import json
from pathlib import Path
import struct

CONTROLS=('E0','E1','E2','E3','E4','A','B','B2','C','D','E','F','G')
OFFSETS=('-2','-1','+1','+2')
CID='01585953494d313210000004d201ab01'
COMMIT='1'*40
sha=lambda b:hashlib.sha256(b).hexdigest()
pattern=lambda n:struct.pack('<I',n)*128

def manifest(judge_sha):
    files={}
    def ref(path):
        raw=('SYNTHETIC ONLY: no hardware, measurement, certificate or witness\n'+path+'\n').encode()
        files[path]=raw;return dict(path=path,sha256=sha(raw))
    m=dict(method='rig-r2',rig_doc=dict(path='hardware/characterisation/ATOMICITY-RIG.md',git_blob='bf2e2c91303efe179f0342e122eb35f30c4eb71f'),
      firmware=dict(source_commit=COMMIT,binary=ref('firmware.bin')),host_script=ref('host.py'),judge_sha256=judge_sha,
      bus=dict(mode='spi',busy_line='MISO',sck_hz=4000000),capture=dict(timer='SIMULATED',clock_hz=150000000,pin_a=2,pin_b=3),
      switch=dict(revision='r2',part='TPS22918',ct_nf=1.0,r_ext_ohm=100.0,bulk_uf=10.0,hysteresis_ohm=2200000.0,
                  buffer_part='SN74LVC1G125',comparator_part='TLV3202'),
      thresholds_measured=dict(a_falling_v=[2.59]*5,b_rising_v=[1.024]*5,
          instrument=dict(model='SIMULATED-NOT-AN-INSTRUMENT',serial='NONE',calibration=ref('calibration.txt')),raw=ref('thresholds.raw')),
      skew_measured_ns=dict(max_abs=250.0,edges=1000,raw=ref('skew.raw')),
      controls={k:dict(result='pass',date='2026-11-04',witness='SIMULATED-NOT-MICHAEL; no actual witness',evidence=[ref('control-'+k+'.raw')]) for k in CONTROLS},
      card=dict(mpn='SYNTHETIC-MPN',mpn_photo=ref('photo.txt'),retail_name='SIMULATED',capacity_bytes=64000000000,
                cid=CID,decoded=dict(mid=1,oid='XY',pnm='SIM12',prv='1.0',psn=1234,mdt='2026-11'),revision='SIM12/1.0'))
    return m,files

def references(m):
    refs=[]
    def walk(v):
        if isinstance(v,dict):
            if set(v)=={'path','sha256'}:refs.append(v)
            else:
                for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(m);return refs

def write_bundle(directory,judge_sha,edit=lambda m:None,files_edit=lambda f:None,raw_edit=lambda b:b):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    m,files=manifest(judge_sha);edit(m);files_edit(files)
    evidence=directory/'evidence';evidence.mkdir()
    for path,raw in files.items():
        target=evidence/path
        assert evidence.resolve() in target.resolve().parents
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    raw=raw_edit((json.dumps(m,sort_keys=True,indent=2)+'\n').encode())
    path=directory/'manifest.json';path.write_bytes(raw)
    return m,path,evidence,sha(raw)

def manifest_cases():
    cs=[]
    def add(name,edit=lambda m:None,files_edit=lambda f:None,raw_edit=lambda b:b,valid=False):
        cs.append(dict(name=name,edit=edit,files_edit=files_edit,raw_edit=raw_edit,valid=valid))
    add('valid-synthetic-records',valid=True)
    add('valid-whitespace-hashed-as-bytes',raw_edit=lambda b:b+b' \n',valid=True)
    add('missing-manifest-file')
    for name,raw in [('array',b'[]'),('null',b'null'),('number',b'123')]:
        add('nonobject-'+name,raw_edit=lambda b,raw=raw:raw)
    for k in CONTROLS:
        add('missing-control-'+k,lambda m,k=k:m['controls'].pop(k))
        add('failed-control-'+k,lambda m,k=k:m['controls'][k].update(result='fail'))
        add('empty-control-evidence-'+k,lambda m,k=k:m['controls'][k].update(evidence=[]))
    files=manifest('0'*64)[1]
    for path in files:
        add('changed-file-'+path,files_edit=lambda f,path=path:f.update({path:b'TAMPERED\n'}))
        add('missing-file-'+path,files_edit=lambda f,path=path:f.pop(path))
    for k in manifest('0'*64)[0]:
        add('missing-key-'+k,lambda m,k=k:m.pop(k))
    add('unknown-key',lambda m:m.update(operator_override=1))
    add('unknown-control',lambda m:m['controls'].update(UNDECLARED=copy.deepcopy(m['controls']['E0'])))
    add('empty-control-witness',lambda m:m['controls']['E0'].update(witness=''))
    add('missing-decoded-cid-field',lambda m:m['card']['decoded'].pop('pnm'))
    add('wrong-method',lambda m:m.update(method='other'))
    add('wrong-judge',lambda m:m.update(judge_sha256='0'*64))
    for name,path in [('parent','../outside'),('absolute','/outside'),('drive','C:/outside'),('backslash','sub\\outside')]:
        add('unsafe-ref-'+name,lambda m,path=path:m['host_script'].update(path=path))
    add('bad-ref-hash',lambda m:m['host_script'].update(sha256='NOT-A-HASH'))
    add('unknown-ref-key',lambda m:m['host_script'].update(extra=True))
    for key,low,high in [('a_falling_v',2.570,2.610),('b_rising_v',1.010,1.040)]:
        add(key+'-inclusive-bounds',lambda m,key=key,low=low,high=high:m['thresholds_measured'].update({key:[low,high,low,high,low]}),valid=True)
        add(key+'-low',lambda m,key=key,low=low:m['thresholds_measured'][key].__setitem__(0,low-0.001))
        add(key+'-high',lambda m,key=key,high=high:m['thresholds_measured'][key].__setitem__(0,high+0.001))
        add(key+'-four-values',lambda m,key=key:m['thresholds_measured'].update({key:[1.0]*4}))
        add(key+'-boolean',lambda m,key=key:m['thresholds_measured'][key].__setitem__(0,True))
    add('skew-inclusive-bound',lambda m:m['skew_measured_ns'].update(max_abs=300),valid=True)
    add('skew-over',lambda m:m['skew_measured_ns'].update(max_abs=300.001))
    add('skew-insufficient-edges',lambda m:m['skew_measured_ns'].update(edges=999))
    add('skew-boolean-edges',lambda m:m['skew_measured_ns'].update(edges=True))
    add('clock-not-positive',lambda m:m['capture'].update(clock_hz=0))
    add('sck-not-integer',lambda m:m['bus'].update(sck_hz=True))
    add('unknown-bus',lambda m:m['bus'].update(mode='sd4'))
    add('wrong-busy-line',lambda m:m['bus'].update(busy_line='DAT0'))
    add('capacity-not-positive',lambda m:m['card'].update(capacity_bytes=0))
    add('malformed-cid',lambda m:m['card'].update(cid='xyz'))
    add('bad-UTF8',raw_edit=lambda b:b'\xff')
    add('truncated-JSON',raw_edit=lambda b:b[:-3])
    add('duplicate-key',raw_edit=lambda b:b.replace(b'{',b'{"method":"other",',1))
    for token in ('NaN','Infinity','-Infinity'):
        add('nonfinite-'+token,raw_edit=lambda b,token=token:b.replace(b'250.0',token.encode(),1))
    return cs

def plan_digest(p):
    # Revision3 canonical identity/schedule encoding plus the two declared v4 terms.
    keys=('run_id','sku','revision','card_cid','block','neighbour_offsets','method','rig_manifest_sha256')
    core={k:p[k] for k in keys};core['trials']=[[t['iteration'],t['cut_offset_fraction']] for t in p['trials']]
    return sha(json.dumps(core,sort_keys=True,separators=(',',':')).encode())

def run_fixture(manifest_sha,count=1001):
    p=dict(plan_version=4,run_id='RIG-RECORDS-SYNTHETIC',sku='SYNTHETIC-MPN',revision='SIM12/1.0',card_cid=CID,
      block=1000,neighbour_offsets=list(OFFSETS),method='rig-r2',rig_manifest_sha256=manifest_sha,
      required_qualifying=1000,trials=[dict(iteration=i,cut_offset_fraction=0.5) for i in range(1,count+1)])
    p['plan_digest']=plan_digest(p);rows=[]
    for n in range(1,count+1):
        neighbours={off:bytes([i+17]).hex()*512 for i,off in enumerate(OFFSETS)}
        rows.append(dict(iteration=n,run_id=p['run_id'],sku=p['sku'],revision=p['revision'],card_cid=CID,
          card_cid_after_cut=CID,plan_digest=p['plan_digest'],method='rig-r2',rig_manifest_sha256=manifest_sha,
          firmware_source_commit=COMMIT,switch_revision='r2',bus_mode='spi',busy_line='MISO',sck_hz=4000000,
          precondition_ok=True,precondition_readback_hex=pattern(n-1).hex(),readback_hex=pattern(n).hex(),
          neighbours=neighbours,neighbour_baseline=copy.deepcopy(neighbours),payload_complete=True,data_response_accepted=True,
          capture_armed_us=90.0,busy_entry_us=100.0,cut_command_us=140.0,rail_open_us=150.0,
          rail_edges_us=[150.0],busy_end_edges_us=[],capture_end_us=200.0,rail_high_at_arm=True))
    rows[-1]['busy_end_edges_us']=[148.999] # Lawful late NEW miss, no qualifying credit.
    return [p],rows

def judge_cases():
    cs=[]
    def add(name,edit=lambda p,r:None,verdict='FAIL',qualifying=1000,problems=False,rollback=(),tears=(),corrupt=(),neighbour=(),loader='valid'):
        cs.append(dict(name=name,edit=edit,loader=loader,expected=dict(verdict=verdict,qualifying=qualifying,
          problems=problems,rollback=list(rollback),tears=list(tears),corrupt=list(corrupt),neighbour=list(neighbour))))
    add('production-1000-plus-late-NEW',verdict='PASS')
    add('OLD-while-busy-is-lawful',lambda p,r:r[0].update(readback_hex=pattern(0).hex()),verdict='PASS')
    add('999-is-short',lambda p,r:r[0].update(busy_end_edges_us=[148.999]),qualifying=999)
    add('operator-cannot-lower-1000',lambda p,r:(p[0].update(required_qualifying=1),r[0].update(busy_end_edges_us=[148.999])),qualifying=999)
    add('completed-write-OLD-fails',lambda p,r:r[-1].update(readback_hex=pattern(1000).hex()),problems=True,rollback=[1001])
    for edge in (149.0,150.0,151.0):
        add('ambiguous-OLD-'+str(edge),lambda p,r,edge=edge:r[-1].update(busy_end_edges_us=[edge],readback_hex=pattern(1000).hex()),verdict='PASS')
    add('just-after-upper-bound-OLD-qualifies',lambda p,r:r[-1].update(busy_end_edges_us=[151.001],readback_hex=pattern(1000).hex()),verdict='PASS',qualifying=1001)
    for label,fields in [('unarmed',dict(capture_armed_us=101.0)),('short-window',dict(capture_end_us=150.5)),
      ('delayed',dict(cut_command_us=0.0,rail_open_us=600.0,rail_edges_us=[600.0],capture_end_us=700.0)),
      ('no-payload-proof',dict(payload_complete=False)),('no-token-proof',dict(data_response_accepted=False)),
      ('chatter',dict(rail_edges_us=[150.0,160.0]))]:
        add('OLD-no-completion-proof-'+label,lambda p,r,fields=fields:r[-1].update(**fields,readback_hex=pattern(1000).hex()),verdict='PASS')
    add('no-opening-OLD',lambda p,r:r[-1].update(rail_open_us=None,rail_edges_us=[],readback_hex=pattern(1000).hex()),verdict='PASS')
    add('record-invalid-is-problem-not-rollback',lambda p,r:r[-1].update(rail_edges_us=[],readback_hex=pattern(1000).hex()),problems=True)
    for field in ('capture_armed_us','busy_entry_us','cut_command_us','capture_end_us','rail_open_us','rail_edges_us','busy_end_edges_us'):
        add('record-missing-'+field,lambda p,r,field=field:r[-1].pop(field),problems=True)
    for label,fields in [('nan',dict(cut_command_us=float('nan'))),('infinite',dict(capture_end_us=float('inf'))),
      ('negative',dict(busy_entry_us=-1)),('boolean',dict(capture_armed_us=True)),
      ('backwards-edges',dict(rail_edges_us=[160.0,150.0])),('outside-window',dict(busy_end_edges_us=[201.0])),
      ('opening-contradiction',dict(rail_open_us=149.0)),('capture-backwards',dict(capture_end_us=80.0))]:
        add('record-invalid-'+label,lambda p,r,fields=fields:r[-1].update(**fields),problems=True)
    add('chatter-without-busy-end-is-miss',lambda p,r:r[-1].update(rail_edges_us=[150.0,160.0],busy_end_edges_us=[]),verdict='PASS')
    torn=(pattern(1000)[:256]+pattern(1001)[256:]).hex()
    for label,fields in [('late',dict()),('ambiguous',dict(busy_end_edges_us=[150.0])),
      ('no-opening',dict(rail_open_us=None,rail_edges_us=[])),('delayed',dict(rail_open_us=641.0,rail_edges_us=[641.0],capture_end_us=700.0)),
      ('chatter',dict(busy_end_edges_us=[],rail_edges_us=[150.0,160.0]))]:
        add('TORN-on-'+label,lambda p,r,fields=fields:r[-1].update(**fields,readback_hex=torn),tears=[1001])
        for off in OFFSETS:
            add('neighbour-'+off+'-on-'+label,lambda p,r,fields=fields,off=off:(r[-1].update(**fields),r[-1]['neighbours'].update({off:'ff'*512})),neighbour=[[1001,off]])
    add('CORRUPT-on-late',lambda p,r:r[-1].update(readback_hex='aa'*512),corrupt=[1001])
    for field,value in [('card_cid_after_cut','2'*32),('card_cid','2'*32),('sku','OTHER'),('revision','OTHER'),
      ('method','other'),('rig_manifest_sha256','0'*64),('sck_hz',4000001),('bus_mode','sd4'),('busy_line','DAT0'),
      ('firmware_source_commit','2'*40),('switch_revision','other'),('rail_high_at_arm',False)]:
        add('row-conflict-'+field,lambda p,r,field=field,value=value:r[-1].update({field:value}),problems=True)
    for field in ('card_cid_after_cut','firmware_source_commit','rail_high_at_arm','rig_manifest_sha256'):
        add('row-missing-'+field,lambda p,r,field=field:r[-1].pop(field),problems=True)
    for field,value in [('sku','OTHER'),('revision','OTHER'),('card_cid','2'*32),('rig_manifest_sha256','0'*64),('method','other')]:
        def repoint(p,r,field=field,value=value):
            p[0][field]=value
            for item in r:
                item[field]=value
                if field=='card_cid':item['card_cid_after_cut']=value
            p[0]['plan_digest']=plan_digest(p[0])
            for item in r:item['plan_digest']=p[0]['plan_digest']
        add('plan-conflict-'+field,repoint,qualifying=None,problems=True)
    add('no-loaded-manifest',qualifying=None,problems=True,loader='none')
    add('loaded-manifest-has-problems',qualifying=None,problems=True,loader='bad')
    add('manifest-bytes-repointed',qualifying=None,problems=True,loader='changed-bytes')
    add('duplicate-row',lambda p,r:r.append(copy.deepcopy(r[0])),qualifying=None,problems=True)
    add('missing-row',lambda p,r:r.pop(),qualifying=None,problems=True)
    return cs
