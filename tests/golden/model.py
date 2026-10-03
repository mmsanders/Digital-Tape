#!/usr/bin/env python3
"""Independent DRAFT-10 timeline/PCM model. Does not import product code."""
import array
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent
HZ = 44100

def read(path):
    data = pathlib.Path(path).read_bytes()
    assert data[:4] == b'RIFF' and data[8:12] == b'WAVE'
    assert data[12:16] == b'fmt ' and struct.unpack('<IHHIIHH', data[16:36]) == (16,1,2,HZ,HZ*4,4,16)
    assert data[36:40] == b'data' and len(data) == 44 + struct.unpack('<I',data[40:44])[0]
    a = array.array('h'); a.frombytes(data[44:])
    if sys.byteorder != 'little': a.byteswap()
    return a

def write(path, samples):
    a = array.array('h', samples)
    if sys.byteorder != 'little': a.byteswap()
    b = a.tobytes()
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(path).write_bytes(struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',36+len(b),b'WAVE',b'fmt ',16,1,2,HZ,HZ*4,4,16,b'data',len(b))+b)

def render(a, start, schedule):
    out = array.array('h'); pos = start << 32; end = (len(a)//2) << 32
    for rate, count in schedule:
        step = rate * 65536  # rate already exact Q16.16
        stopped = False
        if step < 0 and pos >= end: pos = end - (1<<32)
        for _ in range(count):
            if not step or (step > 0 and pos >= end) or stopped: break
            i, f = divmod(pos, 1<<32); j = min(i+1,len(a)//2-1)
            for c in (0,1):
                x, y = int(a[2*i+c]), int(a[2*j+c])
                out.append(x + ((y-x)*f // (1<<32)))
            if step > 0: pos = min(end,pos+step)
            elif pos == 0: stopped = True
            else: pos = max(0,pos+step)
    return out

def edit(a, v, at, mode):
    p = at*2
    if mode == 'splice': return a[:p]+v+a[p:]
    if mode == 'overwrite': return a[:p]+v  # replaces timeline from cursor
    assert mode == 'overdub'
    out = a[:]
    if len(out) < p+len(v): out.extend([0]*(p+len(v)-len(out)))
    for i,x in enumerate(v): out[p+i] = max(-32768,min(32767,int(out[p+i])+int(x)))
    return out

def references():
    quiet=read(ROOT/'src/quiet.wav'); ending=read(ROOT/'src/ending.wav')
    loud=read(ROOT/'src/loudest.wav'); voice=read(ROOT/'src/voice.wav')
    splice=edit(ending,voice,100000,'splice')
    mix=edit(loud,voice,0,'overdub')
    cases={'play-1x-quiet':quiet,'play-1x-fortissimo':ending,
      'scrub-forward':render(ending,0,[(16384,32000),(32768,32000),(65536,32000),(131072,32000),(262144,16000)]),
      'scrub-reverse-1x':render(ending,len(ending)//2,[(-65536,198450)]),
      'scrub-reverse-2x':render(ending,len(ending)//2,[(-131072,100000)]),
      'splice':splice,'overdub':mix,'overwrite':edit(ending,voice,100000,'overwrite'),
      'reset-b':ending,'promote':splice}
    positive=sum(int(loud[i])+int(x)>32767 for i,x in enumerate(voice))
    negative=sum(int(loud[i])+int(x)<-32768 for i,x in enumerate(voice))
    assert positive and negative, (positive,negative)
    return cases, {'positive_saturated_samples':positive,'negative_saturated_samples':negative}

def main():
    cases, census=references()
    # This invocation verifies frozen bytes. Creation is an explicit separate mode.
    create = len(sys.argv)>1 and sys.argv[1]=='--initial-create'
    for name,a in cases.items():
        p=ROOT/'ref'/f'{name}.wav'
        if create: write(p,a)
        else: assert read(p)==a,name
        assert p.stat().st_size<=1048576
    # Causal controls do not replace committed reference files.
    a=read(ROOT/'src/ending.wav'); v=read(ROOT/'src/voice.wav')
    assert render(a,0,[(65536,len(a)//2)])==a
    assert cases['scrub-reverse-1x']==array.array('h',[x for i in range(len(a)//2-1,-1,-1) for x in a[2*i:2*i+2]])
    assert cases['splice'][:200000]==a[:200000] and cases['splice'][288200:]==a[200000:]
    controls = {
      'seek_advance_before_emit':a[2:]+a[-2:]!=cases['play-1x-fortissimo'],
      'reverse_drops_frame_zero':cases['scrub-reverse-1x'][:-2]!=cases['scrub-reverse-1x'],
      'chunk_wrap':a[:262144]+a[:len(a)-262144]!=a,
      'splice_omits_tail':a[:200000]+v!=cases['splice'],
      'overdub_wraps':array.array('h',[((int(x)+int(y)+32768)%65536)-32768 for x,y in zip(read(ROOT/'src/loudest.wav'),v)])!=cases['overdub'][:len(v)],
      'overwrite_retains_tail':a[:200000]+v+a[200000+len(v):]!=cases['overwrite'],
      'reset_keeps_edit':cases['splice']!=cases['reset-b'],
      'promote_keeps_old_a':a!=cases['promote']}
    assert all(controls.values())
    print(json.dumps({'references':len(cases),'controls':controls,**census},sort_keys=True))

if __name__=='__main__': main()
