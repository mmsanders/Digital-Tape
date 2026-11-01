"""Streaming exact all-zero RIFF boundary check; no multi-GiB float allocation."""
import hashlib,json,struct
import audit,model

class LengthOnly:
    def __init__(self,n):self.n=n
    def __len__(self):return self.n

def check(wav_path,raw_manifest,fact,logical_name,seconds,before,joined_peak):
    frames=model.admitted_output_frames(logical_name,fact['effective_frames'],fact['input_rate'])
    count=4*frames
    audit.require(count+36<=0xFFFFFFFF,'capacity','RIFF overflow')
    audit.require(wav_path.stat().st_size==44+count,'count','large WAV length')
    header=struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',count+36,b'WAVE',b'fmt ',16,1,2,44100,176400,4,16,b'data',count)
    digest=hashlib.sha256()
    with wav_path.open('rb') as inp:
        actual=inp.read(44);audit.require(actual==header,'wav','large canonical header');digest.update(actual)
        while block:=inp.read(1024*1024):
            audit.require(block.count(0)==len(block),'silence','nonzero large payload');digest.update(block)
    f=dict(fact,source_sha256=fact['sha256'])
    try:m=model.check_manifest(raw_manifest,LengthOnly(count),[f],[[logical_name]],seconds,wav_sha256=digest.hexdigest())
    except (AssertionError,ValueError,KeyError,TypeError) as e:raise audit.Failure('manifest',str(e)) from e
    s=m['sources'][0]
    audit.require(s['loudness_status']=='digital_silence' and s['applied_gain_db']=='0.000000' and not s['peak_limited'] and s['loudness_reason'] is None,'silence','large zero status')
    audit.require(all(s[k] is None for k in ('input_lufs','input_dbtp','output_lufs','output_dbtp')) and joined_peak is None,'silence','large zero meters')
    audit.require(before=={'kind':'entire-zero','frames':frames},'conversion','large zero observation')
    return raw_manifest,('VERIFIED_ZERO_PCM',frames,digest.hexdigest())
