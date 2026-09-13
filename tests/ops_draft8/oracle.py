#!/usr/bin/env python3
"""Independent DRAFT-8 VT8-001 operation/media oracle.

No product implementation imports. Expectations come from frozen TapeFS §§5.1–5.5, §7–§8,
§9.1–§9.2 and engine public operation semantics only.
"""
from __future__ import annotations
import hashlib, json, struct, zlib
from dataclasses import dataclass
from pathlib import Path

CF = 131072
TAPE_MAX_ENTRIES = 4096
BLOCK = 512
SLOT_BYTES = 65536
LBA_A0, LBA_A1, LBA_B0, LBA_B1, LBA_CHUNK_BASE = 8, 136, 264, 392, 2048
HASHES = {
    'tapefs-v1.md': '3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb',
    'engine-api.md': '537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1',
    'acceptance.md': '7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7',
}
SB_OFF = dict(generation=12, high=56, chunks=52, base=80, mirror=84, stage=124)
SLOT_LBAS = [LBA_A0, LBA_A1, LBA_B0, LBA_B1]

@dataclass(frozen=True)
class Media:
    blocks: int
    primary: bytes
    mirror: bytes
    slots: tuple[bytes, bytes, bytes, bytes]

    def encode(self) -> bytes:
        assert len(self.primary)==BLOCK and len(self.mirror)==BLOCK
        assert all(len(x)==SLOT_BYTES for x in self.slots)
        return b'VO08' + struct.pack('<I', self.blocks) + self.primary + self.mirror + b''.join(self.slots)

    @staticmethod
    def decode(data: bytes) -> 'Media':
        need = 8 + 2*BLOCK + 4*SLOT_BYTES
        if len(data) != need or data[:4] != b'VO08':
            raise ValueError('bad VO08 media envelope')
        blocks = struct.unpack_from('<I', data, 4)[0]
        p = 8; primary=data[p:p+BLOCK]; p+=BLOCK; mirror=data[p:p+BLOCK]; p+=BLOCK
        slots=[]
        for _ in range(4): slots.append(data[p:p+SLOT_BYTES]); p+=SLOT_BYTES
        return Media(blocks, primary, mirror, tuple(slots))

@dataclass(frozen=True)
class Case:
    id: str
    operation: str
    pre: Media


def sb(*, generation=7, high=3, chunks=16, stage=0, blocks=None) -> bytes:
    if blocks is None: blocks=LBA_CHUNK_BASE+chunks*1024+1
    b=bytearray(BLOCK); b[:8]=b'TAPEFS\0\x01'
    struct.pack_into('<H',b,8,1); struct.pack_into('<H',b,10,0)
    struct.pack_into('<I',b,12,generation); struct.pack_into('<B',b,16,0)
    b[20:36]=bytes(range(16))
    struct.pack_into('<I',b,36,44100); struct.pack_into('<H',b,40,2); struct.pack_into('<H',b,42,16)
    struct.pack_into('<I',b,44,524288); struct.pack_into('<I',b,48,60); struct.pack_into('<I',b,52,chunks)
    struct.pack_into('<I',b,56,high); struct.pack_into('<I',b,60,SLOT_BYTES)
    struct.pack_into('<I',b,64,LBA_A0); struct.pack_into('<I',b,68,LBA_A1)
    struct.pack_into('<I',b,72,LBA_B0); struct.pack_into('<I',b,76,LBA_B1)
    struct.pack_into('<I',b,80,LBA_CHUNK_BASE); struct.pack_into('<I',b,84,blocks-1)
    struct.pack_into('<I',b,124,stage)
    struct.pack_into('<I',b,508,zlib.crc32(b[:508]))
    return bytes(b)


def idx(side: int, entries, sequence: int) -> bytes:
    b=bytearray(SLOT_BYTES); b[:8]=b'TAPEIDX\x01'
    total=sum(e[2] for e in entries)
    struct.pack_into('<IB3xIQ', b, 8, sequence, side, len(entries), total)
    for i,e in enumerate(entries): struct.pack_into('<III', b, 512+12*i, *e)
    crc=zlib.crc32(b[:60] + b[512:512+12*len(entries)])
    struct.pack_into('<I', b, 60, crc)
    return bytes(b)


