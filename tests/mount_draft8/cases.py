"""Independent DRAFT-8 byte fixtures. Expected outcomes are assigned by each case.
No implementation headers, code, generated product images, or private adapters used.
"""
import copy
import hashlib
import random
import struct
import zlib
from dataclasses import dataclass, field

CF = 131072
U32 = 0xffffffff
SEED = 0xD8A607
HASHES = {
    'tapefs-v1.md': '3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb',
    'engine-api.md': '537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1',
    'acceptance.md': '7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7',
}
ERROR = dict(OK=0, IO=1, BAD_MAGIC=2, CRC=3, VERSION=4, UNSUPPORTED_STATE=5,
             GEOMETRY=6, INCOMPLETE=7, INCONSISTENT=8, NO_VALID_INDEX=9)
OFF = dict(major=(8,'H'),minor=(10,'H'),generation=(12,'I'),state=(16,'B'),
           sample_rate=(36,'I'),channels=(40,'H'),bits=(42,'H'),chunk_bytes=(44,'I'),
           seconds=(48,'I'),chunks=(52,'I'),high=(56,'I'),slot_bytes=(60,'I'),
           a0=(64,'I'),a1=(68,'I'),b0=(72,'I'),b1=(76,'I'),base=(80,'I'),
           mirror=(84,'I'),stage=(124,'I'),staging=(128,'I'))

def chunks(seconds):
    return (seconds*44100 + CF-1)//CF

def sb(seconds=60, block_count=None, **kw):
    n=chunks(seconds)
    d=dict(major=1,minor=0,generation=7,state=0,sample_rate=44100,channels=2,bits=16,
           chunk_bytes=524288,seconds=seconds,chunks=n,high=3,slot_bytes=65536,
           a0=8,a1=136,b0=264,b1=392,base=2048,mirror=(block_count or (2048+n*1024+1))-1,
           stage=0,staging=0)
    d.update(kw)
    b=bytearray(512);b[:8]=b'TAPEFS\0\x01';b[20:36]=bytes(range(16));b[88:96]=b'Verifier'
    for k,v in d.items(): struct.pack_into('<'+OFF[k][1],b,OFF[k][0],v)
    return sb_crc(b)

def sb_crc(b):
    b=bytearray(b);struct.pack_into('<I',b,508,zlib.crc32(b[:508]));return bytes(b)

def sb_field(b,key,value):
    b=bytearray(b);off,fmt=OFF[key];struct.pack_into('<'+fmt,b,off,value);return sb_crc(b)

def idx(side,entries=(),sequence=10,total=None,count=None):
    b=bytearray(65536);b[:8]=b'TAPEIDX\x01'
    struct.pack_into('<IB3xIQ',b,8,sequence,side,len(entries) if count is None else count,
                     sum(e[2] for e in entries) if total is None else total)
    for i,e in enumerate(entries): struct.pack_into('<III',b,512+12*i,*e)
    struct.pack_into('<I',b,60,zlib.crc32(b[:60]+b[512:512+12*len(entries)]))
    return bytes(b)

def corrupt(b,at=60):
    b=bytearray(b);b[at]^=0x80;return bytes(b)

