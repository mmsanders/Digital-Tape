"""Standalone ordinary-process recorder. Linux CPU accounting; no durability claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import stat
import subprocess
import sys
import time
import zipfile


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    with path.open('xb') as stream:
        stream.write(data)


def emit(path, value):
    write(path, encoded(value))


def safe_path(path):
    path = Path(path)
    if '..' in path.parts or not path.is_absolute():
        raise ValueError('absolute canonical owned path required')
    for part in [path, *path.parents]:
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
                raise ValueError('symlink/reparse path refused')
    if path != path.resolve():
        raise ValueError('alias path refused')
    return path


def files_under(root):
    result = {}
    for path in sorted(root.rglob('*')):
        safe_path(path)
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.read_bytes()
        elif not path.is_dir():
            raise ValueError('nonordinary file')
    return result


def inventory(files):
    return {name: {'bytes': len(data), 'sha256': digest(data)} for name, data in sorted(files.items())}


def identity(request):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', request['case_id']):
        raise ValueError('invalid case id')
    if not isinstance(request['argv'], list) or not request['argv'] or not all(isinstance(x, str) for x in request['argv']):
        raise ValueError('invalid argv')
    for key, size in [('input_sha256', 64), ('binary_sha256', 64), ('helper_sha256', 64), ('source_commit', 40)]:
        if not re.fullmatch('[0-9a-f]{' + str(size) + '}', request[key]):
            raise ValueError('invalid ' + key)
    if not isinstance(request['nonce'], str) or not request['nonce']:
        raise ValueError('invalid nonce')


def validate_case(case, expected):
    identity(expected)
    files = files_under(safe_path(case))
    required = {'input.bin', 'request.json', 'launch.json', 'stdout.bin', 'stderr.bin',
                'exit.json', 'timing.json', 'result.json', 'MANIFEST.json'}
    if set(files) != required:
        raise ValueError('incomplete or unlisted case files')
    raw = {n: b for n, b in files.items() if n != 'MANIFEST.json'}
    if json.loads(files['MANIFEST.json']) != inventory(raw):
        raise ValueError('finalized byte inventory mismatch')
    if json.loads(files['request.json']) != expected or digest(files['input.bin']) != expected['input_sha256']:
        raise ValueError('external request/input mismatch')
    launch = json.loads(files['launch.json'])
    for key in ('argv', 'binary_sha256', 'helper_sha256', 'source_commit', 'nonce'):
        if launch[key] != expected[key]:
            raise ValueError('external identity mismatch: ' + key)
    if type(launch['pid']) is not int or launch['pid'] <= 0:
        raise ValueError('invalid child pid')
    header, body = files['stdout.bin'].split(b'\n', 1)
    if json.loads(header) != dict(pid=launch['pid'], nonce=expected['nonce'],
                                 input_sha256=expected['input_sha256'], input_bytes=len(files['input.bin'])):
        raise ValueError('actual child header identity mismatch')
    mode = expected['mode']
    if mode not in ('text', 'binary', 'empty', 'exit7'):
        raise ValueError('unsupported helper protocol mode')
    out = b'\x00\xffraw\n' if mode == 'binary' else b'' if mode == 'empty' else b'helper-output\n'
    err = b'\x80diagnostic\n' if mode == 'binary' else b'' if mode == 'empty' else b'helper-diagnostic\n'
    if body != out or files['stderr.bin'] != err:
        raise ValueError('helper protocol stream mismatch')
    code = json.loads(files['exit.json'])['code']
    if type(code) is not int or code != (7 if mode == 'exit7' else 0):
        raise ValueError('actual helper exit mismatch')
    timing = json.loads(files['timing.json'])
    if not all(type(timing[k]) is int and timing[k] >= 0 for k in ('start_ns', 'end_ns', 'duration_ns', 'cpu_ns')):
        raise ValueError('invalid timing values')
    if timing['end_ns'] < timing['start_ns'] or timing['duration_ns'] != timing['end_ns'] - timing['start_ns'] or timing['finalized'] is not True:
        raise ValueError('unfinalized timing arithmetic')
    if json.loads(files['result.json']) != dict(case_id=expected['case_id'], evidence='complete', exit=code,
                                              stdout_bytes=len(files['stdout.bin']), stderr_bytes=len(files['stderr.bin'])):
        raise ValueError('stream counts/result mismatch')
    return 'COMPLETE_EVIDENCE'


def cpu_ns():
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time_ns() + round((child.ru_utime + child.ru_stime) * 1e9)


def record(root, request, source_input, seam=None):
    identity(request)
    root = safe_path(root)
    source_input = safe_path(source_input)
    binary = safe_path(Path(request['argv'][0]))
    helper = safe_path(Path(request['argv'][2]))
    if digest(binary.read_bytes()) != request['binary_sha256'] or digest(helper.read_bytes()) != request['helper_sha256']:
        raise ValueError('launch executable/helper mismatch')
    payload = source_input.read_bytes()
    if digest(payload) != request['input_sha256']:
        raise ValueError('launch input mismatch')
    if not root.exists():
        root.mkdir()
    marker = root / '.recorder-root'
    if not marker.exists():
        if any(root.iterdir()):
            raise ValueError('unowned nonempty root')
        write(marker, b'evidence-recorder-v1\n')
    if marker.read_bytes() != b'evidence-recorder-v1\n':
        raise ValueError('wrong root marker')
    for name in ('cases', 'incoming', 'incomplete', 'reserved'):
        path = safe_path(root / name)
        path.mkdir(exist_ok=True)
    name = request['case_id']
    if any((root / lane / name).exists() for lane in ('cases', 'incoming', 'incomplete', 'reserved')):
        raise ValueError('case path already reserved')
    (root / 'reserved' / name).mkdir()  # Exclusive permanent tombstone, never reused.
    stage = root / 'incoming' / name
    stage.mkdir()
    write(stage / 'input.bin', payload)
    emit(stage / 'request.json', request)
    # Frozen request explicitly names this exact retained input path.
    argv = request['argv']
    if argv[argv.index('--input') + 1] != str(stage / 'input.bin') or argv[argv.index('--nonce') + 1] != request['nonce']:
        raise ValueError('argv input/nonce binding mismatch')
    start = time.monotonic_ns()
    used = cpu_ns()
    child = None
    try:
        with (stage / 'stdout.bin').open('xb') as stdout, (stage / 'stderr.bin').open('xb') as stderr:
            child = subprocess.Popen(argv, stdout=stdout, stderr=stderr)
            emit(stage / 'launch.json', dict(request, pid=child.pid))
            if '--ready' in argv:
                ready = Path(argv[argv.index('--ready') + 1])
                deadline = time.monotonic() + 5
                while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(.01)
                if not ready.exists():
                    raise RuntimeError('helper readiness unavailable within five seconds')
                if seam == 'kill-producer':
                    emit(root.parent / (name + '-kill.json'), dict(action='Popen.kill', target_pid=child.pid, supervisor_pid=os.getpid()))
                    child.kill()
            try:
                code = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
                raise RuntimeError('helper exceeded five-second termination bound')
        end = time.monotonic_ns()
        emit(stage / 'exit.json', dict(code=code))
        emit(stage / 'timing.json', dict(start_ns=start, end_ns=end, duration_ns=end-start,
                                       cpu_ns=max(0, cpu_ns()-used), finalized=True))
        if seam in ('kill-producer', 'parser-raises', 'cleanup-raises'):
            raise RuntimeError('disclosed test-driver seam: ' + seam)
        # Parse only after original streams and actual finalized exit/timing exist.
        json.loads((stage / 'stdout.bin').read_bytes().split(b'\n', 1)[0])
        emit(stage / 'result.json', dict(case_id=name, evidence='complete', exit=code,
                                       stdout_bytes=(stage/'stdout.bin').stat().st_size,
                                       stderr_bytes=(stage/'stderr.bin').stat().st_size))
        emit(stage / 'MANIFEST.json', inventory(files_under(stage)))
        validate_case(stage, request)
        # The permanent exclusive ID reservation prevents cooperating recorder
        # processes from acquiring this destination; no replace operation is used.
        final = root / 'cases' / name
        if final.exists():
            raise RuntimeError('commit destination exists')
        stage.rename(final)
        return 'COMPLETE_EVIDENCE'
    except BaseException:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        if stage.exists():
            # A failed validation is never promoted, even if finalization began.
            target = root / 'incomplete' / name
            if target.exists():
                raise RuntimeError('unresolved failed commit; preserve incoming')
            stage.rename(target)
        raise


def validate_archive(path, expected):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate archive member')
        if any(n.startswith('/') or '\\' in n or ':' in n or '..' in Path(n).parts for n in names):
            raise ValueError('unsafe archive member')
        if set(names) != set(expected) | {'ARCHIVE-MANIFEST.json'}:
            raise ValueError('closed archive census mismatch')
        if json.loads(archive.read('ARCHIVE-MANIFEST.json')) != expected:
            raise ValueError('external archive manifest mismatch')
        for name, fact in expected.items():
            raw = archive.read(name)
            if len(raw) != fact['bytes'] or digest(raw) != fact['sha256']:
                raise ValueError('archive bytes mismatch: ' + name)
    return 'ARCHIVE_AUTHENTICATED'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['record', 'validate', 'archive-validate'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--test-seam', choices=['kill-producer', 'parser-raises', 'cleanup-raises'])
    args = parser.parse_args()
    expected = json.loads(args.request.read_bytes())
    try:
        if args.operation == 'record':
            result = record(args.root, expected, args.input, args.test_seam)
        elif args.operation == 'validate':
            result = validate_case(args.root, expected)
        else:
            result = validate_archive(args.root, expected)
        print(result)
    except Exception as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
