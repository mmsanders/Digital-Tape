"""Generated actual-ingest meter qualification sources; no downloaded test audio."""
import json
from pathlib import Path
import numpy as np
import numerics as n

def vectors():
    # Definitions match calibrate.py's independent standards/sinc qualification;
    # published expected numbers came from analytic levels/direct sinc maxima,
    # not Product or a decoder waveform. Source samples are frozen in the pack.
    records=json.loads((Path(__file__).parent/'evidence/calibration.json').read_text(encoding='utf-8'))
    result=[]
    for level in (-18,-23,-33,-60):result.append(('loudness-'+str(-level),n.tone(44100,44100*20,1000,10**(level/20)),'lufs',float(level)))
    for name,segments in [('relative',[(10,-36),(60,-23),(10,-36)]),('absolute',[(10,-72),(10,-36),(60,-23),(10,-36),(10,-72)]),('transition',[(20,-26),(20.1,-20),(20,-26)])]:
        x=np.concatenate([n.tone(44100,round(seconds*44100),1000,10**(db/20)) for seconds,db in segments])
        result.append(('gate-'+name,x,'lufs',-23.0))
    for idx,(divisor,phase,amplitude) in enumerate([(4,0,.5),(4,np.pi/4,.5),(6,np.pi/3,.5),(8,3*np.pi/8,.5),(4,np.pi/4,1.41)]):
        x=n.tone(44100,4410,44100/divisor,amplitude,phase)
        x*=np.minimum(1,np.minimum(np.arange(4410)/441,(4409-np.arange(4410))/441))[:,None]
        result.append(('truepeak-sine-'+str(idx),x,'dbtp',records[7+idx]['expected']))
    finite=[]
    for f in (.07,.25,.40,.47,.49):
        for phase in (0,np.pi/4):finite.append(n.tone(44100,65,44100*f,.6,phase))
    for at in (0,1,16,32):
        x=np.zeros((33,2));x[at]=[.8,-.6];finite.append(x)
    rng=np.random.Generator(np.random.PCG64(0x169))
    finite.extend(rng.uniform(-.5,.5,(65,2)) for _ in range(4))
    for i,x in enumerate(finite):result.append(('truepeak-finite-'+str(i),x,'dbtp',records[12+i]['expected']))
    return result

def check(fact,source_metadata):
    import audit
    if 'qualification_metric' not in fact:return
    metric=fact['qualification_metric'];expected=fact['qualification_expected']
    actual=source_metadata['input_lufs' if metric=='lufs' else 'input_dbtp']
    audit.require(actual is not None,'calibration','missing qualified input measurement')
    if metric=='lufs':audit.require(abs(float(actual)-expected)<=.100000001,'calibration','loudness error>0.1LU')
    else:audit.require(expected-float(actual)<=.100000001,'calibration','true peak underread>0.1dB')
