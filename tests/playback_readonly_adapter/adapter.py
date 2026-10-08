#!/usr/bin/env python3
"""Mechanical JSONL bridge; only frozen public calls and verifier-owned device."""
import ctypes as C
import json,sys,os
from pathlib import Path
lib=C.CDLL(os.environ.get('TAPE_READ1_LIBRARY',str(Path(__file__).with_name('libread1.so'))))
class Device(C.Structure):
    _fields_=[('image',C.c_void_p),('trace',C.c_void_p),('dirty',C.c_void_p),('blocks',C.c_uint32),('seed',C.c_uint32),('read_only',C.c_int),('fail_read',C.c_int),('fail_write',C.c_int),('fail_flush',C.c_int),('fail_read_prefix',C.c_uint32)]
class Dev(C.Structure):
    _fields_=[('read',C.c_void_p),('write',C.c_void_p),('flush',C.c_void_p),('ctx',C.c_void_p),('block_count',C.c_uint32)]
class Warm(C.Structure):
    _fields_=[('data',C.c_void_p),('data_bytes',C.c_uint32),('valid_frames',C.c_uint32),('start_frame',C.c_uint32),('uuid',C.c_ubyte*16),('side',C.c_int)]
class Info(C.Structure):
    _fields_=[('uuid',C.c_ubyte*16),('label',C.c_char*33),('nominal_length_s',C.c_uint32),('total_frames',C.c_uint64),('total_chunks',C.c_uint32),('free_chunks',C.c_uint32),('entry_count',C.c_uint32),('entries_free',C.c_uint32),('version_minor',C.c_uint16),('writable',C.c_bool),('side_b_valid',C.c_bool),('needs_repair',C.c_bool),('warm_start_used',C.c_bool)]
class Status(C.Structure):
    _fields_=[('at_end',C.c_bool),('at_start',C.c_bool),('recording_armed',C.c_bool),('frames_owed',C.c_bool),('entries_free',C.c_uint32),('free_chunks',C.c_uint32)]
class Work(C.Structure):
    _fields_=[(n,C.c_uint64) for n in ('refill_copy_bytes','warm_adoption_copy_bytes','retained_move_bytes','mapping_entry_visits','idle_loop_iterations')]
lib.tape_instance_size.restype=C.c_size_t
lib.tape_init.argtypes=[C.c_void_p,C.c_size_t,C.POINTER(Dev),C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,C.POINTER(C.c_void_p)]
lib.tape_mount.argtypes=[C.c_void_p,C.c_int,C.c_uint64,C.POINTER(Warm)]
lib.tape_seek.argtypes=[C.c_void_p,C.c_uint64]
lib.tape_set_rate.argtypes=[C.c_void_p,C.c_int32]
for fn in ('tape_set_side','tape_arm'):getattr(lib,fn).argtypes=[C.c_void_p,C.c_int]
lib.tape_service.argtypes=[C.c_void_p,C.c_uint32,C.POINTER(C.c_bool)]
lib.tape_render.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32)]
lib.tape_feed.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32)]
for fn in ('tape_tell','tape_unmount'):getattr(lib,fn).argtypes=[C.c_void_p,C.POINTER(C.c_uint64)]
lib.tape_get_info.argtypes=[C.c_void_p,C.POINTER(Info)]
lib.tape_status.argtypes=[C.c_void_p,C.POINTER(Status)]
for fn in ('tape_commit','tape_abort'):getattr(lib,fn).argtypes=[C.c_void_p]
lib.read1_open.argtypes=[C.POINTER(Device),C.c_char_p,C.c_char_p,C.c_uint32,C.c_uint32,C.c_int]
lib.read1_close.argtypes=[C.POINTER(Device)]
try:
    work=Work.in_dll(lib,'tape_read1_work')
    control=C.c_void_p.in_dll(lib,'tape_read1_control')
    lib.tape_read1_seam_work.argtypes=[C.c_uint64]*5
except ValueError:work=None
backend=Device(); tape=C.c_void_p(); trace=None; writable=False

def open_device(cmd):
    f=cmd['fixture']
    return lib.read1_open(C.byref(backend),cmd['image_path'].encode(),trace.encode(),f['block_count'],f['seed'],not writable)

