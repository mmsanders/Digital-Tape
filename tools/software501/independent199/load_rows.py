"""Available host-load PCM/state predicates on actual corrected command records.

No full projected-image replay; prior binding/source/image facts carry. Actual
complete-history projections remain projections, not interrupted host executions.
"""
import argparse,collections,hashlib,json,struct
from pathlib import Path
import rows as R
VOICE='ee38bd19bcaa50ac1e42da7a9e630e65706793767814d3afabe9dca992decfc4'
def digest(b):return hashlib.sha256(b).hexdigest()
def wav(pcm):return b'RIFF'+struct.pack('<I',36+len(pcm))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,2,44100,176400,4,16)+b'data'+struct.pack('<I',len(pcm))+pcm
EMPTY=digest(wav(b''))
def check(o):
    pair=[]
    for side in ('A','B'):
        d=o['dump_'+side];assert d['exit']==0 and d['wav_sha256'] in (EMPTY,VOICE)
        assert d['image_sha256_before']==o['projection_sha256']
        assert all(e.get('cold') is True for e in d['engine'] if e['kind']=='engine_mount')
        pair.append('new' if d['wav_sha256']==VOICE else 'empty')
    assert pair!=['new','empty'],'A committed without the live source B timeline'
    v=o['verify'];assert v['exit']==0 and v['stdout']=='OK\n' or v['exit']==1 and v['stdout']=='NEEDS_REPAIR\n'
    assert v['image_sha256_before']==o['projection_sha256'] and v['image_sha256_after']==o['projection_sha256']
    assert all(e['write_is_null'] for e in v['engine'] if e['kind']=='engine_bind')
    assert all(e['result']=='TAPE_OK' for e in v['engine'] if e['kind']=='engine_mount')
    return '/'.join(pair)
def run(root,out):
    assert digest((R.ROOT/'tests/golden/src/voice.wav').read_bytes())==VOICE
    r={'scope':'bounded actual hash-bound source PCM/pair/publication states; no missing fault execution or full repair-event proof','command_contexts':0,'states':collections.Counter(),'complete_controls':0,'failures':[],'causal_control':{}};first=None
    for part in sorted(root.glob('wp10-subset-load-*/load/part-*')):
      obs={o['projection_sha256']:o for o in R.lines(part/'remounts.jsonl')}
      for o in obs.values():
        try:r['states'][check(o)]+=1;r['command_contexts']+=1;first=o if first is None else first
        except Exception as e:r['failures'].append({'part':str(part.relative_to(root)),'image':o['projection_sha256'],'error':str(e)})
      for run in R.lines(part/'runs.jsonl'):
        if run.get('label')=='complete' and 'trace' in run:
            for q in run['projections']:
                assert check(obs[q['image_sha256']])=='new/new';r['complete_controls']+=1
    if first:
        bad=json.loads(json.dumps(first));bad['dump_A']['wav_sha256']=VOICE;bad['dump_B']['wav_sha256']=EMPTY
        try:check(bad)
        except Exception as e:r['causal_control']['impossible-pair']='REJECTED: '+str(e)
        else:r['causal_control']['impossible-pair']='UNDETECTED'
    r['states']=dict(r['states']);out.write_text(json.dumps(r,indent=2)+'\n');print(r)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.root,a.out)