def invalid_slot() -> bytes: return bytes(SLOT_BYTES)


def sb_valid(b: bytes) -> bool:
    return len(b)==BLOCK and b[:8]==b'TAPEFS\0\x01' and struct.unpack_from('<I',b,508)[0]==zlib.crc32(b[:508])


def select_sb(m: Media) -> bytes:
    vv=[sb_valid(m.primary), sb_valid(m.mirror)]
    if vv==[False,False]: raise ValueError('no valid superblock')
    if vv==[True,False]: return m.primary
    if vv==[False,True]: return m.mirror
    gp=struct.unpack_from('<I',m.primary,12)[0]; gm=struct.unpack_from('<I',m.mirror,12)[0]
    if gp==gm:
        if m.primary != m.mirror: raise ValueError('equal-generation divergent superblocks')
        return m.primary
    return m.primary if gp>gm else m.mirror


def parse_entries(s: bytes):
    count=struct.unpack_from('<I',s,16)[0]
    return [struct.unpack_from('<III',s,512+12*i) for i in range(count)]


def structural_sequence(s: bytes):
    if len(s)!=SLOT_BYTES or s[:8]!=b'TAPEIDX\x01': return None
    count=struct.unpack_from('<I',s,16)[0]
    if count>TAPE_MAX_ENTRIES: return None
    stored=struct.unpack_from('<I',s,60)[0]
    calc=zlib.crc32(s[:60]+s[512:512+12*count])
    if stored!=calc: return None
    return struct.unpack_from('<I',s,8)[0]


def semantic_valid(s: bytes, assigned_side: int, superblock: bytes) -> bool:
    seq=structural_sequence(s)
    if seq is None: return False
    side=s[12]; count=struct.unpack_from('<I',s,16)[0]; total=struct.unpack_from('<Q',s,20)[0]
    if side!=assigned_side: return False
    entries=parse_entries(s)
    if total != sum(e[2] for e in entries): return False
    chunks=struct.unpack_from('<I',superblock,52)[0]; high=struct.unpack_from('<I',superblock,56)[0]
    intervals=[]
    for first,start,n in entries:
        if n<1 or start>=CF: return False
        span=start+n-1; last=first+span//CF
        if last>=chunks: return False
        if assigned_side==0 and last>=high: return False
        lo=first*CF+start; hi=lo+n
        intervals.append((lo,hi))
    intervals.sort()
    if any(intervals[i][1] > intervals[i+1][0] for i in range(len(intervals)-1)): return False
    return True


def live_slot(m: Media, side: int):
    sbx=select_sb(m); ids=(0,1) if side==0 else (2,3)
    valid=[i for i in ids if semantic_valid(m.slots[i],side,sbx)]
    if not valid: return None
    if len(valid)==1: return valid[0]
    a,b=valid; sa=structural_sequence(m.slots[a]); sbq=structural_sequence(m.slots[b])
    if sa==sbq: return None
    return a if sa>sbq else b


def cartridge_sequence(m: Media) -> int:
    seq=[structural_sequence(s) for s in m.slots]
    seq=[x for x in seq if x is not None]
    if not seq: raise ValueError('no structurally valid slot')
    return max(seq)


def free_next(m: Media) -> int:
    sbx=select_sb(m); high=struct.unpack_from('<I',sbx,56)[0]
    b=live_slot(m,1)
    if b is None: return high
    mx=high
    for first,start,n in parse_entries(m.slots[b]):
        last=first+(start+n-1)//CF; mx=max(mx,last+1)
    return mx


