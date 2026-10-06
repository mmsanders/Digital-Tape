#!/usr/bin/env python3
"""WP-14 native capture transport — Software's mechanical binding (Product #392).

Implements the request/response protocol of Verification's
tests/wp14_r1/NATIVE-TRANSPORT.md for tests/wp14_r1/native.py:

    transport.py --build DIR request.json response.json

It launches the real candidate binaries against real, owned virtual device
nodes and returns what was observed. It supplies no verdict and no expectation:
it never reads the verifier's expected fields to decide an outcome, and never
synthesizes an event. Every response points at raw, persistent files.

Device nodes (no physical user disks are ever touched; every node is created
here from a file this transport owns and is detached before it returns):
    linux    losetup -P over a sparse file           (needs root)
    macos    hdiutil attach -nomount, raw I/O /dev/rdiskN (needs root)
    windows  a dynamic VHD of the exact size, attached by diskpart (Administrator)

Observation:
    test binary     tapectl-test's own TAPECTL_TEST_TRACE (host/port/tseam.h),
                    renamed/joined only (normalize_test_trace)
    shipped binary  external OS-call capture (iocap_posix.c / iocap_win.c),
                    normalized from the raw log (normalize_iocap)
Raw traces, logs, facts files, setup transcripts and snapshots are kept under
the request's evidence directory.
"""
import argparse
import hashlib
import json
import os
import platform as pyplatform
import re
import shutil
import struct
import subprocess
import sys
import time
import uuid as uuidlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
GOLDEN = REPO / 'tests' / 'golden'
P1_START, P1_SECTORS, P2_START = 2048, 32768, 34816
DEFAULT_UUID = '00112233445566778899aabbccddeeff'
DEFAULT_EPOCH = 315532800
DEFAULT_LABEL = 'WP14'
BIG_ARTIFACT = 256 * 1024 * 1024        # larger files are listed by streamed hash in a manifest

PLATFORM = {'linux': 'linux', 'darwin': 'macos', 'win32': 'windows'}[sys.platform]
EXE = '.exe' if PLATFORM == 'windows' else ''


# ----------------------------------------------------------------- helpers

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


