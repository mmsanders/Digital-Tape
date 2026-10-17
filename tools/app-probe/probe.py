#!/usr/bin/env python3
"""APP-1 capability probes (#444): facts about what the OS lets a process do
to a whole disk, gathered on hosted runners against attached disk images or
VHDs. Never a physical card, never a write outside the fixture device.

Every command prints one JSON object per observation on stdout:
  {"probe": NAME, "ok": bool, ...native detail (errno, Win32 error)...}
`ok` is what the OS call returned, not a verdict on APP-1.

  probe.py env
  probe.py read-facts DEV            unelevated: what each §5 fact source returns
  probe.py one-open DEV              elevated: one RW open across the provision ->
                                     load -> verify write pattern, rewriting each
                                     sector with the bytes it already holds
  probe.py hold DEV SECONDS          one RO open; read LBA 0 every 0.25 s and log
                                     each result with a monotonic timestamp
  probe.py sig DEV                   a fresh open: LBA 0 disk signature and table
  probe.py touch DEV                 G1 controls: open DEV read-only and close it
"""
import json, os, platform, subprocess, sys, time

WIN = os.name == 'nt'
MAC = sys.platform == 'darwin'
P1_START, P1_SECTORS, P2_START = 2048, 32768, 34816


def out(probe, ok, **kw):
    kw = {'probe': probe, 'ok': bool(ok), **kw}
    print(json.dumps(kw, sort_keys=True), flush=True)


