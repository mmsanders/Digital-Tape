"""Independent plan5 public-interface fixtures, all SYNTHETIC; no card/tool evidence."""
import copy,hashlib,json,struct
SHA=lambda b:hashlib.sha256(b).hexdigest()
BUILD='1'*40;CIDA='a'*32;CIDB='b'*32;CIDC='c'*32
HEX=b':00000001FF\n'
RESIDUAL=['bus: SPI at the logged sck_hz, not SD 4-bit','busy timing and card-off voltage are self-observed','one card unit per model']
OFFSETS=['-2','-1','+1','+2']
pattern=lambda n:struct.pack('<I',n)*128

def digest(p):
 keys=('run_id','method','card_model','card_unit','card_cid','firmware_build','hex_sha256','t_sched_us','block','neighbour_offsets')
 core={k:p[k] for k in keys};core['trials']=[[t['iteration'],t['cut_offset_fraction']] for t in p['trials']]
 return SHA(json.dumps(core,sort_keys=True,separators=(',',':')).encode())

def fixture():
 photo=b'SYNTHETIC PHOTO PLACEHOLDER; NOT AN IMAGE OR CARD RECORD\n'
 card=dict(card_model=dict(brand_line='SYNTHETIC',capacity_label='64 GB',part_number=None,photos=[dict(path='photo.bin',sha256=SHA(photo))]),card_unit=dict(label='SYNTHETIC UNIT',back_print=[]))
 build=dict(firmware_build=BUILD,hex_sha256=SHA(HEX));p=dict(plan_version=5,method='selfrun-r1',run_id='selfrun-SYNTHETIC-UNIT-'+'0'*16,**copy.deepcopy(card),card_cid=None,**build,t_sched_us=200,block=1000000,neighbour_offsets=OFFSETS,planned_attempts=1001,required_qualifying=1000,note='SYNTHETIC ONLY',extends=None,created='2026-11-10T00:00:00Z',trials=[dict(iteration=n,cut_offset_fraction=.5) for n in range(1,1002)])
 p['plan_digest']=digest(p);nb={o:(bytes([10+i])*512).hex() for i,o in enumerate(OFFSETS)};rows=[]
 for n in range(1,1002):
  rows.append(dict(method='selfrun-r1',iteration=n,run_id=p['run_id'],plan_digest=p['plan_digest'],card_unit=card['card_unit']['label'],firmware_build=BUILD,card_cid=None,card_cid_after_cut=None,bus_mode='spi',busy_line='MISO',sck_hz=4000000,precondition_ok=True,precondition_readback_hex=pattern(n-1).hex(),readback_hex=pattern(n if n%2 else n-1).hex(),neighbour_baseline=dict(nb),neighbours=dict(nb),payload_complete=True,data_response_accepted=True,busy_entry_us=100,busy_sampled_us=180,cut_us=185,busy_deassert_us=None if n<=1000 else 181,vcard_off_mv=0,init_ms=None))
 return p,rows,card,build,photo

