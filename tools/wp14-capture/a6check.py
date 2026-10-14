#!/usr/bin/env python3
"""a6check.py — judge one native capture of the SHIPPED tapectl for WP-14 A6.

Software #425 tooling (docs/WP14-NATIVE-CAPTURE.md). Not a verifier tree and not
acceptance: it states whether a capture file contains what the A6 recipe asks
for, and fails closed on anything it cannot read. Verification owns adequacy and
physical acceptance.

    a6check.py verify  --format F --trace FILE --pid N --capacity BYTES
                       (--target PATH | --disk N)
                       [--exe FILE --sha256 HEX] [--stdout FILE --exit-code N]
    a6check.py profile --format F --trace FILE [--pid N] [--target PATH | --disk N]

Formats:
  strace   Linux `strace -f -T` text (the off-platform rehearsal)
  dtrace   lines printed by tools/wp14-capture/a6-macos.d (macOS)
  iocap    JSON lines from tests/wp14_adapter/iocap_posix.c (macOS/Linux)
  etw-xml  `tracerpt -of XML` export of a WPR DiskIO/FileIO kernel trace (Windows)

`verify` PASSes only if, for the given PID: the target was opened read-only and
never for writing, no write reached it, and a read that covers the last sector
(offset <= capacity-512 < offset+length) at an offset above 4294967295 completed
with the full length. Exit 0 PASS, 1 FAIL, 2 unreadable input or usage.
`profile` prints call counts and per-call latency; it judges nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import xml.etree.ElementTree as ET

U32_MAX = 0xFFFFFFFF
SECTOR = 512


class InputError(Exception):
    """The capture cannot be read as the named format: a clean stop, never a PASS."""


# ---------------------------------------------------------------- events
# One normalized record per OS call:
#   pid, op (open|read|write|flush|close), fd (or handle / disk key), path,
#   write_open (bool, opens only), off, len, ret (bytes, or -1), err, dur_s

def ev(**kw):
    base = dict(pid=None, op=None, fd=None, path=None, write_open=False,
                off=None, len=None, ret=None, err=None, dur_s=None, how=None)
    base.update(kw)
    return base


_STRACE = re.compile(
    r'^(?P<pid>\d+)\s+(?:\d\d:\d\d:\d\d(?:\.\d+)?\s+)?(?P<call>\w+)\((?P<args>.*)\)\s+=\s+'
    r'(?P<ret>-?\d+|\?)(?:\s+(?P<err>E[A-Z0-9]+))?[^<]*(?:<(?P<dur>[\d.]+)>)?\s*$')


def parse_strace(text):
    out = []
    for line in text.splitlines():
        if 'unfinished' in line or 'resumed>' in line:
            raise InputError('strace line split across threads; rerun single-threaded or with -f unsplit: '
                             + line[:80])
        m = _STRACE.match(line)
        if not m:
            continue
        pid, call, args = int(m['pid']), m['call'], m['args']
        ret = -1 if m['ret'] == '?' else int(m['ret'])
        dur = float(m['dur']) if m['dur'] else None
        if call in ('open', 'openat'):
            p = re.search(r'"((?:[^"\\]|\\.)*)"', args)
            if not p:
                continue
            flags = args[p.end():]
            out.append(ev(pid=pid, op='open', path=p.group(1), fd=ret if ret >= 0 else None,
                          write_open=bool(re.search(r'O_RDWR|O_WRONLY', flags)),
                          ret=ret, err=m['err'], dur_s=dur))
        elif call in ('pread64', 'pread', 'pwrite64', 'pwrite'):
            fd = re.match(r'\s*(\d+),', args)
            tail = re.search(r',\s*(\d+),\s*(\d+)\s*$', args)
            if not fd or not tail:
                raise InputError('unparsed %s line: %s' % (call, line[:80]))
            out.append(ev(pid=pid, op='read' if 'read' in call else 'write', fd=int(fd.group(1)),
                          len=int(tail.group(1)), off=int(tail.group(2)), ret=ret, err=m['err'], dur_s=dur))
        elif call in ('fsync', 'fdatasync'):
            out.append(ev(pid=pid, op='flush', how=call, fd=int(re.match(r'\s*(\d+)', args).group(1)),
                          ret=ret, err=m['err'], dur_s=dur))
        elif call == 'close':
            out.append(ev(pid=pid, op='close', fd=int(re.match(r'\s*(\d+)', args).group(1)), ret=ret))
    return out


def _kv(line):
    """key=value tokens; path= takes the rest of the line (paths may hold spaces)."""
    d = {}
    head, sep, path = line.partition(' path=')
    for tok in head.split():
        if '=' in tok:
            k, v = tok.split('=', 1)
            d[k] = v
    if sep:
        d['path'] = path.rstrip('\n')
    return d


def parse_dtrace(text):
    out, header = [], False
    for line in text.splitlines():
        if not line.startswith('A6 '):
            continue
        d = _kv(line[3:])
        if 'tool' in d:
            header = True
            continue
        try:
            pid, op = int(d['pid']), d['op']
            ret = int(d.get('ret', '0'))
            err = None if d.get('errno', '0') == '0' else 'errno ' + d['errno']
            dur = int(d['ns']) / 1e9 if 'ns' in d else None
            if op == 'open':
                flags = int(d['flags'], 16)
                out.append(ev(pid=pid, op='open', path=d['path'], fd=ret if ret >= 0 else None,
                              write_open=bool(flags & 0x3), ret=ret, err=err))
            elif op in ('read', 'write'):
                out.append(ev(pid=pid, op=op, fd=int(d['fd']), off=int(d['off']), len=int(d['len']),
                              ret=ret, err=err, dur_s=dur))
            elif op == 'flush':
                out.append(ev(pid=pid, op='flush', fd=int(d['fd']), how=d.get('how'), ret=ret, err=err, dur_s=dur))
            elif op == 'close':
                out.append(ev(pid=pid, op='close', fd=int(d['fd']), ret=ret))
            elif op == 'exit':
                out.append(ev(pid=pid, op='exit', ret=int(d['status'])))
        except (KeyError, ValueError) as e:
            raise InputError('malformed dtrace line (%s): %s' % (e, line[:80]))
    if not header:
        raise InputError('no "A6 trace tool=dtrace" header: not an a6-macos.d capture')
    return out


def parse_iocap(text):
    out, pid = [], None
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            j = json.loads(line)
        except ValueError:
            raise InputError('iocap line %d is not JSON' % n)
        c = j.get('call')
        if c == 'iocap_attach':
            if 'pid' not in j:
                raise InputError('iocap log has no PID (the Windows iocap build does not record one)')
            pid = int(j['pid'])
            continue
        if pid is None:
            raise InputError('iocap record before iocap_attach')
        err = None if not j.get('errno') else 'errno %d' % j['errno']
        if c == 'open':
            out.append(ev(pid=pid, op='open', path=j['path'], fd=j['fd'] if j['fd'] >= 0 else None,
                          write_open=bool(j['write']), ret=j['fd'], err=err))
        elif c in ('pread', 'pwrite'):
            out.append(ev(pid=pid, op='read' if c == 'pread' else 'write', fd=j['fd'], off=j['offset'],
                          len=j['bytes'], ret=j['ret'], err=err))
        elif c in ('fsync', 'fcntl_fullfsync', 'ioctl_synccache'):
            out.append(ev(pid=pid, op='flush', how=c, fd=j['fd'], ret=j['ret'], err=err))
    return out


# Windows kernel (MOF) providers, by GUID, and the opcodes used here.
G_DISKIO = '3d6fa8d4-fe05-11d0-9dda-00c04fd7ba7c'   # 10 Read, 11 Write, 14 FlushBuffers
G_FILEIO = '90cbdc39-4a3e-11d1-84f4-0000f80464e3'   # 64 Create, 67 Read, 68 Write, 76 OpEnd
G_THREAD = '3d6fa8d1-fe05-11d0-9dda-00c04fd7ba7c'   # 1 Start, 3 DCStart
G_PROC = '3d6fa8d0-fe05-11d0-9dda-00c04fd7ba7c'     # 1 Start, 3 DCStart
G_HEADER = '68fdd900-4a3e-11d1-84f4-0000f80464e3'   # 0 header (PerfFreq)


def _int(s):
    s = (s or '').strip()
    return int(s, 16) if s.lower().startswith('0x') else int(s)


def parse_etw_xml(text):
    """tracerpt XML. Returns events plus process names, keyed the same way."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise InputError('not XML: %s' % e)
    raw, threads, procs, perf_freq = [], {}, {}, None
    for e in root.iter():
        if not e.tag.endswith('}Event') and e.tag != 'Event':
            continue
        sysd, data = {}, {}
        for c in e.iter():
            tag = c.tag.split('}')[-1]
            if tag == 'Provider' and c.get('Guid'):
                sysd['guid'] = c.get('Guid').strip('{}').lower()
            elif tag == 'Opcode' and c.text and c.text.strip().isdigit() and 'opcode' not in sysd:
                sysd['opcode'] = int(c.text)
            elif tag == 'Execution':
                sysd['pid'] = c.get('ProcessID')
                sysd['tid'] = c.get('ThreadID')
            elif tag == 'TimeCreated':
                sysd['time'] = c.get('SystemTime')
            elif tag == 'Data' and c.get('Name'):
                data[c.get('Name')] = (c.text or '').strip()
        g, op = sysd.get('guid'), sysd.get('opcode')
        if g == G_THREAD and op in (1, 3) and 'TThreadId' in data:
            threads[_int(data['TThreadId'])] = _int(data['ProcessId'])
        elif g == G_PROC and op in (1, 3) and 'ProcessId' in data:
            procs[_int(data['ProcessId'])] = (data.get('ImageFileName', ''), data.get('CommandLine', ''))
        elif g == G_HEADER and 'PerfFreq' in data:
            perf_freq = _int(data['PerfFreq'])
        elif g in (G_DISKIO, G_FILEIO):
            raw.append((g, op, sysd, data))
    if not raw and not threads:
        raise InputError('no kernel DiskIo/FileIo/Thread events: wrong export or empty trace')

    def owner(data, sysd, key):
        t = data.get(key)
        if t not in (None, ''):
            p = threads.get(_int(t))
            if p is not None:
                return p
        try:
            p = _int(sysd.get('pid'))
            return p if p not in (0, 4, 0xFFFFFFFF, -1) else None
        except (TypeError, ValueError):
            return None

    out, names, status = [], {}, {}
    for g, op, sysd, data in raw:
        if g == G_FILEIO and op == 76 and 'IrpPtr' in data:
            status[data['IrpPtr']] = _int(data.get('NtStatus', '0'))
    for g, op, sysd, data in raw:
        dur = None
        if g == G_DISKIO:
            if 'HighResResponseTime' in data and perf_freq:
                dur = _int(data['HighResResponseTime']) / perf_freq
            key = 'disk%d' % _int(data.get('DiskNumber', '-1'))
            pid = owner(data, sysd, 'IssuingThreadId')
            if op in (10, 11):
                n = _int(data['TransferSize'])
                out.append(ev(pid=pid, op='read' if op == 10 else 'write', fd=key, path=key,
                              off=_int(data['ByteOffset']), len=n, ret=n, dur_s=dur, how='DiskIo'))
            elif op == 14:
                out.append(ev(pid=pid, op='flush', fd=key, path=key, ret=0, dur_s=dur, how='DiskIo'))
        elif g == G_FILEIO:
            fo = data.get('FileObject')
            pid = owner(data, sysd, 'TTID')
            if op == 64:
                names[fo] = data.get('OpenPath', '')
                out.append(ev(pid=pid, op='open', fd=fo, path=names[fo], ret=0,
                              write_open=False, how='FileIo'))
            elif op in (67, 68):
                st = status.get(data.get('IrpPtr'))
                n = _int(data['IoSize'])
                out.append(ev(pid=pid, op='read' if op == 67 else 'write', fd=fo, path=names.get(fo),
                              off=_int(data['Offset']), len=n, ret=(n if st in (None, 0) else -1),
                              err=None if st in (None, 0) else 'NTSTATUS 0x%08x' % st,
                              how='FileIo' + ('' if st is not None else '-nostatus')))
    return out, procs


