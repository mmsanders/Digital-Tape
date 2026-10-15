"""Causal controls for completed observation/transfer/qualification gates."""
import argparse,copy,json,struct
from pathlib import Path
import numpy as np
from scipy import signal
import audit,conversion,fixtures,model,numerics,qualification,relations,review,filter_bounds
from selftest import metadata

def run():
    rows=[]
    def green(id_,fn):fn();rows.append({'id':id_,'result':'GREEN'})
    def red(id_,gate,fn):
        try:fn()
        except audit.Failure as e:
            assert e.gate==gate,(id_,e.gate);rows.append({'id':id_,'result':'DETECTED','gate':gate});return
        raise AssertionError('missed '+id_)
    rate=48000;x=fixtures.signal(rate,9600);lead=fixtures.signal(rate,4800)
    for profile in numerics.FILTERS:
        p=numerics.FILTERS[profile];up=147;down=160;half=p['width']*max(up,down)
        h=signal.firwin(2*half+1,p['cutoff']/max(up,down),window=('kaiser',p['beta']))*up
        expected=conversion.fir(x,rate,{'coefficients':h,'first_highrate_index':half})
        actual=numerics.resample(x,rate,profile)
        green(profile+'-independent-FIR',lambda:conversion.compare(actual,expected))
        shared=numerics.resample(np.concatenate((lead,x)),rate,profile)[4410:]
        red(profile+'-shared-resampler-tail','conversion',lambda:conversion.compare(shared,expected))
        red(profile+'-missed-frame','count',lambda:conversion.compare(actual[:-1],expected))
        red(profile+'-extra-frame','count',lambda:conversion.compare(np.concatenate((actual,actual[-1:])),expected))
    x=fixtures.signal(44100,22050);lufs=numerics.loudness(x)
    pcm,ref=numerics.reference_source(x,44100,'ref_fir_a');m=metadata(x,pcm,ref['gain'])
    green('meter-isolated',lambda:audit.audio(x,pcm,m,original=x))
    history=fixtures.signal(44100,22050)*.01
    wrong=copy.deepcopy(m);wrong['input_lufs']=model.fixed(numerics.loudness(np.concatenate((history,x))))
    red('shared-meter-history','meter',lambda:audit.audio(x,pcm,wrong,original=x))
    f={'qualification_metric':'lufs','qualification_expected':lufs}
    green('candidate-meter-qualification',lambda:qualification.check(f,m))
    wrong=copy.deepcopy(m);wrong['input_lufs']=model.fixed(lufs+.11)
    red('candidate-loudness-calibration','calibration',lambda:qualification.check(f,wrong))
    f={'qualification_metric':'dbtp','qualification_expected':-3.0}
    green('candidate-peak-qualification',lambda:qualification.check(f,{'input_dbtp':'-3.000000'}))
    red('candidate-truepeak-underread','calibration',lambda:qualification.check(f,{'input_dbtp':'-3.110000'}))
    green('encoded-interval-fidelity',lambda:conversion.compare(x,x,True))
    red('guessed-trim-529-with-count-preserved','fidelity',lambda:conversion.compare(np.roll(x,529,axis=0),x,True))
    red('double-trim-1105-with-count-preserved','fidelity',lambda:conversion.compare(np.roll(x,1105,axis=0),x,True))
    rate=96000;wave=numerics.tone(rate,192000,18000,.25)
    good=numerics.resample(wave,rate,'ref_fir_a')
    green('passband-quality',lambda:audit.quality(good,rate,18000,.25))
    h=signal.firwin(4097,.0015,window=('kaiser',14))
    defective=signal.resample_poly(wave,147,320,axis=0,window=h)
    red('bad-passband-filter','src-quality',lambda:audit.quality(defective,rate,18000,.25))
    certified=signal.firwin(2*48*441+1,.88/441,window=('kaiser',10))*441
    green('continuous-band-certificate',lambda:filter_bounds.certify(h=certified,rate=16000))
    red('continuous-alias-bypass','src-quality',lambda:filter_bounds.certify(h=np.array([147.0]),rate=96000))
    red('continuous-passband-loss','src-quality',lambda:filter_bounds.certify(h=np.array([220.5]),rate=16000))
    endpoint=np.zeros((257,2));endpoint[0]=[.25,-.125]
    response=numerics.resample(endpoint,48000,'ref_fir_a')
    green('compensated-endpoint-latency',lambda:audit.latency(response,endpoint,48000))
    delayed=np.concatenate((np.zeros((3,2)),response))[:len(response)]
    red('uncompensated-filter-latency','src-latency',lambda:audit.latency(delayed,endpoint,48000))
    state,a=model.draw(model.SEED);state,b=model.draw(state);state,c=model.draw(state);state,d=model.draw(state)
    tie=np.array([[(.5-a+b)/32768,(1.5-c+d)/32768]])
    exact=model.quantize(tie);assert exact==struct.pack('<hh',0,2)
    first,_=model.draw(model.SEED);second,_=model.draw(first)
    one=np.repeat(np.array([[-(first-second)/2**47]]),2,axis=1);zero=model.quantize(one,mono=True);assert zero==bytes(4)
    green('nonzero-one-frame-quantizes-zero-admitted',lambda:audit.audio(one,zero,metadata(one,zero,0),mono=True,digital_source=False))
    above=tie.copy();above[0,0]=np.nextafter(above[0,0],float('inf'))
    green('exact-one-ulp-above-half',lambda:audit.require(struct.unpack('<hh',model.quantize(above))[0]==1,'dither','lost half-tie displacement'))
    green('round-even-exact-ties',lambda:audit.audio(tie,exact,metadata(tie,exact,0),exact=True))
    wrong=struct.pack('<hh',1,2)
    red('round-away-at-half','dither',lambda:audit.audio(tie,wrong,metadata(tie,wrong,0),exact=True))
    receipts={'checks':{'profile':{'decision':'PASS','reviewer':'Verification','notes':'independently checked mathematical profile and evidence','artifact_sha256':['a'*64]}}}
    green('independent-receipt-binding',lambda:review.reviewed(receipts,'profile',['a'*64]))
    red('unbound-review-evidence','review',lambda:review.reviewed(receipts,'profile',['b'*64]))
    wrong=copy.deepcopy(receipts);wrong['checks']['profile']['reviewer']='Software'
    red('software-self-certification','review',lambda:review.reviewed(wrong,'profile',['a'*64]))
    base={'complete':True,'raw_trace_sha256':'a'*64,'observer_selftest':True,'scenario':'preflight-refusal','exit':2,'events':[],'dest_before':['sentinel'],'dest_after':['sentinel'],'dest_before_sha256':'b'*64,'dest_after_sha256':'b'*64,'owned_stage_after':False,'diagnostic_ok':True,'raw_review':'PASS'}
    green('existing-DEST-preserved',lambda:audit.transaction(base))
    bad=copy.deepcopy(base);bad['dest_after_sha256']='c'*64
    red('existing-DEST-modified','preflight',lambda:audit.transaction(bad))
    for stage in ('preflight','after-preflight'):
        ops=[] if stage=='preflight' else ['preflight_complete','sources_revalidated','stage_create']
        events=[{'seq':i,'op':op,'adjacent':True,'exclusive':True} for i,op in enumerate(ops)]
        rec={'complete':True,'raw_trace_sha256':'a'*64,'observer_selftest':True,'scenario':'write-error','exit':1,'events':events,'dest_after':[],'owned_stage_after':False,'unrelated_unchanged':True,'raw_review':'PASS'}
        green('io-error-cleanup-'+stage,lambda:audit.transaction(rec))
        bad=copy.deepcopy(rec);bad['owned_stage_after']=True
        red('io-error-stage-leak-'+stage,'cleanup',lambda:audit.transaction(bad))
    mutation={'complete':True,'raw_trace_sha256':'a'*64,'observer_selftest':True,'scenario':'mutation','exit':2,'events':[{'seq':0,'op':'source_mutation_detected'}],'dest_after':[],'owned_stage_after':False,'raw_review':'PASS'}
    green('source-mutation-refusal',lambda:audit.transaction(mutation))
    bad=copy.deepcopy(mutation);bad['exit']=0
    red('mutation-published-success','mutation',lambda:audit.transaction(bad))
    ops=['preflight_complete','sources_revalidated','stage_create','output_open','audio_flush_close','manifest_flush_close','publish_dir_noreplace']
    success={'complete':True,'raw_trace_sha256':'a'*64,'observer_selftest':True,'scenario':'success','exit':0,'events':[{'seq':i,'op':op,'adjacent':True,'exclusive':True} for i,op in enumerate(ops)],'dest_after':['audio.wav','manifest.json'],'owned_stage_after':False,'unrelated_unchanged':True,'raw_review':'PASS'}
    for cut in range(len(ops)+1):
        kill=copy.deepcopy(success);kill.update(scenario='kill',exit=None,events=success['events'][:cut],dest_after=['audio.wav','manifest.json'] if cut==len(ops) else [])
        green('kill-cut-'+str(cut),lambda kill=kill:audit.transaction(kill))
        bad=copy.deepcopy(kill);bad['dest_after']=['audio.wav']
        red('kill-half-pair-'+str(cut),'pair',lambda bad=bad:audit.transaction(bad))
    concurrent=copy.deepcopy(success);concurrent.update(scenario='concurrent-dest',exit=1,events=success['events'][:-1],dest_after=['sentinel'],competitor_unchanged=True)
    green('concurrent-DEST-protected',lambda:audit.transaction(concurrent))
    bad=copy.deepcopy(concurrent);bad['competitor_unchanged']=False
    red('concurrent-DEST-overwritten','pair',lambda:audit.transaction(bad))
    bad=copy.deepcopy(success);bad['events'].append({'seq':7,'op':'device_open'})
    red('forbidden-device-open','io-scope',lambda:audit.transaction(bad))
    bad=copy.deepcopy(success);bad['events'].append({'seq':7,'op':'preflight_disk_scratch'})
    red('forbidden-preflight-scratch','io-scope',lambda:audit.transaction(bad))
    info=copy.deepcopy(success);info.update(scenario='informational',events=[],dest_after=[])
    green('informational-no-output',lambda:audit.transaction(info))
    bad=copy.deepcopy(info);bad['events']=[{'seq':0,'op':'stage_create','exclusive':True,'adjacent':True}]
    red('informational-created-stage','preflight',lambda:audit.transaction(bad))
    bad=copy.deepcopy(info);bad['complete']='false'
    red('nonboolean-native-completeness','trace',lambda:audit.transaction(bad))
    green('NFC-path-baseline',lambda:model.logical_names([['é.wav','track2.wav']]))
    try:model.logical_names([['é.wav','e\u0301.wav']])
    except ValueError:rows.append({'id':'NFC-logical-collision','result':'DETECTED','gate':'order'})
    else:raise AssertionError('NFC collision escaped')
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path);a=p.parse_args();rows=run()
    if a.out:a.out.write_text(json.dumps(rows,indent=2)+'\n')
    print(len(rows),'completion baseline/control observations PASS')
