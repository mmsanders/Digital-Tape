"""Verifier-only decoder for auditing fixture construction. NOT an engine substitute.
Deliberately uses byte offsets and pairwise interval comparison, not an allocator.
"""
import struct
import zlib
from cases import CF, U32

def decode_slot(raw,side,high,capacity):
    if raw[:8]!=b'TAPEIDX\1':return None
    seq=struct.unpack_from('<I',raw,8)[0];count=struct.unpack_from('<I',raw,16)[0]
    if count>4096:return None
    if zlib.crc32(raw[:60]+raw[512:512+12*count])!=struct.unpack_from('<I',raw,60)[0]:return None
    total=struct.unpack_from('<Q',raw,20)[0]
    if raw[12]!=side or total>U32:return None
    entries=[struct.unpack_from('<III',raw,512+i*12) for i in range(count)]
    if sum(e[2] for e in entries)!=total:return None
    intervals=[]
    for chunk,start,length in entries:
        if start>=CF or length==0:return None
        base=chunk*CF+start;end=base+length
        if end>capacity*CF or (side==0 and end>high*CF):return None
        # Deliberately different from the permitted sorted implementation.
        if any(base<y and x<end for x,y in intervals):return None
        intervals.append((base,end))
    return seq,entries

def audit(c):
    """Compute only mount metadata verdict; no device I/O or repair simulation."""
    if c.blocks<=2048:return 6,None,None,None
    valid=[(i,s) for i,s in enumerate(c.supers) if s[:8]==b'TAPEFS\0\1' and
           zlib.crc32(s[:508])==struct.unpack_from('<I',s,508)[0]]
    if not valid:return 2,None,None,None
    if len(valid)==2:
        g=[struct.unpack_from('<I',s,12)[0] for _,s in valid]
        if g[0]==g[1] and valid[0][1]!=valid[1][1]:return 8,None,None,None
        selected=max(valid,key=lambda x:struct.unpack_from('<I',x[1],12)[0])
    else:selected=valid[0]
    index,s=selected
    u=lambda offset:struct.unpack_from('<I',s,offset)[0]
    if struct.unpack_from('<H',s,8)[0]!=1:return 4,None,None,None
    if s[16] not in (0,1) or u(124) not in (0,1):return 5,None,None,None
    if s[16]==1:return 7,None,None,None
    frames=u(48)*44100;capacity=(frames+CF-1)//CF;high=u(56)
    geom=(u(36)==44100 and struct.unpack_from('<HH',s,40)==(2,16) and u(44)==524288 and u(60)==65536
          and [u(o) for o in range(64,88,4)]==[8,136,264,392,2048,c.blocks-1]
          and frames>0 and frames<=U32 and capacity==u(52) and high<=capacity
          and 2048+capacity*1024<c.blocks)
    if not geom:return 6,None,None,None
    selected_sides=[];errors=[]
    for side in (0,1):
        parsed=[v for raw in c.slots[side*2:side*2+2] if (v:=decode_slot(raw,side,high,capacity)) is not None]
        err=9 if not parsed else (8 if len(parsed)==2 and parsed[0][0]==parsed[1][0] else 0)
        errors.append(err);selected_sides.append(None if err else max(parsed,key=lambda v:v[0])[1])
    if errors[0]:return errors[0],None,None,None
    aa,bb=selected_sides
    if errors[1] and c.side:return errors[1],None,None,None
    if not errors[1] and u(124)==1:
        S=u(128);rows=0
        if len(aa)==1 and aa[0][:2]==(S,0) and aa==bb:rows+=1
        if S>0 and len(aa)==len(bb)==1 and aa[0][:2]==(0,0) and bb[0][:2]==(S,0) and aa[0][2]==bb[0][2]:rows+=1
        if S>0 and len(aa)==1 and aa[0][:2]==(0,0) and aa==bb and high>(aa[0][2]+CF-1)//CF:rows+=1
        if rows!=1:return 8,None,None,None
    return 0,index,[tuple(e) for e in aa],None if bb is None else [tuple(e) for e in bb]
