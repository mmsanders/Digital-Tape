#!/usr/bin/env python3
"""Bounded POSIX pre-invocation gate. No Product driver or independent oracle import."""
import argparse
import decimal
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import time

MAX = (1 << 63) - 1
COUNTERS = ('task_cpu_ns', 'phase_cpu_ns', 'active_child_cpu_ns', 'build_reserve_ns',
            'task_allocated_bytes', 'phase_allocated_bytes', 'next_cpu_ns', 'next_bytes',
            'completion_cpu_ns', 'completion_bytes', 'task_limit_ns', 'phase_limit_ns',
            'task_limit_bytes', 'phase_limit_bytes', 'cpu_baseline_ns', 'current_cpu_ns',
            'sequence', 'expected_sequence')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def immutable(path, obj):
    data = (json.dumps(obj, sort_keys=True, indent=2) + '\n').encode()
    with Path(path).open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return sha(data)

def decide(r):
    # Validate types before arithmetic; Python integers cannot wrap but contract sums are bounded.
    if any(type(r.get(k)) is not int or not 0 <= r[k] <= MAX for k in COUNTERS):
        return 'REJECT_INVALID'
    if r.get('measurement_ok') is not True:
        return 'REJECT_MEASUREMENT'
    if not r.get('nonce') or r.get('nonce') != r.get('expected_nonce') or r['sequence'] != r['expected_sequence']:
        return 'REJECT_STALE'
    if (r['cpu_baseline_ns'] > r['current_cpu_ns'] or
            r['phase_cpu_ns'] != r['current_cpu_ns'] - r['cpu_baseline_ns'] or
            r['task_cpu_ns'] < r['phase_cpu_ns'] or
            r['task_allocated_bytes'] < r['phase_allocated_bytes']):
        return 'REJECT_BASELINE'
    amounts = (
        r['task_cpu_ns'] + r['active_child_cpu_ns'] + r['build_reserve_ns'] + r['next_cpu_ns'] + r['completion_cpu_ns'],
        r['phase_cpu_ns'] + r['active_child_cpu_ns'] + r['next_cpu_ns'] + r['completion_cpu_ns'],
        r['task_allocated_bytes'] + r['next_bytes'] + r['completion_bytes'],
        r['phase_allocated_bytes'] + r['next_bytes'] + r['completion_bytes'])
    if any(x > MAX for x in amounts):
        return 'REJECT_OVERFLOW'
    limits = ('task_limit_ns', 'phase_limit_ns', 'task_limit_bytes', 'phase_limit_bytes')
    for value, key, label in zip(amounts, limits, ('TASK_CPU', 'PHASE_CPU', 'TASK_BYTES', 'PHASE_BYTES')):
        if value > r[key]:
            return 'REJECT_' + label
    return 'ALLOW'

def census(root):
    """Conservative per-path lstat allocation incl directories/hardlinks, no follow escape."""
    root = Path(root).resolve(strict=True)
    rows = []
    def visit(path):
        s = path.lstat()
        if not hasattr(s, 'st_blocks'):
            raise RuntimeError('allocated-block sensor unsupported')
        kind = 'dir' if stat.S_ISDIR(s.st_mode) else 'file' if stat.S_ISREG(s.st_mode) else 'link' if stat.S_ISLNK(s.st_mode) else 'unsupported'
        if kind == 'unsupported':
            raise RuntimeError('unsupported filesystem node: ' + str(path))
        if kind == 'link' and not path.resolve().is_relative_to(root):
            raise RuntimeError('escaping symlink: ' + str(path))
        rows.append(dict(path=path.relative_to(root).as_posix(), kind=kind, device=s.st_dev,
                         inode=s.st_ino, links=s.st_nlink, logical=s.st_size,
                         blocks=s.st_blocks, block_unit=512, allocated=s.st_blocks * 512))
        if kind == 'dir':
            for child in sorted(path.iterdir()):
                visit(child)
    visit(root)
    return dict(root=str(root), rows=rows, allocated_bytes=sum(x['allocated'] for x in rows),
                logical_bytes=sum(x['logical'] for x in rows), hardlinks_counted_per_path=True,
                errors=[], scan_end_ns=time.monotonic_ns())

def ru_ns(usage):
    # Convert the OS floating representation conservatively upward, never to wall time.
    return int(((decimal.Decimal(str(usage.ru_utime)) + decimal.Decimal(str(usage.ru_stime))) *
                1000000000).to_integral_value(rounding=decimal.ROUND_CEILING))

def own_completed_cpu():
    return ru_ns(resource.getrusage(resource.RUSAGE_SELF)) + ru_ns(resource.getrusage(resource.RUSAGE_CHILDREN))

