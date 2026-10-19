#!/usr/bin/env python3
"""S3 method capability observation, Windows (Verification #208 method gap 1).

Not tapectl and not S3 code: a harmless probe on disposable fixed VHDs of the
query -> write-mode upgrade the S3 method proposes. The query handle is
CreateFileW(\\\\.\\PhysicalDriveN) with GENERIC_READ (and, separately, zero
access); the write-mode handle is ReOpenFile(query, GENERIC_READ|GENERIC_WRITE),
which reopens the query handle's object, not the path. The probe never writes
to a device: each VHD file carries its marker in sector 0 before it is
attached, and only reads identify which disk a handle reaches.

Upgrade routes tried on each held query handle: ReOpenFile; NtCreateFile with
the query handle as RootDirectory and an empty name (a relative open of the
same object); DuplicateHandle asking for GENERIC_READ|GENERIC_WRITE.

Cases:
  same     no change between query and upgrade (GENERIC_READ and zero-access query)
  swap     the VHD detached while the query handle is held and an equal-size
           VHD attached; then ReOpenFile on the held handle, and, as the
           contrast, a path open of the same \\\\.\\PhysicalDriveN

Run elevated. Writes PROBE-windows.json with every result and Win32 error.
"""
import ctypes
import json
import platform
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
HANDLE = ctypes.c_void_p
INVALID = ctypes.c_void_p(-1).value
k32.CreateFileW.restype = HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                            wintypes.DWORD, HANDLE]
k32.ReOpenFile.restype = HANDLE
k32.ReOpenFile.argtypes = [HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
k32.DeviceIoControl.argtypes = [HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
k32.ReadFile.argtypes = [HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
k32.SetFilePointerEx.argtypes = [HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD]
k32.CloseHandle.argtypes = [HANDLE]

GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
SHARE_RW = 3
OPEN_EXISTING = 3
IOCTL_STORAGE_GET_DEVICE_NUMBER = 0x2D1080
IOCTL_STORAGE_CHECK_VERIFY2 = 0x2D0800


def err():
    return ctypes.get_last_error()


def open_path(path, access):
    h = k32.CreateFileW(path, access, SHARE_RW, None, OPEN_EXISTING, 0, None)
    return (None, err()) if h in (None, INVALID) else (h, 0)


def reopen(h, access):
    r = k32.ReOpenFile(h, access, SHARE_RW, 0)
    return (None, err()) if r in (None, INVALID) else (r, 0)


nt = ctypes.WinDLL("ntdll")


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT), ("Buffer", wintypes.LPWSTR)]


class OBJECT_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Length", wintypes.ULONG), ("RootDirectory", HANDLE), ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
                ("Attributes", wintypes.ULONG), ("SecurityDescriptor", ctypes.c_void_p),
                ("SecurityQualityOfService", ctypes.c_void_p)]


class IO_STATUS_BLOCK(ctypes.Structure):
    _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_void_p)]


nt.NtCreateFile.restype = ctypes.c_long
nt.NtCreateFile.argtypes = [ctypes.POINTER(HANDLE), wintypes.ULONG, ctypes.POINTER(OBJECT_ATTRIBUTES),
                            ctypes.POINTER(IO_STATUS_BLOCK), ctypes.c_void_p, wintypes.ULONG, wintypes.ULONG,
                            wintypes.ULONG, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG]
k32.GetCurrentProcess.restype = HANDLE
k32.DuplicateHandle.argtypes = [HANDLE, HANDLE, HANDLE, ctypes.POINTER(HANDLE), wintypes.DWORD, wintypes.BOOL,
                                wintypes.DWORD]


def nt_relative(h, access):
    """NtCreateFile(RootDirectory=h, ObjectName="") with `access`: (handle, NTSTATUS hex)."""
    out = HANDLE()
    us = UNICODE_STRING(0, 2, "")
    oa = OBJECT_ATTRIBUTES(ctypes.sizeof(OBJECT_ATTRIBUTES), h, ctypes.pointer(us), 0, None, None)
    iosb = IO_STATUS_BLOCK()
    st = nt.NtCreateFile(ctypes.byref(out), access | 0x00100000, ctypes.byref(oa), ctypes.byref(iosb), None, 0,
                         SHARE_RW, 1, 0x20, None, 0)
    return (out.value if st == 0 else None), "0x%08X" % (st & 0xFFFFFFFF)


def dup(h, access):
    out = HANDLE()
    me = k32.GetCurrentProcess()
    if not k32.DuplicateHandle(me, h, me, ctypes.byref(out), access, False, 0):
        return None, err()
    return out.value, 0


