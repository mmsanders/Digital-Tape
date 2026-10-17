"""Authoring decoder crosscheck: exact lossless samples and declared raw counts.
Not candidate acceptance and not a universal lossy waveform golden.
"""
import argparse, concurrent.futures, json
from pathlib import Path
import numpy as np
import fixtures, model, formats

def run(root):
    root=Path(root);facts=json.loads((root/'SOURCES.json').read_text(encoding='utf-8'))
    def check(item):
        name,f=item;data=(root/f['path']).read_bytes();assert model.digest(data)==f['sha256'],name
        if f.get('ruling_required'):return {'asset':name,'check':'PENDING_CONTRACT_RULING','finding':f['ruling_required']}
        if f.get('family')=='large-boundary':return {'asset':name,'check':'exact-sparse-PCM-size/hash','frames':f['raw_frames']}
        if f.get('refuse'):return {'asset':name,'check':'hash-only-refusal-fixture'}
        if f.get('container_bits'):
            from scipy.io import wavfile
            rate,q=wavfile.read(root/f['path']);x=q.astype(float).reshape(-1,f['input_channels'])/2**31
            expected=fixtures.signal(rate,f['raw_frames'],f['input_channels']);expected=np.rint(expected*2**(f['bits']-1))/2**(f['bits']-1)
            assert rate==f['input_rate'] and np.array_equal(x,expected),name
            reference=fixtures.decode(root/f['path'],f['input_channels'])
            return {'asset':name,'check':'exact-lossless-samples-independent-WAVE-reader','frames':len(x),'FFmpeg6.1_reference_limitation_frames':len(reference),'note':'container alignment/valid precision; FFmpeg bytes are not an oracle'}
        if name.startswith(('zero-192','positive-192','tie-88200')):pass
        x=fixtures.decode(root/f['path'],f['input_channels'],manual=True,ignore_edit=f['container']=='bmff')
        assert len(x)==f['raw_frames'],(name,len(x),f['raw_frames'])
        assert np.isfinite(x).all(),name
        if f.get('family')=='qualification':
            import qualification,numerics
            key=f['qualification_metric']
            observed=numerics.loudness(x) if key=='lufs' else numerics.peak(x)
            qualification.check(f,{'input_lufs':observed if key=='lufs' else None,'input_dbtp':observed if key=='dbtp' else None})
        if name.startswith('minimal-adts-'):assert formats.validate_generated_adts(data)==f['raw_frames']
        if f.get('lossy'):return {'asset':name,'check':'raw-count','frames':len(x)}
        if f.get('family'):return {'asset':name,'check':'finite-and-count','frames':len(x)}
        y=fixtures.signal(f['input_rate'],f['raw_frames'],f['input_channels'])
        if f['codec']=='pcm' or f['codec']=='flac':y=np.rint(y*2**(f['bits']-1))/2**(f['bits']-1)
        elif f['bits']==32:y=y.astype('f4').astype('f8')
        assert np.array_equal(x,y),(name,float(np.max(abs(x-y))))
        return {'asset':name,'check':'exact-lossless-samples','frames':len(x)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:return list(pool.map(check,sorted(facts.items())))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('--out',required=True);a=ap.parse_args()
    rows=run(a.root);Path(a.out).write_text(json.dumps(rows,indent=2)+'\n');print(len(rows),'fixture hashes/counts checked')