def live_tree(pid):
    """Linux cooperating-process scope: known process-group census, fail on foreign tree."""
    ticks = os.sysconf('SC_CLK_TCK')
    group = []
    for item in Path('/proc').iterdir():
        if not item.name.isdigit():
            continue
        try:
            raw = (item / 'stat').read_text()
        except (FileNotFoundError, ProcessLookupError):
            continue
        # comm may contain spaces/parentheses; fields after final ')' start at state(3).
        fields = raw[raw.rfind(')') + 2:].split()
        if int(fields[2]) == pid:
            group.append(dict(pid=int(item.name), parent=int(fields[1]), state=fields[0],
                              cpu_ns=((int(fields[11]) + int(fields[12])) * 1000000000 + ticks - 1) // ticks))
    return dict(processes=group, cpu_ns=sum(p['cpu_ns'] for p in group), ticks_per_second=ticks)

class Session:
    """One monotonic session; failed/incomplete invocation makes all further launches terminal."""
    def __init__(self, nonce):
        self.nonce = nonce
        self.sequence = 0
        self.stopped = False
        self.task_high = 0
        self.phase_high = 0
        self.phase_baseline = None

    def advance(self, snapshot):
        if self.stopped:
            raise RuntimeError('terminal session; no next invocation')
        if snapshot['nonce'] != self.nonce or snapshot['sequence'] != self.sequence + 1:
            self.stopped = True
            raise RuntimeError('external session/sequence mismatch')
        self.sequence += 1

    def storage(self, allocated, phase_baseline):
        if type(allocated) is not int or type(phase_baseline) is not int or not 0 <= phase_baseline <= allocated:
            self.stopped = True
            raise RuntimeError('missing/invalid storage baseline')
        if self.phase_baseline is None:
            self.phase_baseline = phase_baseline
        if phase_baseline != self.phase_baseline:
            self.stopped = True
            raise RuntimeError('phase baseline replacement')
        self.task_high = max(self.task_high, allocated)
        self.phase_high = max(self.phase_high, allocated - phase_baseline)
        return self.task_high, self.phase_high

    def require_next(self):
        if self.stopped:
            raise RuntimeError('terminal session; next command refused')

def supervise(session, argv, output, timeout=0.5, cpu_cap_ns=1000000000, bytes_cap=64*1024**2):
    # Shared exception-safe finalizer; legacy frozen fixture interface stays direct-child only.
    from task_adapter import supervise as safe_supervise
    return safe_supervise(session, argv, output, timeout, cpu_cap_ns, bytes_cap,
                          sensor=lambda root, stage: census(root))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--request', type=Path, required=True)
    ap.add_argument('--request-sha', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--helper', type=Path, required=True)
    ap.add_argument('--helper-sha', required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--mode', required=True)
    a = ap.parse_args()
    a.out.mkdir(exist_ok=False)
    original = a.request.read_bytes()
    if sha(original) != a.request_sha or sha(a.helper.read_bytes()) != a.helper_sha:
        raise RuntimeError('external request/helper identity mismatch')
    r = json.loads(original)
    (a.out/'request.json').write_bytes(original)
    session = Session(r.get('expected_nonce'))
    decision = decide(r)
    spy = a.out / 'spy.jsonl'
    gate = dict(pid=os.getpid(), parent=os.getppid(), request_sha256=sha(original),
                source_sha256=sha(Path(__file__).read_bytes()), interpreter_sha256=sha(Path(sys.executable).read_bytes()),
                session=r.get('expected_nonce'), sequence=r.get('expected_sequence'),
                fixture_counters=True, decision=decision, finalized=True,
                snapshot_before_launch=True, end_ns=time.monotonic_ns())
    immutable(a.out/'GATE.json', gate)  # fsync completed before Popen.
    row = dict(name=a.name, request=r, decision=decision, gate=gate, launches=[],
               spy_before=0, spy_after=0, next_invocation_count=0)
    measurement = None
    if decision == 'ALLOW':
        session.advance(r)
        argv = [sys.executable, '-B', str(a.helper.resolve()), '--mode', a.mode,
                '--spy', str(spy.resolve()), '--nonce', r['nonce']]
        measurement = supervise(session, argv, a.out)
        launch_path = a.out/'LAUNCH.json'
        row['launches'] = [json.loads(launch_path.read_bytes())] if launch_path.exists() else []
        row['spy_after'] = len(spy.read_bytes().splitlines()) if spy.exists() else 0
        row['next_invocation_count'] = 1
        if a.mode == 'incomplete':
            # Frozen injected FINAL sensor failure; measured raw remains alongside disclosure.
            measurement['injected_final_sensor_failure'] = True
            measurement['accounting_complete'] = False
            session.stopped = True
        if a.mode in ('nonzero', 'timeout', 'incomplete', 'after-raw-failure'):
            before_second = spy.read_bytes()
            try:
                session.require_next()
            except RuntimeError as e:
                row['second_command_refusal'] = str(e)
            else:
                raise AssertionError('failed child did not make session terminal')
            row['second_command_spy_unchanged'] = spy.read_bytes() == before_second
    else:
        session.stopped = True
    raw = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p.read_bytes()))
           for p in a.out.glob('*.bin')}
    row.update(raw_preserved=True, stop_record_finalized=True, raw=raw,
               measurement=measurement, session_stopped=session.stopped)
    immutable(a.out/'STOP.json', dict(terminal=session.stopped, decision=decision,
              raw=raw, measurement=measurement, no_further_command=True))
    immutable(a.out/'RESULT.json', row)
    print(json.dumps(dict(name=a.name, decision=decision, pid=os.getpid())))

if __name__ == '__main__':
    main()
