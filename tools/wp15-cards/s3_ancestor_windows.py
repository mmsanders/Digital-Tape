#!/usr/bin/env python3
"""S3 method capability observation, Windows elevated report (#208 method gap 3).

Not tapectl and not S3 code: a harmless probe, in a scratch directory, of the
object-bound report route the S3 method proposes for an elevated `make`.

Bound route: the volume root is opened, then every ancestor component is
opened with NtCreateFile RELATIVE TO THE HELD PARENT HANDLE (RootDirectory),
FILE_OPEN_REPARSE_POINT, FILE_DIRECTORY_FILE, share read|write without
FILE_SHARE_DELETE; each handle's attributes are read from the handle and a
reparse point refuses before descending. Every ancestor handle stays held
until the leaf exists. The leaf is NtCreateFile(FILE_CREATE,
FILE_NON_DIRECTORY_FILE|FILE_OPEN_REPARSE_POINT) relative to the held parent.
No full-path resolution happens after the first open.

Cases:
  bound            the leaf is created where the held handles are
  rename-held      while the ancestors are held, another process renames an
                   ancestor and puts a junction in its place; then the leaf
  junction         an ancestor that is a junction: refused, nothing created
  naive            CONTRAST, the route the method must not use: a full-path
                   check of the ancestor, the same substitution, then a
                   full-path CREATE_NEW; GetFinalPathNameByHandle shows where
                   the leaf actually went (after it was created there)

Writes PROBE-ancestor.json.
"""
import ctypes
import json
import os
import platform
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

nt = ctypes.WinDLL("ntdll")
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
HANDLE = ctypes.c_void_p


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT), ("Buffer", wintypes.LPWSTR)]


class OBJECT_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Length", wintypes.ULONG), ("RootDirectory", HANDLE), ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
                ("Attributes", wintypes.ULONG), ("SecurityDescriptor", ctypes.c_void_p),
                ("SecurityQualityOfService", ctypes.c_void_p)]


class IO_STATUS_BLOCK(ctypes.Structure):
    _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_void_p)]


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [("dwFileAttributes", wintypes.DWORD), ("c", wintypes.FILETIME), ("a", wintypes.FILETIME),
                ("w", wintypes.FILETIME), ("vol", wintypes.DWORD), ("sh", wintypes.DWORD), ("sl", wintypes.DWORD),
                ("links", wintypes.DWORD), ("ih", wintypes.DWORD), ("il", wintypes.DWORD)]


nt.NtCreateFile.restype = ctypes.c_long
nt.NtCreateFile.argtypes = [ctypes.POINTER(HANDLE), wintypes.ULONG, ctypes.POINTER(OBJECT_ATTRIBUTES),
                            ctypes.POINTER(IO_STATUS_BLOCK), ctypes.c_void_p, wintypes.ULONG, wintypes.ULONG,
                            wintypes.ULONG, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG]
