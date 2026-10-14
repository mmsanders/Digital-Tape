#!/usr/bin/env python3
"""a6check.py — judge one native capture of the SHIPPED tapectl `verify` for WP-14 A6.

Software #425/#428 tooling (docs/WP14-NATIVE-CAPTURE.md). Not a verifier tree, not an
oracle and not acceptance: it states whether a capture contains what the A6 recipe asks
for. Verification #146 owns method adequacy and every physical disposition.

    a6check.py --format {strace,dtrace,etw-xml} --trace FILE --pid N
               --capacity BYTES --geometry FILE --target PATH [--disk N]
               --exe FILE --sha256 HEX --stdout FILE
               --tracer-log FILE --diagnostics FILE [--diagnostics FILE ...]
               [--exit-code N]

Verdicts (exit status): PASS 0 · FAIL 1 (the capture contradicts A6, or the tracer reports
loss/errors) · INPUT-ERROR 2 (unreadable or inconsistent inputs) · HELD 3 (something A6
needs is absent or not observable on this path). Every reason is reported, not only the
first; a verdict is never PASS while any reason stands.

PASS needs ALL of, for the bound tapectl process:
  - the executable file hashes to --sha256 and the traced process is that tapectl;
  - the target is the device/image named by --target (and --disk), and --geometry
    reports exactly --capacity bytes with 512-byte sectors;
  - every byte of [capacity-512, capacity) is covered by bytes that successful reads
    actually returned, from calls whose offset is above 4294967295, with each call's
    native result captured (syscall return, or FileIo OpEnd NtStatus + ExtraInfo);
  - no write by the process reaches the target;
  - verify stdout is exactly "OK", and the exit status is 0 and consistent everywhere
    it was recorded;
  - the tracer completed: every recorded tracer exit is 0, no loss/drop/error is
    reported, and the format's completeness marker is present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET

U32_MAX = 0xFFFFFFFF
SECTOR = 512


class InputError(Exception):
    """The inputs cannot be read as stated: a clean stop, never a PASS."""


class Verdict:
    def __init__(self):
        self.fail, self.held, self.notes = [], [], []

    def name(self):
        return 'FAIL' if self.fail else 'HELD' if self.held else 'PASS'


def ev(**kw):
    base = dict(pid=None, op=None, fd=None, path=None, mode=None, off=None, len=None,
                ret=None, err=None, status_src=None, exe=None, stale=None, why=None)
    base.update(kw)
    return base


# ------------------------------------------------------------------ strace (Linux)

_STRACE = re.compile(
    r'^(?P<pid>\d+)\s+(?:\d\d:\d\d:\d\d(?:\.\d+)?\s+)?(?P<call>\w+)\((?P<args>.*)\)\s+=\s+'
    r'(?P<ret>-?\d+|\?)(?:\s+(?P<err>E[A-Z0-9]+))?[^<]*(?:<[\d.]+>)?\s*$')
_STRACE_EXIT = re.compile(r'^(?P<pid>\d+)\s+(?:\S+\s+)?\+\+\+ exited with (?P<st>\d+) \+\+\+\s*$')
_STRACE_KILLED = re.compile(r'^(?P<pid>\d+)\s+(?:\S+\s+)?\+\+\+ killed by')


def parse_strace(text, v):
    out, meta = [], {'end': False}
    for line in text.splitlines():
        if not line.strip():
            continue
        if 'unfinished' in line or 'resumed>' in line:
            raise InputError('strace call split across threads: ' + line[:80])
        m = _STRACE_EXIT.match(line)
        if m:
            out.append(ev(pid=int(m['pid']), op='exit', ret=int(m['st'])))
            meta['end'] = True
            continue
        if _STRACE_KILLED.match(line):
            v.fail.append('strace: process was killed: ' + line.strip()[:80])
            meta['end'] = True
            continue
        m = _STRACE.match(line)
        if not m:
            if re.search(r'\+\+\+|---', line):
                continue                      # signals and other strace annotations
            raise InputError('unrecognised strace line: ' + line[:80])
        pid, call, args = int(m['pid']), m['call'], m['args']
        ret = -1 if m['ret'] == '?' else int(m['ret'])
        err = m['err']
        if call == 'execve':
            p = re.match(r'\s*"((?:[^"\\]|\\.)*)"', args)
            out.append(ev(pid=pid, op='exec', exe=p.group(1) if p else None, ret=ret, err=err))
        elif call in ('open', 'openat'):
            p = re.search(r'"((?:[^"\\]|\\.)*)"', args)
            if not p:
                raise InputError('unparsed open: ' + line[:80])
            flags = args[p.end():]
            mode = 'write' if re.search(r'O_RDWR|O_WRONLY', flags) else 'read'
            out.append(ev(pid=pid, op='open', path=p.group(1), fd=ret if ret >= 0 else None,
                          mode=mode, ret=ret, err=err))
        elif call in ('pread64', 'pread', 'pwrite64', 'pwrite'):
            fd = re.match(r'\s*(\d+),', args)
            tail = re.search(r',\s*(\d+),\s*(\d+)\s*$', args)
            if not fd or not tail:
                raise InputError('unparsed %s: %s' % (call, line[:80]))
            out.append(ev(pid=pid, op='read' if 'read' in call else 'write', fd=int(fd.group(1)),
                          len=int(tail.group(1)), off=int(tail.group(2)), ret=ret, err=err,
                          status_src='syscall return'))
        elif call in ('write', 'writev', 'pwritev', 'pwritev2'):
            fd = re.match(r'\s*(\d+),', args)
            out.append(ev(pid=pid, op='write', fd=int(fd.group(1)) if fd else None, ret=ret, err=err))
        elif call in ('fsync', 'fdatasync'):
            out.append(ev(pid=pid, op='flush', fd=int(re.match(r'\s*(\d+)', args).group(1)), ret=ret))
        elif call == 'close':
            out.append(ev(pid=pid, op='close', fd=int(re.match(r'\s*(\d+)', args).group(1)), ret=ret))
    if not meta['end']:
        v.held.append('strace: no "+++ exited with" record; the trace may be incomplete')
    return out


# ------------------------------------------------------------------ dtrace (macOS)

_DT_BENIGN = re.compile(r'^dtrace: system integrity protection is on, some features will not be available$')
_DT_RED = re.compile(r'drop|error|failed|invalid|cannot|abort|lost', re.I)


def _kv(line):
    d = {}
    head, sep, path = line.partition(' path=')
    for tok in head.split():
        if '=' in tok:
            k, val = tok.split('=', 1)
            d[k] = val
    if sep:
        d['path'] = path.rstrip('\n')
    return d


def dtrace_diag_line(line, v, where):
    s = line.strip()
    if not s or _DT_BENIGN.match(s):
        return
    if _DT_RED.search(s):
        v.fail.append('dtrace reported a problem (%s): %s' % (where, s[:100]))
    else:
        v.held.append('unrecognised dtrace message (%s): %s' % (where, s[:100]))


def parse_dtrace(text, v):
    out, header, end = [], False, False
    for line in text.splitlines():
        if not line.startswith('A6 '):
            dtrace_diag_line(line, v, 'trace file')
            continue
        body = line[3:]
        if body.startswith('trace tool=dtrace'):
            header = True
            t = _kv(body).get('target')
            out.append(ev(pid=int(t) if t and t.lstrip('-').isdigit() else None, op='target'))
            continue
        if body.strip() == 'end':
            end = True
            continue
        d = _kv(body)
        try:
            pid, op = int(d['pid']), d['op']
            ret = int(d.get('ret', '0'))
            err = None if d.get('errno', '0') == '0' else 'errno ' + d['errno']
            if op == 'open':
                flags = int(d['flags'], 16)
                out.append(ev(pid=pid, op='open', path=d['path'], fd=ret if ret >= 0 else None,
                              mode='write' if flags & 0x3 else 'read', ret=ret, err=err, exe=d.get('exe')))
            elif op in ('read', 'write'):
                out.append(ev(pid=pid, op=op, fd=int(d['fd']), off=int(d['off']), len=int(d['len']),
                              ret=ret, err=err, status_src='syscall return'))
            elif op == 'flush':
                out.append(ev(pid=pid, op='flush', fd=int(d['fd']), ret=ret, err=err))
            elif op == 'close':
                out.append(ev(pid=pid, op='close', fd=int(d['fd'])))
            elif op == 'exit':
                out.append(ev(pid=pid, op='exit', ret=int(d['status'])))
            else:
                raise InputError('unknown dtrace op %r' % op)
        except (KeyError, ValueError) as e:
            raise InputError('malformed dtrace line (%s): %s' % (e, line[:80]))
    if not header:
        raise InputError('no "A6 trace tool=dtrace" header: not an a6-macos.d capture')
    if not end:
        v.held.append('dtrace: no "A6 end" record; tracing did not finish normally')
    return out


# ------------------------------------------------------------------ ETW (Windows)

G_DISKIO = '3d6fa8d4-fe05-11d0-9dda-00c04fd7ba7c'   # 10 Read, 11 Write
G_FILEIO = '90cbdc39-4a3e-11d1-84f4-0000f80464e3'   # 64 Create, 65 Cleanup, 66 Close, 67 Read, 68 Write, 76 OpEnd
G_THREAD = '3d6fa8d1-fe05-11d0-9dda-00c04fd7ba7c'   # 1 Start, 2 End, 3 DCStart, 4 DCEnd
G_PROC = '3d6fa8d0-fe05-11d0-9dda-00c04fd7ba7c'     # 1 Start, 2 End, 3 DCStart, 4 DCEnd
G_HEADER = '68fdd900-4a3e-11d1-84f4-0000f80464e3'   # 0 EventTrace_Header


def _int(s):
    s = (s or '').strip()
    return int(s, 16) if s.lower().startswith('0x') else int(s)


def _irp(text):
    """A request/completion correlation identity: present, numeric and nonzero, else None."""
    try:
        n = _int(text)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def parse_etw_xml(text, v):
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise InputError('not XML: %s' % e)
    events = []
    for e in root.iter():
        if e.tag.split('}')[-1] != 'Event':
            continue
        sysd, data = {}, {}
        for c in e.iter():
            tag = c.tag.split('}')[-1]
            if tag == 'Provider' and c.get('Guid'):
                sysd['guid'] = c.get('Guid').strip('{}').lower()
            elif tag == 'Opcode' and c.text and c.text.strip().isdigit() and 'opcode' not in sysd:
                sysd['opcode'] = int(c.text)
            elif tag == 'TimeCreated':
                sysd['time'] = c.get('SystemTime')
            elif tag == 'Data' and c.get('Name'):
                data[c.get('Name')] = (c.text or '').strip()
        events.append((sysd.get('guid'), sysd.get('opcode'), sysd.get('time'), data))
    if not events:
        raise InputError('no events in the export')

    headers = [d for g, op, t, d in events if g == G_HEADER]
    if not headers:
        v.held.append('ETW: no EventTrace header; loss counters unknown')
    for d in headers:
        for k in ('EventsLost', 'BuffersLost'):
            if k not in d:
                v.held.append('ETW: header has no %s; completeness unknown' % k)
            elif _int(d[k]) != 0:
                v.fail.append('ETW: %s = %s; the trace is incomplete' % (k, d[k]))
    times = [t for g, op, t, d in events if t]
    if times != sorted(times):
        v.held.append('ETW: events are not in time order; thread attribution cannot be trusted')
    elif len(times) < len(events):
        v.held.append('ETW: %d events have no timestamp' % (len(events) - len(times)))

    # Lifetimes are replayed in time order. A record is attributed to a process only while
    # its thread is alive AND that process is alive; a record from a thread whose process
    # has ended (or was never seen starting) is unattributed and remembers the stale owner.
    # A FileObject names a path only from its Create until its Cleanup/Close; a read's
    # path is whatever its object names at that moment, never an older mapping.
    out, threads, live_procs, ended = [], {}, {}, {}
    # IRP lifecycle. Each valid IrpPtr has one entry while ANY request on it is still
    # outstanding: the requests seen, how many completions are still owed, and whether the
    # lifecycle is ambiguous. A request arriving while another is outstanding (any FileIo
    # operation type) makes the whole lifecycle ambiguous, and it STAYS ambiguous until
    # every outstanding request has had its OpEnd: one completion of several never resets
    # it, and requests added meanwhile are ambiguous too. Only a lifecycle that held exactly
    # one request, a read, from start to completion can supply a result, and only from an
    # OpEnd carrying both NtStatus and ExtraInfo. Missing or invalid identities never join.
    # Reuse after a lifecycle fully resolves (zero outstanding) is legitimate.
    files, pending = {}, {}

    def poison(entry, irp):
        entry['ambiguous'] = True
        for other in entry['reqs']:
            if other is not None and other['status_src'] is None:
                other['why'] = 'IrpPtr 0x%x had overlapping requests in one unresolved lifecycle' % irp

    def occupy(irp_text, e2):
        irp = _irp(irp_text)
        if irp is None:
            if e2 is not None:
                e2['why'] = 'no valid IrpPtr on the request'
            return
        entry = pending.get(irp)
        if entry is None:
            pending[irp] = {'reqs': [e2], 'owed': 1, 'ambiguous': False}
            return
        entry['reqs'].append(e2)
        entry['owed'] += 1
        poison(entry, irp)


    def owner(tid_text):
        if tid_text in (None, ''):
            return None, None
        tid = _int(tid_text)
        pid = threads.get(tid)
        if pid is not None and pid in live_procs:
            return pid, None
        return None, pid if pid is not None else ended.get(tid)

    for g, op, t, d in events:
        if g == G_PROC and op in (1, 3):
            live_procs[_int(d['ProcessId'])] = d.get('ImageFileName', '')
            out.append(ev(pid=_int(d['ProcessId']), op='exec', exe=d.get('ImageFileName', ''),
                          path=d.get('CommandLine', ''), ret=0))
        elif g == G_PROC and op in (2, 4):
            gone = _int(d['ProcessId'])
            live_procs.pop(gone, None)
            for tid in [k for k, p in threads.items() if p == gone]:
                ended[tid] = threads.pop(tid)
        elif g == G_THREAD and op in (1, 3):
            threads[_int(d['TThreadId'])] = _int(d['ProcessId'])
            ended.pop(_int(d['TThreadId']), None)
        elif g == G_THREAD and op in (2, 4):
            tid = _int(d['TThreadId'])
            if tid in threads:
                ended[tid] = threads.pop(tid)
        elif g == G_DISKIO and op in (10, 11):
            pid, stale = owner(d.get('IssuingThreadId'))
            n = _int(d['TransferSize'])
            out.append(ev(pid=pid, stale=stale, op='read' if op == 10 else 'write',
                          fd='disk%d' % _int(d['DiskNumber']),
                          off=_int(d['ByteOffset']), len=n, ret=None, status_src=None))
        if g == G_FILEIO and op != 76 and _irp(d.get('FileObject')) is None:
            # Any FileIo record of a process whose FileObject is missing or invalid leaves that
            # process's object lifetimes and write targets unknown: it may have closed or
            # written the target. Recorded here, judged HELD for the selected process.
            bpid, bstale = owner(d.get('TTID'))
            out.append(ev(pid=bpid, stale=bstale, op='badobj', exe=str(op)))
        if g == G_FILEIO and op == 64:
            pid, stale = owner(d.get('TTID'))
            occupy(d.get('IrpPtr'), None)
            fo = _irp(d.get('FileObject'))    # a FileObject must be a valid nonzero identity too
            if fo is not None:
                files[fo] = d.get('OpenPath', '')
            out.append(ev(pid=pid, stale=stale, op='open', fd=fo,
                          path=d.get('OpenPath', ''), mode=None, ret=0))
        elif g == G_FILEIO and op in (65, 66):
            pid, stale = owner(d.get('TTID'))
            occupy(d.get('IrpPtr'), None)
            fo = _irp(d.get('FileObject'))
            if fo is not None:
                files.pop(fo, None)
            out.append(ev(pid=pid, stale=stale, op='close', fd=fo))
        elif g == G_FILEIO and op in (67, 68):
            pid, stale = owner(d.get('TTID'))
            fo = _irp(d.get('FileObject'))
            e2 = ev(pid=pid, stale=stale, op='read' if op == 67 else 'write', fd=fo,
                    path=files.get(fo) if fo is not None else None,
                    off=_int(d['Offset']), len=_int(d['IoSize']))
            e2['fileio'] = True
            if fo is None:
                e2['why'] = 'no valid FileObject on the request'
            occupy(d.get('IrpPtr'), e2)
            out.append(e2)
        elif g == G_FILEIO and op == 76:
            irp = _irp(d.get('IrpPtr'))
            entry = pending.get(irp) if irp is not None else None
            if entry is None:
                continue                      # orphan completion: joins nothing
            entry['owed'] -= 1
            if entry['owed'] <= 0:
                del pending[irp]              # lifecycle fully resolved; later reuse is fresh
            if entry['ambiguous'] or len(entry['reqs']) != 1 or entry['reqs'][0] is None:
                continue                      # ambiguous or non-read lifecycle: no result
            e2 = entry['reqs'][0]
            try:
                st, got = _int(d.get('NtStatus')), _int(d.get('ExtraInfo'))
            except (TypeError, ValueError):
                e2['why'] = 'its OpEnd lacks a valid NtStatus or ExtraInfo'
                continue
            e2['ret'] = got if st == 0 else -1
            e2['err'] = None if st == 0 else 'NTSTATUS 0x%08x' % (st & 0xFFFFFFFF)
            e2['status_src'] = 'FileIo OpEnd NtStatus/ExtraInfo'
        elif g == G_FILEIO and d.get('IrpPtr') is not None:
            # Every other FileIo request class that names an IrpPtr (Info 69-71/74/75,
            # Flush 73, DirEnum 72, DirNotify 77, and any class not listed here) occupies
            # it like any request: it can only add ambiguity, never supply a Read result.
            occupy(d.get('IrpPtr'), None)
    return out


PARSERS = {'strace': parse_strace, 'dtrace': parse_dtrace, 'etw-xml': parse_etw_xml}


# ------------------------------------------------------------------ side files

def read_text(path):
    try:
        raw = open(path, 'rb').read()
    except OSError as e:
        raise InputError('cannot read %s: %s' % (path, e))
    if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
        return raw.decode('utf-16')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise InputError('%s is neither UTF-8 nor UTF-16' % path)


def sha256(path):
    try:
        return hashlib.sha256(open(path, 'rb').read()).hexdigest()
    except OSError as e:
        raise InputError('cannot read %s: %s' % (path, e))


def parse_geometry(text):
    """diskutil info, Get-Disk | Format-List, or a bare byte count."""
    g = {}
    m = re.search(r'Disk Size:.*\((\d+) Bytes\)', text)
    if m:
        g['bytes'] = int(m.group(1))
        b = re.search(r'Device Block Size:\s*(\d+)', text)
        n = re.search(r'Device Node:\s*(\S+)', text)
        g['sector'] = int(b.group(1)) if b else None
        g['node'] = n.group(1) if n else None
        return g
    m = re.search(r'^\s*Size\s*:\s*(\d+)\s*$', text, re.M)
    if m:
        g['bytes'] = int(m.group(1))
        s = re.search(r'^\s*LogicalSectorSize\s*:\s*(\d+)', text, re.M)
        n = re.search(r'^\s*Number\s*:\s*(\d+)', text, re.M)
        g['sector'] = int(s.group(1)) if s else None
        g['number'] = int(n.group(1)) if n else None
        return g
    m = re.fullmatch(r'\s*(\d+)\s*', text)
    if m:
        return {'bytes': int(m.group(1)), 'sector': SECTOR, 'image': True}
    raise InputError('geometry file is not diskutil info, Get-Disk output or a byte count')


def parse_tracer_log(text):
    """Lines "<step> <exit code>", e.g. "dtrace 0", "wpr-start 0". Every occurrence is kept."""
    steps = []
    for line in text.splitlines():
        if not line.strip():
            continue
        m = re.fullmatch(r'\s*([A-Za-z][\w-]*)\s+(-?\d+)\s*', line)
        if not m:
            raise InputError('tracer log line is not "<step> <exit code>": %r' % line[:60])
        steps.append([m.group(1), int(m.group(2))])
    return steps


REQUIRED_STEPS = {'strace': ('strace',), 'dtrace': ('dtrace',), 'etw-xml': ('wpr-start', 'wpr-stop', 'tracerpt')}


# ------------------------------------------------------------------ judgment

def target_matches(path, a):
    if path is None:
        return False
    p = path.replace('/', '\\').lower() if a.format == 'etw-xml' else path
    if a.format == 'etw-xml':
        t = a.target.replace('/', '\\').lower()
        if a.disk is not None and (re.search(r'physicaldrive%d$' % a.disk, p)
                                   or re.search(r'\\device\\harddisk%d\\dr\d+$' % a.disk, p)):
            return True
        return p == t or p.endswith('\\' + t.lstrip('.\\'))
    return path == a.target or path.endswith('/' + a.target.lstrip('./'))


def judge(a):
    v = Verdict()
    inputs = {}
    for k in ('trace', 'geometry', 'exe', 'stdout', 'tracer_log'):
        inputs[k] = {'path': getattr(a, k), 'sha256': sha256(getattr(a, k))}
    inputs['diagnostics'] = [{'path': p, 'sha256': sha256(p)} for p in a.diagnostics]

    # --- executable and geometry
    if inputs['exe']['sha256'] != a.sha256.lower():
        v.fail.append('executable %s hashes to %s, not the expected %s' % (a.exe, inputs['exe']['sha256'], a.sha256))
    geo = parse_geometry(read_text(a.geometry))
    if geo['bytes'] != a.capacity:
        v.fail.append('geometry reports %d bytes, not --capacity %d' % (geo['bytes'], a.capacity))
    if geo.get('sector') not in (SECTOR,):
        v.held.append('geometry does not show 512-byte sectors (%s)' % geo.get('sector'))
    if a.format == 'etw-xml':
        if a.disk is None:
            raise InputError('etw-xml needs --disk N as well as --target')
        if not geo.get('image') and geo.get('number') != a.disk:
            v.fail.append('geometry is for disk %s, not --disk %d' % (geo.get('number'), a.disk))
        if not geo.get('image') and not re.fullmatch(r'\\\\\.\\PhysicalDrive%d' % a.disk, a.target, re.I):
            v.fail.append('--target %s is not \\\\.\\PhysicalDrive%d' % (a.target, a.disk))
    if geo.get('node'):
        raw = geo['node'].replace('/dev/disk', '/dev/rdisk')
        if a.target not in (geo['node'], raw):
            v.fail.append('geometry is for %s, not --target %s' % (geo['node'], a.target))
    mirror = a.capacity - SECTOR
    if mirror <= U32_MAX:
        v.fail.append('capacity %d puts the last sector at %d, not above 4294967295' % (a.capacity, mirror))

    # --- tracer completeness
    steps = parse_tracer_log(read_text(a.tracer_log))
    for s in REQUIRED_STEPS[a.format]:
        codes = [c for name, c in steps if name == s]
        if not codes:
            v.held.append('tracer log has no exit code for step %r' % s)
        for i, c in enumerate(codes):
            if c != 0:
                v.fail.append('tracer step %r exited %d (occurrence %d of %d)' % (s, c, i + 1, len(codes)))
        if len(codes) > 1 and not any(codes):
            v.held.append('tracer step %r is recorded %d times; which attempt produced this trace '
                          'is ambiguous' % (s, len(codes)))
    for p in a.diagnostics:
        txt = read_text(p)
        if a.format == 'dtrace':
            for line in txt.splitlines():
                dtrace_diag_line(line, v, p)
        elif a.format == 'strace':
            for line in txt.splitlines():
                if line.strip():
                    v.fail.append('strace diagnostic: %s' % line.strip()[:100])
        else:
            v.notes.append('ETW diagnostics %s kept raw; loss is judged from the header counters' % p)

    events = PARSERS[a.format](read_text(a.trace), v)

    # --- process binding
    tgt = [e['pid'] for e in events if e['op'] == 'target']
    if tgt and tgt[0] != a.pid:
        v.fail.append('dtrace -c target is PID %s, not --pid %d' % (tgt[0], a.pid))
    mine = [e for e in events if e['pid'] == a.pid and e['op'] != 'target']
    stale = [e for e in events if e.get('stale') == a.pid]
    if stale:
        v.fail.append('%d record(s) come from a thread of PID %d outside the observed life of that '
                      'thread and process; they are not attributed' % (len(stale), a.pid))
    if not mine:
        v.fail.append('no captured record belongs to PID %d' % a.pid)
    bad = [e['exe'] for e in mine if e['op'] == 'badobj']
    if bad:
        v.held.append('PID %d has %d FileIo record(s) without a valid FileObject (opcode %s); its object '
                      'lifetimes and write targets cannot be established' % (a.pid, len(bad), ', '.join(sorted(set(bad)))))
    execs = [e for e in mine if e['op'] == 'exec']
    if a.format in ('strace', 'etw-xml'):
        if not execs:
            v.held.append('no process-start record for PID %d; the image cannot be bound' % a.pid)
        for e in execs:
            name = re.split(r'[\\/]', e['exe'] or '')[-1].lower()
            if not name.startswith('tapectl') or 'tapectl-test' in name or e['ret'] != 0:
                v.fail.append('PID %d runs %r, not the shipped tapectl' % (a.pid, e['exe']))
            if a.format == 'etw-xml' and e['path'] and a.target.lower() not in e['path'].lower():
                v.fail.append('PID %d command line %r does not name %s' % (a.pid, e['path'], a.target))
    else:
        names = {e['exe'] for e in mine if e['op'] == 'open'}
        if not names or None in names:
            v.held.append('dtrace open records carry no exe= name; the image cannot be bound')
        elif any(n != 'tapectl' for n in names):
            v.fail.append('PID %d runs %s, not tapectl' % (a.pid, sorted(names)))

    # --- target binding: opens, reads, writes
    fdmap, opens, calls = {}, [], []
    for e in mine:
        if e['op'] == 'open':
            hit = target_matches(e['path'], a)
            if e['fd'] is not None:
                fdmap[e['fd']] = hit
            if hit:
                opens.append(e)
        elif e['op'] == 'close':
            fdmap.pop(e['fd'], None)
        elif e['op'] in ('read', 'write', 'flush'):
            if a.format == 'etw-xml':
                # DiskIo by disk number; FileIo by the path its object names AT THIS READ.
                if e['fd'] == 'disk%d' % a.disk:
                    calls.append(e)
                elif e.get('fileio') and e['fd'] is None:
                    if e['off'] is not None and e['off'] < a.capacity and e['off'] + (e['len'] or 0) > mirror:
                        v.held.append('a FileIo read by PID %d of the last sector has no valid FileObject; '
                                      'it cannot be bound to the target' % a.pid)
                elif not str(e['fd']).startswith('disk') and target_matches(e['path'], a):
                    calls.append(e)
                elif (not str(e['fd']).startswith('disk') and e['off'] is not None
                      and e['off'] < a.capacity and e['off'] + (e['len'] or 0) > mirror):
                    v.fail.append("a read by PID %d of the last sector is on FileObject %s, which names '%s' "
                                  'at that point, not the target (closed, reused or foreign object)'
                                  % (a.pid, e['fd'], e['path']))
            elif fdmap.get(e['fd']):
                calls.append(e)
    if a.format != 'etw-xml':
        if not [o for o in opens if o['ret'] is not None and o['ret'] >= 0 and not o['err']]:
            v.fail.append('PID %d never opened %s successfully' % (a.pid, a.target))
        if any(o['mode'] == 'write' for o in opens):
            v.fail.append('the target was opened for writing')
        open_claim = 'read-only open shown by the traced open flags' if opens else 'no open observed'
    else:
        open_claim = ('open access mode is not observable in kernel ETW (FileIo Create has no '
                      'DesiredAccess); claim limited to observed reads and no observed writes')
    writes = [c for c in calls if c['op'] == 'write']
    if writes:
        v.fail.append('%d write(s) by PID %d reached the target' % (len(writes), a.pid))

    # --- full last-sector coverage by successful, status-bearing, >4 GiB reads
    reads = [c for c in calls if c['op'] == 'read' and c['off'] is not None
             and c['off'] < a.capacity and c['off'] + (c['len'] or 0) > mirror]
    got = []
    for c in reads:
        if c['status_src'] is None:
            continue
        if c['off'] <= U32_MAX:
            continue
        if c['err'] or c['ret'] is None or c['ret'] <= 0:
            continue
        got.append((c['off'], c['off'] + min(c['ret'], c['len'])))
    covered, pos = False, mirror
    for lo, hi in sorted(got):
        if lo > pos:
            break
        pos = max(pos, hi)
        if pos >= a.capacity:
            covered = True
            break
    if not reads:
        v.fail.append('no read by PID %d touches [%d, %d)' % (a.pid, mirror, a.capacity))
    elif not covered:
        statusless = [c for c in reads if c['status_src'] is None and c['off'] > U32_MAX]
        with_status = [c for c in reads if c['status_src'] is not None]
        if statusless and not with_status:
            v.held.append('reads of the last sector were seen (%s) but carry no native result; '
                          'completion plus verify OK is only an indirect argument for independent '
                          'review, not a captured call result' % ', '.join(
                              'off=%d len=%d%s' % (c['off'], c['len'], ' [%s]' % c['why'] if c['why'] else '')
                              for c in statusless[:3]))
        else:
            v.fail.append('successful returned bytes above 4294967295 do not cover all 512 bytes of '
                          '[%d, %d) (covered up to %d)' % (mirror, a.capacity, pos))

    # --- process result
    out_text = read_text(a.stdout).strip()
    if out_text != 'OK':
        v.fail.append('verify stdout is %r, not exactly OK' % out_text[:40])
    traced = [e['ret'] for e in mine if e['op'] == 'exit']
    if len(set(traced)) > 1:
        raise InputError('the trace records more than one exit status for PID %d: %s' % (a.pid, traced))
    if traced and traced[0] != 0:
        v.fail.append('traced exit status %d: verify failed' % traced[0])
    if a.exit_code is not None and a.exit_code != 0:
        v.fail.append('recorded exit code %d: verify failed' % a.exit_code)
    if traced and a.exit_code is not None and traced[0] != a.exit_code:
        raise InputError('recorded exit code %d contradicts traced exit status %d' % (a.exit_code, traced[0]))
    if not traced and a.exit_code is None:
        v.held.append('no exit status recorded or traced')
    if a.format in ('strace', 'etw-xml') and a.exit_code is None:
        v.held.append('--exit-code (the saved process exit) is required for %s' % a.format)

    return {
        'verdict': v.name(),
        'fail': v.fail,
        'held': v.held,
        'pid': a.pid,
        'capacity': a.capacity,
        'last_sector': [mirror, a.capacity],
        'last_sector_reads': [{k: c[k] for k in ('off', 'len', 'ret', 'err', 'status_src', 'why')} for c in reads],
        'open_claim': open_claim,
        'target_calls': {op: sum(1 for c in calls if c['op'] == op) for op in ('read', 'write', 'flush')},
        'exit': {'traced': traced[0] if traced else None, 'recorded': a.exit_code},
        'tracer_steps': steps,
        'geometry': geo,
        'inputs': inputs,
        'notes': v.notes,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--format', required=True, choices=sorted(PARSERS))
    for k in ('trace', 'geometry', 'target', 'exe', 'sha256', 'stdout', 'tracer-log'):
        p.add_argument('--' + k, required=True)
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--capacity', type=int, required=True)
    p.add_argument('--diagnostics', action='append', required=True)
    p.add_argument('--disk', type=int)
    p.add_argument('--exit-code', type=int)
    a = p.parse_args(argv)
    try:
        rep = judge(a)
    except InputError as e:
        print(json.dumps({'verdict': 'INPUT-ERROR', 'fail': [], 'held': [], 'error': str(e)}, indent=1))
        return 2
    print(json.dumps(rep, indent=1))
    return {'PASS': 0, 'FAIL': 1, 'HELD': 3}[rep['verdict']]


if __name__ == '__main__':
    sys.exit(main())
