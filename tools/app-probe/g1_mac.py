#!/usr/bin/env python3
"""G1 summary for macOS tracers (#444): device-node opens attributed to each
control PID in fs_usage text or eslogger JSON lines.
  g1_mac.py fs_usage FILE NEG_PID POS_PID
  g1_mac.py eslogger FILE NEG_PID POS_PID"""
import json, re, sys

DEV = re.compile(r'/dev/r?disk\d+')


def fs_usage(path, pids):
    hits = {p: [] for p in pids}
    for line in open(path, errors='replace'):
        m = re.search(r'\.(\d+)\s*$', line.rstrip())
        if m and int(m.group(1)) in pids and DEV.search(line) and len(hits[int(m.group(1))]) < 8:
            hits[int(m.group(1))].append(' '.join(line.split()))
    return hits


def eslogger(path, pids):
    hits = {p: [] for p in pids}
    for line in open(path, errors='replace'):
        if '/dev/' not in line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        pid = e.get('process', {}).get('audit_token', {}).get('pid')
        p = (e.get('event', {}).get('open', {}) or {}).get('file', {}).get('path', '')
        if pid in pids and DEV.search(p or '') and len(hits[pid]) < 8:
            hits[pid].append(p)
    return hits


def main(kind, path, neg, pos):
    neg, pos = int(neg), int(pos)
    h = (fs_usage if kind == 'fs_usage' else eslogger)(path, {neg, pos})
    print(json.dumps({'tracer': kind, 'negative': h[neg], 'positive': h[pos],
                      'negative_detected': bool(h[neg]), 'positive_clean': not h[pos]}, sort_keys=True))


if __name__ == '__main__':
    main(*sys.argv[1:5])
