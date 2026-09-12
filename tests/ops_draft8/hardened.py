#!/usr/bin/env python3
"""P1-R1 hardening layered over the independently authored DRAFT-8 media oracle."""
from __future__ import annotations
import hashlib
from pathlib import Path

import oracle as base
from oracle import *  # re-export fixture/media helpers for package tools

OBS_FORMAT = 'VT8-OPS-OBSERVATION-1'


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_spec_dir(spec_dir: Path, expected: dict[str, str] | None = None) -> dict[str, str]:
    expected = HASHES if expected is None else expected
    got = {}
    for name, want in expected.items():
        p = Path(spec_dir) / name
        if not p.is_file():
            raise ValueError(f'missing spec byte source: {p}')
        digest = sha256_bytes(p.read_bytes())
        if digest != want:
            raise ValueError(f'spec hash mismatch for {name}: got {digest}, want {want}')
        got[name] = digest
    return got


def _metadata_range(m: Media, lba: int, count: int) -> bool:
    end = lba + count
    ranges = [(0, 1), (LBA_A0, LBA_A0 + 128), (LBA_A1, LBA_A1 + 128),
              (LBA_B0, LBA_B0 + 128), (LBA_B1, LBA_B1 + 128), (m.blocks - 1, m.blocks)]
    return any(lba >= lo and end <= hi for lo, hi in ranges)


def _validate_event_schema(case: Case, events: list[dict], req) -> None:
    allowed = ({'mount', 'get_info', 'reset_b', 'unmount', 'remount'} if case.operation == 'reset_b'
               else {'mount', 'seek', 'arm', 'feed', 'service', 'commit', 'unmount', 'remount'})
    for i, e in enumerate(events):
        req(isinstance(e, dict), f'event {i} is not an object')
        if not isinstance(e, dict):
            continue
        phase, op = e.get('phase'), e.get('op')
        req(phase in allowed, f'event {i} has illegal phase {phase!r}')
        req(op in {'read', 'write', 'flush'}, f'event {i} has illegal op {op!r}')
        req(type(e.get('rc')) is int, f'event {i} missing integer callback rc')
        if type(e.get('rc')) is int:
            req(e['rc'] == 0, f'event {i} callback rc is nonzero')
        if op in {'read', 'write'}:
            lba, count = e.get('lba'), e.get('count')
            req(type(lba) is int and type(count) is int, f'event {i} missing integer lba/count')
            if type(lba) is int and type(count) is int:
                req(0 <= lba <= 0xFFFFFFFF, f'event {i} lba outside u32')
                req(1 <= count <= 0xFFFFFFFF, f'event {i} count outside callback domain')
                req(lba + count <= case.pre.blocks, f'event {i} callback batch outside block_count')


def _validate_phase_io(case: Case, events: list[dict], req) -> None:
    pre = case.pre
    for e in events:
        if not isinstance(e, dict) or e.get('op') not in {'read', 'write', 'flush'}:
            continue
        p, op = e.get('phase'), e.get('op')
        if case.operation == 'reset_b':
            if p in {'get_info', 'unmount'}:
                req(False, f'{p} unexpectedly performed block I/O')
            elif p in {'mount', 'remount'}:
                req(op == 'read', f'{p} performed non-read block I/O')
                if op == 'read' and type(e.get('lba')) is int and type(e.get('count')) is int:
                    req(_metadata_range(pre, e['lba'], e['count']), f'{p} read outside metadata')
            elif p == 'reset_b' and op in {'read', 'write'} and type(e.get('lba')) is int and type(e.get('count')) is int:
                req(_metadata_range(pre, e['lba'], e['count']), 'reset_b touched chunk/nonmetadata range')
        else:
            if p in {'seek', 'arm', 'feed', 'unmount'}:
                req(False, f'{p} unexpectedly performed block I/O')
            elif p in {'mount', 'remount'}:
                req(op == 'read', f'{p} performed non-read block I/O')
                if op == 'read' and type(e.get('lba')) is int and type(e.get('count')) is int:
                    req(_metadata_range(pre, e['lba'], e['count']), f'{p} read outside metadata')
            elif p == 'commit':
                req(op in {'write', 'flush'}, 'commit performed an unexpected read')
            elif p == 'service' and op == 'write' and type(e.get('lba')) is int and type(e.get('count')) is int:
                lo, hi = base._chunk_bounds(pre, free_next(pre))
                req(e['lba'] >= lo and e['lba'] + e['count'] <= hi, 'service write outside the one allocated chunk')


def _assert_index_commit(events, phase, slot_lba, req) -> None:
    io = [e for e in events if e.get('phase') == phase and e.get('op') in {'write', 'flush'}]
    req(len(io) == 4, f'{phase} index commit did not have exactly 2 writes + 2 flushes')
    if len(io) != 4:
        return
    a, b, c, d = io
    req(a.get('op') == 'write' and a.get('lba') == slot_lba + 1 and a.get('count') == 1,
        f'{phase} entry-array write not exactly slot block 1')
    req(b.get('op') == 'flush', f'{phase} missing entry-array durability flush')
    req(c.get('op') == 'write' and c.get('lba') == slot_lba and c.get('count') == 1,
        f'{phase} header write not exactly slot block 0 after barrier')
    req(d.get('op') == 'flush', f'{phase} missing final header durability flush')


