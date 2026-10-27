"""Independent numerical preflight methods, not Product waveform goldens.

ITU's 48k coefficient pair is bilinear-retuned to 44.1k; metering uses actual
400ms/75%-overlap gating. FIR reference profiles differ by documented filters.
Qualification is on declared vectors, not a universal analogue-device proof.
"""
import math
import numpy as np
from scipy import signal
import model

FILTERS={'ref_fir_a':{'width':48,'cutoff':.88,'beta':10},'ref_fir_b':{'width':64,'cutoff':.90,'beta':14}}

def retune(b,a,rate):
    z,p,k=signal.tf2zpk(b,a)
    za=96000*(z-1)/(z+1);pa=96000*(p-1)/(p+1)
    ka=k*np.prod(1+z)/np.prod(1+p)
    zz,pp,kk=signal.bilinear_zpk(za,pa,float(np.real(ka)),fs=rate)
    return signal.zpk2tf(zz,pp,kk)

def loudness(x):
    x=np.asarray(x,dtype=float)
    if len(x)<17640:return None
    b,a=retune([1.53512485958697,-2.69169618940638,1.19839281085285],[1,-1.69065929318241,.73248077421585],44100)
    y=signal.lfilter(b,a,x,axis=0)
    b,a=retune([1,-2,1],[1,-1.99004745483398,.99007225036621],44100)
    y=signal.lfilter(b,a,y,axis=0)
    e=np.sum(y*y,axis=1)
    powers=np.array([np.mean(e[i:i+17640]) for i in range(0,len(e)-17640+1,4410)])
    with np.errstate(divide='ignore'):levels=-.691+10*np.log10(powers)
    absolute=powers[levels>=-70]
    if not len(absolute):return None
    threshold=-.691+10*np.log10(np.mean(absolute))-10
    selected=powers[(levels>=-70)&(levels>=threshold)]
    return float(-.691+10*np.log10(np.mean(selected)))

def peak(x,factor=16):
    x=np.asarray(x,dtype=float)
    if not len(x) or not np.any(x):return None
    # Documented 256-input-frame half-support, linear-phase sinc reconstruction.
    taps=signal.firwin(2*256*factor+1,1/factor,window=('kaiser',14))
    # Include both endpoint extensions, rather than omit possible reconstruction tails.
    padded=np.pad(x,((256,256),(0,0)))
    y=signal.resample_poly(padded,factor,1,axis=0,window=taps)
    maximum=float(np.max(np.abs(y)))
    return float(20*np.log10(maximum)) if maximum else None

def resample(x,rate,profile):
    x=np.asarray(x,dtype=float)
    if rate==44100:return x.copy()
    p=FILTERS[profile];g=math.gcd(rate,44100);up=44100//g;down=rate//g
    taps=signal.firwin(2*p['width']*max(up,down)+1,p['cutoff']/max(up,down),window=('kaiser',p['beta']))
    y=signal.resample_poly(x,up,down,axis=0,window=taps)
    n=model.output_frames(len(x),rate)
    return y[:n]

def reference_source(x,rate,profile,mono=False):
    x=np.asarray(x,dtype=float)
    if mono:x=np.repeat(x[:,:1],2,axis=1)
    y=resample(x,rate,profile)
    if not np.any(x):return bytes(len(y)*4),{'gain':0,'lufs':None,'peak':None,'status':'digital_silence','before':y}
    l=loudness(y);p=peak(y)
    if p is None:raise ValueError('no valid source peak')
    g=min(0,-1-p-.1) if l is None else min(-16-l,-1-p-.1)
    for _ in range(16):
        z=y*10**(g/20);pcm=model.quantize(z,mono=mono)
        q=np.frombuffer(pcm,dtype='<i2').reshape(-1,2).astype(float)/32768
        qp=peak(q)
        if qp is not None and qp+.1<=-1:break
        if qp is None:break
        g-=max(.00001,qp+.1+1)
    else:raise ValueError('reference gain did not converge')
    ql=loudness(q)
    return pcm,{'gain':g,'lufs':ql,'peak':qp,'status':'unmeasurable' if ql is None else 'measured','before':y}

def tone(rate,n,f=997,a=.1,phase=0,channels=2):
    s=a*np.sin(2*np.pi*f*np.arange(n)/rate+phase)
    return np.repeat(s[:,None],channels,axis=1)
