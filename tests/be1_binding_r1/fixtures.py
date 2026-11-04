"""Verifier-owned simulated BE1-IF/2 bundles; no device or checker dependency."""
import copy
import hashlib
import json
from pathlib import Path
import re
import struct
import wave

CASES = ('play-1x-quiet', 'play-1x-fortissimo', 'splice', 'overdub', 'overwrite', 'reset-b', 'promote')
PIN = 'd96b4245e04d74078f8938744b1394c3018516f7'
TOOLCHAIN = dict(platformio='6.1.19', platform='platformio/teensy@6.0.0',
 framework='platformio/framework-arduinoteensy@1.162.0', uploader='platformio/tool-teensy@1.162.0',
 compiler='platformio/toolchain-gccarmnoneeabi-teensy@1.150201.0')
sha = lambda b: hashlib.sha256(b).hexdigest()


def references(golden):
    golden = Path(golden)
    sums = dict((line.split()[1].removeprefix('*'), line.split()[0])
                for line in (golden/'SHA256SUMS').read_text(encoding='utf-8').splitlines() if line.strip())
    manifest = (golden/'MANIFEST').read_bytes()
    assert sha(manifest) == sums['MANIFEST'], 'Use canonical LF reference MANIFEST, never regenerate it'
    refs = {}
    for line in manifest.decode().splitlines():
        if not line or line.startswith('#'):
            continue
        name = line.split()[0]
        if name not in CASES:
            continue
        raw = (golden/'ref'/f'{name}.wav').read_bytes()
        assert sha(raw) == sums[f'ref/{name}.wav']
        import io
        with wave.open(io.BytesIO(raw), 'rb') as wav:
            assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (2, 2, 44100)
            pcm = wav.readframes(wav.getnframes())
        last = line.split(' && ')[-1]
        if ' play ' in last:
            side, start, count = re.search(r'--side (A|B).*--from (\d+).*--frames (\d+).*--rate 1 ', last).groups()
        else:
            side, start, count = re.search(r'--side (A|B)', last).group(1), '0', '0'
        refs[name] = dict(wav=sha(raw), pcm=pcm, frames=len(pcm)//4,
                          command=f'golden {side} {start} {count}')
    assert set(refs) == set(CASES)
    return refs


def base(refs):
    files = {}
    m = dict(schema='digital-tape/be1-session/1',
      session=dict(id='V382-SIMULATED', kind='simulation', timestamp='2026-11-03T12:00:00-08:00',
                   operator='Verifier fixture generator; no hardware', witness=None,
                   capture_tool=dict(name='V382-fixture', version='1')),
      candidate=dict(product_commit='ee478a913613a16a90e38c85112fb67cbbf53887', engine_tree=PIN,
                     firmware_hex_sha256=sha(b'V382 SIMULATED FIRMWARE\n'), toolchain=copy.deepcopy(TOOLCHAIN)),
      target=dict(board='SIMULATED Teensy 4.1', board_revision=None, audio_board=None),
      requested=['F1', 'F2', 'F5'], files=[], observations=[])
    for i, name in enumerate(CASES):
        ref = refs[name]
        path = name + '.serial'
        files[path] = f"SHA256 {sha(ref['pcm'])} FRAMES {ref['frames']} RESULT 0\r\n".encode()
        m['observations'].append(dict(id=name, criterion='F1', provenance='simulated', sequence=i+1,
          case=name, mode='golden', command=ref['command'], reference_wav_sha256=ref['wav'], transcript=path))
    return m, files


def size_gate(data=0, bss=0, common=0, instance=191600, rodata=1040, ram=None):
    ram = data+bss+common+instance if ram is None else ram
    return (f'== gate: F2 firmware budgets (linked image) ==\n'
      f'        engine objects linked  6\n        engine .data           {data}\n'
      f'        engine .bss            {bss}\n        engine COMMON          {common}\n'
      f'        instance          {instance}   (fw_engine_instance reservation)\n'
      f'        RAM               {ram} / 204800 bytes  ({ram*100//204800}%)\n'
      f'        engine .rodata      {rodata} / 32768 bytes  ({rodata*100//32768}%)\n'
      'PASS  both budgets\n').encode()