k32.GetFileInformationByHandle.argtypes = [HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
k32.GetFinalPathNameByHandleW.argtypes = [HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
k32.CreateFileW.restype = HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                            wintypes.DWORD, HANDLE]
k32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
k32.CloseHandle.argtypes = [HANDLE]

DIR_ACCESS = 0x0001 | 0x0020 | 0x0080 | 0x00100000      # list, traverse, read attributes, synchronize
LEAF_ACCESS = 0x00120116 | 0x0080                       # FILE_GENERIC_WRITE | read attributes
SHARE_RW = 0x1 | 0x2                                    # no FILE_SHARE_DELETE
FILE_OPEN, FILE_CREATE = 1, 2
DIR_OPTS = 0x1 | 0x20 | 0x200000                        # directory, synchronous, open reparse point
LEAF_OPTS = 0x40 | 0x20 | 0x200000                      # non-directory, synchronous, open reparse point
REPARSE = 0x400
INVALID = ctypes.c_void_p(-1).value


def ntopen(root, name, access, disp, opts):
    h = HANDLE()
    us = UNICODE_STRING(len(name) * 2, len(name) * 2 + 2, name)
    oa = OBJECT_ATTRIBUTES(ctypes.sizeof(OBJECT_ATTRIBUTES), root, ctypes.pointer(us), 0x40, None, None)
    iosb = IO_STATUS_BLOCK()
    st = nt.NtCreateFile(ctypes.byref(h), access, ctypes.byref(oa), ctypes.byref(iosb), None, 0x80, SHARE_RW, disp,
                         opts, None, 0)
    return (h.value if st == 0 else None), "0x%08X" % (st & 0xFFFFFFFF)


def attrs(h):
    info = BY_HANDLE_FILE_INFORMATION()
    return info.dwFileAttributes if k32.GetFileInformationByHandle(h, ctypes.byref(info)) else None


def final(h):
    buf = ctypes.create_unicode_buffer(1024)
    n = k32.GetFinalPathNameByHandleW(h, buf, 1024, 0)
    return buf.value if n else None


def bound(path, during=None):
    """Walk `path` (a directory chain under a drive) by held relative handles, then create `leaf`."""
    drive, rest = os.path.splitdrive(str(path))
    parts = [p for p in rest.split("\\") if p]
    leaf, comps = parts[-1], parts[:-1]
    held, steps = [], []
    h, st = ntopen(None, "\\??\\" + drive + "\\", DIR_ACCESS, FILE_OPEN, DIR_OPTS)
    steps.append({"open": drive + "\\", "status": st})
    if h is None:
        return {"steps": steps, "created": False}
    held.append(h)
    out = {"steps": steps, "created": False}
    for c in comps:
        h, st = ntopen(held[-1], c, DIR_ACCESS, FILE_OPEN, DIR_OPTS)
        a = attrs(h) if h else None
        steps.append({"open_relative": c, "status": st, "attributes": a})
        if h is None:
            break
        held.append(h)
        if a is None or a & REPARSE:
            out["refused"] = f"{c} is a reparse point (or its attributes are unreadable)"
            break
    else:
        if during:
            out["during"] = during()
        lh, st = ntopen(held[-1], leaf, LEAF_ACCESS, FILE_CREATE, LEAF_OPTS)
        out["leaf_create"] = st
        if lh:
            out["created"] = True
            out["leaf_final_path"] = final(lh)
            k32.CloseHandle(lh)
    for x in reversed(held):
        k32.CloseHandle(x)
    return out


def ps(cmd):
    p = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    return {"cmd": cmd, "exit": p.returncode, "out": p.stdout.strip()[-400:], "err": p.stderr.strip()[-400:]}


def substitute(anc, elsewhere):
    """Rename `anc` aside and put a junction to `elsewhere` in its place (another process)."""
    return [ps(f"Rename-Item -LiteralPath '{anc}' -NewName '{anc.name}.moved' -ErrorAction Stop"),
            ps(f"New-Item -ItemType Junction -Path '{anc}' -Target '{elsewhere}' -ErrorAction Stop | Out-Null")]


def listing(*dirs):
    return {str(d): sorted(os.listdir(d)) if d.exists() else None for d in dirs}


def main():
    base = Path(sys.argv[sys.argv.index("--dir") + 1]).resolve()
    base.mkdir(parents=True, exist_ok=True)
    rows = {"platform": platform.platform(), "base": str(base), "cases": {}}

    d = base / "bound" / "a" / "b"
    d.mkdir(parents=True)
    r = bound(d / "report.jsonl")
    r["listing"] = listing(d)
    rows["cases"]["bound"] = r

    d = base / "held" / "a" / "b"
    d.mkdir(parents=True)
    other = base / "held-elsewhere"
    other.mkdir()
    (other / "b").mkdir()
    r = bound(d / "report.jsonl", during=lambda: substitute(base / "held" / "a", other))
    r["listing"] = listing(d, other / "b")
    rows["cases"]["rename-held"] = r

    d = base / "junction"
    d.mkdir()
    target = base / "junction-target"
    target.mkdir()
    rows["cases"]["junction-setup"] = ps(f"New-Item -ItemType Junction -Path '{d / 'j'}' -Target '{target}' | Out-Null")
    r = bound(d / "j" / "report.jsonl")
    r["listing"] = listing(target)
    rows["cases"]["junction"] = r

    d = base / "naive" / "a"
    d.mkdir(parents=True)
    other = base / "naive-elsewhere"
    other.mkdir()
    a = k32.GetFileAttributesW(str(d))
    r = {"full_path_check_attributes": a, "check_says_reparse": bool(a & REPARSE)}
    r["substitution"] = substitute(d, other)
    h = k32.CreateFileW(str(d / "report.jsonl"), 0x40000000, 0, None, 1, 0x80, None)   # CREATE_NEW
    r["created"] = h not in (None, INVALID)
    r["create_error"] = ctypes.get_last_error() if not r["created"] else 0
    if r["created"]:
        r["leaf_final_path"] = final(h)
        k32.CloseHandle(h)
    r["listing"] = listing(other)
    rows["cases"]["naive"] = r

    (base / "PROBE-ancestor.json").write_text(json.dumps(rows, indent=1))
    print(json.dumps(rows["cases"], indent=1))


if __name__ == "__main__":
    main()
