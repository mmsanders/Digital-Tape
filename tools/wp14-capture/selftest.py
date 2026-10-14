#!/usr/bin/env python3
"""selftest.py — every a6check.py case must give its stated verdict for its stated reason.

Software #428; docs/WP14-NATIVE-CAPTURE.md §3. Not acceptance and not a CI gate.

    python3 tools/wp14-capture/selftest.py            synthetic + Verification #167 files
    TAPECTL=path/to/tapectl-linux python3 tools/wp14-capture/selftest.py
                                                      plus the real Linux image captures

Each control starts from a complete good input set and changes ONE property. A control
passes only if the verdict matches AND the expected reason text appears in the
reported fail/held/error lines, so a fault cannot "fail" for an unrelated reason.
fixtures/dtrace-good and fixtures/etw-good are synthetic shapes, not captures; no
macOS DTrace or Windows ETW output has been seen. fixtures/linux-* are real strace
captures of the released tapectl-linux on image files (mechanics only).
fixtures/verification-167/ are Verification's published #167 files, byte-identical.
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
FX = HERE / 'fixtures'
LINUX_SHA = '4d8c97a44f163bcd513c98c0903db6a01418001f169cfd6aa126823f6f7a785c'
CAP = 62537072640
CODES = {'PASS': 0, 'FAIL': 1, 'INPUT-ERROR': 2, 'HELD': 3}


def run(args):
    p = subprocess.run([sys.executable, str(HERE / 'a6check.py')] + args, capture_output=True, text=True)
    try:
        j = json.loads(p.stdout)
    except ValueError:
        j = {'verdict': 'UNPARSED', 'fail': [p.stdout + p.stderr], 'held': []}
    return p.returncode, j


class Case:
    def __init__(self, tmp):
        self.tmp = pathlib.Path(tmp)
        self.n = 0
        self.bad = 0
        self.exe = self.tmp / 'stand-in-exe.bin'
        self.exe.write_bytes(b'synthetic stand-in for the shipped binary\n')
        self.exe_sha = hashlib.sha256(self.exe.read_bytes()).hexdigest()

    def file(self, name, text):
        p = self.tmp / ('%03d-%s' % (self.n, name))
        p.write_bytes(text.encode() if isinstance(text, str) else text)
        return str(p)

    def check(self, name, want, reason, args):
        self.n += 1
        rc, j = run(args)
        lines = j.get('fail', []) + j.get('held', []) + ([j['error']] if 'error' in j else [])
        ok = j.get('verdict') == want and rc == CODES[want] and (reason is None or any(reason in s for s in lines))
        if want == 'PASS':
            ok = ok and not lines
        print('%s %-62s %s%s' % ('ok  ' if ok else 'FAIL', name, j.get('verdict'),
                                  '' if reason is None else '  [%s]' % reason))
        if not ok:
            self.bad += 1
            print('     exit %d; reasons: %s' % (rc, json.dumps(lines)[:600]))


def dtrace_set(c, trace=None, out='OK\n', diag='', exits='dtrace 0\n', geo=None, extra=(), cap=CAP):
    d = FX / 'dtrace-good'
    return ['--format', 'dtrace',
            '--trace', c.file('trace', trace if trace is not None else (d / 'verify.trace').read_text()),
            '--pid', '4242', '--capacity', str(cap), '--target', '/dev/rdisk4',
            '--geometry', c.file('geo', geo if geo is not None else (FX / 'mac-card-info.txt').read_bytes()),
            '--exe', str(c.exe), '--sha256', c.exe_sha,
            '--stdout', c.file('out', out), '--diagnostics', c.file('diag', diag),
            '--tracer-log', c.file('exits', exits)] + list(extra)


def etw_set(c, xml=None, out='OK\r\n', exits='wpr-start 0\nwpr-stop 0\ntracerpt 0\n', geo=None,
            disk='1', target='\\\\.\\PhysicalDrive1', code='0', extra=()):
    d = FX / 'etw-good'
    a = ['--format', 'etw-xml',
         '--trace', c.file('xml', xml if xml is not None else (d / 'verify.xml').read_text()),
         '--pid', '4242', '--capacity', str(CAP), '--target', target, '--disk', disk,
         '--geometry', c.file('geo', geo if geo is not None else (d / 'card-info.txt').read_bytes()),
         '--exe', str(c.exe), '--sha256', c.exe_sha,
         '--stdout', c.file('out', out), '--diagnostics', c.file('diag', ''),
         '--tracer-log', c.file('exits', exits)]
    if code is not None:
        a += ['--exit-code', code]
    return a + list(extra)


def main():
    tmp = tempfile.mkdtemp()
    c = Case(tmp)
    try:
        good_dt = (FX / 'dtrace-good' / 'verify.trace').read_text()
        M = '62537072128'

        print('== DTrace shape (synthetic)')
        c.check('good', 'PASS', None, dtrace_set(c))
        c.check('benign SIP notice in dtrace stderr', 'PASS', None, dtrace_set(
            c, diag='dtrace: system integrity protection is on, some features will not be available\n'))
        c.check('last sector read as two contiguous 256-byte reads', 'PASS', None, dtrace_set(c, trace=good_dt.replace(
            'off=%s len=512 ret=512 errno=0 ns=1203000' % M,
            'off=%s len=256 ret=256 errno=0 ns=1\nA6 pid=4242 op=read fd=3 off=62537072384 len=256 ret=256 errno=0 ns=1' % M).replace(
            'off=%s len=512 ret=512 errno=0 ns=1180000\n' % M, '')))
        no_second = good_dt.replace('A6 pid=4242 op=read fd=3 off=%s len=512 ret=512 errno=0 ns=1180000\n' % M, '')
        cover = 'do not cover all 512 bytes'
        c.check('one-byte read of the last sector', 'FAIL', cover, dtrace_set(
            c, trace=no_second.replace('off=%s len=512 ret=512' % M, 'off=%s len=1 ret=1' % M)))
        c.check('short read (ret 100 of 512)', 'FAIL', cover, dtrace_set(
            c, trace=no_second.replace('off=%s len=512 ret=512' % M, 'off=%s len=512 ret=100' % M)))
        c.check('gap between two partial reads', 'FAIL', cover, dtrace_set(c, trace=no_second.replace(
            'off=%s len=512 ret=512 errno=0 ns=1203000' % M,
            'off=%s len=256 ret=256 errno=0 ns=1\nA6 pid=4242 op=read fd=3 off=62537072385 len=255 ret=255 errno=0 ns=1' % M)))
        c.check('failed read (ret -1 errno 5)', 'FAIL', cover, dtrace_set(
            c, trace=no_second.replace('off=%s len=512 ret=512 errno=0' % M, 'off=%s len=512 ret=-1 errno=5' % M)))
        c.check('offset truncated to 32 bits', 'FAIL', 'no read by PID 4242 touches',
                dtrace_set(c, trace=good_dt.replace(M, '2397498880')))
        c.check('traced exit status 1', 'FAIL', 'traced exit status 1',
                dtrace_set(c, trace=good_dt.replace('status=0', 'status=1')))
        c.check('no traced exit status', 'HELD', 'no exit status recorded',
                dtrace_set(c, trace=good_dt.replace('A6 pid=4242 op=exit status=0\n', '')))
        c.check('saved exit code contradicts traced status', 'INPUT-ERROR', 'contradicts',
                dtrace_set(c, extra=['--exit-code', '1']))
        c.check('verify stdout NEEDS_REPAIR', 'FAIL', 'not exactly OK', dtrace_set(c, out='NEEDS_REPAIR\n'))
        c.check('verify stdout empty', 'FAIL', 'not exactly OK', dtrace_set(c, out=''))
        c.check('dtrace drops in its stderr', 'FAIL', 'dtrace reported a problem',
                dtrace_set(c, diag='dtrace: 100 drops on CPU 0\n'))
        c.check('dtrace error in its stderr', 'FAIL', 'dtrace reported a problem',
                dtrace_set(c, diag='dtrace: error on enabled probe ID 7\n'))
        c.check('unrecognised dtrace message', 'HELD', 'unrecognised dtrace message',
                dtrace_set(c, diag='dtrace: description matched 3 probes\n'))
        c.check('dtrace exit 1', 'FAIL', "tracer step 'dtrace' exited 1", dtrace_set(c, exits='dtrace 1\n'))
        c.check('dtrace exit not recorded', 'HELD', "no exit code for step 'dtrace'", dtrace_set(c, exits=''))
        c.check('no "A6 end" completeness marker', 'HELD', 'no "A6 end"',
                dtrace_set(c, trace=good_dt.replace('A6 end\n', '')))
        c.check('wrong PID', 'FAIL', 'no captured record belongs to PID',
                dtrace_set(c, trace=good_dt.replace('pid=4242', 'pid=4243')))
        c.check('records are not from the dtrace -c target', 'FAIL', 'dtrace -c target is PID 4243',
                dtrace_set(c, trace=good_dt.replace('target=4242', 'target=4243')))
        c.check('plain write(2) to the target fd', 'FAIL', 'write(s) by PID 4242',
                dtrace_set(c, trace=good_dt.replace('A6 pid=4242 op=close fd=3\nA6 pid=4242 op=exit',
                           'A6 pid=4242 op=write fd=3 off=-1 len=-1 ret=512 errno=0 ns=0\nA6 pid=4242 op=close fd=3\nA6 pid=4242 op=exit')))
        c.check('stdout write(2) is not a target write', 'PASS', None,
                dtrace_set(c, trace=good_dt.replace('A6 pid=4242 op=exit',
                           'A6 pid=4242 op=write fd=1 off=-1 len=-1 ret=3 errno=0 ns=0\nA6 pid=4242 op=exit')))
        c.check('process is not tapectl', 'FAIL', 'not tapectl',
                dtrace_set(c, trace=good_dt.replace('exe=tapectl ', 'exe=sh ')))
        c.check('target opened for writing', 'FAIL', 'opened for writing',
                dtrace_set(c, trace=good_dt.replace('flags=0x1000000', 'flags=0x1000002', 1)))
        c.check('a write reaches the target', 'FAIL', 'write(s) by PID 4242',
                dtrace_set(c, trace=good_dt.replace('A6 pid=4242 op=close fd=3\nA6 pid=4242 op=exit',
                           'A6 pid=4242 op=write fd=3 off=0 len=512 ret=512 errno=0 ns=1\nA6 pid=4242 op=close fd=3\nA6 pid=4242 op=exit')))
        c.check('reads are on another file', 'FAIL', 'never opened /dev/rdisk4',
                dtrace_set(c, trace=good_dt.replace('/dev/rdisk4', '/tmp/helper.img')))
        c.check('executable hash mismatch', 'FAIL', 'hashes to',
                [x if x != c.exe_sha else LINUX_SHA for x in dtrace_set(c)])
        c.check('geometry size differs from --capacity', 'FAIL', 'geometry reports',
                dtrace_set(c, geo=(FX / 'mac-card-info.txt').read_text().replace('62537072640', '62537073152')))
        c.check('geometry is another disk', 'FAIL', 'geometry is for /dev/disk5',
                dtrace_set(c, geo=(FX / 'mac-card-info.txt').read_text().replace('/dev/disk4', '/dev/disk5')))
        c.check('capacity of exactly 4 GiB (last sector below 2^32)', 'FAIL', 'not above 4294967295', dtrace_set(
            c, trace=good_dt.replace(M, '4294966784'), geo='4294967296\n', cap=4294967296))

        print('== Verification #167 published files, byte-identical')
        v = FX / 'verification-167'
        old = ['--pid', '4242', '--capacity', str(CAP), '--target', '/dev/rdisk4',
               '--geometry', str(FX / 'mac-card-info.txt'), '--exe', str(c.exe), '--sha256', c.exe_sha,
               '--stdout', c.file('out', 'OK\n'), '--diagnostics', c.file('diag', ''),
               '--tracer-log', c.file('exits', 'dtrace 0\n')]
        c.check('good-dtrace.trace (pre-#428 shape: no exe=, no end)', 'HELD', 'no "A6 end"',
                ['--format', 'dtrace', '--trace', str(v / 'good-dtrace.trace')] + old)
        c.check('one-byte-mirror.trace', 'FAIL', cover,
                ['--format', 'dtrace', '--trace', str(v / 'one-byte-mirror.trace')] + old)
        c.check('nonzero-exit.trace', 'FAIL', 'traced exit status 1',
                ['--format', 'dtrace', '--trace', str(v / 'nonzero-exit.trace')] + old)
        c.check('tracer-error-ignored.trace', 'FAIL', 'dtrace reported a problem (trace file): dtrace: 100 drops',
                ['--format', 'dtrace', '--trace', str(v / 'tracer-error-ignored.trace')] + old)
        vw = ['--pid', '4242', '--capacity', str(CAP), '--target', '\\\\.\\PhysicalDrive1', '--disk', '1',
              '--geometry', str(FX / 'etw-good' / 'card-info.txt'), '--exe', str(c.exe), '--sha256', c.exe_sha,
              '--stdout', c.file('out', 'OK\r\n'), '--diagnostics', c.file('diag', ''),
              '--tracer-log', c.file('exits', 'wpr-start 0\nwpr-stop 0\ntracerpt 0\n'), '--exit-code', '0']
        c.check('good-etw.xml (no loss counters, DiskIo only)', 'HELD', 'has no EventsLost',
                ['--format', 'etw-xml', '--trace', str(v / 'good-etw.xml')] + vw)
        c.check('etw-lost-events.xml', 'FAIL', 'EventsLost = 17',
                ['--format', 'etw-xml', '--trace', str(v / 'etw-lost-events.xml')] + vw)

        print('== ETW shape (synthetic; real tracerpt XML never seen)')
        gx = (FX / 'etw-good' / 'verify.xml').read_text()
        c.check('good: FileIo read with OpEnd status, zero loss', 'PASS', None, etw_set(c))
        c.check('EventsLost 17', 'FAIL', 'EventsLost = 17',
                etw_set(c, xml=gx.replace('"EventsLost">0', '"EventsLost">17')))
        c.check('BuffersLost 1', 'FAIL', 'BuffersLost = 1',
                etw_set(c, xml=gx.replace('"BuffersLost">0', '"BuffersLost">1')))
        c.check('header without loss counters', 'HELD', 'has no EventsLost', etw_set(
            c, xml=gx.replace('<Data Name="EventsLost">0</Data><Data Name="BuffersLost">0</Data>', '')))
        hdr = gx.split('\n')[2]
        c.check('no EventTrace header', 'HELD', 'no EventTrace header', etw_set(c, xml=gx.replace(hdr + '\n', '')))
        no_fileio = '\n'.join(l for l in gx.split('\n') if '90cbdc39' not in l)
        c.check('DiskIo only: no native result', 'HELD', 'carry no native result', etw_set(c, xml=no_fileio))
        c.check('OpEnd NtStatus failure', 'FAIL', cover,
                etw_set(c, xml=gx.replace('"NtStatus">0x0', '"NtStatus">0xC0000185')))
        c.check('OpEnd returned 1 byte', 'FAIL', cover,
                etw_set(c, xml=gx.replace('"ExtraInfo">512', '"ExtraInfo">1')))
        c.check('FileIo status record is for another file', 'FAIL', 'not the target (closed, reused or foreign object)',
                etw_set(c, xml=gx.replace('\\Device\\Harddisk1\\DR1', '\\Device\\HarddiskVolume3\\helper.img')))
        lines = gx.split('\n')
        tend = [l for l in lines if '3d6fa8d1' in l and '<Opcode>2<' in l][0]
        rest = [l for l in lines if l != tend]
        moved = '\n'.join(rest[:5] + [tend.replace('18:00:01.0100000', '18:00:01.0000500')] + rest[5:])
        c.check('issuing thread ended before the reads', 'FAIL', 'no read by PID 4242 touches', etw_set(c, xml=moved))
        c.check('thread belongs to another process', 'FAIL', 'no read by PID 4242 touches', etw_set(
            c, xml=gx.replace('<Data Name="ProcessId">0x1092</Data><Data Name="TThreadId">',
                              '<Data Name="ProcessId">0x1093</Data><Data Name="TThreadId">')))
        c.check('process image is powershell.exe', 'FAIL', 'not the shipped tapectl',
                etw_set(c, xml=gx.replace('>tapectl.exe<', '>powershell.exe<')))
        c.check('process image is tapectl-test.exe', 'FAIL', 'not the shipped tapectl',
                etw_set(c, xml=gx.replace('>tapectl.exe<', '>tapectl-test.exe<')))
        c.check('no process-start record (its thread cannot be attributed)', 'FAIL', 'outside the observed life',
                etw_set(c, xml='\n'.join(l for l in lines if '3d6fa8d0' not in l)))
        c.check('command line names another drive', 'FAIL', 'does not name',
                etw_set(c, xml=gx.replace('verify \\\\.\\PhysicalDrive1', 'verify \\\\.\\PhysicalDrive2')))
        c.check('--disk disagrees with geometry Number', 'FAIL', 'geometry is for disk 1',
                etw_set(c, disk='2', target='\\\\.\\PhysicalDrive2'))
        c.check('--target is not PhysicalDrive<disk>', 'FAIL', 'is not',
                etw_set(c, target='\\\\.\\PhysicalDrive2'))
        c.check('a disk write by tapectl', 'FAIL', 'write(s) by PID 4242', etw_set(c, xml=gx.replace(
            '<Opcode>10</Opcode><TimeCreated SystemTime="2026-10-14T18:00:01.0003000Z"/>',
            '<Opcode>11</Opcode><TimeCreated SystemTime="2026-10-14T18:00:01.0003000Z"/>')))
        c.check('timestamps out of order', 'HELD', 'not in time order',
                etw_set(c, xml=gx.replace('18:00:01.0004000Z', '18:00:00.5000000Z')))
        c.check('wpr-stop exit 1', 'FAIL', "tracer step 'wpr-stop' exited 1",
                etw_set(c, exits='wpr-start 0\nwpr-stop 1\ntracerpt 0\n'))
        c.check('tracerpt exit missing', 'HELD', "no exit code for step 'tracerpt'",
                etw_set(c, exits='wpr-start 0\nwpr-stop 0\n'))
        c.check('saved process exit missing', 'HELD', '--exit-code (the saved process exit) is required',
                etw_set(c, code=None))
        c.check('saved process exit 1', 'FAIL', 'recorded exit code 1', etw_set(c, code='1'))
        c.check('geometry not 512-byte sectors', 'HELD', '512-byte sectors', etw_set(
            c, geo=(FX / 'etw-good' / 'card-info.txt').read_text().replace('LogicalSectorSize  : 512', 'LogicalSectorSize  : 4096')))

        print('== Verification #171 published files, byte-identical, with their own side files')
        v1 = FX / 'verification-171'
        base171 = ['--pid', '4242', '--capacity', str(CAP), '--exe', str(v1 / 'stand-in.bin'),
                   '--sha256', '525f1d08f6b6f356ce6a48a2a74a828aa3dc1d41fbea6771df9400de191f8732',
                   '--stdout', str(v1 / 'out.txt'), '--diagnostics', str(v1 / 'diag.txt'), '--format', 'etw-xml',
                   '--geometry', str(v1 / 'win-geometry.txt'), '--target', '\\\\.\\PhysicalDrive1', '--disk', '1',
                   '--exit-code', '0']
        c.check('good-etw.xml (their positive baseline)', 'PASS', None,
                base171 + ['--trace', str(v1 / 'good-etw.xml'), '--tracer-log', str(v1 / 'etw-exits.txt')])
        c.check('process-ended.xml', 'FAIL', 'outside the observed life',
                base171 + ['--trace', str(v1 / 'process-ended.xml'), '--tracer-log', str(v1 / 'etw-exits.txt')])
        c.check('foreign-fileobject-reuse.xml', 'FAIL', "which names 'C:\\helper.img' at that point",
                base171 + ['--trace', str(v1 / 'foreign-fileobject-reuse.xml'), '--tracer-log', str(v1 / 'etw-exits.txt')])
        c.check('duplicate-exit-log.txt (wpr-start 1 then 0)', 'FAIL', "'wpr-start' exited 1 (occurrence 1 of 2)",
                base171 + ['--trace', str(v1 / 'good-etw.xml'), '--tracer-log', str(v1 / 'duplicate-exit-log.txt')])

        print('== ETW lifetime and object binding (synthetic)')
        ev_ = lambda guid, opc, t, data: (
            '<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System><Provider Guid="{%s}"/>'
            '<Opcode>%d</Opcode><TimeCreated SystemTime="2026-10-14T18:00:01.%sZ"/></System><EventData>%s</EventData></Event>'
            % (guid, opc, t, ''.join('<Data Name="%s">%s</Data>' % kv for kv in data)))
        FIO, PRC, THR = '90cbdc39-4a3e-11d1-84f4-0000f80464e3', '3d6fa8d0-fe05-11d0-9dda-00c04fd7ba7c', '3d6fa8d1-fe05-11d0-9dda-00c04fd7ba7c'
        read_line = [l for l in gx.split('\n') if '<Opcode>67<' in l][0]

        def before_read(*evs):
            return gx.replace(read_line, '\n'.join(evs) + '\n' + read_line)
        close66 = ev_(FIO, 66, '0001500', [('TTID', '0x1388'), ('FileObject', '0xF1')])
        clean65 = ev_(FIO, 65, '0001500', [('TTID', '0x1388'), ('FileObject', '0xF1')])
        reopen = ev_(FIO, 64, '0001600', [('IrpPtr', '0xA3'), ('TTID', '0x1388'), ('FileObject', '0xF2'),
                                           ('OpenPath', '\\Device\\Harddisk1\\DR1')])
        c.check('target reopened on a new FileObject before the read', 'PASS', None,
                etw_set(c, xml=before_read(close66, reopen).replace(
                    '<Data Name="FileObject">0xF1</Data><Data Name="TTID">0x1388</Data><Data Name="IoSize">',
                    '<Data Name="FileObject">0xF2</Data><Data Name="TTID">0x1388</Data><Data Name="IoSize">')))
        c.check('FileObject closed, then read through it', 'FAIL', 'closed, reused or foreign object',
                etw_set(c, xml=before_read(close66)))
        c.check('FileObject cleaned up, then read through it', 'FAIL', 'closed, reused or foreign object',
                etw_set(c, xml=before_read(clean65)))
        c.check('process ended (no thread end) before the read', 'FAIL', 'outside the observed life',
                etw_set(c, xml=before_read(ev_(PRC, 2, '0001500', [('ProcessId', '0x1092')]))))
        c.check('a step recorded twice, both 0', 'HELD', 'ambiguous',
                etw_set(c, exits='wpr-start 0\nwpr-start 0\nwpr-stop 0\ntracerpt 0\n'))
        c.check('a step failed after an earlier success', 'FAIL', "'tracerpt' exited 2 (occurrence 2 of 2)",
                etw_set(c, exits='wpr-start 0\nwpr-stop 0\ntracerpt 0\ntracerpt 2\n'))

        print('== Verification #172 published files, byte-identical, with their own side files')
        v2 = FX / 'verification-172'

        def base172(n):
            return ['--format', 'etw-xml', '--trace', str(v2 / ('%s-xml' % n)), '--pid', '4242',
                    '--capacity', str(CAP), '--target', '\\\\.\\PhysicalDrive1', '--disk', '1',
                    '--geometry', str(v2 / ('%s-geo' % n)), '--exe', str(v2 / 'stand-in-exe.bin'),
                    '--sha256', '525f1d08f6b6f356ce6a48a2a74a828aa3dc1d41fbea6771df9400de191f8732',
                    '--stdout', str(v2 / ('%s-out' % n)), '--diagnostics', str(v2 / ('%s-diag' % n)),
                    '--tracer-log', str(v2 / ('%s-exits' % n)), '--exit-code', '0']
        c.check('001-xml (their positive baseline)', 'PASS', None, base172('001'))
        c.check('002-xml (IrpPtr removed from Read and OpEnd)', 'HELD', 'no valid IrpPtr on the request', base172('002'))

        print('== ETW request/completion correlation (synthetic)')
        nores = 'carry no native result'
        rd_irp = '<Data Name="IrpPtr">0xB2</Data><Data Name="FileObject">0xF1</Data>'
        end_irp = '<Data Name="IrpPtr">0xB2</Data><Data Name="ExtraInfo">512</Data>'
        assert rd_irp in gx and end_irp in gx
        c.check('IrpPtr missing on the read only', 'HELD', 'no valid IrpPtr on the request',
                etw_set(c, xml=gx.replace(rd_irp, '<Data Name="FileObject">0xF1</Data>')))
        c.check('IrpPtr missing on the OpEnd only (orphan completion)', 'HELD', nores,
                etw_set(c, xml=gx.replace(end_irp, '<Data Name="ExtraInfo">512</Data>')))
        c.check('IrpPtr empty on both', 'HELD', 'no valid IrpPtr on the request',
                etw_set(c, xml=gx.replace('<Data Name="IrpPtr">0xB2</Data>', '<Data Name="IrpPtr"></Data>')))
        c.check('IrpPtr zero on both', 'HELD', 'no valid IrpPtr on the request',
                etw_set(c, xml=gx.replace('<Data Name="IrpPtr">0xB2</Data>', '<Data Name="IrpPtr">0x0</Data>')))
        c.check('IrpPtr not a number on both', 'HELD', 'no valid IrpPtr on the request',
                etw_set(c, xml=gx.replace('<Data Name="IrpPtr">0xB2</Data>', '<Data Name="IrpPtr">junk</Data>')))
        c.check('OpEnd matches but lacks ExtraInfo', 'HELD', 'lacks a valid NtStatus or ExtraInfo',
                etw_set(c, xml=gx.replace('<Data Name="ExtraInfo">512</Data>', '')))
        c.check('OpEnd matches but lacks NtStatus', 'HELD', 'lacks a valid NtStatus or ExtraInfo',
                etw_set(c, xml=gx.replace('<Data Name="NtStatus">0x0</Data>', '')))
        competing = ev_(FIO, 66, '0002500', [('IrpPtr', '0xB2'), ('TTID', '0x1388'), ('FileObject', '0xF9')])
        c.check('competing Close on the same IrpPtr while the read is pending', 'HELD', 'overlapping requests in one unresolved lifecycle',
                etw_set(c, xml=gx.replace(read_line, read_line + '\n' + competing)))
        second = read_line.replace('18:00:01.0002000Z', '18:00:01.0002500Z')
        c.check('second read on the same IrpPtr while the first is pending', 'HELD', 'overlapping requests in one unresolved lifecycle',
                etw_set(c, xml=gx.replace(read_line, read_line + '\n' + second)))
        early = ev_(FIO, 64, '0001800', [('IrpPtr', '0xB2'), ('TTID', '0x1388'), ('FileObject', '0xF8'),
                                          ('OpenPath', '\\Device\\HarddiskVolume3\\other.txt')])
        early_end = ev_(FIO, 76, '0001900', [('IrpPtr', '0xB2'), ('ExtraInfo', '0'), ('NtStatus', '0x0')])
        c.check('IrpPtr reused only after its earlier request completed', 'PASS', None,
                etw_set(c, xml=before_read(early, early_end)))

        print('== Verification #173 published files, byte-identical, with their own side files')
        v3 = FX / 'verification-173'

        def base173(n):
            return ['--format', 'etw-xml', '--trace', str(v3 / ('%s-xml' % n)), '--pid', '4242',
                    '--capacity', str(CAP), '--target', '\\\\.\\PhysicalDrive1', '--disk', '1',
                    '--geometry', str(v3 / ('%s-geo' % n)), '--exe', str(v3 / 'stand-in-exe.bin'),
                    '--sha256', '525f1d08f6b6f356ce6a48a2a74a828aa3dc1d41fbea6771df9400de191f8732',
                    '--stdout', str(v3 / ('%s-out' % n)), '--diagnostics', str(v3 / ('%s-diag' % n)),
                    '--tracer-log', str(v3 / ('%s-exits' % n)), '--exit-code', '0']
        c.check('001-xml (their positive baseline)', 'PASS', None, base173('001'))
        c.check('002-xml (reuse after one of two completions)', 'HELD',
                'overlapping requests in one unresolved lifecycle', base173('002'))
        c.check('003-xml (missing IrpPtr, as #172)', 'HELD', 'no valid IrpPtr on the request', base173('003'))

        print('== ETW IRP lifecycle across multiple requests and completions (synthetic)')
        done = lambda t: ev_(FIO, 76, t, [('IrpPtr', '0xB2'), ('ExtraInfo', '512'), ('NtStatus', '0x0')])
        rd0 = lambda t: read_line.replace('<Data Name="Offset">62537072128</Data>', '<Data Name="Offset">0</Data>').replace(
            '18:00:01.0002000Z', '18:00:01.%sZ' % t)
        end_line = [l for l in gx.split('\n') if '<Opcode>76<' in l][0]

        def lifecycle(*evs):
            return gx.replace(read_line, '\n'.join(evs) + '\n' + read_line)
        c.check('two reads overlap, both complete, then the mirror read reuses the IrpPtr', 'PASS', None,
                etw_set(c, xml=lifecycle(rd0('0001100'), rd0('0001200'), done('0001300'), done('0001400'))))
        c.check('two reads overlap, one completes, mirror read reuses, two more completions', 'HELD',
                'overlapping requests in one unresolved lifecycle',
                etw_set(c, xml=lifecycle(rd0('0001100'), rd0('0001200'), done('0001300')).replace(
                    end_line, done('0003500') + '\n' + end_line)))
        cr = ev_(FIO, 64, '0001100', [('IrpPtr', '0xB2'), ('TTID', '0x1388'), ('FileObject', '0xF7'),
                                       ('OpenPath', '\\Device\\HarddiskVolume3\\other.txt')])
        cl = ev_(FIO, 65, '0001200', [('IrpPtr', '0xB2'), ('TTID', '0x1388'), ('FileObject', '0xF7')])
        c.check('Create and Cleanup overlap, one completes, mirror read reuses', 'HELD',
                'overlapping requests in one unresolved lifecycle',
                etw_set(c, xml=lifecycle(cr, cl, done('0001300'))))
        c.check('Create and Cleanup overlap, both complete, then mirror read reuses', 'PASS', None,
                etw_set(c, xml=lifecycle(cr, cl, done('0001300'), done('0001400'))))
        c.check('extra orphan completion before the mirror read is harmless', 'PASS', None,
                etw_set(c, xml=lifecycle(done('0001300'))))

        print('== Linux strace captures of the released tapectl-linux (image mechanics only)')
        exe = os.environ.get('TAPECTL')
        if not exe:
            print('SKIP real-capture cases: set TAPECTL to the released tapectl-linux (sha256 %s)' % LINUX_SHA)
        else:
            d = FX / 'linux-4g1m'
            pid = (d / 'verify-pid.txt').read_text().strip()
            base = ['--format', 'strace', '--pid', pid, '--capacity', '4296015872', '--target', 'rehearsal.img',
                    '--geometry', str(d / 'geometry.txt'), '--exe', exe, '--sha256', LINUX_SHA,
                    '--stdout', str(d / 'verify-out.txt'), '--diagnostics', str(d / 'strace-diagnostics.txt'),
                    '--tracer-log', str(d / 'tracer-exits.txt'), '--exit-code', (d / 'verify-exit.txt').read_text().strip()]
            st = (d / 'verify.strace').read_text()
            c.check('4 GiB + 1 MiB image: real capture', 'PASS', None, ['--trace', str(d / 'verify.strace')] + base)
            c.check('real capture, wrong PID', 'FAIL', 'no captured record belongs',
                    ['--trace', str(d / 'verify.strace')] + [x if x != pid else str(int(pid) + 1) for x in base])
            c.check('real capture, last-sector read truncated to 100 bytes', 'FAIL', cover,
                    ['--trace', c.file('st', st.replace('4296015360) = 512', '4296015360) = 100'))] + base)
            c.check('real capture, process killed instead of exiting', 'FAIL', 'process was killed',
                    ['--trace', c.file('st', st.replace('+++ exited with 0 +++', '+++ killed by SIGKILL +++'))] + base)
            c.check('real capture, strace diagnostic present', 'FAIL', 'strace diagnostic',
                    ['--trace', str(d / 'verify.strace')] + base[:-6] + [
                        '--diagnostics', c.file('dg', 'strace: Process 412 detached\n')] + base[-4:])
            old = FX / 'linux-shipped-verify.strace'
            ob = ['--format', 'strace', '--pid', '885', '--capacity', str(CAP), '--target', 'card.img',
                  '--geometry', c.file('g', '%d\n' % CAP), '--exe', exe, '--sha256', LINUX_SHA,
                  '--stdout', c.file('o', 'OK\n'), '--diagnostics', c.file('d', ''),
                  '--tracer-log', c.file('e', 'strace 0\n'), '--exit-code', '0']
            c.check('#425 62.5 GB capture (no execve traced)', 'HELD', 'no process-start record',
                    ['--trace', str(old)] + ob)
    finally:
        shutil.rmtree(tmp)
    print('selftest: %d cases, %d unexpected' % (c.n, c.bad))
    return 1 if c.bad else 0


if __name__ == '__main__':
    sys.exit(main())
