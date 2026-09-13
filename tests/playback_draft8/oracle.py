#!/usr/bin/env python3
"""Independent DRAFT-8 P1-R2-V playback oracle; no product implementation imports."""
from __future__ import annotations
import gzip, hashlib, json, struct, wave, zlib
from pathlib import Path
from typing import Any

BLOCK=512; SLOT=65536; FRAME=4; CF=131072; CHUNK_BYTES=524288
A0,A1,B0,B1,BASE=8,136,264,392,2048
ONE=65536; NEG_ONE=-65536
SPEC={
 "tapefs-v1.md":"3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb",
 "engine-api.md":"537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1",
 "acceptance.md":"7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7"}
PACKAGE_SHA="04fb8faee7575f5cb1ce5e00bbaa601b1d7c5281e0df0a76ebf05a41fac93d66"
ENTRIES=((0,10,5),(2,20,4),(1,30,6)); TARGETS=(0,1,4,5,6,8,9,10)
CHUNK_FRAMES=CF; FRAME_BYTES=FRAME; SLOT_BYTES=SLOT; CHUNK_BYTES=CHUNK_BYTES
LBA_A0=A0; LBA_A1=A1; LBA_B0=B0; LBA_B1=B1; LBA_CHUNK_BASE=BASE
RATE_ONE=ONE; RATE_NEG_ONE=NEG_ONE; SPEC_HASHES=SPEC; PACKAGE_MANIFEST_SHA256=PACKAGE_SHA
EXPECTED_ENTRIES=ENTRIES; EXPECTED_SEEK_TARGETS=TARGETS; EXPECTED_BOUNDARIES=(0,5,9)

class VerificationError(Exception): pass

def sha256_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha256_file(p:Path)->str:return sha256_bytes(p.read_bytes())
def req(x,msg):
 if not x: raise VerificationError(msg)

def authenticate_specs(d:Path):
 got={}
 for n,w in SPEC.items():
  p=d/n; req(p.is_file(),f"missing spec {n}"); got[n]=sha256_file(p); req(got[n]==w,f"spec hash mismatch {n}")
 return got

def load_package(d:Path):
 p=d/"package.json"; req(p.is_file(),"missing package.json"); req(sha256_file(p)==PACKAGE_SHA,"package.json hash mismatch")
 m=json.loads(p.read_text()); req(m.get("schema")=="playback-draft8-package-v1","wrong package schema"); req(m.get("spec_sha256")==SPEC,"declared spec hashes drift")
 authenticate_specs(d/"spec")
 for fam,r in m["goldens"].items():
  q=d/r["path"]; req(q.is_file(),f"missing PCM {fam}"); req(sha256_file(q)==r["sha256"],f"PCM hash mismatch {fam}")
 f=d/m["fixture"]["archive"]; req(f.is_file(),"missing fixture"); req(sha256_file(f)==m["fixture"]["archive_sha256"],"fixture archive hash mismatch")
 q=d/m["fixture"]["metadata"]; req(q.is_file(),"missing fixture metadata"); req(sha256_file(q)==m["fixture"]["metadata_sha256"],"fixture metadata hash mismatch")
 raw=gzip.decompress(f.read_bytes()); req(sha256_bytes(raw)==m["fixture"]["raw_sha256"],"fixture raw hash mismatch"); req(len(raw)==m["fixture"]["raw_bytes"],"fixture size mismatch")
 return m

def decode(raw:bytes):
 req(len(raw)>=8 and raw[:4]==b"VO08","bad VO08"); n=struct.unpack_from("<I",raw,4)[0]; p=raw[8:]; req(len(p)==n*BLOCK,"VO08 size/block_count mismatch"); return n,p

def blk(p,lba,n=1):
 a=lba*BLOCK;b=a+n*BLOCK;req(0<=a<=b<=len(p),"fixture block range");return p[a:b]

def parse_sb(b):
 req(len(b)==BLOCK and b[:8]==b"TAPEFS\0\x01","superblock magic");req(struct.unpack_from("<I",b,508)[0]==zlib.crc32(b[:508]),"superblock CRC")
 u=lambda o,f:struct.unpack_from("<"+f,b,o)[0]
 return dict(major=u(8,"H"),minor=u(10,"H"),gen=u(12,"I"),state=b[16],uuid=b[20:36],rate=u(36,"I"),channels=u(40,"H"),bits=u(42,"H"),chunk_bytes=u(44,"I"),seconds=u(48,"I"),chunks=u(52,"I"),high=u(56,"I"),slot=u(60,"I"),a0=u(64,"I"),a1=u(68,"I"),b0=u(72,"I"),b1=u(76,"I"),base=u(80,"I"),mirror=u(84,"I"),stage=u(124,"I"))