def run(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:  # noqa: BLE001 - the failure is the observation
        return -1, '', repr(e)


def table(lba0):
    """The four MBR entries as the OS-independent bytes say them."""
    ents = []
    for i in range(4):
        e = lba0[446 + 16 * i: 462 + 16 * i]
        ents.append({'status': e[0], 'chs_start': e[1:4].hex(), 'type': e[4], 'chs_end': e[5:8].hex(),
                     'lba': int.from_bytes(e[8:12], 'little'), 'sectors': int.from_bytes(e[12:16], 'little')})
    return {'signature': lba0[440:444].hex(), 'magic': lba0[510:512].hex(), 'entries': ents}


# ---------------------------------------------------------------- POSIX (macOS)

def px_open(path, flags):
    try:
        return os.open(path, flags), None
    except OSError as e:
        return None, {'errno': e.errno, 'err': os.strerror(e.errno)}


def px_pread(fd, n, off):
    try:
        b = os.pread(fd, n, off)
        return b, None if len(b) == n else {'short': len(b)}
    except OSError as e:
        return None, {'errno': e.errno, 'err': os.strerror(e.errno)}


def px_pwrite(fd, b, off):
    try:
        n = os.pwrite(fd, b, off)
        return None if n == len(b) else {'short': n}
    except OSError as e:
        return {'errno': e.errno, 'err': os.strerror(e.errno)}


def mac_fullfsync(fd):
    """WP-14 §6 order: F_FULLFSYNC; only ENOTTY/ENOTSUP permits DKIOCSYNCHRONIZECACHE."""
    import errno, fcntl
    try:
        fcntl.fcntl(fd, 51)  # F_FULLFSYNC
        return None
    except OSError as e:
        if e.errno not in (errno.ENOTTY, errno.ENOTSUP):
            return {'errno': e.errno, 'err': os.strerror(e.errno), 'barrier': 'F_FULLFSYNC'}
    try:
        fcntl.ioctl(fd, 0x20006416)  # DKIOCSYNCHRONIZECACHE = _IO('d', 22)
        return None
    except OSError as e:
        return {'errno': e.errno, 'err': os.strerror(e.errno), 'barrier': 'DKIOCSYNCHRONIZECACHE'}


def plist(argv):
    import plistlib
    rc, so, se = run(argv)
    if rc != 0:
        return rc, None, se.strip()[:300]
    try:
        return rc, plistlib.loads(so.encode()), None
    except Exception as e:  # noqa: BLE001
        return rc, None, repr(e)


MAC_KEYS = ('WholeDisk', 'Removable', 'RemovableMedia', 'RemovableMediaOrExternalDevice', 'Ejectable',
            'Internal', 'BusProtocol', 'VirtualOrPhysical', 'Size', 'TotalSize', 'DeviceIdentifier',
            'Content', 'MediaName', 'IORegistryEntryName', 'DiskUUID', 'MediaUUID', 'VolumeUUID',
            'MountPoint', 'ParentWholeDisk', 'PartitionMapPartition', 'SystemImage', 'OSInternalMedia',
            'DeviceTreePath', 'SMARTStatus', 'Writable', 'WritableMedia')


def mac_read_facts(dev):
    bsd = dev.rsplit('/', 1)[-1].lstrip('r')
    for p in (f'/dev/{bsd}', f'/dev/r{bsd}', '/dev/disk0', '/dev/rdisk0'):
        try:
            st = os.stat(p)
            out('node-mode', True, path=p, mode=oct(st.st_mode & 0o7777), uid=st.st_uid, gid=st.st_gid)
        except OSError as e:
            out('node-mode', False, path=p, errno=e.errno)
        fd, err = px_open(p, os.O_RDONLY)
        if fd is None:
            out('open-rdonly', False, path=p, **err)
            continue
        b, err = px_pread(fd, 512, 0)
        out('read-lba0', b is not None and err is None, path=p, **(err or {}),
            **({'table': table(b)} if b and p.endswith(bsd) else {}))
        os.close(fd)
    for target in (bsd, bsd + 's1', bsd + 's2', '/'):
        rc, pl, err = plist(['diskutil', 'info', '-plist', target])
        out('diskutil-info', pl is not None, target=target, rc=rc, err=err,
            keys={k: pl[k] for k in MAC_KEYS if pl and k in pl})
    rc, pl, err = plist(['diskutil', 'list', '-plist'])
    out('diskutil-list', pl is not None, rc=rc, err=err,
        whole=pl.get('WholeDisks') if pl else None,
        this=[d for d in (pl or {}).get('AllDisksAndPartitions', []) if d.get('DeviceIdentifier') == bsd])
    rc, pl, err = plist(['ioreg', '-r', '-c', 'IOMedia', '-a', '-l'])
    media = []

    def walk(n):
        if isinstance(n, dict):
            if n.get('BSD Name', '').startswith(bsd):
                media.append({k: n.get(k) for k in ('BSD Name', 'Whole', 'Removable', 'Ejectable', 'Size',
                                                     'Base', 'Content', 'Content Hint', 'Partition ID',
                                                     'Writable', 'Leaf')})
            for v in n.get('IORegistryEntryChildren', []):
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(pl)
    out('ioreg-iomedia', pl is not None, rc=rc, err=err, media=media)
    rc, so, se = run(['mount'])
    out('mount-list', rc == 0, rc=rc, this=[l for l in so.splitlines() if f'/dev/{bsd}' in l],
        root=[l for l in so.splitlines() if ' on / ' in l])


def mac_one_open(dev):
    bsd = dev.rsplit('/', 1)[-1].lstrip('r')
    rdev = f'/dev/r{bsd}'
    rc, so, se = run(['diskutil', 'unmountDisk', f'/dev/{bsd}'])
    out('unmount-disk', rc == 0, rc=rc, msg=(so + se).strip()[:200])
    fd, err = px_open(rdev, os.O_RDWR)
    if fd is None:
        return out('open-rdwr', False, path=rdev, **err)
    out('open-rdwr', True, path=rdev)
    lba0, err = px_pread(fd, 512, 0)
    out('read-lba0', err is None, **(err or {}))
    p1, _ = px_pread(fd, 512, P1_START * 512)
    p2, _ = px_pread(fd, 4096, P2_START * 512)
    # provision's pattern: LBA 0 zero, partition 2, partition 1, then the MBR last.
    steps = [('write-lba0-zero', bytes(512), 0), ('write-p2', p2, P2_START * 512),
             ('write-p1', p1, P1_START * 512), ('write-mbr-last', lba0, 0)]
    for name, b, off in steps:
        err = px_pwrite(fd, b, off)
        ferr = mac_fullfsync(fd)
        out(name, err is None and ferr is None, offset=off, write=err, flush=ferr)
    time.sleep(5)
    rc, so, _ = run(['mount'])
    out('mounted-while-held', True, lines=[l for l in so.splitlines() if f'/dev/{bsd}' in l])
    # load's pattern on partition 2, then verify's reads, on the same descriptor.
    err = px_pwrite(fd, p2, P2_START * 512)
    out('write-p2-after-mbr', err is None, write=err, flush=mac_fullfsync(fd))
    for name, off in (('read-p1-after', P1_START * 512), ('read-p2-after', P2_START * 512)):
        b, err = px_pread(fd, 512, off)
        out(name, err is None, **(err or {}))
    os.close(fd)
    time.sleep(5)
    rc, so, _ = run(['mount'])
    out('mounted-after-close', True, lines=[l for l in so.splitlines() if f'/dev/{bsd}' in l])


# ---------------------------------------------------------------- Windows

if WIN:
    import ctypes
    from ctypes import wintypes as W
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateFileW.restype = W.HANDLE
    k32.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD, W.DWORD, W.HANDLE]
    k32.DeviceIoControl.argtypes = [W.HANDLE, W.DWORD, W.LPVOID, W.DWORD, W.LPVOID, W.DWORD,
                                    ctypes.POINTER(W.DWORD), W.LPVOID]
    k32.ReadFile.argtypes = [W.HANDLE, W.LPVOID, W.DWORD, ctypes.POINTER(W.DWORD), W.LPVOID]
    k32.WriteFile.argtypes = [W.HANDLE, W.LPCVOID, W.DWORD, ctypes.POINTER(W.DWORD), W.LPVOID]
    k32.SetFilePointerEx.argtypes = [W.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), W.DWORD]
    k32.FlushFileBuffers.argtypes = [W.HANDLE]
    k32.CloseHandle.argtypes = [W.HANDLE]
    k32.FindFirstVolumeW.restype = W.HANDLE
    k32.FindFirstVolumeW.argtypes = [W.LPWSTR, W.DWORD]
    k32.FindNextVolumeW.argtypes = [W.HANDLE, W.LPWSTR, W.DWORD]
    k32.GetVolumePathNamesForVolumeNameW.argtypes = [W.LPCWSTR, W.LPWSTR, W.DWORD, ctypes.POINTER(W.DWORD)]
    INVALID = W.HANDLE(-1).value
    GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
    SHARE_RW = 3
    OPEN_EXISTING = 3