def upgrades(hq):
    """Each upgrade route on the held query handle: its error, and what the new handle reaches."""
    res = {}
    for name, fn in (("ReOpenFile", lambda: reopen(hq, GENERIC_READ | GENERIC_WRITE)),
                     ("NtCreateFile_relative", lambda: nt_relative(hq, GENERIC_READ | GENERIC_WRITE)),
                     ("DuplicateHandle", lambda: dup(hq, GENERIC_READ | GENERIC_WRITE))):
        h, e = fn()
        res[name] = {"error": e, "reaches": facts(h) if h else None}
        close(h)
    return res


def devnum(h):
    buf = (wintypes.DWORD * 3)()
    got = wintypes.DWORD()
    if not k32.DeviceIoControl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, None, 0, buf, ctypes.sizeof(buf), ctypes.byref(got), None):
        return {"error": err()}
    return {"type": buf[0], "number": buf[1], "partition": buf[2]}


def media_count(h):
    c = wintypes.DWORD()
    got = wintypes.DWORD()
    if not k32.DeviceIoControl(h, IOCTL_STORAGE_CHECK_VERIFY2, None, 0, ctypes.byref(c), 4, ctypes.byref(got), None):
        return {"error": err()}
    return {"count": c.value, "bytes": got.value}


def marker(h):
    if not k32.SetFilePointerEx(h, 0, None, 0):
        return {"error": err()}
    buf = ctypes.create_string_buffer(512)
    got = wintypes.DWORD()
    if not k32.ReadFile(h, buf, 512, ctypes.byref(got), None):
        return {"error": err()}
    return buf.raw[:16].rstrip(b"\0").decode("ascii", "replace")


def facts(h):
    return {"device_number": devnum(h), "check_verify2": media_count(h), "marker": marker(h)}


def diskpart(lines, d):
    s = d / "dp.txt"
    s.write_text("\n".join(lines) + "\n")
    p = subprocess.run(["diskpart", "/s", str(s)], capture_output=True, text=True)
    return {"exit": p.returncode, "out": p.stdout[-600:]}


def vhd(d, name, tag):
    p = d / name
    r = diskpart([f'create vdisk file="{p}" maximum=16 type=fixed'], d)
    with open(p, "r+b") as f:          # the VHD file, before it is attached: its sector 0 is disk sector 0
        f.write(tag.encode().ljust(512, b"\0"))
    return p, r


def attach(p, d):
    r = diskpart([f'select vdisk file="{p}"', "attach vdisk"], d)
    time.sleep(2)
    q = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-DiskImage -ImagePath '{p}' | Get-Disk).Number"],
                       capture_output=True, text=True)
    return int(q.stdout.strip()), r


def detach(p, d):
    return diskpart([f'select vdisk file="{p}"', "detach vdisk"], d)


def close(*hs):
    for h in hs:
        if h:
            k32.CloseHandle(h)


def main():
    d = Path(sys.argv[sys.argv.index("--dir") + 1])
    d.mkdir(parents=True, exist_ok=True)
    rows = {"platform": platform.platform(), "cases": {}}
    a, ra = vhd(d, "A.vhd", "IMAGE-A")
    b, rb = vhd(d, "B.vhd", "IMAGE-B")
    rows["create"] = [ra, rb]

    n, r = attach(a, d)
    path = rf"\\.\PhysicalDrive{n}"
    for qname, qaccess in (("same-read-query", GENERIC_READ), ("same-zero-access-query", 0)):
        hq, e = open_path(path, qaccess)
        row = {"path": path, "query_access": qaccess, "query_open_error": e}
        if hq:
            row["query"] = facts(hq)
            row["upgrades"] = upgrades(hq)
            close(hq)
        rows["cases"][qname] = row

    hq, e = open_path(path, GENERIC_READ)
    row = {"path": path, "attach_a": r, "query_open_error": e, "query": facts(hq) if hq else None}
    row["detach_a_while_held"] = detach(a, d)
    nb, rb2 = attach(b, d)
    row["attach_b"] = rb2
    row["b_disk_number"] = nb
    row["held_query_after_swap"] = facts(hq) if hq else None
    row["upgrades"] = upgrades(hq) if hq else None
    hp, e3 = open_path(rf"\\.\PhysicalDrive{nb}", GENERIC_READ)
    row["path_open_error"] = e3
    row["path_open"] = facts(hp) if hp else None
    close(hp, hq)
    detach(b, d)
    rows["cases"]["swap"] = row

    (d / "PROBE-windows.json").write_text(json.dumps(rows, indent=1))
    print(json.dumps(rows["cases"], indent=1))


if __name__ == "__main__":
    main()
