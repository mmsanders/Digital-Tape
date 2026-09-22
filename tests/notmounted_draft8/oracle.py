#!/usr/bin/env python3
"""Independent DRAFT-8 WP-06h not-mounted oracle."""
from __future__ import annotations
import struct
import zlib
from dataclasses import dataclass

CF=131072
SAMPLE_RATE=44100
NOMINAL_LENGTH_S=60
CHUNK_BYTES=524288
BLOCK=512
BLOCKS_PER_CHUNK=CHUNK_BYTES//BLOCK
SLOT_BYTES=65536
LBA_A0,LBA_A1,LBA_B0,LBA_B1,LBA_CHUNK_BASE=8,136,264,392,2048
SENTINEL=0x1111111111111111

SPEC_SHA256={
    "tapefs-v1.md":"3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb",
    "engine-api.md":"537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1",
    "acceptance.md":"7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7",
}

TARGETS=(
    ("SEEK","tape_seek"),
    ("SET-RATE","tape_set_rate"),
    ("RENDER","tape_render"),
    ("SERVICE","tape_service"),
    ("STATUS","tape_status"),
    ("INFO","tape_get_info"),
    ("TELL","tape_tell"),
    ("ARM","tape_arm"),
    ("FEED","tape_feed"),
    ("COMMIT","tape_commit"),
    ("ABORT","tape_abort"),
    ("SET-SIDE","tape_set_side"),
    ("RESET-B","tape_reset_side_b"),
    ("PROMOTE","tape_promote"),
    ("RESPOOL","tape_respool"),
    ("DUP","tape_dup"),
    ("UNMOUNT","tape_unmount"),
)
TARGET_BY_SLUG=dict(TARGETS)

@dataclass(frozen=True)
class Media:
    blocks:int
    primary:bytes
    mirror:bytes
    slots:tuple[bytes,bytes,bytes,bytes]

    def encode(self)->bytes:
        return b"VO08"+struct.pack("<I",self.blocks)+self.primary+self.mirror+b"".join(self.slots)

    @staticmethod
    def decode(data:bytes)->"Media":
        need=8+2*BLOCK+4*SLOT_BYTES
        if len(data)!=need or data[:4]!=b"VO08":
            raise ValueError("bad VO08")
        blocks=struct.unpack_from("<I",data,4)[0]
        p=8
        primary=data[p:p+BLOCK]; p+=BLOCK
        mirror=data[p:p+BLOCK]; p+=BLOCK
        slots=tuple(data[p+i*SLOT_BYTES:p+(i+1)*SLOT_BYTES] for i in range(4))
        return Media(blocks,primary,mirror,slots)

@dataclass(frozen=True)
class Case:
    id:str
    phase:str
    slug:str
    target:str
    pre:Media

def derived_total_chunks()->int:
    return (NOMINAL_LENGTH_S*SAMPLE_RATE+CF-1)//CF

def sb()->bytes:
    chunks=derived_total_chunks()
    blocks=LBA_CHUNK_BASE+chunks*BLOCKS_PER_CHUNK+1
    b=bytearray(BLOCK)
    b[:8]=b"TAPEFS\0\x01"
    struct.pack_into("<H",b,8,1)
    struct.pack_into("<H",b,10,0)
    struct.pack_into("<I",b,12,7)
    b[20:36]=bytes(range(16))
    struct.pack_into("<I",b,36,SAMPLE_RATE)
    struct.pack_into("<H",b,40,2)
    struct.pack_into("<H",b,42,16)
    struct.pack_into("<I",b,44,CHUNK_BYTES)
    struct.pack_into("<I",b,48,NOMINAL_LENGTH_S)
    struct.pack_into("<I",b,52,chunks)
    struct.pack_into("<I",b,56,3)
    struct.pack_into("<I",b,60,SLOT_BYTES)
    struct.pack_into("<I",b,64,LBA_A0)
    struct.pack_into("<I",b,68,LBA_A1)
    struct.pack_into("<I",b,72,LBA_B0)
    struct.pack_into("<I",b,76,LBA_B1)
    struct.pack_into("<I",b,80,LBA_CHUNK_BASE)
    struct.pack_into("<I",b,84,blocks-1)
    struct.pack_into("<I",b,508,zlib.crc32(b[:508]))
    return bytes(b)

