"""One narrow logical binding run; no child, Product or real POSIX sensors.

Windows resource shim enables import only. Every controller CPU/allocation input
is explicitly injected abstract data. Host process CPU is reported separately.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import types

if sys.platform == 'win32':
    sys.modules['resource'] = types.ModuleType('resource')
import controller as C
import task_adapter as T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    start_cpu, start_wall = time.process_time_ns(), time.monotonic_ns()
    args.out.mkdir(exist_ok=False)
    protocol_path = Path(__file__).resolve().parents[2]/'docs/REVIEW/software525/correction2/independent/protocol.py'
    spec = importlib.util.spec_from_file_location('frozen_protocol', protocol_path)
    protocol = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(protocol)
    protocol_result = protocol.selftest()
    original_cpu, original_popen = C.own_completed_cpu, T.subprocess.Popen
    rows = []
    try:
        cases = [
            ('fresh-task', 80, 90, 91, 100, 20, 9, 1, None, 'REJECT_TASK_CPU', 0),
            ('fresh-phase', 10, 20, 21, 100, 20, 9, 1, None, 'REJECT_PHASE_CPU', 0),
            ('fresh-equality', 80, 90, 90, 100, 20, 9, 1, None, 'ALLOW', 1),
            ('retained-peak', 0, 0, 0, 100, 100, 0, 0, 25, 'REJECT_TASK_BYTES', 0),
            ('peak-equality', 0, 0, 0, 100, 90, 0, 0, 20, 'ALLOW', 1),
        ]
        for name, phase_cpu, gate_cpu, fresh_cpu, task_limit, phase_limit, nxt, done, next_bytes, expected, spy_expected in cases:
            root = args.out/name
            root.mkdir()
            state = dict(cpu=0, spies=0)
            C.own_completed_cpu = lambda: state['cpu']
            def sensor(path, stage):
                if stage == 'phase':
                    state['cpu'] = phase_cpu
                    allocated = 10
                elif stage == 'gate':
                    state['cpu'] = gate_cpu
                    allocated = 40
                else:
                    state['cpu'] = fresh_cpu
                    allocated = 45 if stage == 'before' else 20
                return dict(allocated_bytes=allocated, logical_injection=True, stage=stage)
            def spy(*a, **kw):
                state['spies'] += 1
                raise RuntimeError('LOGICAL Popen boundary intercepted: ZERO actual child')
            T.subprocess.Popen = spy
            task = T.Task(root, name, task_limit, 100 if next_bytes else 1000, 0,
                          done, 0, sensor=sensor)
            task.begin('phase', phase_limit, phase_limit if next_bytes else 1000)
            if next_bytes:
                # Complete synthetic supervision samples 45,80,20; post20.
                # Same production folding function runs immediately after supervise.
                task._retain_allocation(40)
                task._retain_supervision(dict(allocation_before=dict(allocated_bytes=45),
                    monitor=[dict(allocated=80)], allocation_after=dict(allocated_bytes=20)))
                task._retain_allocation(20)
                assert (task.high, task.phase['high']) == (80, 70)
            argv = [str(Path(sys.executable).resolve()), 'LOGICAL-NEVER-EXECUTED']
            rules = [dict(argv=argv, inputs={})]
            out = task.invoke(argv, nxt, next_bytes or 0, rules)
            gate_path = out/('GATE.json' if next_bytes else 'FINAL-GATE.json')
            gate = json.loads(gate_path.read_bytes())
            assert gate['decision'] == expected, (name, gate)
            assert state['spies'] == spy_expected, (name, state)
            assert not (out/'LAUNCH.json').exists()
            before_files = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
            before_spies = state['spies']
            try:
                task.invoke(argv, nxt, next_bytes or 0, rules)
            except RuntimeError:
                pass
            else:
                raise AssertionError('terminal next entry not refused')
            assert state['spies'] == before_spies
            assert sorted(str(p.relative_to(root)) for p in root.rglob('*')) == before_files
            rows.append(dict(name=name, expected=expected, gate=gate,
                logical_popen_boundary_calls=state['spies'], actual_children=0,
                next_spy_unchanged=True, terminal=task.session.stopped,
                task_high=task.high, phase_high=task.phase['high']))
    finally:
        C.own_completed_cpu, T.subprocess.Popen = original_cpu, original_popen
    sources = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
               (Path(__file__), Path(T.__file__), Path(C.__file__), protocol_path)}
    result = dict(status='PASS bounded logical bindings only', sources=sources,
        protocol=protocol_result, rows=rows, injected_CPU_and_allocation=True,
        actual_children=0, Product_calls=0, POSIX_sensor_measurements=0,
        host_parent_cpu_ns=time.process_time_ns()-start_cpu,
        host_wall_ns=time.monotonic_ns()-start_wall,
        failed_correction1_usage='MISSING; not reconstructed or included as zero')
    C.immutable(args.out/'RESULT.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
