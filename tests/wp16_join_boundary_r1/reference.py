"""Independent declared16-phase Kaiser14/sinc reference; no Product imports.

Finite sampled reference only, NOT an enclosure of Product's f32/refined meter.
Uses source code integers, gain0 before dither. L1 gives a conservative independent
reference envelope for arbitrary per-source no-boost gains and1.5LSB quant error.
"""
import math,json
from functools import lru_cache
from cases import corpus,sparse,facts
HALF=256;PHASES=16;BETA=14
def i0(x):
    term=total=1.0
    for k in range(1,100):
        term*=x*x/(4*k*k);total+=term
        if term<total*1e-17:return total
    raise AssertionError('I0 did not converge')
def raw(x):
    if abs(x)>HALF:return 0.0
    sinc=1.0 if x==0 else math.sin(math.pi*x)/(math.pi*x)
    return sinc*i0(BETA*math.sqrt(max(0,1-(x/HALF)**2)))/i0(BETA)
@lru_cache(None)
def kernel():
    norm=math.fsum(raw(k/PHASES) for k in range(-HALF*PHASES,HALF*PHASES+1))/PHASES
    h={k:raw(k/PHASES)/norm for k in range(-HALF*PHASES,HALF*PHASES+1)}
    l1=max(math.fsum(abs(h[k]) for k in h if k%PHASES==phase) for phase in range(PHASES))
    return h,l1
def measure(points):
    h,l1=kernel();peak=0.0;where=None;absbound=0.0
    # Only nonzero input support can affect this declared finite-support reference.
    centers=set(t for i in points for t in range(i-HALF,i+HALF+1))
    for t in sorted(centers):
        for phase in range(PHASES):
            terms=[(h.get((t-i)*PHASES+phase,0),row) for i,row in points.items() if abs(t-i)<=HALF+1]
            for ch in [0,1]:
                value=abs(math.fsum(v*row[ch]/32768 for v,row in terms))
                bound=math.fsum(abs(v*row[ch]/32768) for v,row in terms)
                absbound=max(absbound,bound)
                if value>peak:peak=value;where=[t,phase,ch]
    # Arithmetic allowance is for this engineering reference, not a Product tolerance.
    return dict(sampled_peak_amplitude=peak,sampled_peak_dbtp=20*math.log10(peak) if peak else None,coordinate=where,no_boost_quantized_reference_upper=absbound+1.5/32768*l1+1e-9,l1=l1)
def report():
    cache={};out=[]
    for c in corpus():
        assembled={};sources=[];at=0
        for f,folder in enumerate(c['folders']):
            for s in folder:
                key=json.dumps(s,sort_keys=True)
                if key not in cache:cache[key]=measure(sparse(s))
                sources.append(cache[key]);assembled.update({at+i:v for i,v in sparse(s).items()});at+=s['frames']
            if f+1<len(c['folders']):at+=88200
        out.append(dict(name=c['name'],sources=sources,assembled=measure(assembled),facts=facts(c)))
    return out
if __name__=='__main__':print(json.dumps(report(),indent=2,sort_keys=True))