def parse_idx(b,side):
 req(len(b)==SLOT and b[:8]==b"TAPEIDX\x01","index magic"); seq=struct.unpack_from("<I",b,8)[0]; req(b[12]==side,"index side"); c=struct.unpack_from("<I",b,16)[0]; req(c<=4096,"index count"); total=struct.unpack_from("<Q",b,20)[0]
 req(struct.unpack_from("<I",b,60)[0]==zlib.crc32(b[:60]+b[512:512+12*c]),"index CRC"); e=tuple(struct.unpack_from("<III",b,512+12*i) for i in range(c));req(total==sum(x[2] for x in e),"index total"); return dict(seq=seq,entries=e,total=total)

def verify_fixture(raw):
 n,p=decode(raw); s0=blk(p,0); sm=blk(p,n-1);req(s0==sm,"superblock copies differ");s=parse_sb(s0)
 req((s["major"],s["minor"],s["gen"],s["state"],s["stage"])==(1,0,7,0,0),"fixture version/state");req((s["rate"],s["channels"],s["bits"],s["chunk_bytes"],s["slot"])==(44100,2,16,CHUNK_BYTES,SLOT),"fixture PCM/layout")
 req((s["chunks"],s["high"],s["a0"],s["a1"],s["b0"],s["b1"],s["base"],s["mirror"])==(4,3,A0,A1,B0,B1,BASE,n-1),"fixture geometry");req((s["seconds"]*44100+CF-1)//CF==4 and n==BASE+4*1024+1,"fixture geometry derivation")
 a0=parse_idx(blk(p,A0,128),0);a1=parse_idx(blk(p,A1,128),0);b0=parse_idx(blk(p,B0,128),1);b1=parse_idx(blk(p,B1,128),1)
 req(a0["seq"]==10 and a1["seq"]==9 and a0["entries"]==ENTRIES and a1["entries"]==ENTRIES and a0["total"]==15,"A index drift");req(b0["seq"]==20 and b1["seq"]==19 and b0["entries"]==() and b1["entries"]==(),"B index drift")
 ints=[]
 for first,start,count in ENTRIES:
  req(count and start<CF,"run geometry");last=first+(start+count-1)//CF;req(last<s["high"],"A ownership");ints.append((first*CF+start,first*CF+start+count))
 ints.sort();req(all(ints[i][1]<=ints[i+1][0] for i in range(len(ints)-1)),"physical overlap")
 return dict(blocks=n,payload=p,sb=s,index=a0)

def timeline_pcm(raw):
 f=verify_fixture(raw);o=bytearray()
 for first,start,count in ENTRIES:
  a=BASE*BLOCK+(first*CF+start)*FRAME;o+=f["payload"][a:a+count*FRAME]
 req(len(o)==60,"timeline length");return bytes(o)

def frames(pcm):req(len(pcm)%4==0,"PCM alignment");return [struct.unpack_from("<hh",pcm,i) for i in range(0,len(pcm),4)]
def expected_outputs(raw):
 p=timeline_pcm(raw);fr=frames(p);return {"forward_1x":p,"seek_boundaries":b"".join(struct.pack("<hh",*fr[i]) for i in TARGETS),"reverse_neg1x":b"".join(struct.pack("<hh",*x) for x in reversed(fr))}

def interpolate(a,b,f):
 d=(int(b)-int(a))*int(f);q=(d>>32) if d>=0 else -(((-d)+0xffffffff)>>32);return int(a)+q

def draft5_bad_reverse(raw):
 fr=frames(timeline_pcm(raw)); pos=(len(fr)<<32)-1; out=[]; step=1<<32
 for _ in range(len(fr)):
  i=pos>>32;f=pos&0xffffffff;a=fr[i];b=fr[i+1] if i+1<len(fr) else a;out.append((interpolate(a[0],b[0],f),interpolate(a[1],b[1],f)));pos=max(0,pos-step)
 return b"".join(struct.pack("<hh",*x) for x in out)

def pcm_diff(e,a):
 es=frames(e) if len(e)%4==0 else [];as_=frames(a) if len(a)%4==0 else []; first=None;count=peak=0
 for i in range(max(len(es),len(as_))):
  E=es[i] if i<len(es) else (0,0);A=as_[i] if i<len(as_) else (0,0)
  for ch in range(2):
   d=A[ch]-E[ch]
   if d or i>=len(es) or i>=len(as_):
    count+=1;peak=max(peak,abs(d)); first=first or dict(frame=i,channel=ch,expected=E[ch],actual=A[ch],delta=d)
 return dict(match=e==a,expected_bytes=len(e),actual_bytes=len(a),first_difference=first,differing_samples=count,peak_abs_delta=peak)

def write_difference_wav(e,a,path):
 E=frames(e) if len(e)%4==0 else [];A=frames(a) if len(a)%4==0 else [];d=bytearray()
 for i in range(max(len(E),len(A))):
  x=E[i] if i<len(E) else (0,0);y=A[i] if i<len(A) else (0,0);v=[max(-32768,min(32767,y[c]-x[c])) for c in (0,1)];d+=struct.pack("<hh",*v)
 path.parent.mkdir(parents=True,exist_ok=True)
 with wave.open(str(path),"wb") as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(bytes(d))

def services(calls,p):
 start=p;done=False
 while p<len(calls) and calls[p].get("call")=="tape_service":
  c=calls[p];req(c.get("result")==0 and c.get("block_budget")==1024 and isinstance(c.get("more_work"),bool),"bad service");req(not done,"service after completion");done=not c["more_work"];p+=1
 req(p>start and done,"service sequence incomplete");return p

def call(c,n):return c.get("call")==n and c.get("result")==0
def validate_calls(fam,c):
 req(c and call(c[0],"tape_mount") and c[0].get("side")=="A" and c[0].get("resume_frame")==0 and c[0].get("warm") is None,f"{fam}: mount")
 if fam=="forward_1x":
  req(call(c[1],"tape_set_rate") and c[1].get("rate_q16_16")==ONE,"forward rate");p=services(c,2);req(call(c[p],"tape_render") and (c[p].get("requested"),c[p].get("rendered"))==(15,15),"forward render");p+=1
 elif fam=="reverse_neg1x":
  req(call(c[1],"tape_seek") and c[1].get("frame")==15,"reverse seek end");req(call(c[2],"tape_set_rate") and c[2].get("rate_q16_16")==NEG_ONE,"reverse rate");p=services(c,3);req(call(c[p],"tape_render") and (c[p].get("requested"),c[p].get("rendered"))==(15,15),"reverse render");p+=1
 else:
  req(call(c[1],"tape_set_rate") and c[1].get("rate_q16_16")==ONE,"seek rate");p=2
  for t in TARGETS:
   req(call(c[p],"tape_seek") and c[p].get("frame")==t,f"seek target {t}");p=services(c,p+1);req(call(c[p],"tape_render") and (c[p].get("requested"),c[p].get("rendered"))==(1,1),f"seek render {t}");p+=1
 req(p==len(c)-1 and call(c[p],"tape_unmount"),f"{fam}: unmount/order")

def validate_callbacks(fam,calls,events,blocks):
 req(isinstance(events,list) and events,f"{fam}: callbacks missing");m=s=0
 for i,e in enumerate(events):
  ci=e.get("call_index");req(isinstance(ci,int) and 0<=ci<len(calls),f"{fam}: callback index {i}");name=calls[ci].get("call");req(name in ("tape_mount","tape_service"),f"{fam}: I/O during {name}");req(e.get("op")=="read" and e.get("rc")==0,f"{fam}: non-read/failing callback");l=e.get("lba");n=e.get("count");req(isinstance(l,int) and isinstance(n,int) and n>=1 and 0<=l<blocks and l+n<=blocks,f"{fam}: callback range");m+=name=="tape_mount";s+=name=="tape_service"
 req(m>0 and s>0,f"{fam}: need mount and service reads")

def check_run(raw,obs,outputs):
 f=verify_fixture(raw);req(obs.get("schema")=="playback-draft8-observation-v1","observation schema");req(obs.get("fixture_sha256")==sha256_bytes(raw),"observation fixture hash");req(obs.get("adapter",{}).get("kind") in ("synthetic","product"),"adapter kind");cs=obs.get("cases");req(isinstance(cs,dict),"cases missing");exp=expected_outputs(raw);r={"pass":True,"families":{}}
 for fam in ("forward_1x","seek_boundaries","reverse_neg1x"):
  req(fam in cs and fam in outputs,f"missing family {fam}");c=cs[fam].get("calls");req(isinstance(c,list),f"{fam}: calls");validate_calls(fam,c);validate_callbacks(fam,c,cs[fam].get("callbacks"),f["blocks"]);d=pcm_diff(exp[fam],outputs[fam]);r["families"][fam]=d;r["pass"] &= d["match"]
 return r

# Descriptive aliases used by adapters/readers.
decode_vo08 = decode
