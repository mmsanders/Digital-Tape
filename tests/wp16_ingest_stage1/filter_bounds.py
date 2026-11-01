"""Continuous-band FIR magnitude bounds using DTFT nodes + derivative enclosure.

For centered coefficients h/up, |dH/df| <= 2pi*sum(|h[k]*(k-c)|)/(fs*up).
Every frequency lies within half a node spacing. Thus max/min node magnitude
plus/minus that enclosure covers the whole band, not merely chosen tones.
An explicit1e-8 amplitude numerical allowance is added; direct DTFT spotchecks
corroborate zoom-FFT nodes. A difficult alternate filter may use an independently
reviewed analytic enclosure of the SAME issued bounds, never wider tolerances.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from scipy import signal
import audit,model,numerics

def certify(h,rate):
    up=44100//math.gcd(rate,44100);fs=rate*up;h=np.asarray(h,float)
    audit.require(h.ndim==1 and len(h)>0 and np.isfinite(h).all(),'src-definition','invalid FIR')
    center=(len(h)-1)/2
    derivative=float(2*np.pi*np.sum(abs(h)*abs(np.arange(len(h))-center))/(fs*up))
    def band(lo,hi,allowance):
        spacing=allowance/max(derivative,1e-300)
        count=max(2,int(math.ceil((hi-lo)/spacing))+1)
        values=signal.zoom_fft(h,[lo,hi],count,fs=fs,endpoint=True)/up
        frequencies=np.linspace(lo,hi,count)
        for i in sorted(set((0,count//2,count-1,int(np.argmax(abs(values)))))):
            direct=np.exp(-2j*np.pi*frequencies[i]*np.arange(len(h))/fs)@h/up
            audit.require(abs(direct-values[i])<=1e-8,'src-definition','DTFT numerical allowance exceeded')
        guard=derivative*(hi-lo)/(count-1)/2+1e-8
        return float(np.min(abs(values))-guard),float(np.max(abs(values))+guard),count,guard
    lo,hi,count,guard=band(20,min(18000,.4*rate),.002)
    audit.require(lo>=10**(-.1/20) and hi<=10**(.1/20),'src-quality','continuous passband bound')
    result={'rate':rate,'passband_lower_db':20*math.log10(lo),'passband_upper_db':20*math.log10(hi),'passband_nodes':count,'derivative_amplitude_per_hz':derivative,'numerical_allowance':1e-8}
    if rate>44100:
        lo,hi,count,guard=band(22050,rate/2,.00004)
        audit.require(hi<=1e-4,'src-quality','continuous alias rejection bound')
        result.update(alias_upper_db=20*math.log10(hi),alias_nodes=count)
    return result

def references():
    rows=[]
    for profile,p in numerics.FILTERS.items():
        for rate in model.RATES:
            if rate==44100:continue
            up=44100//math.gcd(rate,44100);down=rate//math.gcd(rate,44100)
            h=signal.firwin(2*p['width']*max(up,down)+1,p['cutoff']/max(up,down),window=('kaiser',p['beta']))*up
            row=certify(h,rate);row['profile']=profile;rows.append(row)
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();rows=references();a.out.write_text(json.dumps(rows,indent=2)+'\n');print(len(rows),'continuous-band reference FIR certificates PASS')