def idx(side:int,entries,sequence:int)->bytes:
    b=bytearray(SLOT_BYTES)
    b[:8]=b"TAPEIDX\x01"
    total=sum(e[2] for e in entries)
    struct.pack_into("<IB3xIQ",b,8,sequence,side,len(entries),total)
    for i,e in enumerate(entries):
        struct.pack_into("<III",b,512+12*i,*e)
    struct.pack_into("<I",b,60,zlib.crc32(b[:60]+b[512:512+12*len(entries)]))
    return bytes(b)

def healthy()->Media:
    s=sb()
    chunks=derived_total_chunks()
    blocks=LBA_CHUNK_BASE+chunks*BLOCKS_PER_CHUNK+1
    return Media(
        blocks,s,s,
        (idx(0,[(0,0,256)],10),bytes(SLOT_BYTES),
         idx(1,[(0,0,64)],20),bytes(SLOT_BYTES))
    )

def make_cases()->list[Case]:
    media=healthy()
    out=[]
    for phase in ("BEFORE","AFTER"):
        for slug,target in TARGETS:
            out.append(Case(f"NM-{phase}-{slug}",phase.lower(),slug,target,media))
    return out

def _calls(obs:dict,phase:str,fn:str)->list[dict]:
    return [c for c in obs.get("calls",[]) if c.get("phase")==phase and c.get("fn")==fn]

def check(case:Case,observation:dict)->list[str]:
    err=[]
    def req(cond,msg):
        if not cond: err.append(msg)

    req(observation.get("format")=="WP06H-OBSERVATION-2","wrong observation format")
    calls=observation.get("calls")
    req(isinstance(calls,list),"calls missing/not a list")
    if not isinstance(calls,list):
        return err

    init=_calls(observation,"setup","tape_init")
    req(len(init)==1 and init[0].get("result")=="TAPE_OK","tape_init missing/failed")

    if case.phase=="after":
        mounts=_calls(observation,"setup","tape_mount")
        unmounts=_calls(observation,"setup","tape_unmount")
        req(len(mounts)==1 and mounts[0].get("result")=="TAPE_OK","after-case setup mount missing/failed")
        req(len(unmounts)==1 and unmounts[0].get("result")=="TAPE_OK","after-case setup unmount missing/failed")
        if mounts:
            req(mounts[0].get("side")=="A","after-case setup mounted wrong side")
        req(
            [(c.get("phase"),c.get("fn")) for c in calls] ==
            [("setup","tape_init"),("setup","tape_mount"),("setup","tape_unmount"),("probe",case.target)],
            "after-case call order/shape mismatch",
        )
    else:
        req(not _calls(observation,"setup","tape_mount"),"before-case unexpectedly mounted")
        req(not _calls(observation,"setup","tape_unmount"),"before-case unexpectedly unmounted")
        req(
            [(c.get("phase"),c.get("fn")) for c in calls] ==
            [("setup","tape_init"),("probe",case.target)],
            "before-case call order/shape mismatch",
        )

    probes=[c for c in calls if c.get("phase")=="probe"]
    req(len(probes)==1,"expected exactly one isolated probe call")
    if probes:
        p=probes[0]
        req(p.get("fn")==case.target,f"wrong probe target: {p.get('fn')}")
        req(p.get("result")=="TAPE_ERR_NOT_MOUNTED",case.target+" was not NOT_MOUNTED")
        if case.target=="tape_tell":
            req(p.get("out_frame_before")==SENTINEL,"tell sentinel not initialized")
            req(p.get("out_frame_after")==SENTINEL,"tell mutated out_frame")
    return err

def synth_observation(case:Case)->dict:
    calls=[{"phase":"setup","fn":"tape_init","result":"TAPE_OK"}]
    if case.phase=="after":
        calls += [
            {"phase":"setup","fn":"tape_mount","result":"TAPE_OK","side":"A"},
            {"phase":"setup","fn":"tape_unmount","result":"TAPE_OK"},
        ]
    probe={
        "phase":"probe",
        "fn":case.target,
        "result":"TAPE_ERR_NOT_MOUNTED",
        "src_callbacks":0,
        "src_writes":0,
        "dst_callbacks":0,
        "dst_writes":0,
    }
    if case.target=="tape_tell":
        probe["out_frame_before"]=SENTINEL
        probe["out_frame_after"]=SENTINEL
    calls.append(probe)
    return {
        "format":"WP06H-OBSERVATION-2",
        "adapter_kind":"synthetic",
        "calls":calls,
    }