def make_cases():
    blocks=LBA_CHUNK_BASE+16*1024+1; s=sb(blocks=blocks)
    # Reset: A0 live at 10; A1 is structurally valid at 900 but semantically invalid for A
    # because its side byte is B. B0/B1 are both semantically valid at equal sequence 500 -> degraded-B.
    reset=Media(blocks,s,s,(
        idx(0,[(0,0,128)],10), idx(1,[(1,0,64)],900),
        idx(1,[(0,0,128)],500), idx(1,[(1,0,128)],500)))
    # Record: B0 live at 20 and only references A-owned chunk 0, hence free_next==H==3.
    # A1 again carries an issued structural sequence 700 while being semantically invalid for A.
    record=Media(blocks,s,s,(
        idx(0,[(0,0,128)],10), idx(1,[(1,0,64)],700),
        idx(1,[(0,0,128)],20), invalid_slot()))
    return [Case('VT8-001-RB-ALLSLOT','reset_b',reset),
            Case('VT8-001-REC-ALLOCSEQ','record_splice_128',record)]


def _slot_header_lba(i): return SLOT_LBAS[i]

def _chunk_bounds(m: Media, chunk: int):
    base=struct.unpack_from('<I',select_sb(m),80)[0]
    return base+chunk*1024, base+(chunk+1)*1024


def _writes(events, phase=None):
    return [e for e in events if e.get('op')=='write' and (phase is None or e.get('phase')==phase)]


def check(case: Case, post: Media, events: list[dict]) -> list[str]:
    err=[]
    def req(x,msg):
        if not x: err.append(msg)
    pre=case.pre; sbpre=select_sb(pre); sbpost=select_sb(post)
    req(pre.blocks==post.blocks,'block_count changed')
    pre_seq=cartridge_sequence(pre)
    # Frozen all-slot definition is itself an oracle precondition.
    if case.id=='VT8-001-RB-ALLSLOT':
        req(pre_seq==900,'fixture lost high structural sequence')
        req(live_slot(pre,0)==0,'fixture A0 not live')
        req(live_slot(pre,1) is None,'fixture not degraded-B equal-sequence shape')
        req(post.primary==pre.primary and post.mirror==pre.mirror,'reset_b changed superblock at stage 0')
        req(post.slots[0]==pre.slots[0] and post.slots[1]==pre.slots[1] and post.slots[3]==pre.slots[3],
            'reset_b changed non-destination slot')
        req(structural_sequence(post.slots[2])==901,'reset_b did not consume all-slot max + 1')
        req(semantic_valid(post.slots[2],1,sbpost),'reset_b B0 result invalid')
        req(parse_entries(post.slots[2])==parse_entries(pre.slots[0]),'reset_b did not copy live A entries')
        req(live_slot(post,1)==2,'reset_b result not live after recovery')
        req(free_next(post)==struct.unpack_from('<I',sbpost,56)[0],'reset_b free_next should equal H')
        # No audio or superblock writes. §8 ordering: B0 entries, flush, B0 header, flush.
        for e in _writes(events):
            l=e['lba']; c=e['count'];
            req(l < LBA_CHUNK_BASE,'reset_b moved/wrote chunk data')
            req(not (l<=0<l+c or l<=post.blocks-1<l+c),'reset_b wrote superblock at stage 0')
        b0h=LBA_B0
        hdr=[i for i,e in enumerate(events) if e.get('op')=='write' and e['lba']<=b0h<e['lba']+e['count']]
        ent=[i for i,e in enumerate(events) if e.get('op')=='write' and e['lba']<=b0h+1<e['lba']+e['count']]
        req(bool(hdr) and bool(ent),'reset_b missing B0 entry/header writes')
        if hdr and ent:
            req(ent[0] < hdr[0],'reset_b header written before entry array')
            req(any(e.get('op')=='flush' for e in events[ent[0]+1:hdr[0]]),'reset_b missing flush before header')
            req(any(e.get('op')=='flush' for e in events[hdr[0]+1:]),'reset_b missing final flush')
    elif case.id=='VT8-001-REC-ALLOCSEQ':
        req(pre_seq==700,'fixture lost high structural sequence')
        req(live_slot(pre,1)==2,'fixture B0 not live')
        fn=free_next(pre); high=struct.unpack_from('<I',sbpre,56)[0]
        req(fn==3 and high==3,'record fixture free_next/H drift')
        req(post.primary==pre.primary and post.mirror==pre.mirror,'ordinary recording changed sb_generation/superblock')
        req(post.slots[0]==pre.slots[0] and post.slots[1]==pre.slots[1] and post.slots[2]==pre.slots[2],
            'record changed non-destination index slot')
        req(structural_sequence(post.slots[3])==701,'record commit did not consume all-slot max + 1')
        req(semantic_valid(post.slots[3],1,sbpost),'record B1 result invalid')
        req(parse_entries(post.slots[3])==[(0,0,128),(3,0,128)],'record splice index/allocation not at derived free_next')
        req(live_slot(post,1)==3,'record commit not live')
        req(free_next(post)==4,'post-record free_next not advanced to 4')
        # Every service audio write must be within newly allocated chunk 3, hence >= H.
        lo,hi=_chunk_bounds(pre,fn)
        svc=_writes(events,'service')
        req(bool(svc),'record service produced no audio write observation')
        for e in svc:
            req(e['lba']>=lo and e['lba']+e['count']<=hi,'record audio write outside derived allocation chunk')
        # Commit itself is metadata only and exactly two flushes for a non-empty commit.
        cw=_writes(events,'commit')
        req(all(e['lba']<LBA_CHUNK_BASE for e in cw),'commit wrote chunk data')
        cf=[e for e in events if e.get('phase')=='commit' and e.get('op')=='flush']
        req(len(cf)==2,'non-empty commit did not perform exactly two flushes')
        b1h=LBA_B1
        hdr=[i for i,e in enumerate(events) if e.get('phase')=='commit' and e.get('op')=='write' and e['lba']<=b1h<e['lba']+e['count']]
        ent=[i for i,e in enumerate(events) if e.get('phase')=='commit' and e.get('op')=='write' and e['lba']<=b1h+1<e['lba']+e['count']]
        req(bool(hdr) and bool(ent),'record commit missing B1 entry/header writes')
        if hdr and ent: req(ent[0] < hdr[0],'record header written before entries')
        # Strong WP-10 structural uniqueness check after commit.
        ss=[structural_sequence(x) for x in post.slots]; ss=[x for x in ss if x is not None]
        req(len(ss)==len(set(ss)),'post-record structurally valid slots share sequence')
    else:
        err.append('unknown case')
    return err


