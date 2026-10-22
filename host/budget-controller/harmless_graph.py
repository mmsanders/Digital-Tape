"""Correction-only cooperating three-process graph. No Product/tool invocation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

mode, root, role = sys.argv[1:]
root = Path(root)
with (root/'spy.jsonl').open('ab') as f:
    f.write((json.dumps(dict(pid=os.getpid(), parent=os.getppid(), group=os.getpgrp(), role=role))+'\n').encode())
    f.flush()
if role != 'leaf':
    next_role = 'tracer' if role == 'adapter' else 'leaf'
    p = subprocess.Popen([sys.executable, '-B', __file__, mode, str(root), next_role])
    code = p.wait()
    raise SystemExit(code)
for folder in ('source', 'build', 'work', 'temp', 'archive', 'retained'):
    p = root/folder
    p.mkdir(exist_ok=True)
    with (p/(str(os.getpid())+'.bin')).open('xb') as f:
        f.write((folder.encode()+b'\0\xff')*128)
        f.flush()
        os.fsync(f.fileno())
sys.stdout.buffer.write(b'original\0\xffraw\n')
sys.stdout.buffer.flush()
sys.stderr.buffer.write(b'original\x80diagnostic\n')
sys.stderr.buffer.flush()
if mode == 'unsupported':
    # A distinct unexpected argv must cause terminal refusal, never be ignored.
    p = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(1)'])
    p.wait()
else:
    time.sleep(.12)
