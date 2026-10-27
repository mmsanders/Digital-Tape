"""Expand the six coherent INGEST-1 rows; descriptors are not candidate results."""
import argparse,json
from pathlib import Path
import model
ROWS={
 'R1':'I1/I8 byte-detected full codec/rate/channel matrix and strict refusals',
 'R2':'I2/I3 isolated SRC, mono, exact dither, calibration, constant gain and exceptions',
 'R3':'I4 explicit trim, joins, silence gaps and source isolation',
 'R4':'I5/I6 natural ordering, canonical manifest and deterministic identities',
 'R5':'I7 source admission, exact capacity and RIFF arithmetic',
 'R6':'I7/I8 native preflight, source binding, pair transaction and licence census'}

def expand(facts):
    cases=[]
    def add(id,row,folders=None,seconds=60,exit=0,**kw):
        cases.append(dict(id=id,row=row,folders=folders or [],seconds=seconds,expected_exit=exit,**kw))
    def file(asset,name=None):return dict(asset=asset,name=name or asset)
    for name,f in sorted(facts.items()):
        if f.get('family') in ('unsafe-join','large-boundary'):continue # tested as pair plus individual below
        bad=f.get('refuse') or not model.output_frames(f.get('effective_frames',1),f.get('input_rate',44100))
        row='R1' if not f.get('family') else 'R2'
        if name in ('zero-192-n1.wav','zero-192-n2.wav','positive-192-n3.wav','tie-88200.wav'):row='R5'
        seconds=max(60,(model.output_frames(f.get('effective_frames',1),f.get('input_rate',44100))+44099)//44100+1)
        add('asset/'+name,row,[[file(name)]],seconds=seconds,exit=2 if bad else 0,checks=['manifest','audio','native-preflight'] if not bad else ['named-refusal','no-output-open'])
        if name.startswith('sowt-') and f.get('refuse'):
            positive=name.rsplit('-',1)[0]+'-16.aif'
            add('adr180/neighbour/'+name,'R1',[[file(positive,'1.aif'),file(name,'2.aif')]],exit=2,diagnostic='2.aif: sowt16-only; whole request refuses')
    for bad,good in [('adts-crc-mismatch-1.aac','minimal-adts-1-crc.aac'),('adts-crc-mismatch-2.aac','minimal-adts-2-crc.aac'),('bad-fdk-crc-1.aac','fdk-crc-1.aac'),('bad-fdk-crc-2.aac','fdk-crc-2.aac'),('adts-multiblock.aac','minimal-adts-1-plain.aac'),('tag-crc-invalid.mp3','tag-crc-lame.mp3'),('short-stts-alone.m4a','aac-44100-2.m4a'),('short-stts-conflict.m4a','aac-44100-2.m4a')]:
        add('adr180/neighbour/'+bad,'R1',[[file(good,'1'+Path(good).suffix),file(bad,'2'+Path(bad).suffix)]],exit=2,diagnostic='last source named; no output/staging')
    add('trim/outside-neighbour','R1',[[file('short-trim.mp3','1.mp3'),file('trim-outside.mp3','2.mp3')]],exit=2,diagnostic='2.mp3: trim outside decoded interval; whole request refuses')
    add('bytes/renamed-wave','R1',[[file('wave-44100-2-16.wav','music.bin')]])
    add('bytes/renamed-mp3','R1',[[file('mp3-44100-2-vbr.mp3','music.wav')]])
    add('bytes/unsupported-suffix-wave','R1',[[file('wave-44100-2-16.wav','music.w64')]])
    add('bytes/supported-suffix-outside','R1',[[file('wave64.w64','music.wav')]],exit=2)
    add('joins/unsafe','R3',[[file('join-plus.wav','1.wav'),file('join-minus.wav','2.wav')]],exit=2,diagnostic='boundary/source true peak')
    for name in ('join-plus.wav','join-minus.wav'):add('joins/isolated-'+name,'R3',[[file(name)]])
    add('joins/sources','R3',[[file('ordinary.wav','1.wav'),file('short.wav','2.wav'),file('ordinary.wav','3.wav')]],checks=['standalone-segment-identity','joined-peak'])
    add('joins/folder-gaps','R3',[[file('ordinary.wav')],[file('silence.wav')],[file('short.wav')]],checks=['exact-88200-zero-gaps','standalone-segment-identity'])
    add('trim/repeated-mp3','R3',[[file('mp3-44100-2-vbr.mp3','1.mp3'),file('mp3-44100-2-vbr.mp3','2.mp3')]],checks=['trim-once','standalone-segment-identity','bounded-fidelity'])
    add('trim/repeated-bmff','R3',[[file('aac-44100-2.m4a','1.m4a'),file('aac-44100-2.m4a','2.m4a')]],checks=['trim-once','standalone-segment-identity','bounded-fidelity'])
    names=['10.wav','2.wav','02.wav','1.wav','A02.wav','a2.wav','é.wav','٢.wav','x'+('9'*80)+'.wav','x'+('1'+'0'*80)+'.wav']
    add('order/numeric-unicode','R4',[[file('short.wav',v) for v in reversed(names)]],native_names='refuse if set unrepresentable; distinct representable subset also required')
    add('order/folder-argv','R4',[[file('ordinary.wav','z.wav')],[file('short.wav','a.wav')]],checks=['argv-order'])
    for mode in ('repeat','relocate','different-target','standalone-versus-batch','cross-os'):
        add('identity/'+mode,'R4',[[file('ordinary.wav')]],relation=mode,checks=['wav-identical','manifest-identical except target_seconds/capacity_frames for different-target','same-profile'])
    add('capacity/exact','R5',[[file('exact-one-second.wav')]],seconds=1)
    add('capacity/one-over','R5',[[file('one-frame-over.wav')]],seconds=1,exit=2,diagnostic='1 frame;00:01')
    add('capacity/gap-exact','R5',[[file('exact-one-second.wav')],[file('exact-one-second.wav')]],seconds=4)
    add('capacity/gap-one-over','R5',[[file('exact-one-second.wav')],[file('one-frame-over.wav')]],seconds=4,exit=2,diagnostic='1 frame;00:01')
    for name in ('zero-192-n1.wav','zero-192-n2.wav'):
        add('zero/positive-neighbour-'+name,'R5',[[file(name),file('ordinary.wav')]],exit=2,diagnostic=name+': too short')
        add('zero/gap-rescue-'+name,'R5',[[file(name)],[file('ordinary.wav')]],exit=2,diagnostic=name+': too short')
    add('capacity/riff-overflow','R5',[[file('riff-overflow-source.wav')]],seconds=30000,exit=2,recipe='sparse signedPCM16 mono7350;178956970 frames;RIFF source valid;output1073741820 frames over uint32 RIFF size')
    add('capacity/riff-largest-legal','R5',[[file('riff-largest-source.wav')]],seconds=30000,exit=0,recipe='178956969 mono7350 zero frames;1073741814 output frames;4294967300-byte canonical WAV, RIFF size4294967292;stream checked, not allocated in RAM')
    refusals={
      'folder-missing':'missing folder','folder-empty':'empty folder','folder-duplicate':'same filesystem identity by different path',
      'folder-symlink':'folder symlink','file-symlink':'immediate symlink','nested-directory':'immediate subdirectory',
      'hidden-file':'unsupported .DS_Store','artwork':'unsupported cover.jpg','invalid-unicode':'native invalid Unicode/unrepresentable name',
      'nfc-collision':'é.wav and e+combining acute.wav normalize to same path','case-unrepresentable':'set unrepresentable on native filesystem',
      'dest-exists':'preexisting DEST with unrelated sentinel; preserve it',
      'syntax-missing-out':'omit --out','syntax-zero-length':'--length0','syntax-negative-length':'--length-1','syntax-fractional-length':'--length1.5','syntax-overflow-length':'unbounded integer overflow',
      'unknown-option':'unknown flag'}
    for id,description in refusals.items():add('native/'+id,'R6',[[file('short.wav')]],exit=2,scenario='preflight-refusal',setup=description)
    for id in ('help','version'):add('cli/'+id,'R6',exit=0,scenario='informational',setup='--'+id+'; no output creation;version includes profile')
    for scenario,exit_ in [('success',0),('mutation',2),('concurrent-dest',[1,2]),('write-error',1),('kill',None)]:
        add('transaction/'+scenario,'R6',[[file('ordinary.wav')]],exit=exit_,scenario=scenario,setup='native observation at each declared cut; raw evidence required')
    for cut in ('before-stage','audio-open','audio-flush','manifest-open','manifest-flush','before-publish','after-publish'):
        add('kill/'+cut,'R6',[[file('ordinary.wav')]],exit=None,scenario='kill',cut=cut,setup='kill at named event;after-publish allows COMPLETE pair only')
    for fault in ('read-open','decode-read','stage-create','audio-write','audio-flush','manifest-write','manifest-flush','publish'):
        add('io-error/'+fault,'R6',[[file('ordinary.wav')]],exit=1,scenario='write-error',cut=fault,setup='native error at actual operation;no pair;clean only own stage')
    add('resources/exhaustion','R6',[[file('ordinary.wav')]],exit=1,scenario='write-error',setup='bounded memory exhaustion;no disk scratch or published output')
    assert len({c['id'] for c in cases})==len(cases)
    return cases

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('sources',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    cases=expand(json.loads(a.sources.read_text(encoding='utf-8')));a.out.write_bytes(model.canonical({'rows':ROWS,'cases':cases}));print(len(cases),'expanded case descriptors')
