"""Independent DRAFT-10 bytes/mappings. Payload is generated at the device callback.

Metadata file is sparse; counting_device.c synthesizes untouched chunk data from
the physical frame coordinate. Actual writes override it. Never mount the sparse
metadata file through a normal file port: its holes are not the PCM fixture.
"""
from __future__ import annotations
import hashlib
import json
import struct
import zlib
from pathlib import Path

CF, CB, BASE, FB, BLOCK = 131072, 1024, 2048, 4, 512
UUID = bytes.fromhex('17014617014617014617014617014617')
SLOTS = (8, 136, 264, 392)

def crc(b): return zlib.crc32(b) & 0xffffffff
def ceildiv(a,b): return (a+b-1)//b
def coordinate(p, seed=0):
    x=(p*2654435761+0x5a17c3e1+seed)&0xffffffff
    return struct.pack('<I',x)
def frame(fixture, side, frame):
    t=frame
    for first,start,n in fixture['sides'][side]:
        if t<n:
            return coordinate(first*CF+start+t,fixture['seed'])
        t-=n
    raise IndexError(frame)
def length(fixture,side): return sum(e[2] for e in fixture['sides'][side])
def entries(fixture,side): return len(fixture['sides'][side])
def mapped_intervals(fixture,side):
    return [(first*CF+start,first*CF+start+n) for first,start,n in fixture['sides'][side]]

def make(name):
    seed=0
    if name.startswith('contiguous-'):
        n=int(name.split('-')[1]); a=[[0,0,n]] if n else []
        b=a
    elif name.startswith('fragment-'):
        _,e,kind=name.split('-');e=int(e); n=1 if kind=='short' else 256
        a=[]
        for i in range(e):
            p=i*(n+128);a.append([p//CF,p%CF,n])
        b=list(reversed(a))
    elif name=='edges':
        a=[[1,CF-72,200],[3,1000,300],[0,5,6],[4,127,3],[3,100,50]]
        b=[a[1],a[4],a[0],a[3],a[2]]
    elif name=='behavior':
        a=[[0,0,40000]];b=[[1,127,35000]]
    elif name=='empty': a=[];b=[]
    else: raise ValueError(name)
    high=max([ceildiv(first*CF+start+n,CF) for first,start,n in a+b]+[1])
    # One spare chunk, with a truthful label, makes public content-edit cases possible.
    nominal=ceildiv((high+1)*CF,44100)
    if name=='contiguous-158760000':nominal=3600
    chunks=ceildiv(nominal*44100,CF)
    f={'schema':'read1-fixture-v1','name':name,'seed':seed,'uuid':UUID.hex(),
       'sides':{'A':a,'B':b},'high':high,'nominal':nominal,'chunks':chunks,
       'block_count':BASE+chunks*CB+1}
    validate(f)
    return f

def validate(f):
    assert 1<=f['nominal'] and f['chunks']==ceildiv(f['nominal']*44100,CF)
    assert BASE+f['chunks']*CB<=f['block_count']-1
    for side in ('A','B'):
        es=f['sides'][side];assert len(es)<=4096
        assert length(f,side)<=0xffffffff
        iv=[]
        for first,start,n in es:
            assert 0<=start<CF and n>=1
            assert ceildiv(first*CF+start+n,CF)<=f['high']<=f['chunks']
            iv.append((first*CF+start,first*CF+start+n))
        iv.sort();assert all(x[1]<=y[0] for x,y in zip(iv,iv[1:]))

def metadata(f):
    sb=bytearray(512);sb[:8]=b'TAPEFS\0\x01'
    struct.pack_into('<HHI',sb,8,1,0,1);sb[20:36]=bytes.fromhex(f['uuid'])
    struct.pack_into('<IHHIIII',sb,36,44100,2,16,524288,f['nominal'],f['chunks'],f['high'])
    struct.pack_into('<IIIIIII',sb,60,65536,8,136,264,392,2048,f['block_count']-1)
    sb[88:93]=b'READ1';struct.pack_into('<I',sb,508,crc(sb[:508]))
    blocks={0:bytes(sb),f['block_count']-1:bytes(sb)}
    for side,base,seq in [('A',8,1),('B',264,2)]:
        raw=b''.join(struct.pack('<III',*e) for e in f['sides'][side])
        h=bytearray(512);h[:8]=b'TAPEIDX\x01';struct.pack_into('<I',h,8,seq)
        h[12]=0 if side=='A' else 1
        struct.pack_into('<IQ',h,16,len(f['sides'][side]),length(f,side))
        struct.pack_into('<I',h,60,crc(h[:60]+raw));blocks[base]=bytes(h)
        for i in range(ceildiv(len(raw),512)):
            blocks[base+1+i]=raw[i*512:(i+1)*512].ljust(512,b'\0')
    return blocks

def write(f,path):
    path=Path(path)
    with path.open('wb') as out:
        out.truncate(f['block_count']*512)
        for lba,b in metadata(f).items(): out.seek(lba*512);out.write(b)
    # Fixture identity binds semantic payload rule as well as sparse metadata.
    digest=hashlib.sha256(json.dumps(f,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return digest

def block(f,lba):
    if lba in metadata(f): return metadata(f)[lba]
    if BASE<=lba<f['block_count']-1:
        p=(lba-BASE)*128
        return b''.join(coordinate(p+i,f['seed']) for i in range(128))
    return bytes(512)