def synth_post(case: Case):
    """Conforming synthetic observations used only to mutation-test this oracle."""
    p=case.pre
    if case.id=='VT8-001-RB-ALLSLOT':
        slots=list(p.slots); slots[2]=idx(1,[(0,0,128)],901)
        post=Media(p.blocks,p.primary,p.mirror,tuple(slots))
        ev=[{'phase':'reset_b','op':'write','lba':LBA_B0+1,'count':1},
            {'phase':'reset_b','op':'flush'},
            {'phase':'reset_b','op':'write','lba':LBA_B0,'count':1},
            {'phase':'reset_b','op':'flush'}]
        return post,ev
    slots=list(p.slots); slots[3]=idx(1,[(0,0,128),(3,0,128)],701)
    post=Media(p.blocks,p.primary,p.mirror,tuple(slots))
    lo,_=_chunk_bounds(p,3)
    ev=[{'phase':'service','op':'write','lba':lo,'count':1},{'phase':'service','op':'flush'},
        {'phase':'commit','op':'write','lba':LBA_B1+1,'count':1},{'phase':'commit','op':'flush'},
        {'phase':'commit','op':'write','lba':LBA_B1,'count':1},{'phase':'commit','op':'flush'}]
    return post,ev


def record(case: Case, post: Media, events, status, errors):
    return {'id':case.id,'pre_sha256':hashlib.sha256(case.pre.encode()).hexdigest(),
            'post_sha256':hashlib.sha256(post.encode()).hexdigest(),'status':status,'errors':errors,
            'events':events}