IOCTLS = {  # name: (code, out size) - each with the access the Windows SDK declares
    'STORAGE_GET_DEVICE_NUMBER': (0x2D1080, 12),    # any access
    'STORAGE_QUERY_PROPERTY': (0x2D1400, 1024),     # any access
    'DISK_GET_DRIVE_GEOMETRY_EX': (0x700A0, 256),   # any access
    'DISK_GET_DRIVE_LAYOUT_EX': (0x70050, 4096),    # any access
    'DISK_GET_LENGTH_INFO': (0x7405C, 8),           # FILE_READ_ACCESS
    'STORAGE_CHECK_VERIFY2': (0x2D0800, 4),         # any access; media change count
    'STORAGE_CHECK_VERIFY': (0x2D4800, 4),          # FILE_READ_ACCESS
    'STORAGE_GET_HOTPLUG_INFO': (0x2D0C14, 8),      # any access
}


def w_err():
    e = ctypes.get_last_error()
    return {'win32': e, 'err': ctypes.FormatError(e).strip()}


def w_open(path, access):
    h = k32.CreateFileW(path, access, SHARE_RW, None, OPEN_EXISTING, 0, None)
    return (None, w_err()) if h in (None, INVALID) else (h, None)


def w_ioctl(h, name, inbuf=None):
    code, size = IOCTLS[name]
    ob = ctypes.create_string_buffer(size)
    got = W.DWORD(0)
    ib = ctypes.create_string_buffer(inbuf) if inbuf else None
    ok = k32.DeviceIoControl(h, code, ib, len(inbuf) if inbuf else 0, ob, size, ctypes.byref(got), None)
    return (ob.raw[:got.value], None) if ok else (None, w_err())


def w_seek(h, off):
    return k32.SetFilePointerEx(h, off, None, 0)


def w_read(h, n, off):
    if not w_seek(h, off):
        return None, w_err()
    b = ctypes.create_string_buffer(n)
    got = W.DWORD(0)
    if not k32.ReadFile(h, b, n, ctypes.byref(got), None):
        return None, w_err()
    return b.raw[:got.value], None if got.value == n else {'short': got.value}