def cases():
 out=[]
 def add(name,edit=lambda p,r:None,**wanted):out.append(dict(name=name,edit=edit,wanted=wanted))
 add('all-null-CID-unknown-part-number',verdict='PASS',qualifying=1000,card_cid=None,cids_seen=[],cid_disagreements=[])
 add('gap-equality-5us',verdict='PASS',qualifying=1000)
 add('gap-over-5us',lambda p,r:r[0].update(cut_us=185.000001),verdict='FAIL',qualifying=999,non_qualifying={'busy sample older than 5 us at the cut':1,'busy ended before the cut':1})
 add('old-busy-sample-50ms',lambda p,r:r[0].update(cut_us=50180),verdict='FAIL',qualifying=999)
 add('voltage-equality-200',lambda p,r:r[0].update(vcard_off_mv=200),verdict='PASS',qualifying=1000,vcard_off_mv_max=200)
 for v in [201,3300,4001,-1,200.0,True,None,'200']:
  add('voltage-'+repr(v),lambda p,r,v=v:r[0].update(vcard_off_mv=v),verdict='FAIL',problem=True)
 def before(r,old=True,equal=True):r[0].update(cut_us=181 if equal else 181.5,busy_deassert_us=181,readback_hex=pattern(0 if old else 1).hex())
 add('completed-OLD-equality',lambda p,r:before(r),verdict='FAIL',qualifying=999,completed_before_old=[1],torn_iterations=[],problem_text='completed write reads OLD')
 add('completed-OLD-strict-before',lambda p,r:before(r,equal=False),verdict='FAIL',completed_before_old=[1])
 add('completed-NEW-retained-miss',lambda p,r:before(r,False),verdict='FAIL',qualifying=999,completed_before_old=[],torn_iterations=[])
 add('completed-OLD-among-1000-other-qualifying',lambda p,r:r[-1].update(readback_hex=pattern(1000).hex()),verdict='FAIL',qualifying=1000,completed_before_old=[1001],torn_iterations=[])
 add('deassert-equals-last-sample-invalid',lambda p,r:r[0].update(busy_deassert_us=180),verdict='FAIL',problem=True)
 add('CID-before-after-diagnostic',lambda p,r:r[0].update(card_cid=CIDA,card_cid_after_cut=CIDB),verdict='PASS',qualifying=1000,cids_seen=[CIDA,CIDB],card_cid=None,cid_disagreements=[dict(iteration=1,kind='before_after',values=[CIDA,CIDB])])
 def cid_plan(p,r):
  p['card_cid']=CIDA;p['plan_digest']=digest(p)
  for row in r:row['plan_digest']=p['plan_digest']
  r[0].update(card_cid=CIDB,card_cid_after_cut=CIDC)
 add('CID-disagrees-with-plan-only-diagnostic',cid_plan,verdict='PASS',qualifying=1000,cids_seen=[CIDA,CIDB,CIDC],card_cid=None,cid_disagreements=[dict(iteration=1,kind='before_after',values=[CIDB,CIDC]),dict(iteration=1,kind='vs_plan',values=[CIDA,CIDB]),dict(iteration=1,kind='vs_plan',values=[CIDA,CIDC])])
 add('only-one-observed-CID',lambda p,r:r[0].update(card_cid=CIDA),verdict='PASS',card_cid=CIDA,cids_seen=[CIDA])
 for key in ('card_cid','card_cid_after_cut'):
  for v in ['',CIDA.upper(),'fake',True,0]:add(key+'-malformed-'+repr(v),lambda p,r,key=key,v=v:r[0].update({key:v}),verdict='FAIL',problem=True)
 def tear(r,i):
  n=r[i]['iteration'];r[i]['readback_hex']=(pattern(n-1)[:256]+pattern(n)[256:]).hex()
 add('planted-tear-busy',lambda p,r:tear(r,0),verdict='FAIL',torn_iterations=[1])
 add('planted-tear-on-miss',lambda p,r:tear(r,1000),verdict='FAIL',torn_iterations=[1001],damage_on_non_qualifying=[1001])
 add('neighbour-on-miss',lambda p,r:r[-1]['neighbours'].update({'+1':(b'\xff'*512).hex()}),verdict='FAIL',neighbour_damage=[[1001,'+1']],damage_on_non_qualifying=[1001])
 add('corrupt-target',lambda p,r:r[0].update(readback_hex=(b'\xff'*512).hex()),verdict='FAIL',corrupt_iterations=[1])
 for key in ('method','run_id','plan_digest','card_unit','firmware_build'):
  add('identity-'+key,lambda p,r,key=key:r[0].update({key:'OTHER'}),verdict='FAIL',problem=True)
 for key in fixture()[1][0]:add('missing-row-'+key,lambda p,r,key=key:r[0].pop(key),verdict='FAIL',problem=True)
 add('unknown-row-field',lambda p,r:r[0].update(operator_waiver=True),verdict='FAIL',problem=True)
 for key in ('busy_entry_us','busy_sampled_us','busy_deassert_us','cut_us'):
  for label,v in [('bool',True),('negative',-1),('string','180'),('nan',float('nan')),('inf',float('inf'))]:add(key+'-'+label,lambda p,r,key=key,v=v:r[0].update({key:v}),verdict='FAIL')
 for key in ('payload_complete','data_response_accepted','precondition_ok'):
  add('nonboolean-'+key,lambda p,r,key=key:r[0].update({key:1}),verdict='FAIL',problem=True)
 add('entry-without-sample',lambda p,r:r[0].update(busy_sampled_us=None),verdict='FAIL',problem=True)
 add('sample-without-entry',lambda p,r:r[0].update(busy_entry_us=None),verdict='FAIL',problem=True)
 add('busy-order-backwards',lambda p,r:r[0].update(busy_sampled_us=99),verdict='FAIL',problem=True)
 add('sample-after-cut',lambda p,r:r[0].update(busy_sampled_us=186),verdict='FAIL',problem=True)
 add('no-busy-entry-retained-miss',lambda p,r:r[0].update(busy_entry_us=None,busy_sampled_us=None),verdict='FAIL',qualifying=999,completed_before_old=[])
 add('unaccepted-response-retained-miss',lambda p,r:r[0].update(data_response_accepted=False,busy_entry_us=None,busy_sampled_us=None),verdict='FAIL',qualifying=999)
 add('payload-incomplete-retained-miss',lambda p,r:r[0].update(payload_complete=False),verdict='FAIL',qualifying=999)
 for key,v in [('bus_mode','sd4'),('busy_line','DAT0'),('sck_hz',True),('sck_hz',0),('init_ms',-1),('init_ms',True),('precondition_ok',False),('precondition_readback_hex',pattern(1).hex()),('readback_hex','00'),('iteration',True)]:add('malformed-'+key+'-'+repr(v)[:12],lambda p,r,key=key,v=v:r[0].update({key:v}),verdict='FAIL',problem=True)
 add('mixed-sck',lambda p,r:r[0].update(sck_hz=1000000),verdict='FAIL',problem=True)
 add('missing-neighbour',lambda p,r:r[0]['neighbours'].pop('+2'),verdict='FAIL',problem=True)
 add('duplicate-attempt',lambda p,r:r.append(copy.deepcopy(r[0])),verdict='FAIL',qualifying=1000,problem=True)
 add('missing-attempt',lambda p,r:r.pop(),verdict='FAIL',problem=True)
 add('extra-attempt',lambda p,r:r.append(dict(r[0],iteration=2000)),verdict='FAIL',problem=True)
 add('operator-minimum-zero',lambda p,r:(p.update(required_qualifying=0),r[0].update(cut_us=50180)),verdict='FAIL',qualifying=999,required_qualifying=1000)
 return out
