"""Source-bound C adapter mechanics; execution still requires independent C clearance."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import controller as C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--sha', required=True)
    a = ap.parse_args()
    raw = a.input.read_bytes()
    if C.sha(raw) != a.sha:
        raise RuntimeError('external payload identity mismatch')
    req = json.loads(raw)
    for path, digest in req['inputs'].items():
        if C.sha(Path(path).read_bytes()) != digest:
            raise RuntimeError('input identity mismatch')
    root = Path(req['task_root']).resolve(strict=True)
    for path in req['owned_paths']:
        if not Path(path).resolve().is_relative_to(root):
            raise RuntimeError('path outside task census')
    out = Path(req['domain_dir'])
    out.mkdir(exist_ok=False)
    C.immutable(out/'REQUEST.json', dict(request=req, adapter_pid=os.getpid(), input_sha256=a.sha))
    env = dict(os.environ)
    env.update(req['environment'])
    start = time.monotonic_ns()
    with (out/'stdout.bin').open('xb') as so, (out/'stderr.bin').open('xb') as se:
        # Same argv/env/cwd and full syscall output as retained514. Unlike its
        # adapter, inherit the controller's owned process group; NEVER setsid here.
        child = subprocess.Popen(req['argv'], stdout=so, stderr=se, env=env, cwd=req['cwd'])
        C.immutable(out/'LAUNCH.json', dict(argv=req['argv'], pid=child.pid,
                    group=os.getpgrp(), source=req['source'], start_ns=start))
        code = child.wait()  # task supervisor owns termination; reap before root exit
    C.immutable(out/'EXIT.json', dict(code=code, end_ns=time.monotonic_ns()))
    C.immutable(out/'MANIFEST.json', {p.name:dict(bytes=p.stat().st_size, sha256=C.sha(p.read_bytes()))
                for p in sorted(out.iterdir()) if p.is_file()})
    sys.stdout.buffer.write(b'helper-output\n')
    sys.stderr.buffer.write(b'helper-diagnostic\n')
    if code < 0:
        raise RuntimeError('native signal; original raw retained')


if __name__ == '__main__':
    main()