def add_f2(m, f, instance=191600, reserve=191600, stack=8192):
    f['firmware.hex'] = b'V382 SIMULATED FIRMWARE\n'
    f['SHA256SUMS'] = f"{sha(f['firmware.hex'])}  firmware.hex\n".encode()
    f['size-gate.txt'] = size_gate()
    f['info.serial'] = (f'INFO state 1 instance {instance} reserve {reserve} card_blocks 100000 '
      f'p2_base 34816 p2_blocks 65184 stack_high_water {stack} underruns 0\r\n').encode()
    m['observations'].append(dict(id='f2', criterion='F2', provenance='simulated', sequence=50,
      size_gate='size-gate.txt', sha256sums='SHA256SUMS', transcript='info.serial'))


def add_f5(m, f):
    f['controls.serial'] = (b'CARD MOUNTED side A frames 198450 label V382\r\nPLAY 0\r\n'
      b'STOP 0\r\nPOSITION 10\r\nPLAY 0\r\nSTOP 0\r\nPOSITION 20\r\n'
      b'PLAY 0\r\nUNMOUNT 0\r\nCARD GONE removed\r\n')
    f['verify.txt'] = b'OK\n'
    card = dict(manufacturer='SIMULATED', part_number='NOT-A-CARD', capacity_bytes=64000000000,
                revision='SIM', cid=None)
    m['observations'].append(dict(id='f5', criterion='F5', provenance='simulated', sequence=40,
      transcript='controls.serial', witness=None, card_before=card, card_after=copy.deepcopy(card),
      verify_command='tapectl verify SIMULATED.img', verify_stdout='verify.txt', verify_exit=0))


