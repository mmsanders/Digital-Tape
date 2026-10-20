#!/usr/bin/env python3
"""S3 method capability observation, Linux (Verification #208 method gap 1).

Not tapectl and not S3 code: a harmless probe on disposable loop devices of the
query -> write-mode upgrade the S3 method proposes. A read-only query fd is
held; the write-mode fd is open("/proc/self/fd/<query>", O_RDWR), which
reopens the same device inode, not the path; BLKGETDISKSEQ on the query fd
(before the policy) must equal it on the upgraded fd before any write. The
probe never writes to any device.

Cases (each on its own loop device, images in --dir):
  same      no change between query and upgrade
  detach    `losetup -d` while the query fd is held, then an attempt to attach
            another image at that loop number, then the upgrade
  changefd  a read-only loop whose backing file is replaced (LOOP_CHANGE_FD)
            while the query fd is held; the upgrade is read-only (a read-only
            loop refuses write-mode opens), so this shows only whether
            diskseq exposes a media change behind the same node
  reuse     the query fd closed, the loop detached, another image attached at
            the same number: a path open reaches it, with a new diskseq

Run as root. Writes PROBE-linux.json with every syscall result and errno.
"""
import errno
import fcntl
import json
import os
import platform
import struct
import subprocess
import sys
from pathlib import Path

BLKGETDISKSEQ = 0x80081280   # _IOR(0x12, 128, __u64)
LOOP_CHANGE_FD = 0x4C06


def sh(*cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return {"cmd": list(cmd), "exit": p.returncode, "out": p.stdout.strip(), "err": p.stderr.strip()}


def diskseq(fd):
    try:
        return struct.unpack("Q", fcntl.ioctl(fd, BLKGETDISKSEQ, b"\0" * 8))[0]
    except OSError as e:
        return {"errno": errno.errorcode.get(e.errno, e.errno)}


def ident(fd):
    st = os.fstat(fd)
    return {"rdev": [os.major(st.st_rdev), os.minor(st.st_rdev)], "ino": st.st_ino, "dev": st.st_dev,
            "diskseq": diskseq(fd)}


def marker(fd):
    try:
        return os.pread(fd, 16, 0).rstrip(b"\0").decode("ascii", "replace")
    except OSError as e:
        return {"errno": errno.errorcode.get(e.errno, e.errno)}


def upgrade(q, flags):
    try:
        fd = os.open(f"/proc/self/fd/{q}", flags)
    except OSError as e:
        return None, {"errno": errno.errorcode.get(e.errno, e.errno)}
    return fd, ident(fd)


def image(d, name, tag):
    p = d / name
    with open(p, "wb") as f:
        f.write(tag.encode().ljust(512, b"\0"))
        f.truncate(8 << 20)
    return str(p)


def attach(img, ro=False):
    r = sh("losetup", "-f", "--show", *(["-r"] if ro else []), img)
    return r["out"], r


def main():
    d = Path(sys.argv[sys.argv.index("--dir") + 1])
    d.mkdir(parents=True, exist_ok=True)
    a, b = image(d, "A.img", "IMAGE-A"), image(d, "B.img", "IMAGE-B")
    rows = {"platform": platform.platform(), "kernel": os.uname().release, "cases": {}}

    # same
    dev, r = attach(a)
    q = os.open(dev, os.O_RDONLY)
    before = ident(q)
    rw, after = upgrade(q, os.O_RDWR)
    rows["cases"]["same"] = {"dev": dev, "attach": r, "query": before, "upgrade": after,
                             "same_inode": isinstance(after, dict) and after.get("ino") == before["ino"],
                             "seq_equal": after.get("diskseq") == before["diskseq"],
                             "marker_on_upgrade": marker(rw) if rw is not None else None}
    for fd in (rw, q):
        if fd is not None:
            os.close(fd)
    sh("losetup", "-d", dev)

    # detach while held
    dev, r = attach(a)
    q = os.open(dev, os.O_RDONLY)
    before = ident(q)
    det = sh("losetup", "-d", dev)
    busy = sh("losetup", dev, b)
    rw, after = upgrade(q, os.O_RDWR)
    rows["cases"]["detach"] = {"dev": dev, "attach": r, "query": before, "detach_while_held": det,
                               "attach_other_at_same_number": busy, "upgrade": after,
                               "seq_equal": isinstance(after, dict) and after.get("diskseq") == before["diskseq"],
                               "marker_on_upgrade": marker(rw) if rw is not None else None}
    for fd in (rw, q):
        if fd is not None:
            os.close(fd)
    rows["cases"]["detach"]["after_close"] = sh("losetup", "-l", "-n", "-O", "NAME,BACK-FILE")
    sh("losetup", "-d", dev)

    # LOOP_CHANGE_FD behind the held query fd
    dev, r = attach(a, ro=True)
    q = os.open(dev, os.O_RDONLY)
    before = ident(q)
    before["marker"] = marker(q)
    bf = os.open(b, os.O_RDONLY)
    try:
        lf = os.open(dev, os.O_RDONLY)
        fcntl.ioctl(lf, LOOP_CHANGE_FD, bf)
        os.close(lf)
        change = "ok"
    except OSError as e:
        change = {"errno": errno.errorcode.get(e.errno, e.errno)}
    os.close(bf)
    held_after = ident(q)
    held_after["marker"] = marker(q)
    rwt, rw_try = upgrade(q, os.O_RDWR)
    ro, after = upgrade(q, os.O_RDONLY)
    rows["cases"]["changefd"] = {"dev": dev, "attach": r, "query": before, "change_fd": change,
                                 "query_after_change": held_after, "write_mode_upgrade_on_ro_loop": rw_try,
                                 "readonly_upgrade": after,
                                 "seq_changed": isinstance(after, dict) and after.get("diskseq") != before["diskseq"],
                                 "marker_on_upgrade": marker(ro) if ro is not None else None}
    for fd in (rwt, ro, q):
        if fd is not None:
            os.close(fd)
    sh("losetup", "-d", dev)

    # path reuse after a real detach
    dev, r = attach(a)
    q = os.open(dev, os.O_RDONLY)
    before = ident(q)
    os.close(q)
    det = sh("losetup", "-d", dev)
    re = sh("losetup", dev, b)
    p = os.open(dev, os.O_RDONLY)
    now = ident(p)
    rows["cases"]["reuse"] = {"dev": dev, "query": before, "detach": det, "attach_other_at_same_number": re,
                              "path_open": now, "marker_on_path_open": marker(p),
                              "seq_equal": now["diskseq"] == before["diskseq"]}
    os.close(p)
    sh("losetup", "-d", dev)

    out = d / "PROBE-linux.json"
    out.write_text(json.dumps(rows, indent=1))
    for k, v in rows["cases"].items():
        print(k, json.dumps({x: v[x] for x in v if x in ("seq_equal", "seq_changed", "same_inode", "marker_on_upgrade",
                                                          "marker_on_path_open", "change_fd")}))


if __name__ == "__main__":
    main()
