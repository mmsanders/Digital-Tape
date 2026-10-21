"""Execute only the independently frozen32 helper/recorder controls once."""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time
import warnings
import zipfile

import recorder as component

REPO = Path(__file__).resolve().parents[2]
METHOD = REPO / 'tests/evidence_recorder_r1'
spec = importlib.util.spec_from_file_location('frozen_cases', METHOD / 'cases.py')
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)
PYTHON = Path(sys.executable).resolve()
RECORDER = Path(__file__).with_name('recorder.py')
HELPER = METHOD / 'helper.py'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir()  # Never repeat/overwrite an actual attempt.
    start = time.monotonic()
    rows = []
    command_number = 0

    def relative(path):
        return path.relative_to(out).as_posix()

    def save(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        component.write(path, data)

    def js(path, value):
        save(path, component.encoded(value))

    def census(path):
        return component.inventory(component.files_under(path))

    def invoke(argv, action=None):
        nonlocal command_number
        root = out / 'commands' / f'{command_number:04d}'
        command_number += 1
        root.mkdir(parents=True)
        t0 = time.monotonic_ns()
        u0 = component.cpu_ns()
        with (root/'stdout.bin').open('xb') as stdout, (root/'stderr.bin').open('xb') as stderr:
            proc = subprocess.Popen(argv, stdout=stdout, stderr=stderr)
            js(root/'launch.json', dict(argv=argv, pid=proc.pid, parent_pid=os.getpid(), source=args.source))
            if action:
                action(proc, root)
            code = proc.wait(timeout=10)
        t1 = time.monotonic_ns()
        js(root/'exit.json', dict(code=code))
        js(root/'timing.json', dict(start_ns=t0, end_ns=t1, duration_ns=t1-t0,
                                  cpu_ns=max(0, component.cpu_ns()-u0), finalized=True))
        return code, relative(root)

    def add(name, observed, request, evidence, commands, reason):
        rows.append(dict(name=name, observed=observed, original_request=relative(request),
                         evidence_root=relative(evidence), commands=commands, reason=reason))

    def request(name, mode, root, payload=b'owned ordinary input\n', wait=False):
        source = out/'inputs'/f'{name}.bin'
        save(source, payload)
        nonce = os.urandom(16).hex()
        argv = [str(PYTHON), '-B', str(HELPER), '--mode', 'wait' if wait else mode,
                '--input', str(root/'incoming'/name/'input.bin'), '--nonce', nonce]
        if wait:
            argv += ['--ready', str(out/'ready'/name)]
        value = dict(case_id=name, mode=mode, input_sha256=component.digest(payload), argv=argv,
                     binary_sha256=component.digest(PYTHON.read_bytes()),
                     helper_sha256=component.digest(HELPER.read_bytes()), source_commit=args.source, nonce=nonce)
        path = out/'requests'/f'{name}.json'
        js(path, value)
        return path, source, value

    def command(operation, root, expected):
        return [str(PYTHON), '-B', str(RECORDER), operation, '--root', str(root), '--request', str(expected)]

    (out/'ready').mkdir()
    root = out/'owned'
    complete = {}
    # All six ORIGINAL child runs, not synthetic receipts.
    for suffix, mode in [('text','text'),('binary','binary'),('empty','empty'),('exit7','exit7'),
                         ('unicode-input','text'),('second-case','text')]:
        name = 'complete-' + suffix
        previous = census(root) if root.exists() else {}
        req, inp, value = request(name, mode, root, 'owned λ input\n'.encode() if suffix == 'unicode-input' else b'owned ordinary input\n')
        rc, launch = invoke(command('record', root, req) + ['--input', str(inp)])
        assert rc == 0, name
        final = root/'cases'/name
        rc, validation = invoke(command('validate', final, req))
        assert rc == 0, name
        after = census(root)
        assert all(after[n] == fact for n, fact in previous.items()), 'prior case changed'
        js(out/'censuses'/f'{name}-before.json', previous)
        js(out/'censuses'/f'{name}-after.json', after)
        complete[name] = (req, final, value)
        add(name, 'COMPLETE_EVIDENCE', req, final, [launch, validation], 'Actual child and component validator completed; code7 is failed-child evidence only.')

    for name in ('producer-killed-after-ready','recorder-killed-after-ready','parser-raises','cleanup-raises'):
        wait = 'killed' in name
        req, inp, value = request(name, 'text', root, wait=wait)
        before = census(root)
        js(out/'censuses'/f'{name}-before.json', before)
        action = None
        if name == 'recorder-killed-after-ready':
            def kill(proc, receipts, name=name):
                ready = out/'ready'/name
                stage = root/'incoming'/name
                deadline = time.monotonic()+5
                while time.monotonic() < deadline:
                    if ready.exists() and (stage/'launch.json').exists() and (stage/'stdout.bin').stat().st_size:
                        break
                    time.sleep(.01)
                else:
                    raise RuntimeError('five-second readiness stop')
                child = json.loads((stage/'launch.json').read_bytes())['pid']
                js(receipts/'before-kill.json', dict(recorder_pid=proc.pid, child_pid=child,
                   ready_sha256=component.digest(ready.read_bytes()), observed=census(stage)))
                save(receipts/'observed-prefix.bin', (stage/'stdout.bin').read_bytes())
                js(receipts/'kill-command.json', dict(actions=[['Popen.kill',proc.pid],['os.kill',child,signal.SIGKILL]], supervisor_pid=os.getpid()))
                proc.kill()
                proc.wait(timeout=5)
                os.kill(child, signal.SIGKILL)
                # Preserve byte-for-byte; supervisor supplies no case manifest.
                stage.rename(root/'incomplete'/name)
            action = kill
        seam = 'kill-producer' if name == 'producer-killed-after-ready' else name if name in ('parser-raises','cleanup-raises') else None
        argv = command('record', root, req) + ['--input', str(inp)]
        if seam:
            argv += ['--test-seam', seam]
        rc, receipt = invoke(argv, action)
        assert rc != 0
        partial = root/'incomplete'/name
        assert partial.is_dir() and not (root/'cases'/name).exists() and not (partial/'MANIFEST.json').exists()
        raw = (partial/'stdout.bin').read_bytes()
        head, body = raw.split(b'\n', 1)
        assert json.loads(head)['nonce'] == value['nonce'] and body == b'helper-output\n'
        assert (partial/'stderr.bin').read_bytes() == b'helper-diagnostic\n'
        after = census(root)
        assert all(after[n] == fact for n, fact in before.items())
        js(out/'censuses'/f'{name}-after.json', after)
        add(name, 'INCOMPLETE_RAW_RETAINED', req, partial, [receipt], 'Actual interruption/disclosed post-raw seam; no final case manifest or completion.')

    req, positive, original = complete['complete-text']
    for name in ('duplicate-id','existing-case-path','path-traversal'):
        if name == 'duplicate-id':
            expected = req
            inp = out/'inputs/complete-text.bin'
        else:
            expected, inp, value = request('existing' if name == 'existing-case-path' else 'traversal', 'text', root)
            if name == 'existing-case-path':
                (root/'cases/existing').mkdir()
                save(root/'cases/existing/retained.bin', b'original bytes\n')
            else:
                value['case_id'] = '../escape'
                expected = out/'requests/traversal-invalid.json'
                js(expected, value)
                save(out/'sibling-sentinel.bin', b'preserve sibling\n')
        before = census(root)
        sentinel = (out/'sibling-sentinel.bin').read_bytes() if name == 'path-traversal' else None
        rc, receipt = invoke(command('record', root, expected) + ['--input', str(inp)])
        assert rc != 0 and census(root) == before
        if sentinel is not None:
            assert (out/'sibling-sentinel.bin').read_bytes() == sentinel and not (out/'escape').exists()
        js(out/'censuses'/f'{name}-before.json', before)
        js(out/'censuses'/f'{name}-after.json', census(root))
        add(name, 'REFUSED_UNCHANGED', expected, root, [receipt], 'Actual refused invocation, complete prior owned census unchanged.')

    frozen = cases.corpus()
    for row in frozen:
        if row['kind'] != 'actual-positive-copy-corruption':
            continue
        name = row['name']
        mutant = out/'mutants'/name
        shutil.copytree(positive, mutant)
        before = census(mutant)
        def change(file, fn):
            path = mutant/file
            path.write_bytes(component.encoded(fn(json.loads(path.read_bytes()))))
        if name == 'changed-stdout':
            with (mutant/'stdout.bin').open('ab') as f: f.write(b'changed')
        elif name == 'truncated-stderr':
            p = mutant/'stderr.bin';p.write_bytes(p.read_bytes()[:-1])
        elif name in ('missing-exit','missing-input','incomplete-promoted'):
            (mutant/{'missing-exit':'exit.json','missing-input':'input.bin','incomplete-promoted':'timing.json'}[name]).unlink()
        elif name == 'stale-timing-checksum':
            change('timing.json', lambda t: dict(t,cpu_ns=t['cpu_ns']+1))
        elif name.startswith('wrong-') and name not in ('wrong-stream-count',):
            key = {'wrong-argv':'argv','wrong-binary':'binary_sha256','wrong-source':'source_commit',
                   'wrong-input-identity':'input_sha256','wrong-nonce':'nonce','wrong-pid':'pid'}[name]
            value = ['different'] if key == 'argv' else original.get('nonce','')+'-different' if key == 'nonce' else 1 if key == 'pid' else '0'* (40 if key == 'source_commit' else 64)
            change('request.json' if key == 'input_sha256' else 'launch.json', lambda t:dict(t,**{key:value}))
        elif name == 'unlisted-case-file':
            save(mutant/'unlisted', b'extra')
        elif name == 'wrong-stream-count':
            change('result.json', lambda t:dict(t,stdout_bytes=t['stdout_bytes']+1))
        elif name == 'negative-timing':
            change('timing.json', lambda t:dict(t,cpu_ns=-1))
        else:
            raise AssertionError(name)
        if name != 'stale-timing-checksum':
            data = component.files_under(mutant);data.pop('MANIFEST.json')
            (mutant/'MANIFEST.json').write_bytes(component.encoded(component.inventory(data)))
        js(out/'recipes'/f'{name}.json', dict(name=name,before=before,after=census(mutant),internally_rehashed=name!='stale-timing-checksum'))
        rc, receipt = invoke(command('validate', mutant, req))
        assert rc != 0, name
        add(name, 'REJECTED', req, mutant, [receipt], 'Actual component validator rejected a preserved copy corruption against original external request.')

    # Archive controls use original positive bytes and externally held inventory.
    original_files = component.files_under(positive)
    expected = component.inventory(original_files)
    expected_path = out/'archive-controls/expected.json'
    js(expected_path, expected)
    def zip_bytes(extra=None, duplicate=False):
        buffer = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
                for n,b in original_files.items():z.writestr(n,b)
                z.writestr('ARCHIVE-MANIFEST.json',component.encoded(expected))
                if extra:z.writestr(extra,b'bad')
                if duplicate:z.writestr('input.bin',b'bad')
        return buffer.getvalue()
    good = out/'archive-controls/original.zip'
    save(good, zip_bytes())
    rc, _ = invoke(command('archive-validate', good, expected_path))
    assert rc == 0
    for name, data in [('archive-extra',zip_bytes(extra='extra')),('archive-duplicate',zip_bytes(duplicate=True)),
                       ('archive-traversal',zip_bytes(extra='../escape')),('archive-truncated',good.read_bytes()[:-25])]:
        path = out/'archive-controls'/(name+'.zip')
        save(path,data)
        rc, receipt = invoke(command('archive-validate', path, expected_path))
        assert rc != 0
        add(name,'REJECTED',req,path.parent,[receipt],'Original good archive preserved; actual external-inventory validator rejected mutated ZIP.')
    assert {r['name'] for r in rows} == {r['name'] for r in frozen} and len(rows)==32
    assert all(r['observed']==next(c['expected'] for c in frozen if c['name']==r['name']) for r in rows)
    js(out/'OBSERVATIONS.json',rows)
    js(out/'IMPORT.json',dict(author='72278bde6747c316fa8d4dcf8bd03490b88a38cd',
       merge='8fbd72c9294178e5017c9dd0ac1a121e4d30ffe5',tree='c370a4e975fe506d884abaacca493cf417e09c5d',
       files=component.inventory(component.files_under(METHOD))))
    elapsed=time.monotonic()-start
    conservative=600+elapsed*os.cpu_count()
    assert conservative<7200
    js(out/'RUNTIME.json',dict(source=args.source,python=sys.version,platform=platform.platform(),
       binary_sha256=component.digest(PYTHON.read_bytes()),recorder_sha256=component.digest(RECORDER.read_bytes()),
       adapter_sha256=component.digest(Path(__file__).read_bytes()),host_cpu_count=os.cpu_count(),
       timing_method='monotonic_ns wall; process_time_ns + RUSAGE_CHILDREN user/system deltas',
       conservative_cpu_seconds_including_build_reserve=conservative,
       accounting='600-second build/supervision reserve plus all elapsed seconds times host logical CPUs bounds current ordinary helper descendants including interrupted child',
       wall_seconds=elapsed,component_acceptance='pending independent252'))
    files=component.files_under(out)
    manifest=component.inventory(files)
    js(out/'ARCHIVE-MANIFEST.json',manifest)
    archive=out.parent/'software511-exact-return.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for name,data in component.files_under(out).items():z.writestr(name,data)
    component.validate_archive(archive,manifest)
    assert archive.stat().st_size < 512*1024**2
    # Reapply independent predicates only AFTER actual originals were retained.
    spec=importlib.util.spec_from_file_location('independent_oracle',METHOD/'oracle.py')
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    for req, final, value in complete.values():oracle.check_complete(component.files_under(final),value)
    oracle.check_archive(archive.read_bytes(),files)
    print(json.dumps(dict(frozen_cases=32,archive_bytes=archive.stat().st_size,
                         archive_sha256=component.digest(archive.read_bytes()),
                         conservative_cpu_seconds=conservative,independent_disposition='pending')))


if __name__ == '__main__':
    main()