PARSERS = {'strace': parse_strace, 'dtrace': parse_dtrace, 'iocap': parse_iocap}


def load(fmt, path):
    try:
        with open(path, 'r', encoding='utf-8', errors='strict') as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(path, 'r', encoding='utf-16') as f:   # tracerpt may write UTF-16
            text = f.read()
    except OSError as e:
        raise InputError('cannot read %s: %s' % (path, e))
    if fmt == 'etw-xml':
        return parse_etw_xml(text)
    return PARSERS[fmt](text), {}


# ---------------------------------------------------------------- verify

def target_calls(events, pid, target, disk):
    """Calls by `pid` on the target, resolving fds through that PID's opens."""
    fdmap, opens, calls = {}, [], []
    for e in events:
        if e['pid'] != pid:
            continue
        if e['op'] == 'open':
            hit = (disk is None and e['path'] is not None
                   and (e['path'] == target or e['path'].endswith('/' + target.lstrip('./'))
                        or e['path'].endswith('\\' + target)))
            if e['fd'] is not None:
                fdmap[e['fd']] = hit
            if hit:
                opens.append(e)
        elif e['op'] == 'close':
            fdmap.pop(e['fd'], None)
        elif disk is not None and e['fd'] == 'disk%d' % disk:
            calls.append(e)
        elif disk is None and fdmap.get(e['fd']):
            calls.append(e)
    return opens, calls


