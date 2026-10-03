#!/usr/bin/env python3
"""Reproducible source fetch/conversion; frozen hashes are authoritative."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import urllib.request
import shutil
from model import write
import array
import sys

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('destination'); ap.add_argument('--download',action='store_true'); args=ap.parse_args()
    root=pathlib.Path(__file__).resolve().parent
    dest=pathlib.Path(args.destination); dest.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((root/'SOURCES.json').read_text())
    for s in manifest['sources']:
        original=dest/s['original_name']
        if args.download and not original.exists():
            # Wikimedia refuses the generic urllib UA. Identify this client,
            # preserve the exact pinned URL and verify every byte.
            req=urllib.request.Request(s['download_url'],headers={'User-Agent':manifest['download_user_agent']})
            pending=original.with_suffix(original.suffix+'.partial')
            with urllib.request.urlopen(req,timeout=60) as response, pending.open('wb') as out:
                shutil.copyfileobj(response,out)
            assert sha(pending)==s['original_sha256'],pending
            pending.replace(original)
        assert sha(original)==s['original_sha256'],original
        raw=dest/(s['role']+'.raw')
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(original),'-map_metadata','-1','-ac','2','-ar','44100','-c:a','pcm_s16le','-fflags','+bitexact','-flags:a','+bitexact','-f','s16le',str(raw)],check=True)
        a=array.array('h'); a.frombytes(raw.read_bytes())
        if sys.byteorder!='little':a.byteswap()
        canonical=dest/s['canonical_name']; write(canonical,a)
        assert sha(canonical)==s['canonical_sha256'],canonical
        print(s['role'],s['original_sha256'],s['canonical_sha256'])

if __name__=='__main__':main()
