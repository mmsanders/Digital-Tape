#!/usr/bin/env python3
"""Fetch and authenticate the durable READOPT-D10-1 evidence asset."""
import argparse, io, tarfile, urllib.request
from pathlib import Path
from check import load, require, sha

def extract(data, destination, m=None):
    m=m or load(); pin=m['asset']
    require(len(data)==pin['bytes'] and sha(data)==pin['sha256'], 'whole release asset identity')
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as t:
        entries=t.getmembers()
        require(len(entries)==len(pin['files']) and {e.name for e in entries}==set(pin['files']), 'release member census')
        for e in entries:
            require(e.isfile() and not Path(e.name).is_absolute() and '..' not in Path(e.name).parts,'safe release member')
            b=t.extractfile(e).read();require(sha(b)==pin['files'][e.name],'release member identity '+e.name)
        for e in entries:
            target=Path(destination)/e.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(t.extractfile(e).read())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',required=True);p.add_argument('--archive');args=p.parse_args();m=load();a=m['asset']
    url='https://github.com/'+a['repository']+'/releases/download/'+a['tag']+'/'+a['file']
    data=Path(args.archive).read_bytes() if args.archive else urllib.request.urlopen(url,timeout=60).read()
    extract(data,args.destination,m);print('authenticated '+a['sha256'])
if __name__=='__main__':main()