class Case:
    """One request's working directory, transcript and artifacts."""

    def __init__(self, request, evidence_dir):
        self.req = request
        self.name = re.sub(r'[^A-Za-z0-9._-]', '_', request['case'])
        self.dir = Path(evidence_dir) / ('capture-' + self.name)
        if self.dir.exists():
            shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True)
        self.work = self.dir / 'work'          # backing files: removed or hashed, never artifacts
        self.work.mkdir()
        self.transcript = []                   # every command this transport ran, in order
        self.artifacts = []

    def log(self, **entry):
        entry['t'] = round(time.time(), 3)
        self.transcript.append(entry)

    def run(self, argv, env=None, check=False, capture=True, timeout=7200, label=None):
        """Run a helper command (setup, attach, inspect), transcribed."""
        e = dict(os.environ)
        if env:
            e.update(env)
        try:
            r = subprocess.run(argv, env=e, capture_output=capture, text=True, timeout=timeout)
        except FileNotFoundError:
            # An optional helper (e.g. udevadm in a container) is absent; a
            # required one (check=True) still fails the transport.
            self.log(kind='command', label=label, argv=[str(a) for a in argv], exit=None, missing_tool=True)
            if check:
                raise
            return subprocess.CompletedProcess(argv, 127, '', 'tool not installed')
        self.log(kind='command', label=label, argv=[str(a) for a in argv], exit=r.returncode,
                 stdout=(r.stdout or '')[-20000:], stderr=(r.stderr or '')[-20000:])
        if check and r.returncode != 0:
            raise RuntimeError(f'{label or argv[0]} failed ({r.returncode}): {r.stderr or r.stdout}')
        return r

    def keep(self, path):
        self.artifacts.append(Path(path))
        return Path(path)

    def finish_artifacts(self):
        t = self.dir / 'transcript.json'
        t.write_text(json.dumps(self.transcript, indent=1) + '\n')
        self.keep(t)
        out, big = [], []
        for p in self.artifacts:
            if not p.exists():
                continue
            if p.stat().st_size > BIG_ARTIFACT:
                big.append({'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha256_file(p)})
            else:
                out.append({'path': str(p), 'sha256': sha256_file(p)})
        if big:
            m = self.dir / 'large-artifacts.json'
            m.write_text(json.dumps(big, indent=1) + '\n')
            out.append({'path': str(m), 'sha256': sha256_file(m)})
        return out


# ----------------------------------------------------------- device nodes

def vhd_dynamic(path, size):
    """A dynamic VHD (Microsoft VHD format spec v1.0) of exactly `size` bytes,
    every block unallocated. Windows refuses sparse fixed VHDs; a dynamic one
    holds an exact current size with no data allocated."""
    assert size % 512 == 0
    block = 2 * 1024 * 1024
    entries = (size + block - 1) // block
    bat_bytes = ((entries * 4 + 511) // 512) * 512

    def checksum(b):
        return (~sum(b)) & 0xffffffff

    # CHS geometry per the spec's algorithm (capped as the spec caps it).
    total = min(size // 512, 65535 * 16 * 255)
    if total >= 65535 * 16 * 63:
        spt, heads = 255, 16
        cth = total // spt
    else:
        spt = 17
        cth = total // spt
        heads = max((cth + 1023) // 1024, 4)
        if cth >= heads * 1024 or heads > 16:
            spt, heads = 31, 16
            cth = total // spt
        if cth >= heads * 1024:
            spt, heads = 63, 16
            cth = total // spt
    cyl = cth // heads
    footer = bytearray(512)
    footer[0:8] = b'conectix'
    struct.pack_into('>I', footer, 8, 2)                  # features: reserved
    struct.pack_into('>I', footer, 12, 0x00010000)        # format version
    struct.pack_into('>Q', footer, 16, 512)               # data offset: dynamic header
    struct.pack_into('>I', footer, 24, 0)                 # timestamp
    footer[28:32] = b'wp14'                               # creator application
    struct.pack_into('>I', footer, 32, 0x00010000)
    footer[36:40] = b'Wi2k'
    struct.pack_into('>Q', footer, 40, size)              # original size
    struct.pack_into('>Q', footer, 48, size)              # current size
    struct.pack_into('>HBB', footer, 56, cyl, heads, spt)
    struct.pack_into('>I', footer, 60, 3)                 # disk type: dynamic
    footer[68:84] = uuidlib.uuid4().bytes
    struct.pack_into('>I', footer, 64, checksum(footer))
    header = bytearray(1024)
    header[0:8] = b'cxsparse'
    struct.pack_into('>Q', header, 8, 0xffffffffffffffff)  # data offset: none
    struct.pack_into('>Q', header, 16, 1536)              # BAT offset
    struct.pack_into('>I', header, 24, 0x00010000)
    struct.pack_into('>I', header, 28, entries)
    struct.pack_into('>I', header, 32, block)
    struct.pack_into('>I', header, 36, checksum(header))
    with open(path, 'wb') as f:
        f.write(footer)
        f.write(header)
        f.write(b'\xff' * bat_bytes)
        f.write(footer)


class Device:
    """A virtual device node over an owned backing file."""

    def __init__(self, case, size):
        self.case, self.size = case, size
        # WP14_BACKING_DIR may place the backing file on another owned volume
        # (CI: a macOS RAM disk, so the disk image's cache flushes do not each
        # wait for the runner's own disk). The device node is unchanged.
        where = Path(os.environ['WP14_BACKING_DIR']) if os.environ.get('WP14_BACKING_DIR') else case.work
        self.backing = where / (case.name + ('-backing.vhd' if PLATFORM == 'windows' else '-backing.img'))
        self.path = None
        self.number = None
        self.mounted_p1 = None

    # -- creation
    def create_blank(self):
        if PLATFORM == 'windows':
            vhd_dynamic(self.backing, self.size)
        else:
            with open(self.backing, 'wb') as f:
                f.truncate(self.size)
        self.case.log(kind='backing', path=str(self.backing), bytes=self.size, how='blank sparse')

    def create_from_image(self, image):
        """Bind an exact byte image: the backing holds exactly those bytes
        (Windows: written through the attached device)."""
        image = Path(image)
        assert image.stat().st_size == self.size, (image, self.size)
        if PLATFORM == 'windows':
            vhd_dynamic(self.backing, self.size)
            self.attach()
            write_nonzero(image, self.path, self.size)
            self.case.log(kind='backing', path=str(self.backing), bytes=self.size,
                          how='exact image written through the device', image=str(image),
                          image_sha256=sha256_file(image))
            return
        copy_sparse(image, self.backing)
        self.case.log(kind='backing', path=str(self.backing), bytes=self.size, how='exact sparse copy',
                      image=str(image), image_sha256=sha256_file(image))

    # -- attach / detach
    def attach(self):
        c = self.case
        if PLATFORM == 'linux':
            r = c.run(['losetup', '-fP', '--show', str(self.backing)], check=True, label='attach')
            self.path = r.stdout.strip()
            c.run(['udevadm', 'settle'], label='settle')
        elif PLATFORM == 'macos':
            r = c.run(['hdiutil', 'attach', '-nomount', '-imagekey', 'diskimage-class=CRawDiskImage',
                       str(self.backing)], check=True, label='attach')
            self.path = r.stdout.split()[0]
            time.sleep(1)
            self.unmount_all()
        else:
            diskpart(c, [f'select vdisk file="{self.backing}"', 'attach vdisk'], 'attach')
            r = c.run(['powershell', '-NoProfile', '-Command',
                       f"(Get-DiskImage -ImagePath '{self.backing}' | Get-Disk).Number"], check=True, label='disk-number')
            self.number = int(r.stdout.strip())
            self.path = '\\\\.\\PhysicalDrive%d' % self.number
        c.log(kind='attached', device=self.path)
        return self.path

    def detach(self):
        c = self.case
        if self.path is None:
            return
        self.unmount_p1()
        if PLATFORM == 'linux':
            c.run(['sync'], label='sync')
            c.run(['losetup', '-d', self.path], check=True, label='detach')
            c.run(['sh', '-c', 'echo 3 > /proc/sys/vm/drop_caches'], label='drop-caches')
        elif PLATFORM == 'macos':
            c.run(['hdiutil', 'detach', self.path, '-force'], check=True, label='detach')
        else:
            diskpart(c, [f'select vdisk file="{self.backing}"', 'detach vdisk'], 'detach')
        c.log(kind='detached', device=self.path)
        self.path = None

    def os_size(self):
        """The size of the attached node as the OS reports it."""
        c = self.case
        if PLATFORM == 'linux':
            r = c.run(['blockdev', '--getsize64', self.path], check=True, label='os-size')
            return int(r.stdout.strip())
        if PLATFORM == 'macos':
            r = c.run(['diskutil', 'info', '-plist', self.path], check=True, label='os-size')
            return int(re.search(r'<key>(?:Total)?Size</key>\s*<integer>(\d+)</integer>', r.stdout).group(1))
        r = c.run(['powershell', '-NoProfile', '-Command', f'(Get-Disk -Number {self.number}).Size'], check=True, label='os-size')
        return int(r.stdout.strip())

    def reattach(self):
        old = self.path
        self.detach()
        self.attach()
        self.case.log(kind='reattached', old=old, new=self.path)

    # -- volumes
    def unmount_all(self):
        """macOS mounts recognised volumes on its own; the requests state
        their mounts, so anything the OS mounted unasked is taken down."""
        if PLATFORM == 'macos' and self.path:
            self.case.run(['diskutil', 'unmountDisk', 'force', self.path], label='unmount-all')

    def p1_node(self):
        if PLATFORM == 'linux':
            return self.path + 'p1'
        if PLATFORM == 'macos':
            return self.path + 's1'
        return None

    def mount_p1(self, readonly=False):
        """Actually mount our partition 1 through the OS; return its path.
        readonly: for reading the volume only, so the OS writes nothing back."""
        c = self.case
        if PLATFORM == 'linux':
            # The kernel learns a partition table written after attach only
            # when asked to re-read it.
            c.run(['blockdev', '--rereadpt', self.path], label='rereadpt')
            c.run(['udevadm', 'settle'], label='settle')
            where = str(c.work / 'p1-mount')
            os.makedirs(where, exist_ok=True)
            c.run(['mount', '-t', 'vfat'] + (['-o', 'ro'] if readonly else []) + [self.p1_node(), where],
                  check=True, label='mount-p1')
        elif PLATFORM == 'macos':
            c.run(['diskutil', 'mount'] + (['readOnly'] if readonly else []) + [self.p1_node()], check=True, label='mount-p1')
            r = c.run(['diskutil', 'info', '-plist', self.p1_node()], check=True, label='p1-info')
            m = re.search(r'<key>MountPoint</key>\s*<string>([^<]+)</string>', r.stdout)
            where = m.group(1)
        else:
            # Automount is off on the runner (mountvol /N), so the letter is
            # given explicitly: the first free one, after Windows re-reads the
            # partition table written since attach.
            n = self.number
            r = c.run(['powershell', '-NoProfile', '-Command',
                       f"$ErrorActionPreference='Stop'; Update-Disk -Number {n}; "
                       f"$p = Get-Partition -DiskNumber {n} -PartitionNumber 1; "
                       "if (-not [char]::IsLetter([char]$p.DriveLetter)) { "
                       "$l = [char[]](68..90) | Where-Object { -not (Test-Path ($_ + ':\\')) } | Select-Object -First 1; "
                       f"Set-Partition -DiskNumber {n} -PartitionNumber 1 -NewDriveLetter $l }}; "
                       f"(Get-Partition -DiskNumber {n} -PartitionNumber 1).DriveLetter"],
                      check=True, label='mount-p1')
            letter = r.stdout.strip()
            if not re.fullmatch(r'[A-Za-z]', letter):
                raise RuntimeError(f'mount-p1: no drive letter for partition 1 ({r.stdout!r} {r.stderr!r})')
            where = letter + ':'
        self.mounted_p1 = where
        c.log(kind='mounted-p1', where=where)
        return where

    def unmount_p1(self):
        if not self.mounted_p1:
            return
        c = self.case
        if PLATFORM == 'linux':
            c.run(['umount', self.mounted_p1], label='unmount-p1')
        elif PLATFORM == 'macos':
            c.run(['diskutil', 'unmount', 'force', self.mounted_p1], label='unmount-p1')
        else:
            letter = self.mounted_p1.rstrip(':')
            c.run(['powershell', '-NoProfile', '-Command',
                   f'Remove-PartitionAccessPath -DiskNumber {self.number} -PartitionNumber 1 -AccessPath {letter}:\\'],
                  label='unmount-p1')
        self.mounted_p1 = None

    def facts_where_p1(self):
        """The mount path as the platform probe reports it (None: not mounted yet)."""
        if self.mounted_p1 is None:
            return None
        if PLATFORM == 'windows':
            return '\\\\.\\' + self.mounted_p1
        return self.mounted_p1

    def os_volume(self):
        """Read README.TXT and the volume label through the OS's own FAT driver."""
        c = self.case
        where = self.mount_p1(readonly=True)
        readme = Path(where + ('\\' if PLATFORM == 'windows' else '/') + 'README.TXT').read_bytes()
        if PLATFORM == 'linux':
            label = c.run(['blkid', '-o', 'value', '-s', 'LABEL', self.p1_node()], check=True, label='label').stdout.strip()
        elif PLATFORM == 'macos':
            r = c.run(['diskutil', 'info', '-plist', self.p1_node()], check=True, label='label')
            label = re.search(r'<key>VolumeName</key>\s*<string>([^<]*)</string>', r.stdout).group(1)
        else:
            label = c.run(['powershell', '-NoProfile', '-Command',
                           f"(Get-Volume -DriveLetter {where[0]}).FileSystemLabel"], check=True, label='label').stdout.strip()
        self.unmount_p1()
        return {'read_via': 'native-filesystem', 'path': where, 'volume_label': label,
                'content_hex': readme.hex()}

    def snapshot(self, out):
        """The device's bytes as a sparse file of exactly its size."""
        if PLATFORM == 'windows':
            read_device_sparse(self.path, self.size, out)
            how = 'read through the attached device'
        else:
            self.case.run(['sync'], label='sync')
            copy_sparse(self.backing, out)
            how = 'sparse copy of the device backing file'
        self.case.log(kind='snapshot', path=str(out), bytes=self.size, how=how)
        return out


def diskpart(case, lines, label):
    script = case.work / f'diskpart-{label}.txt'
    script.write_text('\r\n'.join(lines) + '\r\n')
    r = case.run(['diskpart', '/s', str(script)], label='diskpart-' + label)
    if r.returncode != 0:
        raise RuntimeError(f'diskpart {label}: {r.stdout}')


def copy_sparse(src, dst):
    """Copy only nonzero 1 MiB blocks; the size is exact."""
    size = os.path.getsize(src)
    zero = bytes(1 << 20)
    with open(src, 'rb') as a, open(dst, 'wb') as b:
        if PLATFORM == 'windows':
            subprocess.run(['fsutil', 'sparse', 'setflag', str(dst)], capture_output=True)
        b.truncate(size)
        off = 0
        while off < size:
            block = a.read(1 << 20)
            if not block:
                break
            if block != zero[:len(block)]:
                b.seek(off)
                b.write(block)
            off += len(block)


def write_nonzero(image, device, size):
    """Windows: write an image's nonzero 1 MiB blocks to a raw device."""
    zero = bytes(1 << 20)
    fd = os.open(device, os.O_RDWR | getattr(os, 'O_BINARY', 0))
    try:
        with open(image, 'rb') as a:
            off = 0
            while off < size:
                block = a.read(1 << 20)
                if not block:
                    break
                if block != zero[:len(block)]:
                    os.lseek(fd, off, 0)
                    os.write(fd, block)
                off += len(block)
        if hasattr(os, 'fsync'):
            os.fsync(fd)
    finally:
        os.close(fd)


def read_device_sparse(device, size, out):
    fd = os.open(device, os.O_RDONLY | getattr(os, 'O_BINARY', 0))
    zero = bytes(1 << 20)
    try:
        with open(out, 'wb') as b:
            if PLATFORM == 'windows':
                subprocess.run(['fsutil', 'sparse', 'setflag', str(out)], capture_output=True)
            b.truncate(size)
            off = 0
            while off < size:
                os.lseek(fd, off, 0)
                block = os.read(fd, min(1 << 20, size - off))
                if not block:
                    break
                if block != zero[:len(block)]:
                    b.seek(off)
                    b.write(block)
                off += len(block)
    finally:
        os.close(fd)


# ---------------------------------------------------------- environment

def os_build():
    if PLATFORM == 'macos':
        v = subprocess.run(['sw_vers', '-productVersion'], capture_output=True, text=True).stdout.strip()
        b = subprocess.run(['sw_vers', '-buildVersion'], capture_output=True, text=True).stdout.strip()
        return f'macOS {v} build {b}, {pyplatform.machine()}'
    if PLATFORM == 'windows':
        r = subprocess.run(['powershell', '-NoProfile', '-Command',
                            "$o=Get-CimInstance Win32_OperatingSystem; $o.Caption + ' ' + $o.Version + ' build ' + $o.BuildNumber"],
                           capture_output=True, text=True)
        return r.stdout.strip()
    pretty = 'Linux'
    for line in Path('/etc/os-release').read_text().splitlines():
        if line.startswith('PRETTY_NAME='):
            pretty = line.split('=', 1)[1].strip('"')
    return f'{pretty}, kernel {pyplatform.release()}, {pyplatform.machine()}'


def facts_file(case, request, device):
    """The issued facts-file keys only (ADR-164 §5). Written for the test
    binary; never used with the shipped binary, the probe or an image."""
    f = request.get('facts') or {}
    lines = []
    if f:
        lines += [f"whole={int(bool(f.get('whole')))}", f"removable={int(bool(f.get('removable')))}",
                  f"sd_bus={int(bool(f.get('sd_bus')))}", f"bytes={int(f.get('bytes', 0))}",
                  f"holds_os={int(bool(f.get('holds_os')))}", f"layout_ok={int(bool(f.get('layout_ok')))}"]
        for m in f.get('mounted', []):
            part, _, what = m.partition(':')
            if what == 'owned':
                # Written only once the partition is really mounted; the
                # facts file is rewritten after the mount.
                if device.facts_where_p1() is not None:
                    lines.append(f'mounted={part}:{device.facts_where_p1()}')
            else:
                lines.append(f'mounted={m}')
        if f.get('foreign_mount'):
            lines.append('mounted=0:foreign volume (injected test fact)')
    p = case.dir / 'facts.txt'
    p.write_text(''.join(x + '\n' for x in lines))
    case.keep(p)
    return p


# ------------------------------------------------------------ invocation

class Binaries:
    def __init__(self, build):
        self.test = Path(build) / ('tapectl-test' + EXE)
        self.shipped = Path(build) / ('tapectl' + EXE)
        self.iocap = Path(build) / {'linux': 'iocap.so', 'macos': 'iocap.dylib', 'windows': 'iocap.dll'}[PLATFORM]
        self.iocap_launcher = Path(build) / 'iocap.exe'


def invoke_test(case, bins, args, label, facts=None, control=None, trace=True, payloads=False, device=None):
    """Run tapectl-test with its own trace. Returns (exit, stdout, stderr, trace)."""
    env = dict(os.environ)
    for k in ('TAPECTL_TEST_FACTS', 'TAPECTL_TEST_TRACE', 'TAPECTL_TEST_FAULT', 'TAPECTL_TEST_PAYLOADS'):
        env.pop(k, None)
    raw = case.dir / f'{label}.trace.json'
    if trace:
        env['TAPECTL_TEST_TRACE'] = str(raw)
    if facts is not None:
        env['TAPECTL_TEST_FACTS'] = str(facts)
    if control:
        env['TAPECTL_TEST_FAULT'] = control
    if payloads:
        env['TAPECTL_TEST_PAYLOADS'] = '1'
    argv = [str(bins.test)] + [str(a) for a in args]
    r = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=7200)
    case.log(kind='candidate', label=label, binary='test', argv=argv,
             env={k: env[k] for k in env if k.startswith('TAPECTL_TEST')}, exit=r.returncode)
    for stream, text in (('stdout', r.stdout), ('stderr', r.stderr)):
        p = case.dir / f'{label}.{stream}.txt'
        p.write_text(text)
        case.keep(p)
    tr = None
    if trace:
        case.keep(raw)
        tr = annotate_unopened(json.loads(raw.read_text()), device)
    return r.returncode, r.stdout, r.stderr, tr


def invoke_shipped(case, bins, args, label, device_bytes):
    """Run the shipped tapectl under external OS-call capture."""
    log = case.dir / f'{label}.iocap.jsonl'
    if log.exists():
        log.unlink()
    env = dict(os.environ)
    for k in list(env):
        if k.startswith('TAPECTL_TEST'):
            env.pop(k)
    env['IOCAP_LOG'] = str(log)
    if PLATFORM == 'linux':
        env['LD_PRELOAD'] = str(bins.iocap)
        argv = [str(bins.shipped)] + [str(a) for a in args]
    elif PLATFORM == 'macos':
        env['DYLD_INSERT_LIBRARIES'] = str(bins.iocap)
        argv = [str(bins.shipped)] + [str(a) for a in args]
    else:
        argv = [str(bins.iocap_launcher), str(bins.iocap), str(bins.shipped)] + [str(a) for a in args]
    r = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=7200)
    case.log(kind='candidate', label=label, binary='shipped', argv=argv, capture='iocap', exit=r.returncode)
    for stream, text in (('stdout', r.stdout), ('stderr', r.stderr)):
        p = case.dir / f'{label}.{stream}.txt'
        p.write_text(text)
        case.keep(p)
    if not log.exists():
        raise RuntimeError('external capture did not load (no iocap log)')
    case.keep(log)
    raw = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
    # The attach marker proves the shim was loaded. dyld interposition is
    # active from load, before the shim's constructor runs, so on macOS calls
    # made by system initializers may be logged ahead of the marker.
    if not any(e.get('call') == 'iocap_attach' for e in raw):
        raise RuntimeError('external capture did not attach')
    return r.returncode, r.stdout, r.stderr, normalize_iocap(raw, args, r, device_bytes)


def normalize_iocap(raw, args, result, device_bytes):
    """Rename/join the external capture into the wp14-trace-1 event shape.
    Only device-node file activity is kept (sysfs/procfs reads of the probe
    are not target I/O); nothing is added that the log does not show."""
    target = str(args[1]) if len(args) > 1 else ''
    dev_fds = {}
    events = []
    for e in raw:
        call = e['call']
        if call == 'open':
            path = e['path']
            if not (path == target or path.startswith('/dev/') or path.startswith('\\\\.\\')
                    or path.replace('/dev/r', '/dev/') == target):
                continue
            ok = (e.get('fd', 0) >= 0) if 'fd' in e else e.get('error', 0) == 0
            key = e.get('fd', e.get('handle'))
            if ok:
                dev_fds[key] = path
            events.append({'kind': 'write_open' if e['write'] else 'open', 'path': path, 'device': True, 'ok': ok,
                           'os_error': e.get('errno') or e.get('error') or None})
            continue
        key = e.get('fd', e.get('handle'))
        if key not in dev_fds:
            continue
        if call == 'pread':
            ok = e.get('ok', e.get('ret', -1) == e.get('bytes'))
            events.append({'kind': 'read', 'offset': e['offset'], 'bytes': e['bytes'], 'success': bool(ok),
                           'calls': 1, 'phase': 'other'})
        elif call == 'pwrite':
            ok = e.get('ok', e.get('ret', -1) == e.get('bytes'))
            events.append({'kind': 'write', 'offset': e['offset'], 'bytes': e['bytes'], 'issued_before_return': True,
                           'coalesced': False, 'ok': bool(ok)})
        elif call in ('fsync', 'fcntl_fullfsync', 'ioctl_synccache', 'flush'):
            ok = e.get('ok', e.get('ret', -1) == 0)
            os_call = {'fsync': 'fsync', 'fcntl_fullfsync': 'F_FULLFSYNC', 'ioctl_synccache': 'DKIOCSYNCHRONIZECACHE',
                       'flush': 'FlushFileBuffers'}[call]
            events.append({'kind': 'flush', 'os_call': os_call, 'os_success': bool(ok), 'success': bool(ok)})
    text = result.stdout + result.stderr
    refusals = re.findall(r'REFUSE_[A-Z_]+', text)
    return {'schema': 'wp14-trace-1', 'platform': PLATFORM, 'capture': 'external OS-call capture of the shipped binary '
            '(tests/wp14_adapter/iocap_*.c), normalized by transport.py', 'operation': str(args[0]), 'argv': [str(a) for a in args],
            'events': events, 'target': target, 'target_kind': 'device', 'target_bytes': device_bytes,
            # From the binary's own exit and message: a §5 refusal precedes any engine call.
            'refusal': refusals[0] if result.returncode == 3 and refusals else None,
            'engine_used': False if result.returncode == 3 else None,
            'exit': result.returncode, 'success': result.returncode == 0}


def annotate_unopened(tr, device):
    """A target refused before tapectl opened it has no size in tapectl's own
    trace. Join the transport's own observation of the node it attached: the
    path and the OS-reported size. Marked as such; nothing else is added."""
    if tr is not None and not tr.get('target') and device is not None and device.path:
        tr['target'] = device.path
        tr['target_kind'] = 'device'
        tr['target_bytes'] = device.os_size()
        tr['target_bytes_source'] = 'transport: OS-reported size of the attached device node (target not opened)'
    return tr


# ------------------------------------------------------------- the cases

def source_wav(request):
    if request.get('source'):
        return Path(request['source'])
    return GOLDEN / 'src' / 'quiet.wav'


def provision_args(device, request, uuid=DEFAULT_UUID, epoch=DEFAULT_EPOCH, label=DEFAULT_LABEL, erase=True):
    a = ['provision', device.path, '--label', label, '--uuid', uuid, '--epoch', epoch]
    if request.get('label_seconds'):
        a += ['--length-s', request['label_seconds']]
    if erase:
        a += ['--erase', device.path]
    return a


def setup_card(case, bins, device, facts, request, load=True):
    """Provision (and load quiet audio) as untraced setup, recorded in the transcript."""
    rc, out, err, _ = invoke_test(case, bins, provision_args(device, request), 'setup-provision', facts=facts, trace=False)
    if rc != 0:
        raise RuntimeError(f'setup provision failed: {err}')
    device.unmount_all()
    if load:
        rc, out, err, _ = invoke_test(case, bins, ['load', device.path, source_wav(request) if not request.get('roundtrip')
                                                   else GOLDEN / 'src' / 'quiet.wav'], 'setup-load', facts=facts, trace=False)
        if rc != 0:
            raise RuntimeError(f'setup load failed: {err}')
        device.unmount_all()


def command_args(cmd, device, case):
    if cmd == 'verify':
        return ['verify', device.path]
    if cmd == 'dump':
        return ['dump', device.path, '--side', 'A', '-o', case.keep(case.dir / 'dump.wav')]
    if cmd == 'play':
        return ['play', device.path, '--side', 'A', '--from', 0, '--frames', 128, '--rate', 1, '-o', case.keep(case.dir / 'play.wav')]
    if cmd == 'scrub':
        return ['scrub', device.path, '--side', 'A', '--from', 128, '--schedule', '-1:129', '-o', case.keep(case.dir / 'scrub.wav')]
    if cmd == 'record':
        return ['record', device.path, '--at', 0, '--mode', 'overwrite', GOLDEN / 'src' / 'voice.wav']
    if cmd in ('promote', 'reset-b', 'respool'):
        return [cmd, device.path]
    raise ValueError(cmd)


def handle(request, bins):
    case = Case(request, request['evidence_dir'])
    resp = {'case': request['case'], 'platform': PLATFORM, 'head_sha': request['head_sha'],
            'os_build': os_build(), 'request_sha256': request['request_sha256'],
            'capture_origin': 'native-candidate', 'control_applied': request.get('control')}
    req_copy = case.dir / 'request.json'
    req_copy.write_text(json.dumps(request, indent=1, sort_keys=True) + '\n')
    case.keep(req_copy)
    build_info = Path(os.environ.get('WP14_BUILD_INFO', '')) if os.environ.get('WP14_BUILD_INFO') else None
    if build_info and build_info.exists():
        case.keep(build_info)
    cmd = request['command']
    device = None
    try:
        if cmd == 'symbols':
            binary = bins.shipped if request.get('binary_kind') == 'shipped' else bins.test
            tool = shutil.which('nm') or 'nm'
            r = case.run([tool, str(binary)], label='symbols')
            p = case.dir / 'symbols.txt'
            p.write_text(r.stdout)
            case.keep(p)
            resp.update(symbols=r.stdout, symbol_tool_exit=r.returncode, symbol_tool=tool, binary_path=str(binary),
                        binary_sha256=sha256_file(binary))
            return finish(case, resp)

        binary = bins.shipped if request.get('binary_kind') == 'shipped' else bins.test
        resp.update(binary_path=str(binary), binary_sha256=sha256_file(binary))
        size = request['target_bytes']
        device = Device(case, size)
        image = request.get('backing') if (request.get('fixture') or 'mbr_corruption' in request
                                            or request.get('zero_table') or request.get('snapshot_sha256')) else None
        if image:
            device.create_from_image(image)
        else:
            device.create_blank()
        if device.path is None:
            device.attach()
        facts = None if request.get('binary_kind') == 'shipped' or cmd == 'probe' else facts_file(case, request, device)

        if request.get('binary_kind') == 'shipped':
            args = command_args(cmd, device, case) if cmd != 'provision' else provision_args(device, request)
            rc, out, err, tr = invoke_shipped(case, bins, args, 'candidate', device.os_size())
            resp.update(exit=rc, stdout=out, stderr=err, trace=tr)
            return finish(case, resp, device)

        if cmd == 'probe':
            rc, out, err, tr = invoke_test(case, bins, ['probe', device.path], 'candidate', device=device)
            facts_parsed = {'source': 'platform probe', 'mounted': []}
            for line in out.splitlines():
                k, _, v = line.partition('=')
                if k in ('whole', 'removable', 'sd_bus', 'holds_os', 'layout_ok'):
                    facts_parsed[k] = bool(int(v))
                elif k == 'bytes':
                    facts_parsed[k] = int(v)
                elif k == 'mounted':
                    facts_parsed['mounted'].append(v)
                elif k in ('refusal', 'detail'):
                    facts_parsed[k] = v
            resp.update(exit=rc, stdout=out, stderr=err, trace=tr, probe_facts=facts_parsed, facts_env_supplied=False)
            return finish(case, resp, device)

        control = request.get('control')

        if cmd == 'provision':
            if request.get('seed_nonzero_mbr'):
                seed = Path(request['backing']).read_bytes()[:512]
                write_lba0(device, seed)
                case.log(kind='seed-mbr', sha256=hashlib.sha256(seed).hexdigest())
            if any(str(m).endswith(':owned') for m in (request.get('facts') or {}).get('mounted', [])):
                # A real provisioned card whose partition 1 the OS has mounted.
                setup_card(case, bins, device, facts_file(case, dict(request, facts=dict(request['facts'], mounted=[])), device),
                           request, load=False)
                device.mount_p1()
                facts = facts_file(case, request, device)
            if request.get('required_replay'):
                base = case.keep(case.dir / 'baseline.img')
                device.snapshot(base)
                resp['baseline'] = str(base)
                args = provision_args(device, request, uuid=request['new_uuid'], epoch=request['new_epoch'],
                                      label=request['new_label'], erase=request.get('erase_matches', True))
            else:
                args = provision_args(device, request, erase=request.get('erase_matches', True))
            rc, out, err, tr = invoke_test(case, bins, args, 'candidate', facts=facts, control=control, device=device)
            device.unmount_all()
            resp.update(exit=rc, stdout=out, stderr=err, trace=tr)
            if request.get('required_replay'):
                final = case.keep(case.dir / 'final-snapshot.img')
                device.snapshot(final)
                resp['final_snapshot'] = str(final)
            if request.get('required_os_readme') and rc == 0:
                # The snapshot is the bytes provision left, taken before the OS
                # reads the volume (an OS read may update a FAT access date).
                snap = case.dir / 'snapshot.img'
                device.snapshot(snap)
                resp['snapshot'] = str(snap)
                case.log(kind='snapshot-hash', sha256=sha256_file(snap))
                resp['os_readme'] = device.os_volume()
                vrc, vout, verr, vtr = invoke_test(case, bins, ['verify', device.path], 'post-provision-verify', facts=facts, device=device)
                resp.update(verify_exit=vrc, verify_output=vout + verr, verify_trace=vtr)
            return finish(case, resp, device)

        if cmd == 'load':
            setup_card(case, bins, device, facts, request, load=False)
            src = source_wav(request)
            rc, out, err, tr = invoke_test(case, bins, ['load', device.path, src], 'candidate', facts=facts, control=control, device=device)
            device.unmount_all()
            resp.update(exit=rc, stdout=out, stderr=err, trace=tr)
            if request.get('roundtrip') and rc == 0:
                device.reattach()
                resp['reattached'] = True
                dumps, traces = {}, {}
                for side in ('A', 'B'):
                    out_wav = case.keep(case.dir / f'dump-{side}.wav')
                    drc, dout, derr, dtr = invoke_test(case, bins, ['dump', device.path, '--side', side, '-o', out_wav],
                                                       f'dump-{side}', facts=facts, device=device)
                    dumps[side] = str(out_wav)
                    traces[side] = dtr
                    resp[f'dump_{side}_exit'] = drc
                resp.update(dumps=dumps, dump_traces=traces)
            return finish(case, resp, device)

        # verify / dump / play / scrub / record / promote / reset-b / respool
        if not image:
            setup_card(case, bins, device, facts, request, load=True)
        rc, out, err, tr = invoke_test(case, bins, command_args(cmd, device, case), 'candidate', facts=facts, control=control, device=device)
        device.unmount_all()
        resp.update(exit=rc, stdout=out, stderr=err, trace=tr)
        return finish(case, resp, device)
    except Exception as e:                      # transport failure: never a candidate verdict
        case.log(kind='transport-error', error=repr(e))
        if device is not None:
            try:
                device.detach()
            except Exception as d:
                case.log(kind='transport-error', error='detach: ' + repr(d))
        case.finish_artifacts()
        raise


def write_lba0(device, data):
    if PLATFORM == 'windows':
        fd = os.open(device.path, os.O_RDWR | os.O_BINARY)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
    else:
        raw = device.path.replace('/dev/disk', '/dev/rdisk') if PLATFORM == 'macos' else device.path
        with open(raw, 'r+b', buffering=0) as f:
            f.write(data)
            os.fsync(f.fileno())
    device.unmount_all()


def finish(case, resp, device=None):
    if device is not None:
        device.detach()
        if device.backing.exists():
            device.backing.unlink()
    resp['capture_artifacts'] = case.finish_artifacts()
    return resp


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--build', required=True, type=Path, help='directory with tapectl, tapectl-test and the iocap shim')
    ap.add_argument('request', type=Path)
    ap.add_argument('response', type=Path)
    a = ap.parse_args()
    request = json.loads(a.request.read_text())
    resp = handle(request, Binaries(a.build.resolve()))
    a.response.write_text(json.dumps(resp) + '\n')


if __name__ == '__main__':
    main()
