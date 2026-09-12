#!/usr/bin/env python3
"""Negative controls for VT8 oracle, evidence capture, spec authentication and replay."""
from __future__ import annotations
import copy
import hashlib
import json
import shutil
import struct
import tempfile
from pathlib import Path

from hardened import *
from runner import run_package
from replay import replay_bundle


def expect_fail(c, post, ev, calls, label):
    errors = check(c, post, ev, calls)
    if not errors:
        raise AssertionError('mutation escaped: ' + label)
    print('CAUGHT', label, '=>', errors[0])


def _fake_specs(path: Path):
    path.mkdir()
    data = {
        'tapefs-v1.md': b'fake tapefs for selftest\n',
        'engine-api.md': b'fake engine api for selftest\n',
        'acceptance.md': b'fake acceptance for selftest\n',
    }
    hashes = {}
    for name, content in data.items():
        (path / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    return hashes


def main():
    rb, rec = make_cases()
    for c in (rb, rec):
        p, e, calls = synth_observation(c)
        errors = check(c, p, e, calls)
        if errors:
            raise AssertionError((c.id, errors))
        print('PASS conforming', c.id)

    # Original six mutations.
    p,e,calls=synth_observation(rb); s=list(p.slots); s[2]=idx(1,[(0,0,128)],501)
    expect_fail(rb,Media(p.blocks,p.primary,p.mirror,tuple(s)),e,calls,'reset live-only sequence base')
    p,e,calls=synth_observation(rb); e=copy.deepcopy(e); e.insert(1,{'phase':'reset_b','op':'write','lba':LBA_CHUNK_BASE+2*1024,'count':1,'rc':0})
    expect_fail(rb,p,e,calls,'reset chunk write')
    p,e,calls=synth_observation(rec); s=list(p.slots); s[3]=idx(1,[(0,0,128),(3,0,128)],21)
    expect_fail(rec,Media(p.blocks,p.primary,p.mirror,tuple(s)),e,calls,'record live-only sequence base')
    p,e,calls=synth_observation(rec); e=copy.deepcopy(e); e[0]['lba']=LBA_CHUNK_BASE+2*1024
    expect_fail(rec,p,e,calls,'record allocation below H/free_next')
    p,e,calls=synth_observation(rec); b=bytearray(p.primary); struct.pack_into('<I',b,12,8); struct.pack_into('<I',b,508,zlib.crc32(b[:508])); bad=bytes(b)
    expect_fail(rec,Media(p.blocks,bad,bad,p.slots),e,calls,'record sb_generation increment')
    p,e,calls=synth_observation(rec); s=list(p.slots); s[3]=idx(1,[(0,0,128),(0,64,128)],701)
    expect_fail(rec,Media(p.blocks,p.primary,p.mirror,tuple(s)),e,calls,'record overlapping committed index')

    p,e,calls=synth_observation(rec); bad=[e[0], e[1], e[2], e[4], e[3], e[5]]
    expect_fail(rec,p,bad,calls,'V01 commit flush ordering')
    p,e,calls=synth_observation(rec); bad=copy.deepcopy(e); bad.insert(2,{'phase':'service','op':'write','lba':bad[0]['lba'],'count':1,'rc':0})
    expect_fail(rec,p,bad,calls,'record chunk-data durability barrier')
    p,e,calls=synth_observation(rec); bad=copy.deepcopy(e); bad.insert(0,{'phase':'feed','op':'write','lba':LBA_CHUNK_BASE,'count':1,'rc':0})
    expect_fail(rec,p,bad,calls,'V02 feed write below H')
    p,e,calls=synth_observation(rec); bad=copy.deepcopy(e); bad[0]['lba']=rec.pre.blocks
    expect_fail(rec,p,bad,calls,'callback out of range')
    p,e,calls=synth_observation(rec); bad=copy.deepcopy(e); bad[0]['rc']=-1
    expect_fail(rec,p,bad,calls,'callback nonzero rc')
    p,e,calls=synth_observation(rec); badc=copy.deepcopy(calls); badc[3]['accepted']=127
    expect_fail(rec,p,e,badc,'public tape_feed result mismatch')

    with tempfile.TemporaryDirectory(prefix='vt8-selftest-') as td:
        td=Path(td); specs=td/'spec'; expected=_fake_specs(specs)
        assert verify_spec_dir(specs, expected) == expected
        (specs/'tapefs-v1.md').write_bytes((specs/'tapefs-v1.md').read_bytes()+b'tamper')
        try:
            verify_spec_dir(specs, expected)
            raise AssertionError('tampered spec escaped authentication')
        except ValueError:
            print('CAUGHT tampered spec bytes')
        shutil.rmtree(specs); expected=_fake_specs(specs)

        evdir=td/'evidence'
        rc, _ = run_package(adapter=Path(__file__).with_name('_synthetic_adapter.py'), evidence_dir=evdir,
                            spec_dir=specs, adapter_kind='synthetic', adapter_source='selftest-source',
                            adapter_build='python synthetic adapter', verifier_source='selftest-verifier',
                            expected_hashes=expected)
        if rc: raise AssertionError('synthetic runner did not pass')
        rc, errs = replay_bundle(evdir, expected)
        if rc: raise AssertionError(('offline replay did not pass', errs))

        miss=td/'missing'; shutil.copytree(evdir, miss)
        (miss/'cases'/rb.id/'input.vo08.gz').unlink()
        rc,_=replay_bundle(miss, expected)
        if rc == 0: raise AssertionError('missing evidence escaped replay')
        print('CAUGHT missing replay evidence')
        tamp=td/'tampered'; shutil.copytree(evdir, tamp)
        out=tamp/'cases'/rec.id/'output.vo08.gz'; b=bytearray(out.read_bytes()); b[-1]^=1; out.write_bytes(b)
        rc,_=replay_bundle(tamp, expected)
        if rc == 0: raise AssertionError('tampered evidence escaped replay')
        print('CAUGHT tampered replay evidence')

    print('SELFTEST PASS: 2 conforming + 12 oracle controls + spec/evidence/replay controls')


if __name__ == '__main__':
    main()