def judge(events, procs, a):
    reasons, notes = [], []
    mirror = a.capacity - SECTOR
    if mirror <= U32_MAX:
        reasons.append('capacity %d puts the last sector at %d, not beyond 4294967295' % (a.capacity, mirror))
    mine = [e for e in events if e['pid'] == a.pid]
    if not mine:
        reasons.append('no captured call belongs to PID %d' % a.pid)
    if procs:
        img = procs.get(a.pid)
        if img is None:
            reasons.append('trace has no process record for PID %d' % a.pid)
        elif 'tapectl' not in img[0].lower():
            reasons.append('PID %d is %r, not tapectl' % (a.pid, img[0]))
        else:
            notes.append('process %d image %s command %s' % (a.pid, img[0], img[1]))
    opens, calls = target_calls(events, a.pid, a.target, a.disk)
    if a.disk is None:
        good = [o for o in opens if o['ret'] is not None and o['ret'] >= 0 and not o['err']]
        if not good:
            reasons.append('PID %d never opened %s successfully' % (a.pid, a.target))
        if any(o['write_open'] for o in opens):
            reasons.append('the target was opened for writing; this is a read-only witness')
    writes = [c for c in calls if c['op'] == 'write']
    if writes:
        reasons.append('%d write call(s) reached the target' % len(writes))
    covering = [c for c in calls if c['op'] == 'read' and c['off'] is not None
                and c['off'] <= mirror < c['off'] + c['len']]
    high = [c for c in covering if c['off'] > U32_MAX]
    ok = [c for c in high if c['ret'] == c['len'] and not c['err']]
    if not covering:
        reasons.append('no read by PID %d covers byte offset %d (capacity-512)' % (a.pid, mirror))
    elif not high:
        reasons.append('the read covering capacity-512 is at offset %d, not above 4294967295'
                       % covering[0]['off'])
    elif not ok:
        c = high[0]
        reasons.append('the read at %d did not complete: ret=%s err=%s' % (c['off'], c['ret'], c['err']))
    if ok and ok[0]['how'] in ('DiskIo', 'FileIo-nostatus'):
        # A kernel DiskIo record carries no status: completion plus verify OK is the result.
        if a.stdout is None or a.exit_code is None:
            reasons.append('%s records carry no call status: --stdout and --exit-code are required'
                           % ok[0]['how'])
        else:
            out = open(a.stdout, 'rb').read().decode('utf-8', 'replace').strip()
            if a.exit_code != 0 or out != 'OK':
                reasons.append('verify did not print exactly OK with exit 0 (exit %d, %r)' % (a.exit_code, out[:40]))
            else:
                notes.append('call status from verify OK/exit 0: both superblock copies read valid')
    exits = [e['ret'] for e in mine if e['op'] == 'exit']
    if exits:
        notes.append('traced exit status %d' % exits[-1])
        if a.exit_code is not None and a.exit_code != exits[-1]:
            reasons.append('--exit-code %d disagrees with the traced exit status %d' % (a.exit_code, exits[-1]))
    if a.exe:
        h = hashlib.sha256(open(a.exe, 'rb').read()).hexdigest()
        if a.sha256 and h != a.sha256.lower():
            reasons.append('executable sha256 %s is not the expected %s' % (h, a.sha256))
        notes.append('executable sha256 %s' % h)
    return {
        'verdict': 'FAIL' if reasons else 'PASS',
        'reasons': reasons,
        'pid': a.pid,
        'capacity': a.capacity,
        'mirror_offset': mirror,
        'mirror_reads': [{k: c[k] for k in ('off', 'len', 'ret', 'err', 'how', 'dur_s')} for c in covering],
        'target_opens': [{k: o[k] for k in ('path', 'write_open', 'ret', 'err')} for o in opens],
        'target_calls': {op: sum(1 for c in calls if c['op'] == op) for op in ('read', 'write', 'flush')},
        'max_read_offset': max((c['off'] for c in calls if c['op'] == 'read'), default=None),
        'exit_status': exits[-1] if exits else None,
        'notes': notes,
    }