def w_write(h, data, off):
    if not w_seek(h, off):
        return w_err()
    got = W.DWORD(0)
    if not k32.WriteFile(h, data, len(data), ctypes.byref(got), None):
        return w_err()
    return None if got.value == len(data) else {'short': got.value}


def w_flush(h):
    return None if k32.FlushFileBuffers(h) else w_err()


def decode(name, b):
    import struct
    if name == 'STORAGE_GET_DEVICE_NUMBER':
        t, n, p = struct.unpack('<III', b[:12])
        return {'device_type': t, 'device_number': n, 'partition_number': p}
    if name == 'STORAGE_QUERY_PROPERTY':
        # STORAGE_DEVICE_DESCRIPTOR: Version, Size, DeviceType, DeviceTypeModifier, RemovableMedia,
        # CommandQueueing, VendorIdOffset, ProductIdOffset, ProductRevisionOffset, SerialNumberOffset, BusType
        v, s, dt, dtm, rem, cq, vo, po, ro, so, bus = struct.unpack('<IIBBBBIIIII', b[:32])

        def s_at(o):
            return b[o:b.index(b'\0', o)].decode('latin-1').strip() if o and o < len(b) else ''
        return {'removable_media': rem, 'bus_type': bus, 'vendor': s_at(vo), 'product': s_at(po),
                'serial': s_at(so)}
    if name == 'DISK_GET_LENGTH_INFO':
        return {'bytes': struct.unpack('<q', b[:8])[0]}
    if name == 'DISK_GET_DRIVE_GEOMETRY_EX':
        return {'media_type': struct.unpack('<I', b[8:12])[0], 'bytes_per_sector': struct.unpack('<I', b[20:24])[0],
                'disk_size': struct.unpack('<q', b[24:32])[0]}
    if name in ('STORAGE_CHECK_VERIFY2', 'STORAGE_CHECK_VERIFY'):
        return {'media_change_count': struct.unpack('<I', b[:4])[0]} if len(b) >= 4 else {}
    if name == 'STORAGE_GET_HOTPLUG_INFO':
        _, media_removable, media_hotplug, device_hotplug, _ = struct.unpack('<IBBBB', b[:8])
        return {'media_removable': media_removable, 'media_hotplug': media_hotplug, 'device_hotplug': device_hotplug}
    if name == 'DISK_GET_DRIVE_LAYOUT_EX':
        style, count = struct.unpack('<II', b[:8])
        r = {'style': style, 'count': count, 'mbr_signature': f'{struct.unpack("<I", b[8:12])[0]:08x}', 'parts': []}
        for i in range(count):
            e = b[48 + 144 * i: 48 + 144 * (i + 1)]
            if len(e) < 144:
                break
            so_, pl, pn = struct.unpack('<qqI', e[8:28])
            if pl == 0:
                continue
            ptype, boot, recog = e[32], e[33], e[34]
            r['parts'].append({'number': pn, 'offset': so_, 'length': pl, 'type': ptype, 'boot': boot,
                               'recognized': recog, 'hidden_sectors': struct.unpack('<I', e[36:40])[0]})
        return r
    return {'hex': b.hex()}


def win_volumes(disk):
    vols = []
    buf = ctypes.create_unicode_buffer(260)
    fv = k32.FindFirstVolumeW(buf, 260)
    if fv in (None, INVALID):
        out('find-volume', False, **w_err())
        return vols
    while True:
        name = buf.value
        h, err = w_open(name.rstrip('\\'), 0)
        rec = {'volume': name, 'open0': err}
        if h is not None:
            ob = ctypes.create_string_buffer(256)
            got = W.DWORD(0)
            if k32.DeviceIoControl(h, 0x560000, None, 0, ob, 256, ctypes.byref(got), None):
                import struct
                n = struct.unpack('<I', ob.raw[:4])[0]
                rec['extents'] = [dict(zip(('disk', 'offset', 'length'),
                                           struct.unpack('<Iqq', ob.raw[8 + 24 * i: 8 + 24 * i + 4] +
                                                         ob.raw[16 + 24 * i: 32 + 24 * i])))
                                  for i in range(n)]
            else:
                rec['extents_err'] = w_err()
            k32.CloseHandle(h)
        names = ctypes.create_unicode_buffer(512)
        need = W.DWORD(0)
        if k32.GetVolumePathNamesForVolumeNameW(name, names, 512, ctypes.byref(need)):
            rec['mount_points'] = [p for p in names[:need.value].split('\0') if p]
        if disk is None or any(e['disk'] == disk for e in rec.get('extents', [])):
            vols.append(rec)
        if not k32.FindNextVolumeW(fv, buf, 260):
            break
    return vols


