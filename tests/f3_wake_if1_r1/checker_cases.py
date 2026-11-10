"""Single-build F3-IF/1 offline CLI vectors; synthetic, never Michael evidence."""
import copy,hashlib,json
from cases import ID
SHA=lambda b:hashlib.sha256(b).hexdigest()
COMMIT='1'*40
PINS=dict(platformio='6.1.19',platform='platformio/teensy@6.0.0',framework='platformio/framework-arduinoteensy@1.162.0',uploader='platformio/tool-teensy@1.162.0',compiler='platformio/toolchain-gccarmnoneeabi-teensy@1.150201.0')

def intel(data):
 out=[]
 for start in range(0,len(data),16):
  b=data[start:start+16];r=bytes([len(b),start>>8,start&255,0])+b;out.append(':'+r.hex().upper()+f'{(-sum(r))&255:02X}')
 return ('\n'.join(out)+'\n:00000001FF\n').encode()

def fixture(kind='candidate',elapsed=99000,provenance='actual',session='physical',verdict='acceptable'):
 inject=0 if kind=='candidate' else 150000;env='teensy41' if not inject else 'teensy41_ctl_wake150'
 marker=f'DTBUILD id={ID} commit={COMMIT} dirty=0 env={env} inject_us={inject}'.encode()
 image=intel(b'SYNTHETIC IMAGE; NOT FLASHABLE\0'+marker+b'\0');elf=b'SYNTHETIC ELF PLACEHOLDER NOT LINKED\n'
 build=dict(schema='digital-tape/fw-build/1',id=ID,commit=COMMIT,dirty=0,env=env,inject_us=inject,engine_tree='d96b4245e04d74078f8938744b1394c3018516f7',toolchain=copy.deepcopy(PINS),firmware_hex_sha256=SHA(image),firmware_elf_sha256=SHA(elf))
 raw=(f'BUILD id {ID} commit {COMMIT} dirty 0 env {env} inject_us {inject} cpu_hz 600000000 warm_frames_max 8192\r\nSLEEP 0 position 44100 unmount_position 52292 warm_frames 8192\r\nWAKE trigger button status ok elapsed_us {elapsed} cycles {elapsed*600} cpu_hz 600000000 millis {elapsed//1000} engine_us {elapsed} warm 1 mount 0 position 44100 inject_us {inject} id {ID}\r\n').encode()
 files={'firmware.hex':image,'firmware.elf':elf,'build.json':json.dumps(build).encode(),'capture.log':raw}
 ob=dict(id='SYNTHETIC-F3-1',sequence=1,provenance=provenance,kind=kind,capture='capture.log')
 if provenance=='actual' and kind=='candidate':
  record=dict(schema='digital-tape/michael-check/1',id='MC-20261110-1',date='2026-11-10',criterion='F3',build_id=ID,firmware_hex_sha256=SHA(image),log_sha256=SHA(raw),tried='SYNTHETIC FIXTURE, NOT MICHAEL OR A PHYSICAL CHECK',logged=dict(elapsed_us=elapsed,millis=elapsed//1000,warm=1),verdict=verdict,note='SYNTHETIC NOTE' if verdict=='not acceptable' else None,pm_disposition=None)
  files['michael/MC-20261110-1.json']=json.dumps(record).encode();ob['michael_check']='michael/MC-20261110-1.json'
 m=dict(schema='digital-tape/f3-session/1',session=dict(id='SYNTHETIC-F3-SESSION',kind=session,timestamp='2026-11-10T00:00:00Z',operator='SYNTHETIC NOT MICHAEL',capture_tool=dict(name='bench_capture.py',version='BE1-IF/3')),candidate=dict(build_id=ID,firmware_hex_sha256=SHA(image)),files=[],observations=[ob])
 return m,files

def record_edit(files,fn):
 k='michael/MC-20261110-1.json';d=json.loads(files[k]);fn(d);files[k]=json.dumps(d).encode()
def build_edit(files,fn):
 d=json.loads(files['build.json']);fn(d);files['build.json']=json.dumps(d).encode()

def cases():
 out=[]
 def add(name,edit=lambda m,f:None,code=0,setup=None,reason=None):out.append(dict(name=name,edit=edit,exit=code,setup=setup or {},reason=reason))
 add('single-build-actual-artifact-consistency')
 add('simulation-no-Michael-record',setup=dict(provenance='simulated',session='simulation'))
 add('met-target-human-declines',code=1,setup=dict(verdict='not acceptable'))
 add('target-equality-is-recorded-miss',setup=dict(elapsed=100000))
 add('exact-twenty-percent-miss',setup=dict(elapsed=120000))
 add('over-twenty-percent-needs-PM',code=1,setup=dict(elapsed=120001))
 def pm(m,f):record_edit(f,lambda r:r.update(pm_disposition=dict(reference='https://example.invalid/SYNTHETIC-NOT-PM-AUTHORIZATION',build_id=ID,log_sha256=SHA(f['capture.log']),elapsed_us=120001)))
 add('PM-fields-match-is-consistency-only',edit=pm,setup=dict(elapsed=120001))
 add('PM-fields-mismatch',edit=lambda m,f:(pm(m,f),record_edit(f,lambda r:r['pm_disposition'].update(build_id='b'*32))),code=1,setup=dict(elapsed=120001))
 add('actual-missing-record-stays-NOT-RUN',edit=lambda m,f:(m['observations'][0].pop('michael_check'),f.pop('michael/MC-20261110-1.json')))
 for key,value in [('build_id','b'*32),('firmware_hex_sha256','0'*64),('log_sha256','0'*64)]:add('Michael-mismatch-'+key,edit=lambda m,f,key=key,value=value:record_edit(f,lambda r:r.update({key:value})),code=2,reason='michael_record_mismatch')
 add('Michael-numbers-mismatch',edit=lambda m,f:record_edit(f,lambda r:r['logged'].update(elapsed_us=1)),code=2)
 add('bad-verdict',edit=lambda m,f:record_edit(f,lambda r:r.update(verdict='maybe')),code=2,reason='verdict_value')
 add('negative-verdict-without-note',edit=lambda m,f:record_edit(f,lambda r:r.update(verdict='not acceptable',note=None)),code=2)
 for elapsed,code in [(149999,2),(150000,0),(150001,0)]:add('control-'+str(elapsed),setup=dict(kind='control_wake150',elapsed=elapsed,provenance='simulated',session='simulation'),code=code,reason='injected_delay_underreported' if code else None)
 for key,value in [('engine_tree','0'*40),('id','b'*32),('firmware_hex_sha256','0'*64)]:add('build-record-mismatch-'+key,edit=lambda m,f,key=key,value=value:build_edit(f,lambda b:b.update({key:value})),code=2)
 add('toolchain-mismatch',edit=lambda m,f:build_edit(f,lambda b:b['toolchain'].update(platformio='OTHER')),code=2)
 add('candidate-image-hash-mismatch',edit=lambda m,f:m['candidate'].update(firmware_hex_sha256='0'*64),code=2)
 add('hex-byte-mismatch-with-rehashed-file-table',edit=lambda m,f:f.update({'firmware.hex':f['firmware.hex']+b'X'}),code=2)
 for tag,edit in [('serial-trigger',lambda raw:raw.replace(b'trigger button',b'trigger serial')),('duplicate-BUILD',lambda raw:raw+raw.splitlines(keepends=True)[0]),('missing-WAKE',lambda raw:b''.join(x for x in raw.splitlines(keepends=True) if not x.startswith(b'WAKE '))),('wrong-order',lambda raw:b''.join(reversed(raw.splitlines(keepends=True)))),('truncated-line',lambda raw:raw[:-2]),('non-ASCII',lambda raw:raw+b'\xff\r\n'),('unknown-line',lambda raw:raw+b'UNKNOWN\r\n'),('bad-timer-crosscheck',lambda raw:raw.replace(b'millis 99',b'millis 90'))]:
  def update(m,f,edit=edit):f['capture.log']=edit(f['capture.log']);record_edit(f,lambda r:r.update(log_sha256=SHA(f['capture.log'])))
  add('capture-'+tag,edit=update,code=2)
 add('control-offered-as-candidate',edit=lambda m,f:m['observations'][0].update(kind='candidate'),setup=dict(kind='control_wake150',elapsed=150000,provenance='simulated',session='simulation'),code=2,reason='control_build_as_candidate')
 def replace_image(m,f,data):
  f['firmware.hex']=intel(data);h=SHA(f['firmware.hex']);m['candidate']['firmware_hex_sha256']=h;build_edit(f,lambda b:b.update(firmware_hex_sha256=h));record_edit(f,lambda r:r.update(firmware_hex_sha256=h))
 marker_bytes=f'DTBUILD id={ID} commit={COMMIT} dirty=0 env=teensy41 inject_us=0'.encode()
 add('decoded-image-marker-missing',edit=lambda m,f:replace_image(m,f,b'SYNTHETIC NO MARKER'),code=2)
 add('decoded-image-marker-duplicate',edit=lambda m,f:replace_image(m,f,marker_bytes+b'\0'+marker_bytes+b'\0'),code=2)
 add('simulation-session-actual-conflict',edit=lambda m,f:m['session'].update(kind='simulation'),code=2)
 add('manifest-unknown-key',edit=lambda m,f:m.update(unknown=True),code=2,reason='field_unknown')
 add('duplicate-observation-id',edit=lambda m,f:m['observations'].append(copy.deepcopy(m['observations'][0])),code=2)
 add('observation-sequence-duplicate',edit=lambda m,f:m['observations'].append(dict(m['observations'][0],id='OTHER')),code=2)
 add('simulation-cannot-carry-Michael-entry',edit=lambda m,f:(m['session'].update(kind='simulation'),m['observations'][0].update(provenance='simulated')),code=2)
 add('cold-wake-stays-observed',edit=lambda m,f:(f.update({'capture.log':f['capture.log'].replace(b'warm 1',b'warm 0')}),record_edit(f,lambda r:(r['logged'].update(warm=0),r.update(log_sha256=SHA(f['capture.log']))))))
 return out
