#!/usr/bin/env python3
"""Deterministically build P1-R6 playback fixtures and verifier candidate PCM."""
from __future__ import annotations
import argparse, gzip, hashlib, io, json, struct, zlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
BLOCK=512; SLOT=65536; CF=131072; FRAME=4; BASE=2048
A0,A1,B0,B1=8,136,264,392
TOTAL_CHUNKS=12; BLOCKS=BASE+TOTAL_CHUNKS*1024+1
LONG_N=1_100_000; SIDE_B_N=7
RATES=(262144,297097,332049,367002,401954,436907,471859,506812,541764,576717,611669,646622,681574,716527,751479,786432)
COUNTS=(4410,)*15+(22050,)

def sha(b): return hashlib.sha256(b).hexdigest()
def frame(i, side=0):
    # Deliberately non-constant, deterministic, full signed-range-friendly waveform.
    # A 1024-frame period keeps the million-frame media compact in Git without
    # weakening interpolation/rate coverage inside any row.
    j=i & 1023
    l=((j*257 + side*1009 + 12345) & 0xffff)-32768
    r=((j*911 + side*3001 + 4567) & 0xffff)-32768
    return l,r
def pcm(frames): return b"".join(struct.pack("<hh",*x) for x in frames)
def index(seq,side,entries):
    b=bytearray(SLOT); b[:8]=b"TAPEIDX\x01"
    struct.pack_into("<IB3xIQ",b,8,seq,side,len(entries),sum(x[2] for x in entries))
    for i,e in enumerate(entries): struct.pack_into("<III",b,512+12*i,*e)
    struct.pack_into("<I",b,60,zlib.crc32(b[:60]+b[512:512+12*len(entries)]))
    return bytes(b)
def superblock(high,label):
    b=bytearray(BLOCK); b[:8]=b"TAPEFS\0\x01"
    struct.pack_into("<HHIB3x16sIHHIIIII",b,8,1,0,7,0,bytes(range(16)),44100,2,16,CF*FRAME,33,TOTAL_CHUNKS,high,SLOT)
    struct.pack_into("<IIIIII",b,64,A0,A1,B0,B1,BASE,BLOCKS-1)
    b[88:88+len(label)]=label; struct.pack_into("<III",b,120,0,0,0)
    struct.pack_into("<I",b,508,zlib.crc32(b[:508])); return bytes(b)
def raw_fixture(kind):
    if kind=="long": ae=((0,0,LONG_N),); be=((9,0,SIDE_B_N),); high=9
    elif kind=="one": ae=((0,0,1),); be=(); high=1
    elif kind=="empty": ae=(); be=(); high=0
    else: raise ValueError(kind)
    raw=bytearray(8+BLOCKS*BLOCK); raw[:4]=b"VO08"; struct.pack_into("<I",raw,4,BLOCKS); p=memoryview(raw)[8:]
    sb=superblock(high,("P1R6"+kind).encode()); p[:BLOCK]=sb; p[-BLOCK:]=sb
    for lba,seq,side,entries in ((A0,10,0,ae),(A1,9,0,ae),(B0,20,1,be),(B1,19,1,be)):
        p[lba*BLOCK:lba*BLOCK+SLOT]=index(seq,side,entries)
    if kind=="long":
        p[BASE*BLOCK:BASE*BLOCK+LONG_N*FRAME]=pcm(frame(i) for i in range(LONG_N))
        off=BASE*BLOCK+9*CF*FRAME; p[off:off+SIDE_B_N*FRAME]=pcm(frame(i,1) for i in range(SIDE_B_N))
    elif kind=="one": p[BASE*BLOCK:BASE*BLOCK+FRAME]=pcm((frame(0),))
    return bytes(raw)
def gz(b):
    o=io.BytesIO()
    with gzip.GzipFile(filename="",mode="wb",fileobj=o,compresslevel=9,mtime=0) as f:f.write(b)
    return o.getvalue()
def interp(a,b,f):
    d=(b-a)*f; q=(d>>32) if d>=0 else -(((-d)+0xffffffff)>>32); return a+q
def render(start,rates):
    pos=start<<32; maxpos=LONG_N<<32; out=[]
    if rates[0]<0 and pos>=maxpos: pos=maxpos-1
    for rate,count in zip(rates,COUNTS):
        step=rate*65536
        for _ in range(count):
            i=pos>>32; f=pos&0xffffffff; a=frame(i); b=frame(i+1) if i+1<LONG_N else a
            out.append((interp(a[0],b[0],f),interp(a[1],b[1],f)))
            if step>0: pos=min(maxpos,pos+step)
            else: pos=max(0,pos-(-step))
    return pcm(out)
def generated():
    raws={k:raw_fixture(k) for k in ("long","one","empty")}
    files={f"fixtures/{k}.vo08.gz":gz(v) for k,v in raws.items()}
    files["candidate/scrub-forward.pcm"]=render(0,RATES)
    files["candidate/scrub-reverse.pcm"]=render(LONG_N,tuple(-x for x in RATES))
    meta={"schema":"playback-complete-draft8-fixtures-v1","long_side_a_frames":LONG_N,"long_side_b_frames":SIDE_B_N,"rates_q16_16":list(RATES),"row_render_frames":list(COUNTS),"total_output_frames":sum(COUNTS),"raw_sha256":{k:sha(v) for k,v in raws.items()}}
    files["fixtures/fixture.json"]=(json.dumps(meta,indent=2,sort_keys=True)+"\n").encode(); return raws,files
def manifest_records(files): return {k:{"bytes":len(v),"sha256":sha(v)} for k,v in sorted(files.items())}
def check(files):
    m=json.loads((HERE/"package.json").read_text()); want=m["generated_files"]
    if manifest_records(files)!=want: raise ValueError("generated files disagree with package.json")
    for n,b in files.items():
        if not (HERE/n).is_file() or (HERE/n).read_bytes()!=b: raise ValueError("checked-in drift: "+n)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--write",action="store_true"); ap.add_argument("--print-records",action="store_true"); a=ap.parse_args(); _,files=generated()
    if a.print_records: print(json.dumps(manifest_records(files),indent=2,sort_keys=True)); return 0
    if a.write:
        for n,b in files.items(): p=HERE/n; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b)
    check(files); print("PASS deterministic P1-R6 fixture/candidate regeneration")
    for n,r in manifest_records(files).items(): print(n,r["bytes"],r["sha256"])
    return 0
if __name__=="__main__": raise SystemExit(main())