def _validate_calls(case: Case, calls: list[dict] | None, req) -> None:
    req(isinstance(calls, list), 'missing public-call result evidence')
    if not isinstance(calls, list):
        return
    for i, c in enumerate(calls):
        req(isinstance(c, dict), f'call {i} is not an object')
        if isinstance(c, dict):
            req(isinstance(c.get('phase'), str) and isinstance(c.get('call'), str), f'call {i} missing phase/call')
            req(isinstance(c.get('result'), str), f'call {i} missing result')
    if case.operation == 'reset_b':
        want = [('mount','tape_mount'), ('get_info','tape_get_info'), ('reset_b','tape_reset_side_b'),
                ('unmount','tape_unmount'), ('remount','tape_mount')]
        got = [(c.get('phase'), c.get('call')) for c in calls if isinstance(c, dict)]
        req(got == want, 'reset_b public-call sequence differs from script')
        if len(calls) == len(want):
            req(all(c.get('result') == 'TAPE_OK' for c in calls), 'reset_b script public call returned non-OK')
            req(calls[1].get('side_b_valid') is False, 'degraded-B was not proven via public info')
            req(calls[4].get('side') == 'B', 'reset_b remount did not identify Side B')
        return
    names = [(c.get('phase'), c.get('call')) for c in calls if isinstance(c, dict)]
    req(len(names) >= 8, 'record public-call evidence incomplete')
    if len(names) < 8:
        return
    req(names[:4] == [('mount','tape_mount'), ('seek','tape_seek'), ('arm','tape_arm'), ('feed','tape_feed')],
        'record setup public-call sequence differs from script')
    svc = [i for i, x in enumerate(names) if x == ('service','tape_service')]
    req(bool(svc), 'record script contains no tape_service result')
    if svc:
        req(svc == list(range(4, 4 + len(svc))), 'service calls are not contiguous')
        tail = 4 + len(svc)
        req(names[tail:] == [('commit','tape_commit'), ('unmount','tape_unmount'), ('remount','tape_mount')],
            'record completion public-call sequence differs from script')
        sc = calls[4:tail]
        req(all(c.get('result') == 'TAPE_OK' for c in sc), 'tape_service returned non-OK')
        req(all(type(c.get('block_budget')) is int and c.get('block_budget') > 0 for c in sc),
            'service result missing positive block_budget')
        req(all(c.get('more_work') is True for c in sc[:-1]) and sc[-1].get('more_work') is False,
            'service more_work sequence is not true* then false')
    req(calls[0].get('result') == 'TAPE_OK' and calls[0].get('side') == 'B', 'mount result/side mismatch')
    req(calls[1].get('result') == 'TAPE_OK' and calls[1].get('frame') == 128, 'seek result/argument mismatch')
    req(calls[2].get('result') == 'TAPE_OK' and calls[2].get('mode') == 'TAPE_REC_SPLICE', 'arm result/mode mismatch')
    req(calls[3].get('result') == 'TAPE_OK' and calls[3].get('requested') == 128 and calls[3].get('accepted') == 128,
        'feed did not prove all 128 frames accepted')
    req(calls[-3].get('result') == 'TAPE_OK', 'commit did not return TAPE_OK')
    req(calls[-2].get('result') == 'TAPE_OK', 'unmount did not return TAPE_OK')
    req(calls[-1].get('result') == 'TAPE_OK' and calls[-1].get('side') == 'B', 'remount did not prove Side B')


def check(case: Case, post: Media, events: list[dict], calls: list[dict] | None = None) -> list[str]:
    """Base media oracle plus P1-R1 trace/order/call-result hardening."""
    errors = list(base.check(case, post, events))
    def req(x, msg):
        if not x and msg not in errors:
            errors.append(msg)
    _validate_event_schema(case, events, req)
    _validate_phase_io(case, events, req)
    _validate_calls(case, calls, req)
    if case.operation == 'reset_b':
        _assert_index_commit(events, 'reset_b', LBA_B0, req)
    else:
        svc_write_pos = [i for i,e in enumerate(events) if e.get('phase') == 'service' and e.get('op') == 'write']
        commit_write_pos = [i for i,e in enumerate(events) if e.get('phase') == 'commit' and e.get('op') == 'write']
        if svc_write_pos and commit_write_pos:
            barrier = [e for e in events[max(svc_write_pos)+1:min(commit_write_pos)]
                       if e.get('phase') == 'service' and e.get('op') == 'flush' and e.get('rc') == 0]
            req(bool(barrier), 'record metadata began without chunk-data durability barrier')
        _assert_index_commit(events, 'commit', LBA_B1, req)
    return errors


def synth_calls(case: Case):
    if case.operation == 'reset_b':
        return [
            {'phase':'mount','call':'tape_mount','result':'TAPE_OK','side':'A'},
            {'phase':'get_info','call':'tape_get_info','result':'TAPE_OK','side_b_valid':False},
            {'phase':'reset_b','call':'tape_reset_side_b','result':'TAPE_OK'},
            {'phase':'unmount','call':'tape_unmount','result':'TAPE_OK'},
            {'phase':'remount','call':'tape_mount','result':'TAPE_OK','side':'B'},
        ]
    return [
        {'phase':'mount','call':'tape_mount','result':'TAPE_OK','side':'B'},
        {'phase':'seek','call':'tape_seek','result':'TAPE_OK','frame':128},
        {'phase':'arm','call':'tape_arm','result':'TAPE_OK','mode':'TAPE_REC_SPLICE'},
        {'phase':'feed','call':'tape_feed','result':'TAPE_OK','requested':128,'accepted':128},
        {'phase':'service','call':'tape_service','result':'TAPE_OK','block_budget':64,'more_work':False},
        {'phase':'commit','call':'tape_commit','result':'TAPE_OK'},
        {'phase':'unmount','call':'tape_unmount','result':'TAPE_OK'},
        {'phase':'remount','call':'tape_mount','result':'TAPE_OK','side':'B'},
    ]


def synth_observation(case: Case):
    post, events = base.synth_post(case)
    events = [dict(e, rc=e.get('rc', 0)) for e in events]
    return post, events, synth_calls(case)
