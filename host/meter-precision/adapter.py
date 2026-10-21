"""Conforming A252 helper adapter; domain bytes are a separately closed sidecar.

The recorder's source, nine-file schema, fixed streams and five-second bound are
unchanged. A native subcommand has a stricter four-second bound and direct files.
Failure leaves its original sidecar and the recorder's incomplete case intact.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha(b):
    return hashlib.sha256(b).hexdigest()


def emit(p, value):
    with p.open('xb') as f:
        f.write((json.dumps(value, sort_keys=True) + '\n').encode())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--nonce', required=True)
    a = p.parse_args()
    raw = a.input.read_bytes()
    sys.stdout.buffer.write((json.dumps(dict(pid=os.getpid(), nonce=a.nonce,
        input_sha256=sha(raw), input_bytes=len(raw)), sort_keys=True)+'\n').encode())
    sys.stdout.buffer.flush()
    req = json.loads(raw)
    out = Path(req['domain_dir'])
    out.mkdir()  # Exclusive, permanently new, no resume/retry.
    emit(out/'REQUEST.json', dict(request=req, recorder_nonce=a.nonce,
                                  recorder_input_sha256=sha(raw), adapter_pid=os.getpid()))
    binary = Path(req['argv'][0])
    assert sha(binary.read_bytes()) == req['binary_sha256']
    for name, expected in req['inputs'].items():
        assert sha(Path(name).read_bytes()) == expected
    start = time.monotonic_ns()
    with (out/'stdout.bin').open('xb') as so, (out/'stderr.bin').open('xb') as se:
        child = subprocess.Popen(req['argv'], stdout=so, stderr=se)
        emit(out/'LAUNCH.json', dict(argv=req['argv'], pid=child.pid,
             binary_sha256=req['binary_sha256'], source=req['source'], start_ns=start))
        timeout = False
        try:
            code = child.wait(timeout=4)
        except subprocess.TimeoutExpired:
            timeout = True
            child.kill()
            code = child.wait(timeout=.3)
    emit(out/'EXIT.json', dict(code=code, timeout=timeout, end_ns=time.monotonic_ns()))
    facts = {f.name:dict(bytes=f.stat().st_size, sha256=sha(f.read_bytes()))
             for f in sorted(out.iterdir()) if f.is_file()}
    emit(out/'MANIFEST.json', facts)
    assert code == 0 and not timeout, 'native subcommand failed; raw retained, no retry'
    sys.stdout.buffer.write(b'helper-output\n')
    sys.stderr.buffer.write(b'helper-diagnostic\n')


if __name__ == '__main__':
    main()