def win_read_facts(dev):
    disk = int(dev.rsplit('PhysicalDrive', 1)[-1])
    for path in (dev, r'\\.\PhysicalDrive0'):
        for access, aname in ((0, 'none'), (GENERIC_READ, 'GENERIC_READ')):
            h, err = w_open(path, access)
            out('open', h is not None, path=path, access=aname, **(err or {}))
            if h is None:
                continue
            for name in IOCTLS:
                b, err = w_ioctl(h, name, bytes(12) if name == 'STORAGE_QUERY_PROPERTY' else None)
                out('ioctl', b is not None, path=path, access=aname, ioctl=name,
                    **(err or {}), **({'value': decode(name, b)} if b is not None else {}))
            b, err = w_read(h, 512, 0)
            out('read-lba0', b is not None and err is None, path=path, access=aname, **(err or {}),
                **({'table': table(b)} if b and path == dev else {}))
            k32.CloseHandle(h)
    out('volumes-on-disk', True, disk=disk, volumes=win_volumes(disk))
    windir = os.environ.get('SystemRoot', r'C:\Windows')
    out('system-volume', True, windir=windir, volumes=[v for v in win_volumes(None)
                                                        if any(m.upper() == windir[:3].upper()
                                                               for m in v.get('mount_points', []))])
    rc, so, se = run(['powershell', '-NoProfile', '-Command',
                      f'Get-Disk -Number {disk} | Select Number,BusType,IsSystem,IsBoot,Size,'
                      'PartitionStyle,IsOffline | ConvertTo-Json -Compress'])
    out('get-disk', rc == 0 and bool(so.strip()), rc=rc, value=so.strip()[:500], err=se.strip()[:300])
    rc, so, se = run(['powershell', '-NoProfile', '-Command',
                      'Get-CimInstance Win32_PageFileUsage | Select Name | ConvertTo-Json -Compress'])
    out('pagefiles-cim', rc == 0, rc=rc, value=so.strip()[:300], err=se.strip()[:300])


def win_one_open(dev):
    disk = int(dev.rsplit('PhysicalDrive', 1)[-1])
    # The one exception tapectl takes: lock and dismount its own partition 1, held to exit.
    locks = []
    for v in win_volumes(disk):
        h, err = w_open(v['volume'].rstrip('\\'), GENERIC_READ | GENERIC_WRITE)
        if h is None:
            out('volume-open', False, volume=v['volume'], **err)
            continue
        got = W.DWORD(0)
        lk = k32.DeviceIoControl(h, 0x90018, None, 0, None, 0, ctypes.byref(got), None)  # FSCTL_LOCK_VOLUME
        le = None if lk else w_err()
        dm = k32.DeviceIoControl(h, 0x90020, None, 0, None, 0, ctypes.byref(got), None)  # FSCTL_DISMOUNT_VOLUME
        out('lock-dismount', bool(lk and dm), volume=v['volume'], lock=le, dismount=None if dm else w_err(),
            extents=v.get('extents'))
        locks.append(h)
    h, err = w_open(dev, GENERIC_READ | GENERIC_WRITE)
    if h is None:
        return out('open-rdwr', False, path=dev, **err)
    out('open-rdwr', True, path=dev)
    lba0, err = w_read(h, 512, 0)
    out('read-lba0', err is None, **(err or {}))
    p1, _ = w_read(h, 512, P1_START * 512)
    p2, _ = w_read(h, 4096, P2_START * 512)
    steps = [('write-lba0-zero', bytes(512), 0), ('write-p2', p2, P2_START * 512),
             ('write-p1', p1, P1_START * 512), ('write-mbr-last', lba0, 0)]
    for name, b, off in steps:
        e = w_write(h, b, off)
        f = w_flush(h)
        out(name, e is None and f is None, offset=off, write=e, flush=f)
    time.sleep(5)
    out('volumes-while-held', True, volumes=win_volumes(disk))
    e = w_write(h, p2, P2_START * 512)
    out('write-p2-after-mbr', e is None, write=e, flush=w_flush(h))
    e = w_write(h, p1, P1_START * 512)
    out('write-p1-after-mbr', e is None, write=e)
    for name, off in (('read-p1-after', P1_START * 512), ('read-p2-after', P2_START * 512)):
        b, err = w_read(h, 512, off)
        out(name, err is None, **(err or {}))
    k32.CloseHandle(h)
    for lh in locks:
        k32.CloseHandle(lh)
    time.sleep(5)
    out('volumes-after-close', True, volumes=win_volumes(disk))


