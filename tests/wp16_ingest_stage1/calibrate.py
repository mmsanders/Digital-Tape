"""Generated independent meter/calibration and two-filter feasibility vectors.

No copyrighted audio downloaded. Definitions follow public ITU/EBU equations;
all generated vectors are CC0. Direct finite-sinc maximization is independent
of the FIR/polyphase peak implementation being checked.
"""
import json
import math
from pathlib import Path
import numpy as np
from scipy import optimize,signal
import numerics as n


def direct_peak(x):
    x=np.asarray(x,float);length=len(x)
    assert length<=256
    indices=np.arange(length)
    def value(t):return np.sinc(t-indices)@x
    times=np.arange(-64,length+64,1/64)
    values=np.array([np.max(np.abs(value(t))) for t in times])
    best=float(max(values,default=0))
    for i in np.argpartition(values,-min(12,len(values)))[-12:]:
        result=optimize.minimize_scalar(lambda t:-float(np.max(np.abs(value(t)))),bounds=(times[i]-1/64,times[i]+1/64),method='bounded',options={'xatol':1e-12})
        best=max(best,-result.fun)
    # Outside these finite bounds, |sinc(t-k)| <= 1/(pi*distance).
    far=float(np.sum(np.max(np.abs(x),axis=1))/(np.pi*64))
    assert far<best,'extend direct reconstruction interval'
    return 20*math.log10(best)


def run():
    observations=[]
    for level in (-18,-23,-33,-60):
        x=n.tone(44100,44100*20,1000,10**(level/20))
        measured=n.loudness(x);assert abs(measured-level)<=.1,(level,measured)
        observations.append(dict(kind='EBU-stereo1kHz',expected=level,observed=measured,error_lu=measured-level))
    # Independently generated EBU integrated gating cases3/4/5. Full durations
    # retained: shrinking them would alter block/gate decisions.
    for name,segments in [('relative',[(10,-36),(60,-23),(10,-36)]),('absolute',[(10,-72),(10,-36),(60,-23),(10,-36),(10,-72)]),('transition',[(20,-26),(20.1,-20),(20,-26)])]:
        x=np.concatenate([n.tone(44100,round(seconds*44100),1000,10**(db/20)) for seconds,db in segments])
        measured=n.loudness(x);assert abs(measured+23)<=.1,(name,measured)
        observations.append(dict(kind='EBU-gate-'+name,expected=-23,observed=measured,error_lu=measured+23))
    assert n.loudness(n.tone(44100,44100,1000,1e-5)) is None
    assert n.loudness(n.tone(44100,17639)) is None
    # EBU sinusoidal true-peak cases plus finite boundary/impulse/random tests.
    vectors=[]
    for divisor,phase,amplitude in [(4,0,.5),(4,np.pi/4,.5),(6,np.pi/3,.5),(8,3*np.pi/8,.5),(4,np.pi/4,1.41)]:
        x=n.tone(44100,4410,44100/divisor,amplitude,phase)
        fade=np.minimum(1,np.minimum(np.arange(4410)/441,(4409-np.arange(4410))/441))
        x*=fade[:,None]
        measured=n.peak(x);expected=20*np.log10(amplitude)
        assert abs(measured-expected)<=.1,(divisor,phase,measured,expected)
        observations.append(dict(kind='EBU-truepeak-sine',divisor=divisor,phase=float(phase),observed=measured,expected=float(expected),underread_db=float(expected-measured)))
    for f in (.07,.25,.40,.47,.49):
        for phase in (0,np.pi/4):vectors.append(('finite-sine',n.tone(44100,65,44100*f,.6,phase)))
    for at in (0,1,16,32):
        x=np.zeros((33,2));x[at]=[.8,-.6];vectors.append(('endpoint-impulse',x))
    rng=np.random.Generator(np.random.PCG64(0x169))
    for _ in range(4):vectors.append(('finite-random',rng.uniform(-.5,.5,(65,2))))
    for kind,x in vectors:
        expected=direct_peak(x);observed=n.peak(x);under=expected-observed
        assert under<=.1,(kind,expected,observed,under)
        observations.append(dict(kind=kind,expected=expected,observed=observed,underread_db=under))
    # Two independent conforming FIR designs, each judged against issued bounds,
    # never against each other's waveform bytes. Window is fixed at100ms each
    # end, wider than the declared64 input-frame half-support at every rate.
    for profile in n.FILTERS:
        for rate in __import__('model').RATES:
            frequencies=sorted(set((20,997,min(18000,.4*rate),23000,rate*.47)))
            for f in frequencies:
                if f>=rate/2:continue
                x=n.tone(rate,rate*2,f,.5);y=n.resample(x,rate,profile)
                steady=y[4410:-4410,0];t=np.arange(4410,len(y)-4410)/44100
                alias=abs((f+22050)%44100-22050)
                basis=np.stack((np.sin(2*np.pi*alias*t),np.cos(2*np.pi*alias*t)),axis=1)
                fit=np.linalg.lstsq(basis,steady,rcond=None)[0];amplitude=float(np.linalg.norm(fit))
                db=20*math.log10(max(amplitude,1e-300)/.5)
                if f<=min(18000,.4*rate):assert abs(db)<=.1,(profile,rate,f,db)
                elif f>=22050:assert db<=-80,(profile,rate,f,db)
                observations.append(dict(kind='SRC-quality',profile=profile,rate=rate,frequency=f,response_db=db,window_frames=[4410,len(y)-4410]))
    return observations


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    observations=run();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(observations,indent=2)+'\n')
    print(len(observations),'independent meter/filter calibration observations passed')
