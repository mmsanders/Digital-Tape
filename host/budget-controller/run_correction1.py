"""Changed focused correction1 controls ONLY. Never rerun the original38."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time
import zipfile
import controller as C
from task_adapter import Task

HERE = Path(__file__).resolve().parent
M = 1024**2
S = 1000000000


def inventory(root):
    return {p.relative_to(root).as_posix():dict(bytes=p.stat().st_size, sha256=C.sha(p.read_bytes()))
            for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()}


def graph(root, mode='ok'):
    exe = str(Path(sys.executable).resolve())
    script = str(HERE/'harmless_graph.py')
    rules = []
    for role, parents in [('adapter', []), ('tracer', ['adapter']), ('leaf', ['tracer'])]:
        argv = [exe, '-B', script, mode, str(root), role]
        rules.append(dict(role=role, parents=parents, argv=argv,
                          exe_sha256=C.sha(Path(exe).read_bytes()), max_live=1,
                          inputs={exe:C.sha(Path(exe).read_bytes()), script:C.sha(Path(script).read_bytes())}))
    return rules[0]['argv'], rules


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--source', required=True)
    a = ap.parse_args()
    a.out.mkdir(exist_ok=False)
    start = time.monotonic_ns()
    cpu_start = C.own_completed_cpu()
    source = a.out/'producer-source'
    source.mkdir()
    for p in HERE.glob('*.py'):
        shutil.copyfile(p, source/p.name)
    C.immutable(a.out/'SOURCE.json', dict(commit=a.source, files=inventory(source),
                interpreter=sys.executable, interpreter_sha256=C.sha(Path(sys.executable).read_bytes()),
                python=sys.version, platform=platform.platform(), correction='7b4d09591753ad78841bb8da772fc2abc9d5772b',
                original38_replayed=False, Product_calls=0))
    outcomes = []
    names = ['handoffs', 'bound-crash-shape', 'before-failure', 'final-failure', 'monitor-failure',
             'unsupported-process', 'phase-byte-slack', 'task-cpu', 'estimate-stop', 'source-mismatch']
    for name in names:
        # Whole experiment cap, including prior failed roots; reserve uncompressed transport.
        assert C.census(a.out)['allocated_bytes']+32*M < 512*M
        assert C.own_completed_cpu()-cpu_start+120*S < 7200*S
        root = a.out/name
        root.mkdir()
        calls = []
        def sensor(path, stage):
            calls.append(stage)
            if ((name == 'before-failure' and stage == 'before') or
                    (name == 'final-failure' and stage == 'final') or
                    (name == 'monitor-failure' and stage == 'monitor')):
                # Actually call the production census on a nonexistent root. The
                # original FileNotFoundError crosses the real supervisor finalizer.
                return C.census(Path(path)/'absent-measurement-root')
            return C.census(path)
        task = Task(root, name, 60*S, 32*M, S, S, M, sensor=sensor)
        task.begin('build', 20*S, 16*M)
        argv, rules = graph(root, 'unsupported' if name == 'unsupported-process' else 'ok')
        if name == 'bound-crash-shape':
            # Exercise the actual changed crash wrapper with surrogate tracer/leaf,
            # never strace or tapectl. The payload and source identities are retained.
            exe = argv[0]
            wrapper = str(HERE/'crash_child.py')
            payload = root/'payload.json'
            value = dict(inputs={str(HERE/'harmless_graph.py'):C.sha((HERE/'harmless_graph.py').read_bytes())},
                         task_root=str(root.resolve()), owned_paths=[str(root.resolve())],
                         domain_dir=str(root/'domain'), environment={}, cwd=str(root),
                         argv=rules[1]['argv'], source='harmless surrogate; no Product invocation')
            C.immutable(payload, value)
            argv = [exe, '-B', wrapper, '--input', str(payload), '--sha', C.sha(payload.read_bytes())]
            rules[0].update(argv=argv, inputs={exe:C.sha(Path(exe).read_bytes()),
                                             wrapper:C.sha(Path(wrapper).read_bytes())})
        if name == 'phase-byte-slack':
            task.phase['bytes_limit'] = M  # completion alone fills it; task has32MiB slack
        if name == 'task-cpu':
            task.limits = (S, 32*M)  # build+completion already exceeds total
        if name == 'source-mismatch':
            rules[0]['inputs'][argv[0]] = '0'*64
        out = task.invoke(argv, 3*S, 2*M, rules)
        if name == 'estimate-stop':
            # A separate changed estimate case: next allocation0 rejects real
            # output growth during monitoring. No retry of this invocation.
            assert not task.session.stopped
            task.close()
            task.begin('row', 20*S, 16*M)
            out = task.invoke(argv, 3*S, 0, rules)
        if name == 'bound-crash-shape':
            assert not task.session.stopped
            domain = root/'domain'
            assert b'original\0\xffraw\n' in (domain/'stdout.bin').read_bytes()
            assert json.loads((domain/'EXIT.json').read_bytes())['code'] == 0
            task.close()
        elif name == 'handoffs':
            assert not task.session.stopped
            first_high = task.high
            first_cpu_origin = task.cpu_origin
            observed_roles = {r['role'] for m in json.loads((out/'RESULT.json').read_bytes())['measurement']['monitor']
                              for r in m['live']['rows']}
            assert observed_roles == {'adapter', 'tracer', 'leaf'}, observed_roles
            for phase in ('positive', 'row'):
                task.close()
                task.begin(phase, 20*S, 16*M)
                out = task.invoke(argv, 3*S, 2*M, rules)
                assert not task.session.stopped
                assert task.high >= first_high and task.cpu_origin == first_cpu_origin and task.build == S
            task.close()
            scans = json.loads((out/'POST.json').read_bytes())['scan']['rows']
            assert all(any(r['path'].startswith(d+'/') for r in scans)
                       for d in ('source','build','work','temp','archive','retained'))
        else:
            assert task.session.stopped, name
            spy = root/'spy.jsonl'
            before_spy = spy.read_bytes() if spy.exists() else b''
            try:
                task.invoke(argv, 3*S, 2*M, rules)
            except RuntimeError:
                pass
            else:
                raise AssertionError('next invocation was not refused')
            assert (spy.read_bytes() if spy.exists() else b'') == before_spy
            assert (out/'STOP.json').exists()
            if name in ('before-failure', 'phase-byte-slack', 'task-cpu', 'source-mismatch'):
                assert not spy.exists()
            if name == 'final-failure':
                receipt = json.loads((out/'ACCOUNTING-STOP.json').read_bytes())
                m = receipt['measurement']
                assert m['child_reaped'] and m['allocation_after'] is None and not m['accounting_complete']
                assert any('FileNotFoundError' in e['exception'] for e in m['errors'])
                assert b'original\0\xffraw\n' in (out/'stdout.bin').read_bytes()
                assert b'original\x80diagnostic\n' in (out/'stderr.bin').read_bytes()
                assert receipt['status'] == 'INCOMPLETE STOP'
        outcomes.append(dict(name=name, terminal=task.session.stopped, sensor_stages=calls,
                             task_cpu_origin=task.cpu_origin, build_charge_once=task.build,
                             task_high=task.high, phase=task.phase))
    C.immutable(a.out/'RESULT.json', dict(outcomes=outcomes, original38_replayed=False,
                Product_calls=0, limits='2CPUh/512MiB including source/raw/temp/archive',
                hard_overshoot_guarantee=False))
    C.immutable(a.out/'FILES.json', inventory(a.out))
    archive = a.out.parent/'software525-correction1.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(a.out.rglob('*')):
            if p.is_file():
                z.write(p, p.relative_to(a.out).as_posix())
    final = C.census(a.out.parent)
    C.immutable(a.out.parent/'FINAL.json', dict(scan=final, receipt_reserve=65536,
                cpu_ns=C.own_completed_cpu()-cpu_start, build_supervision_reserve_ns=120*S,
                wall_ns=time.monotonic_ns()-start, archive_bytes=archive.stat().st_size,
                archive_sha256=C.sha(archive.read_bytes()), members=len(zipfile.ZipFile(archive).namelist())))
    assert final['allocated_bytes']+65536 < 512*M
    assert C.own_completed_cpu()-cpu_start+120*S < 7200*S


if __name__ == '__main__':
    main()
