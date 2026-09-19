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


def _with_superblock(case, superblock):
    return Case(case.id, case.operation,
                Media(case.pre.blocks, superblock, superblock, case.pre.slots))


def _rewrite_status_hash(bundle: Path, case_id: str) -> None:
    manifest_path=bundle/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    entry=next(item for item in manifest['cases'] if item['id'] == case_id)
    status_path=bundle/entry['files']['adapter_status']['path']
    entry['files']['adapter_status']['sha256']=hashlib.sha256(status_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n')


def main():
    rb, rec = make_cases()
    derived=derived_total_chunks(NOMINAL_LENGTH_S)
    if derived != 21 or rb.pre.blocks != LBA_CHUNK_BASE + derived*BLOCKS_PER_CHUNK + 1:
        raise AssertionError('frozen fixture geometry derivation drift')
    print('PASS fixture geometry: ceil(60*44100/131072)=21, blocks=23553')
    mismatch_sb=sb(chunks=16, blocks=rb.pre.blocks)
    mismatch=_with_superblock(rb, mismatch_sb)
    errors=fixture_contract_errors(mismatch)
    if 'fixture stored total_chunks differs from frozen derivation' not in errors:
        raise AssertionError(('mismatched stored/derived chunks escaped fixture proof', errors))
    print('CAUGHT mismatched stored/derived fixture chunks')
    small_blocks=rb.pre.blocks-1
    small_sb=sb(chunks=derived, blocks=small_blocks)
    too_small=Case(rb.id, rb.operation, Media(small_blocks, small_sb, small_sb, rb.pre.slots))
    errors=fixture_contract_errors(too_small)
    if 'fixture derived chunk region does not fit before reserved last block' not in errors:
        raise AssertionError(('too-small fixture media escaped fixture proof', errors))
    print('CAUGHT too-small fixture media')
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

        faildir=td/'failing-evidence'
        rc, _ = run_package(adapter=Path(__file__).with_name('_synthetic_adapter_fail.py'), evidence_dir=faildir,
                            spec_dir=specs, adapter_kind='synthetic', adapter_source='selftest-failing-source',
                            adapter_build='python nonzero-exit synthetic control', verifier_source='selftest-verifier',
                            expected_hashes=expected)
        if rc != 1: raise AssertionError('nonzero adapter control did not create a failing bundle')
        rc, errs = replay_bundle(faildir, expected)
        want=[c.id + ': adapter returned 7' for c in (rb, rec)]
        if rc != 1 or errs != want:
            raise AssertionError(('nonzero adapter failure did not replay exactly', errs, want))
        print('PASS nonzero adapter failure replays exactly')

        status_tamper=td/'status-tamper'; shutil.copytree(faildir, status_tamper)
        status=status_tamper/'cases'/rb.id/'adapter-status.json'
        status.write_text(status.read_text().replace('"returncode": 7', '"returncode": 8'))
        rc,_=replay_bundle(status_tamper, expected)
        if rc == 0: raise AssertionError('tampered adapter status escaped replay')
        print('CAUGHT tampered adapter status evidence')

        status_missing=td/'status-missing'; shutil.copytree(faildir, status_missing)
        (status_missing/'cases'/rb.id/'adapter-status.json').unlink()
        rc,_=replay_bundle(status_missing, expected)
        if rc == 0: raise AssertionError('missing adapter status escaped replay')
        print('CAUGHT missing adapter status evidence')

        status_relabel=td/'status-relabel'; shutil.copytree(faildir, status_relabel)
        status=status_relabel/'cases'/rb.id/'adapter-status.json'
        data=json.loads(status.read_text()); data['outcome']='successful'
        status.write_text(json.dumps(data, sort_keys=True, indent=2)+'\n')
        _rewrite_status_hash(status_relabel, rb.id)
        rc,_=replay_bundle(status_relabel, expected)
        if rc == 0: raise AssertionError('relabeled adapter status escaped replay')
        print('CAUGHT relabeled adapter status evidence')

        occupied=td/'occupied'; occupied.mkdir(); sentinel=occupied/'sentinel'; sentinel.write_text('keep\n')
        try:
            run_package(adapter=Path(__file__).with_name('_synthetic_adapter.py'), evidence_dir=occupied,
                        spec_dir=specs, adapter_kind='synthetic', adapter_source='selftest-source',
                        adapter_build='python synthetic adapter', verifier_source='selftest-verifier',
                        expected_hashes=expected)
            raise AssertionError('nonempty evidence destination was overwritten')
        except ValueError:
            pass
        if sentinel.read_text() != 'keep\n': raise AssertionError('nonempty destination sentinel changed')
        print('CAUGHT nonempty evidence destination without modifying it')

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

    print('SELFTEST PASS: 2 conforming + 2 geometry + 12 oracle + adapter-status/spec/evidence/replay controls')


if __name__ == '__main__':
    main()