def call(cmd):
    global mem,play,rec,dev,tape,trace,writable,control_buffer
    fn=cmd['fn'];o={};rc=0
    before=[getattr(work,n) for n,_ in Work._fields_] if work else []
    if fn=='init':
        trace=cmd['trace_path'];writable=cmd['writable'];rc=open_device(cmd)
        if rc:raise RuntimeError('read1_open failed')
        mem=C.create_string_buffer(lib.tape_instance_size());play=C.create_string_buffer(cmd['play_ring_len']);rec=C.create_string_buffer(cmd['rec_ring_len'])
        dev=Dev(C.cast(lib.read1_read,C.c_void_p),C.cast(lib.read1_write,C.c_void_p) if writable else None,C.cast(lib.read1_flush,C.c_void_p),C.addressof(backend),backend.blocks)
        if work:
            control_buffer=C.create_string_buffer((cmd.get('control') or '').encode());control.value=C.addressof(control_buffer)
        rc=lib.tape_init(mem,len(mem),C.byref(dev),play,len(play),rec,len(rec),C.byref(tape))
        o['write_callback_null']=dev.write is None
    elif fn=='replace_unmounted_fixture':
        lib.read1_close(C.byref(backend));rc=open_device(cmd)
    elif fn=='inject':
        for name in ('fail_read','fail_write','fail_flush','fail_read_prefix'):setattr(backend,name,cmd.get(name,0))
    elif fn=='seam_work':
        if work:lib.tape_read1_seam_work(*[cmd['work'][n] for n,_ in Work._fields_])
    elif fn=='tape_mount':
        w=cmd.get('warm');wp=None
        if w is not None:
            data=C.create_string_buffer(bytes.fromhex(w['data_hex'])) if w['data_hex'] is not None else None
            warm=Warm(C.addressof(data) if data is not None else None,w['data_bytes'],w['valid_frames'],w['start_frame'],(C.c_ubyte*16).from_buffer_copy(bytes.fromhex(w['uuid'])),0 if w['side']=='A' else 1);wp=C.byref(warm)
        rc=lib.tape_mount(tape,0 if cmd['side']=='A' else 1,cmd['resume'],wp)
    elif fn=='tape_service':
        more=C.c_bool();rc=lib.tape_service(tape,cmd['budget'],C.byref(more));o['more_work']=more.value
    elif fn=='tape_render':
        pcm=(C.c_int16*(cmd['frames']*2))();rendered=C.c_uint32();rc=lib.tape_render(tape,pcm,cmd['frames'],C.byref(rendered))
        pos=C.c_uint64();status=Status();lib.tape_tell(tape,C.byref(pos));lib.tape_status(tape,C.byref(status))
        o.update(rendered=rendered.value,pcm_hex=bytes(pcm)[:rendered.value*4].hex(),position_frame=pos.value,at_start=status.at_start,at_end=status.at_end)
    elif fn in ('tape_tell','tape_unmount'):
        pos=C.c_uint64();rc=getattr(lib,fn)(tape,C.byref(pos));o['position_frame']=pos.value
    elif fn=='tape_get_info':
        info=Info();rc=lib.tape_get_info(tape,C.byref(info));o['warm_start_used']=info.warm_start_used
    elif fn=='tape_status':
        status=Status();rc=lib.tape_status(tape,C.byref(status));o.update(at_start=status.at_start,at_end=status.at_end)
    elif fn=='tape_feed':
        data=C.create_string_buffer(bytes.fromhex(cmd['pcm_hex']));accepted=C.c_uint32();rc=lib.tape_feed(tape,data,cmd['frames'],C.byref(accepted));o['accepted']=accepted.value
    elif fn in ('tape_commit','tape_abort'):rc=getattr(lib,fn)(tape)
    elif fn=='tape_seek':rc=lib.tape_seek(tape,cmd['frame'])
    elif fn=='tape_set_rate':rc=lib.tape_set_rate(tape,cmd['rate'])
    elif fn=='tape_set_side':rc=lib.tape_set_side(tape,0 if cmd['side']=='A' else 1)
    elif fn=='tape_arm':rc=lib.tape_arm(tape,cmd['mode'])
    else:raise ValueError(fn)
    if work and fn not in ('init','inject','replace_unmounted_fixture'):
        o['counters']={n:getattr(work,n)-before[i] for i,(n,_) in enumerate(Work._fields_)}
        if control_buffer.value==b'invented-zero-seam' and fn=='seam_work':o['counters']=dict.fromkeys(o['counters'],0)
    o.update(result=rc,ordinal=cmd['ordinal']);return o
for line in sys.stdin:
    print(json.dumps(call(json.loads(line)),separators=(',',':')),flush=True)
if backend.image:lib.read1_close(C.byref(backend))
