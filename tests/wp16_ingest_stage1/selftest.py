"""Green reference observations plus causal defects. Not Product acceptance."""
import argparse, copy, json, math
from pathlib import Path
import numpy as np
import audit as a, model as m, numerics as n, fixtures, formats


def metadata(x,pcm,g):
    q=np.frombuffer(pcm,dtype='<i2').reshape(-1,2)/32768
    il=n.loudness(x);ol=n.loudness(q);ip=n.peak(x);op=n.peak(q)
    target=None if il is None else -16-il
    silence=not np.any(x)
    return dict(input_lufs=m.fixed(il),output_lufs=m.fixed(ol),input_dbtp=m.fixed(ip),output_dbtp=m.fixed(op),
        applied_gain_db=m.fixed(g),target_gain_db=m.fixed(target),peak_limited=target is not None and g<target-.000002,
        loudness_status='digital_silence' if silence else 'unmeasurable' if ol is None else 'measured',
        loudness_reason=None if silence or ol is not None else 'too_short' if len(x)<17640 else 'gated_out')


def run():
    records=[]
    def positive(label,fn):
        fn();records.append(dict(id=label,result='PASS',kind='green-baseline'))
    def catch(label,gate,fn):
        try:fn()
        except a.Failure as e:
            assert e.gate==gate,(label,e.gate,str(e))
            records.append(dict(id=label,result='DETECTED',gate=gate,kind='causal-control'));return
        raise AssertionError('missed causal control '+label)
    source=fixtures.signal(44100,22050)
    pcm,ref=n.reference_source(source,44100,'ref_fir_a');meta=metadata(source,pcm,ref['gain'])
    positive('finite-gain-baseline',lambda:a.audio(source,pcm,meta,original=source))
    # Compressor modifies actual PCM; recompute honest meters so only signal gate catches.
    q=source*10**(ref['gain']/20);bad=m.quantize(np.tanh(q*3)/3)
    catch('compressor','constant-gain',lambda:a.audio(source,bad,metadata(source,bad,ref['gain']),original=source))
    tone=n.tone(44100,22050,11025,.5,np.pi/4)
    p,r=n.reference_source(tone,44100,'ref_fir_a');positive('intersample-safe-baseline',lambda:a.audio(tone,p,metadata(tone,p,r['gain'])))
    sampleg=-1.1-20*np.log10(np.max(abs(tone)));bad=m.quantize(tone*10**(sampleg/20))
    catch('sample-peak-only','peak',lambda:a.audio(tone,bad,metadata(tone,bad,sampleg)))
    crest=fixtures.signal(44100,22050)*.01;crest[11025]=[.8,-.8]
    p,r=n.reference_source(crest,44100,'ref_fir_a');positive('peak-limited-baseline',lambda:a.audio(crest,p,metadata(crest,p,r['gain'])))
    # Fault forces amplitude toward the loudness target, crossing the ceiling.
    forceg=20*np.log10(.96/.8);bad=m.quantize(crest*10**(forceg/20))
    catch('force-target-above-ceiling','peak',lambda:a.audio(crest,bad,metadata(crest,bad,forceg)))
    for label,x in [('short',fixtures.signal(44100,17)),('gated',fixtures.signal(44100,22050)*1e-5),('silence',np.zeros((64,2)))]:
        p,r=n.reference_source(x,44100,'ref_fir_a');positive(label+'-baseline',lambda x=x,p=p,r=r:a.audio(x,p,metadata(x,p,r['gain'])))
    zeros=np.zeros((64,2));noisy=bytearray(bytes(256));noisy[0]=1
    catch('noisy-digital-silence','silence',lambda:a.audio(zeros,bytes(noisy),metadata(zeros,bytes(noisy),0)))
    dyadic=np.array([[0,.25],[.125,-.125],[-.25,0],[.0625,.1875]]*16)
    p=m.quantize(dyadic);dmeta=metadata(dyadic,p,0)
    positive('exact-stereo-dither-baseline',lambda:a.audio(dyadic,p,dmeta,exact=True))
    bad=m.quantize(dyadic,seed=1)
    catch('shared-dither-state','dither',lambda:a.audio(dyadic,bad,metadata(dyadic,bad,0),exact=True))
    mono=dyadic[:,:1];stereo=np.repeat(mono,2,axis=1);p=m.quantize(stereo,mono=True)
    positive('exact-mono-dither-baseline',lambda:a.audio(stereo,p,metadata(stereo,p,0),mono=True,exact=True))
    bad=m.quantize(stereo)
    catch('independent-mono-draws','mono',lambda:a.audio(stereo,bad,metadata(stereo,bad,0),mono=True))
    positive('reset-identity-baseline',lambda:a.identity(p,p,p))
    catch('shared-filter-meter-state','identity',lambda:a.identity(p,p[:-4]+bytes(4),p))
    # Source intervals and folder gaps independently derived, not checked by hash alone.
    facts=[dict(source_sha256='0'*64,input_rate=44100,input_channels=2,raw_frames=64,trim_head=0,trim_tail=0,trim_evidence='none',effective_frames=64)]*2
    gap=bytes(m.GAP*4);payload=p+gap+p
    sources=[]
    for i,start in enumerate((0,64+m.GAP)):
        sources.append(dict(facts[i],logical_path=str(i)+'/s.wav',container='wave',codec='float',codec_profile='float',output_frames=64,start_frame=start,gapless_status='gapless_known',**metadata(stereo,p,0)))
    obj=dict(schema=1,contract='INGEST-1',tool_version='independent-reference',build_profile='ref',libraries={'numpy':'2.3.5'},resampler_profile='ref_fir_a',meter_profile='independent-16x',dither_profile='INGEST-1-xorshift32',target_seconds=10,capacity_frames=441000,total_frames=128+m.GAP,wav_sha256=m.digest(m.wav(payload)),folders=[{'ordinal':0,'source_count':1},{'ordinal':1,'source_count':1}],sources=sources,gaps=[{'start_frame':64,'frames':m.GAP}])
    def check(o=obj,rawpcm=payload):a.manifest(m.canonical(o),rawpcm,facts,[['s.wav'],['s.wav']],10)
    positive('manifest-two-folders-baseline',check)
    for label,change in [
        ('guessed-trim',lambda o:o['sources'][0].update(trim_head=1)),
        ('double-trim',lambda o:o['sources'][0].update(effective_frames=63,output_frames=63)),
        ('missed-frame',lambda o:o['sources'][0].update(output_frames=63)),
        ('extra-frame',lambda o:o['sources'][0].update(output_frames=65)),
        ('metadata-drift',lambda o:o['sources'][0].update(source_sha256='1'*64)),
        ('volatile-manifest-metadata',lambda o:o.update(timestamp='2026-10-15T00:00:00Z')),
        ('absolute-manifest-path',lambda o:o.update(input_root='/private/input')),
        ('noninteger-folder-count',lambda o:o['folders'][0].update(source_count=True)),
        ('noninteger-gap-count',lambda o:o['gaps'][0].update(frames=float(m.GAP))),
        ('global-folder-sort',lambda o:o['sources'].reverse()),
        ('source-omission',lambda o:o['sources'].pop()),
        ('gap-omission',lambda o:o.update(gaps=[]))]:
        bad=copy.deepcopy(obj);change(bad);catch(label,'manifest',lambda bad=bad:check(bad))
    bad=bytearray(payload);bad[64*4]=1;o=copy.deepcopy(obj);o['wav_sha256']=m.digest(m.wav(bad))
    catch('noisy-folder-gap','manifest',lambda:check(o,bytes(bad)))
    catch('noncanonical-json','manifest',lambda:a.manifest(json.dumps(obj).encode(),payload,facts,[['s.wav'],['s.wav']],10))
    expected=['1','02','2','10','A','a','é','٢']
    assert m.natural(list(reversed(expected)))==expected
    positive('unicode-natural-comparator',lambda:None)
    require_order=lambda actual:a.require(actual==expected,'order','comparator mismatch')
    catch('locale-lexical-sort','order',lambda:require_order(sorted(expected)))
    base=dict(complete=True,raw_trace_sha256='a'*64,observer_selftest=True,scenario='success',exit=0,dest_after=['audio.wav','manifest.json'],owned_stage_after=False,raw_review='PASS')
    operations=['preflight_complete','sources_revalidated','stage_create','output_open','audio_flush_close','manifest_flush_close','publish_dir_noreplace']
    base['events']=[dict(seq=i,op=k,exclusive=True,adjacent=True) for i,k in enumerate(operations)]
    positive('pair-transaction-baseline',lambda:a.transaction(base))
    bad=copy.deepcopy(base);bad['events'][-1]['op']='publish_file'
    catch('half-published-output','pair',lambda:a.transaction(bad))
    bad=copy.deepcopy(base);bad['events'][0]['op'],bad['events'][2]['op']=bad['events'][2]['op'],bad['events'][0]['op']
    catch('preflight-output-open','preflight',lambda:a.transaction(bad))
    bad=copy.deepcopy(base);bad.update(scenario='mutation',exit=2,dest_after=[])
    catch('source-mutation-undetected','mutation',lambda:a.transaction(bad))
    bad=copy.deepcopy(base);bad['complete']=False
    catch('truncated-observer','trace',lambda:a.transaction(bad))
    # Both alternate filters retain standalone/batch/repeat identity and exact count;
    # independently assess transition ends and interior impulse latency/energy.
    for profile in n.FILTERS:
        for rate in (8000,44100,48000,192000):
            x=fixtures.signal(rate,rate//20)
            alone,r=n.reference_source(x,rate,profile)
            batch,_=n.reference_source(x,rate,profile);repeat,_=n.reference_source(x,rate,profile)
            positive(profile+'-reset-'+str(rate),lambda:a.identity(alone,batch,repeat))
            assert len(alone)//4==m.output_frames(len(x),rate)
            for at in (0,len(x)-1,len(x)//2):
                z=np.zeros_like(x);z[at]=[.25,-.125];y=n.resample(z,rate,profile)
                assert len(y)==m.output_frames(len(z),rate)
                if at==len(x)//2:assert abs(np.argmax(abs(y[:,0]))-at*44100/rate)<=1
    # Each isolated constant is safe; the unmodified neighbouring step is unsafe.
    plus=np.full((64,2),.7);minus=-plus
    pa,ra=n.reference_source(plus,44100,'ref_fir_a');pb,rb=n.reference_source(minus,44100,'ref_fir_a')
    positive('safe-isolated-join-left',lambda:a.joined(pa));positive('safe-isolated-join-right',lambda:a.joined(pb))
    catch('unsafe-joined-boundary','join-peak',lambda:a.joined(pa+pb))
    # No filter bytes are universal: each path satisfies the numerical predicate.
    for profile in n.FILTERS:
        x=n.tone(96000,192000,23000,.25);y=n.resample(x,96000,profile)
        positive(profile+'-alias-baseline',lambda:a.quality(y,96000,23000,.25))
    bad=n.tone(44100,88200,21100,.25)
    catch('alias-filter-bypass','src-quality',lambda:a.quality(bad,96000,23000,.25))
    return records

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path);a_=ap.parse_args();rows=run()
    if a_.out:a_.out.write_text(json.dumps(rows,indent=2)+'\n')
    print(len(rows),'baseline/control observations PASS (not Product acceptance)')