def stream(ref):
    pcm = ref['pcm']
    return (b'PCM\r\n' + struct.pack('<I', len(pcm)//4) + pcm + struct.pack('<I', 0) +
      f"SHA256 {sha(pcm)} FRAMES {len(pcm)//4} RESULT 0\r\n".encode())


def catalog(refs):
    """Each expected state is authored here, never computed by a Product checker."""
    result = []
    def add(name, edit=lambda m, f: None, criterion='F1', state='CONSISTENT', code=None, exit=0):
        m, f = base(refs)
        edit(m, f)
        result.append(dict(name=name, manifest=m, payloads=f,
          expected=dict(criterion=criterion, state=state, code=code, exit=exit, complete=False, physical_run=False)))
    add('seven-digest-positive')
    for index, name in enumerate(CASES):
        ref = refs[name]
        def obs(m): return m['observations'][index]
        def mutate_digest(m, f, digest, index=index, name=name, ref=ref):
            f[name+'.serial'] = f"SHA256 {digest} FRAMES {ref['frames']} RESULT 0\r\n".encode()
        add(name+'-wrong-pcm-digest', lambda m, f, fn=mutate_digest: fn(m, f, '0'*64), state='MISMATCH', code='f1_digest_mismatch', exit=1)
        add(name+'-wav-is-not-pcm', lambda m, f, fn=mutate_digest, ref=ref: fn(m, f, ref['wav']), state='MISMATCH', code='f1_digest_mismatch', exit=1)
        add(name+'-stream-positive', lambda m, f, index=index, name=name, ref=ref: (
            m['observations'][index].update(mode='stream', command=ref['command'].replace('golden','stream')),
            f.update({name+'.serial':stream(ref)})))
        def altered(m, f, index=index, name=name, ref=ref):
            p=bytearray(ref['pcm']);p[0]^=1
            bad=dict(ref, pcm=bytes(p))
            m['observations'][index].update(mode='stream', command=ref['command'].replace('golden','stream'))
            f[name+'.serial']=stream(bad) # file hash and device digest both follow changed sample
        add(name+'-altered-sample-rehashed', altered, state='MISMATCH', code='f1_stream_mismatch', exit=1)
        for delta in (-1, 1):
            add(name+f'-frames-{delta:+d}', lambda m, f, name=name, ref=ref, delta=delta: f.update({name+'.serial':
                f"SHA256 {sha(ref['pcm'])} FRAMES {ref['frames']+delta} RESULT 0\n".encode()}),
                state='MISMATCH', code='f1_frames_mismatch', exit=1)
        add(name+'-reference', lambda m, f, index=index:m['observations'][index].update(reference_wav_sha256='0'*64), state='MISMATCH',code='f1_reference_mismatch',exit=1)
        add(name+'-command', lambda m, f, index=index:m['observations'][index].update(command='golden B 1 1'),state='MISMATCH',code='f1_command_mismatch',exit=1)
        add(name+'-missing-case', lambda m, f, index=index:m['observations'].pop(index),state='NOT_RUN',code='f1_case_missing')
    first=CASES[0]
    add('bare-lf',lambda m,f:f.update({first+'.serial':f[first+'.serial'].replace(b'\r\n',b'\n')}))
    add('truncated-line',lambda m,f:f.update({first+'.serial':f[first+'.serial'].rstrip(b'\r\n')}),state='INVALID',code='transcript_truncated',exit=2)
    add('unknown-line',lambda m,f:f.update({first+'.serial':b'PRIVATE GUESS\n'+f[first+'.serial']}),state='INVALID',code='line_unknown',exit=2)
    add('duplicate-digest',lambda m,f:f.update({first+'.serial':f[first+'.serial']*2}),state='INVALID',code='transcript_malformed',exit=2)
    add('engine-error',lambda m,f:f.update({first+'.serial':f[first+'.serial'].replace(b'RESULT 0',b'RESULT -1')}),state='MISMATCH',code='f1_result_error',exit=1)
    add('scrub-is-not-f1',lambda m,f:m['observations'][0].update(case='scrub-forward'),state='INVALID',code='f1_case_unknown',exit=2)
    def truncated_stream(m,f):
        m['observations'][0].update(mode='stream',command=refs[first]['command'].replace('golden','stream'))
        f[first+'.serial']=b'PCM\r\n'+struct.pack('<I',3)+b'\0'*7
    add('truncated-stream-run',truncated_stream,state='INVALID',code='transcript_truncated',exit=2)
    def live(m,f,underruns):
        m['observations'][0].update(mode='live',command=' '.join(refs[first]['command'].replace('golden','live').split()[:3]))
        f[first+'.serial']=f'UNDERRUNS {underruns}\n'.encode()+f[first+'.serial']
    add('live-positive',lambda m,f:live(m,f,0))
    add('live-underrun',lambda m,f:live(m,f,1),state='MISMATCH',code='f1_underruns',exit=1)
    add('all-absent',lambda m,f:(m.update(observations=[]),f.clear()),state='NOT_RUN',code='observation_absent')
    add('declared-not-run',lambda m,f:(m.update(observations=[dict(id='nr',criterion='F1',provenance='not_run',sequence=1,reason='No target exists')]),f.clear()),state='NOT_RUN',code='not_run_declared')
    add('unrequested-failure-still-nonzero',lambda m,f:(m.update(requested=['F2']),f.update({first+'.serial':b'SHA256 '+b'0'*64+b' FRAMES 198450 RESULT 0\n'})),state='MISMATCH',code='f1_digest_mismatch',exit=1)
    add('mixed-simulated-remains-nonphysical',lambda m,f:m['session'].update(kind='physical'))
    add('simulation-actual-marker',lambda m,f:m['observations'][0].update(provenance='actual'),criterion=None,state='INVALID',code='provenance_conflict',exit=2)
    add('simulation-witness-marker',lambda m,f:m['session'].update(witness='SIMULATED; not a real witness'),criterion=None,state='INVALID',code='witness_on_simulation',exit=2)
    add('wrong-engine',lambda m,f:m['candidate'].update(engine_tree='0'*40),criterion=None,state='MISMATCH',code='engine_tree_mismatch',exit=1)
    add('wrong-toolchain',lambda m,f:m['candidate']['toolchain'].update(platformio='0'),criterion=None,state='MISMATCH',code='toolchain_mismatch',exit=1)
    add('duplicate-sequence',lambda m,f:m['observations'][1].update(sequence=1),criterion=None,state='INVALID',code='sequence_invalid',exit=2)
    add('dangling-supersede',lambda m,f:m['observations'][0].update(superseded_by='absent',supersede_reason='test'),criterion=None,state='INVALID',code='supersede_invalid',exit=2)
    for label,edit,state,code,exit in (
      ('positive',lambda m,f:None,'CONSISTENT',None,0),
      ('stack-zero',lambda m,f:f.update({'info.serial':f['info.serial'].replace(b'water 8192',b'water 0')}),'INVALID','f2_stack_invalid',2),
      ('stack-unaligned',lambda m,f:f.update({'info.serial':f['info.serial'].replace(b'water 8192',b'water 7')}),'INVALID','f2_stack_invalid',2),
      ('stack-over',lambda m,f:f.update({'info.serial':f['info.serial'].replace(b'water 8192',b'water 8196')}),'MISMATCH','f2_stack_exceeds',1),
      ('target-missing',lambda m,f:m['observations'][-1].update(transcript=None),'NOT_RUN','f2_stack_missing',0),
      ('instance-over-reserve',lambda m,f:f.update({'info.serial':f['info.serial'].replace(b'instance 191600',b'instance 191604')}),'MISMATCH','f2_instance_exceeds_reserve',1),
      ('reserve-conflict',lambda m,f:f.update({'info.serial':f['info.serial'].replace(b'reserve 191600',b'reserve 191604')}),'MISMATCH','f2_reserve_mismatch',1),
      ('bad-sum',lambda m,f:f.update({'size-gate.txt':size_gate(ram=191604)}),'MISMATCH','f2_ram_sum_mismatch',1),
      ('ram-over',lambda m,f:f.update({'size-gate.txt':size_gate(instance=204804)}),'MISMATCH','f2_static_fail',1),
      ('rodata-over',lambda m,f:f.update({'size-gate.txt':size_gate(rodata=32769)}),'MISMATCH','f2_static_fail',1),
      ('malformed-static',lambda m,f:f.update({'size-gate.txt':b'no map evidence\n'}),'INVALID','f2_static_malformed',2),
      ('candidate-conflict',lambda m,f:f.update({'SHA256SUMS':b'0'*64+b'  firmware.hex\n'}),'MISMATCH','candidate_conflict',1),
      ('stack-before-workload',lambda m,f:m['observations'][-1].update(sequence=0),'INVALID','f2_stack_before_workload',2),
    ):
        add('f2-'+label,lambda m,f,edit=edit:(add_f2(m,f),edit(m,f)),criterion='F2',state=state,code=code,exit=exit)
    add('f2-budget-boundaries',lambda m,f:(add_f2(m,f,instance=204800,reserve=204800),f.update({'size-gate.txt':size_gate(instance=204800,rodata=32768)})),criterion='F2')
    # No synthetic witness is supplied: a lawfully missing witness stays NOT_RUN.
    add('f5-no-fabricated-witness',add_f5,criterion='F5',state='NOT_RUN',code='f5_witness_missing')
    add('f5-position-does-not-advance',lambda m,f:(add_f5(m,f),f.update({'controls.serial':f['controls.serial'].replace(b'POSITION 20',b'POSITION 10')})),criterion='F5',state='MISMATCH',code='f5_position_not_increasing',exit=1)
    add('f5-removal-after-stop',lambda m,f:(add_f5(m,f),f.update({'controls.serial':f['controls.serial'].replace(b'UNMOUNT 0',b'STOP 0\nPOSITION 20\nUNMOUNT 0')})),criterion='F5',state='MISMATCH',code='f5_removal_not_mid_play',exit=1)
    add('f5-sequence-missing',lambda m,f:(add_f5(m,f),f.update({'controls.serial':b'CARD MOUNTED side A frames 100 label SIM\n'})),criterion='F5',state='NOT_RUN',code='f5_sequence_missing')
    for name,wire,state,reason,exit in (
      ('file-hash-mismatch','digest','MISMATCH','file_digest_mismatch',1),
      ('file-size-mismatch','size','MISMATCH','file_size_mismatch',1),
      ('file-missing','missing','INVALID','file_missing',2),
      ('file-unlisted','unlisted','INVALID','file_unlisted',2),
      ('unsafe-reference-path','unsafe','INVALID','path_unsafe',2),
      ('manifest-unknown-key','unknown','INVALID','field_unknown',2),
      ('manifest-missing','no-manifest','INVALID','manifest_missing',2),
      ('manifest-malformed','bad-json','INVALID','manifest_unreadable',2),
    ):
        add(name,criterion=None,state=state,code=reason,exit=exit)
        result[-1]['wire']=wire
    return result


def materialize(case, directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    m=copy.deepcopy(case['manifest'])
    for path,raw in case['payloads'].items():
        p=directory/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    m['files']=[dict(path=p,sha256=sha(b),bytes=len(b)) for p,b in sorted(case['payloads'].items())]
    wire=case.get('wire')
    if wire=='digest':m['files'][0]['sha256']='0'*64
    if wire=='size':m['files'][0]['bytes']+=1
    if wire=='missing':(directory/m['files'][0]['path']).unlink()
    if wire=='unlisted':(directory/'unlisted.raw').write_bytes(b'SIMULATED failed attempt\n')
    if wire=='unsafe':m['files'][0]['path']='../outside.raw'
    if wire=='unknown':m['unrecognized_typo']=True
    (directory/'manifest.json').write_text(json.dumps(m,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    if wire=='no-manifest':(directory/'manifest.json').unlink()
    if wire=='bad-json':(directory/'manifest.json').write_bytes(b'{truncated')
    return m
