"""ADR180 causal format/interval controls with admitted neighbours."""
import argparse,json,struct
from pathlib import Path
import numpy as np
import formats,model

def run(root=None):
    results=[]
    def ok(name,fn):fn();results.append({'id':name,'result':'GREEN'})
    def bad(name,fn):
        try:fn()
        except (ValueError,AssertionError):results.append({'id':name,'result':'DETECTED'});return
        raise AssertionError('escaped '+name)
    for bits in (8,16,24,32):
        for comp in (None,b'NONE',b'sowt'):
            data=formats.aiff(np.zeros((256,1)),11025,bits,comp)
            fn=lambda data=data:formats.aifc_precision(data)
            if comp==b'sowt' and bits!=16:bad('sowt-non16-'+str(bits),fn)
            else:ok('aiff-scope-'+str(comp)+'-'+str(bits),fn)
    for ch in (1,2):
        for protected in (False,True):
            data=formats.adts_silence(protected,channels=ch)
            ok('adts-positive-%s-%s'%(ch,protected),lambda data=data:formats.validate_generated_adts(data))
            if protected:
                defect=bytearray(data);defect[8]^=1
                bad('adts-crc-byte-only-'+str(ch),lambda defect=defect:formats.validate_generated_adts(defect))
        defect=bytearray(formats.adts_silence(False,channels=ch));defect[6]|=1
        bad('adts-multiblock-'+str(ch),lambda defect=defect:formats.validate_generated_adts(defect))
    if root:
        root=Path(root);facts=json.loads((root/'SOURCES.json').read_text(encoding='utf-8'))
        for name in ('tag-crc-lame.mp3','tag-crc-ffmpeg.mp3'):
            data=(root/facts[name]['path']).read_bytes()
            ok(name,lambda data=data:formats.mp3_interval(data))
            defect=bytearray(data);s,length,p=formats.mp3_tag_location(defect);defect[p+35]^=1
            bad(name+'-crc-corruption',lambda defect=defect:formats.mp3_interval(defect))
        data=(root/facts['short-trim.mp3']['path']).read_bytes();ok('short-MP3-valid-trim',lambda:formats.mp3_interval(data))
        for name in ('trim-outside.mp3','xing-count.mp3'):
            data=(root/facts[name]['path']).read_bytes();bad(name,lambda data=data:formats.mp3_interval(data))
        for name in ('aac-44100-2.m4a','no-edit.m4a'):
            data=(root/facts[name]['path']).read_bytes();ok('bmff-positive-'+name,lambda data=data:formats.bmff_presentation(data))
        for name in ('short-stts-alone.m4a','short-stts-conflict.m4a','edit-negative.m4a','edit-fractional.m4a','edit-zero.m4a','edit-outside.m4a','edit-multiple.m4a','edit-rate.m4a'):
            data=(root/facts[name]['path']).read_bytes();bad(name,lambda data=data:formats.bmff_presentation(data))
        assert sum(name.startswith('sowt-') and f.get('refuse',False) for name,f in facts.items())==90
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sources');p.add_argument('--out',type=Path);a=p.parse_args();rows=run(a.sources)
    if a.out:a.out.write_text(json.dumps(rows,indent=2)+'\n')
    print(len(rows),'format baseline/control observations PASS')
