"""Frozen18-case44100-Hz PCM16 boundary family; authored before Software500."""
import hashlib,json,struct
RATE=44100;GAP=88200;BLOCK=1<<20
def source(n,channels=1,amplitude=2048,shape='ends',opposite=False):
    return dict(frames=n,channels=channels,amplitude=amplitude,shape=shape,opposite=opposite)
def sparse(s):
    n=s['frames'];a=s['amplitude']
    points={0:a,n-1:-a} if n>1 else {0:a}
    if s['shape']=='edgepair' and n>=2:points={n-2:a,n-1:-a}
    if s['shape']=='last':points={n-1:a}
    return {i:(v,v if not s['opposite'] else -v) for i,v in points.items()}
def wav(s):
    out=bytearray(s['frames']*s['channels']*2)
    for i,row in sparse(s).items():
        for ch in range(s['channels']):struct.pack_into('<h',out,(i*s['channels']+ch)*2,row[ch])
    c=s['channels'];b=bytes(out)
    return struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',36+len(b),b'WAVE',b'fmt ',16,1,c,RATE,RATE*c*2,c*2,16,b'data',len(b))+b
def corpus():
    rows=[]
    def add(name,folders,kind,exit0=False):rows.append(dict(name=name,folders=folders,kind=kind,target_seconds=30,expect_success=exit0))
    for n in [1,2,255,257]:add('endpoint-'+str(n),[[source(n,channels=1 if n%2 else 2)]],'short endpoint/support',True)
    for amp in [2048,29000]:
        for shift in [0,1]:add('join-'+str(amp)+'-'+str(shift),[[source(255+shift,amplitude=amp,shape='edgepair'),source(257,amplitude=amp,shape='last')]],'join support/grid',amp==2048)
    for separate in [False,True]:
        ss=[source(255,shape='edgepair'),source(257,shape='last')]
        add('gap-'+str(int(separate)),[[ss[0]],[ss[1]]] if separate else [ss],'same-source gap contrast',True)
    for shift in range(4):add('threshold-channel-'+str(shift),[[source(1+shift,amplitude=29000+shift%2,channels=1 if shift<2 else 2,opposite=shift==3,shape='edgepair')]],'quantization/channel/grid probe')
    for delta in [-1,0,1,2]:
        tail=BLOCK+delta-11*GAP-11*6500
        folders=[[source(6500,shape='last')] for _ in range(11)]+[[source(tail,amplitude=29000,shape='edgepair')]]
        add('block-end-'+str(delta),folders,'global block/reset endpoint probe')
    assert len(rows)==18
    return rows
def facts(case):
    at=0;rows=[];gaps=[]
    for f,folder in enumerate(case['folders']):
        for j,s in enumerate(folder):
            raw=wav(s)
            rows.append(dict(path=f'{f}/source{j+1:02d}.wav',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),frames=s['frames'],channels=s['channels'],start_frame=at))
            at+=s['frames']
        if f+1<len(case['folders']):gaps.append(dict(start_frame=at,frames=GAP));at+=GAP
    return dict(name=case['name'],sources=rows,gaps=gaps,total_frames=at,capacity_frames=case['target_seconds']*RATE)
if __name__=='__main__':
    import argparse,pathlib
    p=argparse.ArgumentParser();p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
    for c in corpus():
        for f,folder in enumerate(c['folders']):
            dest=a.out/c['name']/('folder'+str(f));dest.mkdir(parents=True,exist_ok=False)
            for j,s in enumerate(folder):(dest/f'source{j+1:02d}.wav').write_bytes(wav(s))
    print(json.dumps([facts(c) for c in corpus()],indent=2))