# ---------------------------------------------------------------- profile

def profile(events, a):
    if a.pid is not None:
        events = [e for e in events if e['pid'] == a.pid]
    if a.target or a.disk is not None:
        _, events = target_calls(events, a.pid, a.target, a.disk) if a.pid is not None else (None, events)
    rep = {}
    for op in ('read', 'write', 'flush'):
        es = [e for e in events if e['op'] == op]
        d = sorted(e['dur_s'] for e in es if e['dur_s'] is not None)
        r = {'calls': len(es), 'bytes': sum(e['len'] or 0 for e in es)}
        if d:
            r.update(timed=len(d), sum_s=round(sum(d), 6), mean_ms=round(1000 * statistics.mean(d), 4),
                     p50_ms=round(1000 * d[len(d) // 2], 4), p99_ms=round(1000 * d[min(len(d) - 1, int(len(d) * 0.99))], 4),
                     max_ms=round(1000 * d[-1], 4))
        rep[op] = r
    rep['note'] = ('per-call latency as recorded by the tracer; not physical media service time unless the '
                   'tracer is kernel disk I/O on the card itself')
    return rep


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=('verify', 'profile'))
    p.add_argument('--format', required=True, choices=('strace', 'dtrace', 'iocap', 'etw-xml'))
    p.add_argument('--trace', required=True)
    p.add_argument('--pid', type=int)
    p.add_argument('--capacity', type=int)
    p.add_argument('--target')
    p.add_argument('--disk', type=int)
    p.add_argument('--exe')
    p.add_argument('--sha256')
    p.add_argument('--stdout')
    p.add_argument('--exit-code', type=int)
    a = p.parse_args(argv)
    try:
        events, procs = load(a.format, a.trace)
        if a.mode == 'verify':
            if a.pid is None or a.capacity is None or (a.target is None) == (a.disk is None):
                p.error('verify needs --pid, --capacity and exactly one of --target/--disk')
            rep = judge(events, procs, a)
        else:
            rep = profile(events, a)
    except InputError as e:
        print(json.dumps({'verdict': 'INPUT-ERROR', 'reasons': [str(e)]}, indent=1))
        return 2
    print(json.dumps(rep, indent=1))
    return 0 if a.mode == 'profile' or rep['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