# ---------------------------------------------------------------- common

def hold(dev, seconds):
    t0 = time.monotonic()
    if WIN:
        h, err = w_open(dev, GENERIC_READ)
        if h is None:
            return out('hold-open', False, path=dev, **err)
        b, _ = w_ioctl(h, 'STORAGE_CHECK_VERIFY2')
        out('hold-open', True, path=dev, t=0.0, check_verify2=decode('STORAGE_CHECK_VERIFY2', b) if b else None)
    else:
        bsd = dev.rsplit('/', 1)[-1].lstrip('r')
        fd, err = px_open(f'/dev/r{bsd}', os.O_RDONLY)
        if fd is None:
            return out('hold-open', False, path=dev, **err)
        out('hold-open', True, path=f'/dev/r{bsd}', t=0.0)
    last = None
    while time.monotonic() - t0 < seconds:
        if WIN:
            b, err = w_read(h, 512, 0)
            cv, cverr = w_ioctl(h, 'STORAGE_CHECK_VERIFY2')
            state = (b is not None and err is None, json.dumps(err, sort_keys=True), b[440:444].hex() if b else None,
                     json.dumps(decode('STORAGE_CHECK_VERIFY2', cv) if cv else cverr, sort_keys=True))
        else:
            b, err = px_pread(fd, 512, 0)
            state = (b is not None and err is None, json.dumps(err, sort_keys=True), b[440:444].hex() if b else None, None)
        if state != last:
            out('hold-read', state[0], t=round(time.monotonic() - t0, 2), err=json.loads(state[1]),
                signature=state[2], check_verify2=json.loads(state[3]) if state[3] else None)
            last = state
        time.sleep(0.25)
    out('hold-end', True, t=round(time.monotonic() - t0, 2))


def sig(dev):
    if WIN:
        h, err = w_open(dev, GENERIC_READ)
        if h is None:
            return out('fresh-open', False, path=dev, **err)
        b, err = w_read(h, 512, 0)
        k32.CloseHandle(h)
    else:
        bsd = dev.rsplit('/', 1)[-1].lstrip('r')
        fd, err = px_open(f'/dev/r{bsd}', os.O_RDONLY)
        if fd is None:
            return out('fresh-open', False, path=dev, **err)
        b, err = px_pread(fd, 512, 0)
        os.close(fd)
    out('fresh-open', err is None, path=dev, **(err or {}), **({'table': table(b)} if b else {}))


def touch(dev):
    if WIN:
        h, err = w_open(dev, 0)
        out('touch', h is not None, path=dev, pid=os.getpid(), **(err or {}))
        if h is not None:
            k32.CloseHandle(h)
    else:
        fd, err = px_open(dev, os.O_RDONLY)
        out('touch', fd is not None, path=dev, pid=os.getpid(), **(err or {}))
        if fd is not None:
            os.close(fd)


def env():
    info = {'platform': platform.platform(), 'machine': platform.machine(), 'python': platform.python_version()}
    if WIN:
        info['is_admin_token'] = bool(ctypes.windll.shell32.IsUserAnAdmin())
        info['user'] = os.environ.get('USERNAME')
    else:
        info['uid'], info['euid'] = os.getuid(), os.geteuid()
    out('env', True, **info)


def main(a):
    cmd = a[0]
    if cmd == 'env':
        return env()
    if cmd == 'read-facts':
        return (win_read_facts if WIN else mac_read_facts)(a[1])
    if cmd == 'one-open':
        return (win_one_open if WIN else mac_one_open)(a[1])
    if cmd == 'hold':
        return hold(a[1], float(a[2]))
    if cmd == 'sig':
        return sig(a[1])
    if cmd == 'touch':
        return touch(a[1])
    sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