A=[(0,0,4)];B=[(4,0,5)]
@dataclass
class Case:
    id: str
    section: str
    blocks: int=2048+chunks(60)*1024+1
    side: int=0
    resume: int=0
    writable: int=1
    fail_write: int=0
    fail_flush: int=0
    supers: list=field(default_factory=lambda:[sb(),sb()])
    slots: list=field(default_factory=lambda:[idx(0,A,10),bytes(65536),idx(1,B,20),bytes(65536)])
    allowed: tuple=(0,)
    live_a: list=field(default_factory=lambda:copy.deepcopy(A))
    live_b: object=field(default_factory=lambda:copy.deepcopy(B))
    selected: int=0
    repair: object=None
    phase0: bool=False
    note: str=''
    def encode(self):
        return struct.pack('<4sIIQIII',b'VM08',self.blocks,self.side,self.resume,self.writable,
                           self.fail_write,self.fail_flush)+b''.join(self.supers+self.slots)
    def expected(self):
        if self.allowed!=(0,): return {}
        s=self.supers[self.selected]
        vals={k:struct.unpack_from('<'+fmt,s,off)[0] for k,(off,fmt) in OFF.items()}
        entries=self.live_a if self.side==0 else self.live_b
        free_next=max([vals['high']]+[c+(start+length-1)//CF+1 for c,start,length in (self.live_b or [])])
        return dict(total_frames=sum(e[2] for e in entries),entry_count=len(entries),
                    entries_free=4096-len(entries),total_chunks=vals['chunks'],
                    free_chunks=vals['chunks']-free_next,nominal_length_s=vals['seconds'],
                    version_minor=vals['minor'],writable=int(bool(self.writable and vals['minor']==0)),
                    side_b_valid=int(self.live_b is not None),
                    needs_repair=int(self.repair is not None and (not self.writable or vals['minor']>0 or self.fail_write or self.fail_flush)),
                    warm_start_used=0,uuid=s[20:36].hex())

def cases():
    out=[]
    def add(name,section='TapeFS 4.1',**kw):
        c=Case(name,section,**kw);out.append(c);return c
    def refuse(c,error): c.allowed=(ERROR[error],);return c
    def pair(c,key,value): c.supers=[sb_field(s,key,value) for s in c.supers]
    add('M-base-A');add('M-base-B',side=1)
    c=add('M-device-u32-max',blocks=U32);pair(c,'mirror',U32-1)
    c=add('M-all-store-owned-A');pair(c,'high',chunks(60))
    c=add('M-timeline-u32-max',blocks=2048+chunks(97391)*1024+1,
          live_a=[(0,0,U32)],live_b=[(0,0,U32)],resume=(1<<64)-1)
    c.supers=[sb(97391,c.blocks,high=chunks(97391))]*2
    c.slots=[idx(0,c.live_a,1),bytes(65536),idx(1,c.live_b,2),bytes(65536)]
    for n in [0,1,2,2047,2048]:
        refuse(add('M-phase0-'+str(n),blocks=n,phase0=True),'GEOMETRY')
    c=add('M-addressable-but-no-store',blocks=2049);pair(c,'mirror',2048);refuse(c,'GEOMETRY')
    for side in (0,1):
        c=add('M-empty-'+str(side),side=side,live_a=[],live_b=[])
        c.slots=[idx(0,[],1),bytes(65536),idx(1,[],2),bytes(65536)];pair(c,'high',0)
    for seconds in [1,3600,5400,7200,97391]:
        n=chunks(seconds);bc=2048+n*1024+1
        c=add('M-geometry-fit-'+str(seconds),blocks=bc,live_a=[],live_b=[])
        c.supers=[sb(seconds,bc,high=0)]*2;c.slots=[idx(0,[],1),bytes(65536),idx(1,[],2),bytes(65536)]
        d=copy.deepcopy(c);d.id='M-geometry-mirror-overlap-'+str(seconds);d.blocks-=1
        d.supers=[sb_field(s,'mirror',d.blocks-1) for s in d.supers];refuse(d,'GEOMETRY');out.append(d)
    for key,value in [('seconds',0),('seconds',97392),('seconds',U32),('chunks',0),('chunks',chunks(60)+1),
                      ('high',chunks(60)+1),('sample_rate',48000),('channels',1),('bits',24),
                      ('chunk_bytes',524287),('slot_bytes',65535),('a0',9),('a1',137),('b0',265),
                      ('b1',393),('base',2049),('mirror',7)]:
        c=add('M-geometry-'+key+'-'+str(value));pair(c,key,value);refuse(c,'GEOMETRY')
    c=add('M-no-magic');c.supers=[bytes(512)]*2;c.allowed=(ERROR['BAD_MAGIC'],ERROR['CRC'])
    c=add('M-bad-crc');c.supers=[corrupt(sb(),508)]*2;c.allowed=(ERROR['BAD_MAGIC'],ERROR['CRC'])
    # §4.1 permits BAD_MAGIC or CRC without precedence; do not invent a tighter oracle.
    for winner in (0,1):
        loser=1-winner
        for kind in ('invalid','stale'):
            for mode in ('rw','ro','minor','writefail','flushfail'):
                c=add(f'M-repair-{winner}-{kind}-{mode}',selected=winner,repair=loser)
                if mode=='ro':c.writable=0
                if mode=='minor':pair(c,'minor',1)
                c.supers[loser]=corrupt(c.supers[loser],508) if kind=='invalid' else sb_field(c.supers[loser],'generation',6)
                c.fail_write=int(mode=='writefail');c.fail_flush=int(mode=='flushfail')
    c=add('M-equal-super-divergent');c.supers[1]=sb_field(c.supers[1],'high',4);refuse(c,'INCONSISTENT')
    for key,value,error in [('major',2,'VERSION'),('state',2,'UNSUPPORTED_STATE'),('stage',2,'UNSUPPORTED_STATE'),('state',1,'INCOMPLETE')]:
        for damaged in (False,True):
            c=add(f'M-admit-{key}-{value}-{damaged}');pair(c,key,value)
            if damaged:c.supers[1]=corrupt(c.supers[1],508)
            refuse(c,error)
    for fields,error,name in [([('major',2),('state',2),('seconds',0)],'VERSION','major-first'),
                              ([('state',1),('stage',2),('seconds',0)],'UNSUPPORTED_STATE','defined-first'),
                              ([('state',1),('seconds',0)],'INCOMPLETE','wip-first')]:
        c=add('M-precedence-'+name)
        for k,v in fields:pair(c,k,v)
        c.supers[1]=corrupt(c.supers[1],508);refuse(c,error)
    # Selection must use highest structurally-valid SB BEFORE semantic admission.
    c=add('M-newer-unsupported-wins',selected=1);c.supers[1]=sb_field(sb_field(sb(),'generation',8),'major',2);refuse(c,'VERSION')
    c=add('M-newer-water-wins',selected=1,repair=0,live_a=[(3,0,4)])
    c.supers[1]=sb_field(sb_field(sb(),'generation',8),'high',4);c.slots[0]=idx(0,c.live_a,10)
    # Invalid slot cases keep A1 absent: A failure is mandatory on BOTH requested sides.
    invalids={
        'magic':corrupt(idx(0,A),0),'crc':corrupt(idx(0,A)),
        'wrong-side':idx(1,A),'count-4097':idx(0,[],count=4097),'count-u32':idx(0,[],count=U32),
        'total-mismatch':idx(0,A,total=5),'total-cap':idx(0,[(0,0,U32),(1,0,1)],total=U32+1),
        'zero-length':idx(0,[(0,0,0)]),'start-bound':idx(0,[(0,CF,1)]),
        'chunk-bound':idx(0,[(chunks(60),0,1)]),'water-bound':idx(0,[(3,0,1)]),
        'run-crosses-water':idx(0,[(2,CF-1,2)]),'extent-u32-overflow':idx(0,[(0,CF-1,U32)]),
        'chunk-add-overflow':idx(0,[(U32,CF-1,2)]),
        'overlap-min':idx(0,[(0,0,1),(0,0,1)]),'overlap-cross-chunk':idx(0,[(0,CF-1,2),(1,0,1)])}
    for name,image in invalids.items():
        for side in (0,1):
            c=add(f'M-index-{name}-{side}','TapeFS 5.1-5.3',side=side);c.slots[0]=image
            c.supers[1]=corrupt(c.supers[1],508);refuse(c,'NO_VALID_INDEX')
    for side in (0,1):
        c=add('M-A-equal-sequence-'+str(side),side=side);c.slots[1]=idx(0,A,10);refuse(c,'INCONSISTENT')
    for live_slot in (0,1):
        c=add('M-A-newest-'+str(live_slot),live_a=[(1,7,9)])
        c.slots[live_slot]=idx(0,c.live_a,90);c.slots[1-live_slot]=idx(0,A,10)
        c=add('M-A-invalid-newest-fallback-'+str(live_slot),live_a=A)
        c.slots[live_slot]=idx(0,A,10);c.slots[1-live_slot]=idx(0,[(3,0,7)],91)
    c=add('M-ignore-index-undefined-tail');v=bytearray(c.slots[0]);v[1024:]=b'\xD7'*(65536-1024);c.slots[0]=bytes(v)
    for name,entries in [('same-chunk-adjacent',[(0,0,1),(0,1,1)]),('same-chunk-gap',[(0,0,1),(0,2,1)]),
                         ('timeline-reverse',[(1,0,3),(0,0,2)]),('run-water-last-valid',[(1,CF-1,CF+1)]),
                         ('max-entries',[(0,i,1) for i in range(4096)])]:
        c=add('M-valid-'+name,'TapeFS 5.1-5.3',live_a=entries);c.slots[0]=idx(0,entries)
    for cause in ('absent','equal'):
        for stage in (0,1):
            for side in (0,1):
                c=add(f'M-degraded-{cause}-stage{stage}-side{side}',side=side,live_b=None)
                c.slots[2:]=[bytes(65536)]*2 if cause=='absent' else [idx(1,[(4,0,1)],20),idx(1,[(5,0,2)],20)]
                pair(c,'stage',stage)
                if side:refuse(c,'NO_VALID_INDEX' if cause=='absent' else 'INCONSISTENT')
    # §9.3.3 shape checks only; no promote or resume operation is called.
    for name,staging,high,aa,bb in [
        ('row1',5,6,[(5,0,7)],[(5,0,7)]),('row1-S0',0,2,[(0,0,7)],[(0,0,7)]),
        ('row2',5,6,[(0,0,7)],[(5,0,7)]),('row3',5,6,[(0,0,7)],[(0,0,7)])]:
        for side in (0,1):
            c=add(f'M-stage-{name}-side{side}','TapeFS 4.2 / 9.3.3',side=side,live_a=aa,live_b=bb)
            for k,v in [('stage',1),('staging',staging),('high',high)]:pair(c,k,v)
            c.slots=[idx(0,aa,30),bytes(65536),idx(1,bb,31),bytes(65536)]
    for name,aa,bb,staging,high in [('wrong-B',[(0,0,7)],[(4,0,7)],5,6),
                ('length-mismatch',[(0,0,7)],[(5,0,8)],5,6),
                ('fragmented-A',[(0,0,3),(1,0,4)],[(5,0,7)],5,6),
                ('row3-H-boundary',[(0,0,7)],[(0,0,7)],5,1)]:
        c=add('M-stage-unmatched-'+name,live_a=aa,live_b=bb)
        for k,v in [('stage',1),('staging',staging),('high',high)]:pair(c,k,v)
        c.slots=[idx(0,aa,30),bytes(65536),idx(1,bb,31),bytes(65536)]
        c.supers[1]=corrupt(c.supers[1],508);refuse(c,'INCONSISTENT')
    for name,entries in [('references-A',A),('empty-B',[]),('last-chunk',[(chunks(60)-1,CF-1,1)]),
                         ('B-run-crosses-chunks',[(4,CF-1,CF+2)]),('leaked-hole',[(8,0,1)]),
                         ('both-owned-regions',[(0,0,4),(6,3,2)])]:
        for side in (0,1):
            c=add(f'M-ownership-{name}-side{side}','TapeFS 7',side=side,live_b=entries);c.slots[2]=idx(1,entries,20)
    c=add('M-B-newest-determines-free',live_b=[(6,0,1)]);c.slots[3]=idx(1,c.live_b,21)
    c=add('M-B-invalid-high-slot-excluded',live_b=B);c.slots[3]=idx(1,[(chunks(60),0,1)],1000)
    # structurally valid but semantically bad slots must not prevent mount. Their
    # high sequence is NOT observable here; future commits must test consumption.
    c=add('M-structural-high-sequence-semantic-invalid');c.slots[1]=idx(1,[(3,0,1)],U32)
    for value in [0,3,4,5,1<<32,(1<<64)-1]:add('M-resume-'+str(value),resume=value)
    rng=random.Random(SEED)
    for i in range(64):
        start=rng.randrange(CF-200);length=rng.randrange(1,100);gap=rng.randrange(0,100)
        entries=[(1,start,length),(1,start+length+gap,1)]
        rng.shuffle(entries)
        c=add(f'M-generated-disjoint-{i:02}','TapeFS 5.1',live_a=entries);c.slots[0]=idx(0,entries)
        overlap=[(1,start,length),(1,start+length-1,1)]
        c=add(f'M-generated-overlap-{i:02}','TapeFS 5.1');c.slots[0]=idx(0,overlap);refuse(c,'NO_VALID_INDEX')
    assert len({c.id for c in out})==len(out)
    return out

def authenticate(root):
    for name,want in HASHES.items():
        got=hashlib.sha256((root/name).read_bytes()).hexdigest()
        if got!=want: raise ValueError(f'{name}: candidate drift: {got} != {want}')
