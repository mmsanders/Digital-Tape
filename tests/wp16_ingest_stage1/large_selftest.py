"""Exercise actual >4GiB verifier file handling, not a Product/card test."""
import argparse,json,struct,tempfile
from pathlib import Path
import asset,audit,large,model

def run():
    n=178956969;out=model.output_frames(n,7350);assert out==1073741814
    assert out*4+36<=0xFFFFFFFF and model.output_frames(n+1,7350)*4+36>0xFFFFFFFF
    header=struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',out*4+36,b'WAVE',b'fmt ',16,1,2,44100,176400,4,16,b'data',out*4)
    f={'sha256':'0'*64,'container':'wave','codec':'pcm','codec_profile':'pcm','input_rate':7350,'input_channels':1,'raw_frames':n,'trim_head':0,'trim_tail':0,'trim_evidence':'none','effective_frames':n}
    s={k:v for k,v in f.items() if k!='sha256'};s.update(source_sha256=f['sha256'],logical_path='0/zero.wav',output_frames=out,start_frame=0,input_lufs=None,input_dbtp=None,output_lufs=None,output_dbtp=None,target_gain_db=None,applied_gain_db='0.000000',peak_limited=False,loudness_status='digital_silence',loudness_reason=None,gapless_status='gapless_known')
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'audio.wav'
        with p.open('wb') as stream:stream.write(header);stream.seek(44+out*4-1);stream.write(b'\0')
        assert p.stat().st_size==4294967300
        m={'schema':1,'contract':'INGEST-1','tool_version':'synthetic-reference','build_profile':'ref','libraries':{'reference':'1'},'resampler_profile':'ref_fir_a','meter_profile':'ref','dither_profile':'INGEST-1','target_seconds':30000,'capacity_frames':30000*44100,'total_frames':out,'wav_sha256':asset.sha_file(p),'folders':[{'ordinal':0,'source_count':1}],'sources':[s],'gaps':[]}
        raw=model.canonical(m);before={'kind':'entire-zero','frames':out}
        large.check(p,raw,f,'zero.wav',30000,before,None)
        with p.open('r+b') as stream:stream.seek(-1,2);stream.write(b'\1')
        try:large.check(p,raw,f,'zero.wav',30000,before,None)
        except audit.Failure as e:assert e.gate=='silence'
        else:raise AssertionError('nonzero last byte escaped')
    return {'result':'PASS','actual_wav_bytes':4294967300,'source_frames':n,'output_frames':out,'controls':['nonzero-final-byte'],'scope':'verifier sparse-file selftest only; no Product/native/card acceptance'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path);a=p.parse_args();r=run()
    if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r))
