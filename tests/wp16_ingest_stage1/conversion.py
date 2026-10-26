"""Independent decoded-interval/FIR/fidelity checks, not universal wave hashes."""
import math
import numpy as np
from scipy import signal
import audit,fixtures,formats,model

def decoded(root,f):
    path=root/f['path']
    if f['container']=='wave':x,rate=formats.generated_pcm(path.read_bytes())
    elif not f.get('lossy'):
        # All tiny lossless matrix bytes have been separately cross-decoded to
        # the generated mathematical samples, including every FLAC precision.
        x=fixtures.signal(f['input_rate'],f['raw_frames'],f['input_channels'])
        x=np.rint(x*2**(f['bits']-1))/2**(f['bits']-1)
    else:x=fixtures.decode(path,f['input_channels'],manual=True,ignore_edit=f['container']=='bmff')
    audit.require(len(x)==f['raw_frames'],'decode-count','independent raw count')
    end=len(x)-f['trim_tail'];x=x[f['trim_head']:end]
    audit.require(len(x)==f['effective_frames'],'trim','exact encoded interval')
    if f['input_channels']==1:x=np.repeat(x,2,axis=1)
    return x

def fir(x,rate,descriptor):
    g=math.gcd(rate,44100);up=44100//g;down=rate//g
    h=np.asarray(descriptor['coefficients'],float);first=descriptor['first_highrate_index']
    audit.require(h.ndim==1 and len(h)>0 and np.isfinite(h).all() and type(first)is int and first>=0,'src-definition','finite FIR and latency')
    # h includes any interpolation scale. This describes a mathematical transfer
    # function, not a demand for a particular Product implementation/library.
    padding=(-first)%down;h=np.pad(h,(padding,0));start=(first+padding)//down
    y=signal.upfirdn(h,x,up,down,axis=0)
    count=model.output_frames(len(x),rate)
    y=np.pad(y,((0,max(0,start+count-len(y))),(0,0)))
    return y[start:start+count]

def compare(observed,expected,lossy=False,source_scale=None):
    observed=np.asarray(observed,float);expected=np.asarray(expected,float)
    audit.require(observed.shape==expected.shape,'count','converted frame count')
    audit.require(np.isfinite(observed).all(),'conversion','nonfinite observed SRC')
    scale=float(np.max(abs(expected),initial=0)) if source_scale is None else source_scale
    if scale==0:
        audit.require(not np.any(observed),'conversion','digital zero changed');return
    if not lossy:
        tolerance=2e-6*scale
        audit.require(np.all(abs(observed-expected)<=tolerance),'conversion','not declared isolated transfer')
    else:
        # Selected generated encoded vectors only. Cross-decoder rounding is
        # allowed; trim/phase shifts and guessed padding are not. Zero reference
        # has an absolute bound, avoiding an undefined relative denominator.
        rms=float(np.sqrt(np.mean(expected*expected))) if len(expected) else 0
        error=float(np.sqrt(np.mean((observed-expected)**2))) if len(expected) else 0
        audit.require(error<=max(1/32768,.02*rms),'fidelity','>2%RMS or1LSB absolute on selected encoded interval')
