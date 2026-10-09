#!/usr/bin/env python3
"""Rebuild a WP-14 transport snapshot from its compact artifact form.

    unsparse.py IMAGE.extents.json [OUT]

IMAGE.blocks holds the snapshot's nonzero 1 MiB blocks in order and
IMAGE.extents.json their offsets, the exact size and the SHA-256 of the whole
image (also listed in the capture's large-artifacts.json). The rebuilt image
is sparse where the filesystem allows, and is refused unless it hashes to
the recorded value. Product #392 transport tooling; no verdicts.
"""
import hashlib
import json
import sys
from pathlib import Path


def main():
    meta_path = Path(sys.argv[1])
    meta = json.loads(meta_path.read_text())
    blocks = Path(str(meta_path)[:-len('.extents.json')] + '.blocks')
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else meta_path.with_name(meta['image'])
    if hashlib.sha256(blocks.read_bytes()).hexdigest() != meta['blocks_sha256']:
        sys.exit(f'{blocks}: blocks hash differs from {meta_path}')
    with open(blocks, 'rb') as src, open(out, 'wb') as dst:
        dst.truncate(meta['bytes'])
        for off in meta['offsets']:
            dst.seek(off)
            dst.write(src.read(min(meta['block'], meta['bytes'] - off)))
    h = hashlib.sha256()
    with open(out, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    if h.hexdigest() != meta['sha256']:
        sys.exit(f'{out}: rebuilt image does not hash to {meta["sha256"]}')
    print(f'{out}: {meta["bytes"]} bytes, sha256 {meta["sha256"]}')


if __name__ == '__main__':
    main()
