#!/usr/bin/env python3
"""Independent DRAFT-8 WP-36 source-slot oracle."""
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

SPEC_SHA256={
    "tapefs-v1.md":"3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb",
    "engine-api.md":"537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1",
    "acceptance.md":"7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7",
}

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
    pre:Media
    mount_side:str
    kind:str
    needs_repair:bool=False

def derived_total_chunks()->int:
    return (NOMINAL_LENGTH_S*SAMPLE_RATE+CF-1)//CF

def sb(*,high=3,minor=0,generation=7)->bytes:
    chunks=derived_total_chunks()
    blocks=LBA_CHUNK_BASE+chunks*BLOCKS_PER_CHUNK+1
    b=bytearray(BLOCK)
    b[:8]=b"TAPEFS\0\x01"
    struct.pack_into("<H",b,8,1)
    struct.pack_into("<H",b,10,minor)
    struct.pack_into("<I",b,12,generation)
    b[20:36]=bytes(range(16))
    struct.pack_into("<I",b,36,SAMPLE_RATE)
    struct.pack_into("<H",b,40,2)
    struct.pack_into("<H",b,42,16)
    struct.pack_into("<I",b,44,CHUNK_BYTES)
    struct.pack_into("<I",b,48,NOMINAL_LENGTH_S)
    struct.pack_into("<I",b,52,chunks)
    struct.pack_into("<I",b,56,high)
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

def invalid_slot()->bytes:
    return bytes(SLOT_BYTES)

def cartridge(*,repair=False)->Media:
    primary=sb()
    mirror=bytes(BLOCK) if repair else primary
    chunks=derived_total_chunks()
    blocks=LBA_CHUNK_BASE+chunks*BLOCKS_PER_CHUNK+1
    return Media(
        blocks,primary,mirror,
        (idx(0,[(0,0,128)],10),invalid_slot(),
         idx(1,[(0,0,128)],20),invalid_slot())
    )

def make_cases()->list[Case]:
    clean=cartridge()
    repair=cartridge(repair=True)
    return [
        Case("WP36-SRC-A",clean,"A","playback"),
        Case("WP36-SRC-B",clean,"B","playback"),
        Case("WP36-SRC-MUTATORS-B",clean,"B","mutators"),
        Case("WP36-SRC-MUTATORS-A",clean,"A","mutators"),
        Case("WP36-SRC-REPAIR-A",repair,"A","repair",True),
    ]

def _calls(calls:list[dict],fn:str)->list[dict]:
    return [c for c in calls if c.get("fn")==fn]

def check(case:Case,post:Media,observation:dict)->list[str]:
    err=[]
    def req(cond,msg):
        if not cond: err.append(msg)

    req(observation.get("format")=="WP36-SLOT-OBSERVATION-2","wrong observation format")
    events=observation.get("events")
    calls=observation.get("calls")
    req(isinstance(events,list),"events missing/not a list")
    req(isinstance(calls,list),"calls missing/not a list")
    if not isinstance(events,list) or not isinstance(calls,list):
        return err

    req(post.encode()==case.pre.encode(),"source-slot media mutated")
    req(not [e for e in events if e.get("op")=="write"],"source-slot device received a write")

    init=_calls(calls,"tape_init")
    mount=_calls(calls,"tape_mount")
    info=_calls(calls,"tape_get_info")
    unmount=_calls(calls,"tape_unmount")
    req(len(init)==1 and init[0].get("result")=="TAPE_OK","tape_init missing/failed")
    req(len(mount)==1 and mount[0].get("result")=="TAPE_OK","source-slot mount missing/failed")
    if mount:
        req(mount[0].get("side")==case.mount_side,"wrong side mounted")
    req(len(info)==1 and info[0].get("result")=="TAPE_OK","tape_get_info missing/failed")
    if info:
        req(info[0].get("writable") is False,"writable was not false")
        req(info[0].get("needs_repair") is case.needs_repair,"needs_repair mismatch")
    req(len(unmount)==1 and unmount[0].get("result")=="TAPE_OK","tape_unmount missing/failed")

    if case.kind=="playback":
        for fn in ("tape_seek","tape_set_rate"):
            hits=_calls(calls,fn)
            req(len(hits)==1 and hits[0].get("result")=="TAPE_OK",fn+" missing/failed")
        service=_calls(calls,"tape_service")
        req(bool(service),"tape_service missing")
        req(bool(service) and all(c.get("result")=="TAPE_OK" for c in service),"tape_service failed")
        req(bool(service) and service[-1].get("more_work") is False,"tape_service did not finish")
        render=_calls(calls,"tape_render")
        req(len(render)==1 and render[0].get("result")=="TAPE_OK","tape_render missing/failed")
        if render:
            req(render[0].get("rendered")==8,"tape_render did not return eight frames")

    elif case.kind=="mutators":
        for fn in ("tape_arm","tape_reset_side_b","tape_promote","tape_respool"):
            hits=_calls(calls,fn)
            req(len(hits)==1 and hits[0].get("result")=="TAPE_ERR_READ_ONLY",fn+" not READ_ONLY")
        for fn in ("tape_feed","tape_commit"):
            hits=_calls(calls,fn)
            req(len(hits)==1 and hits[0].get("result")=="TAPE_ERR_BUSY",fn+" not BUSY after refused arm")

    elif case.kind=="repair":
        req(not [e for e in events if e.get("op") in ("write","flush")],
            "read-only repair path attempted write/flush")
    else:
        req(False,"unknown case kind")
    return err

def synth_observation(case:Case):
    calls=[
        {"fn":"tape_init","result":"TAPE_OK"},
        {"fn":"tape_mount","result":"TAPE_OK","side":case.mount_side},
        {"fn":"tape_get_info","result":"TAPE_OK","writable":False,"needs_repair":case.needs_repair},
    ]
    if case.kind=="playback":
        calls += [
            {"fn":"tape_seek","result":"TAPE_OK"},
            {"fn":"tape_set_rate","result":"TAPE_OK"},
            {"fn":"tape_service","result":"TAPE_OK","more_work":False},
            {"fn":"tape_render","result":"TAPE_OK","rendered":8},
        ]
    elif case.kind=="mutators":
        calls += [
            {"fn":"tape_arm","result":"TAPE_ERR_READ_ONLY"},
            {"fn":"tape_feed","result":"TAPE_ERR_BUSY","accepted":0},
            {"fn":"tape_commit","result":"TAPE_ERR_BUSY"},
            {"fn":"tape_reset_side_b","result":"TAPE_ERR_READ_ONLY"},
            {"fn":"tape_promote","result":"TAPE_ERR_READ_ONLY","more_work":False},
            {"fn":"tape_respool","result":"TAPE_ERR_READ_ONLY","more_work":False},
        ]
    calls.append({"fn":"tape_unmount","result":"TAPE_OK"})
    return case.pre,{
        "format":"WP36-SLOT-OBSERVATION-2",
        "adapter_kind":"synthetic",
        "debug_assertions":True,
        "calls":calls,
        "events":[],
    }
