#!/usr/bin/env python3
"""Measure worst-case windowed sustained write on a microSD card.

Michael chose C-60 as the standard tape (ADR-018), and issue #5 is the finding
that made that the right call. At 635 MB the copy needs **21.2 MB/s** sustained
write -- inside every V30 card's guaranteed floor with ~40% margin, on plain
high-speed 4-bit at 3.3 V, with no 1.8 V switching anywhere.

So this is no longer a gate. It is a **headroom measurement**: it says how much
room a V30 card actually has above the requirement. This media measurement is
not end-to-end copy acceptance, and it attributes nothing to the card alone --
every number is a property of the whole path (card, reader, host, filesystem).

SCHEMA 2 -- what changed, and why (P1-R17-V-A01, P1-R18)
--------------------------------------------------------
Schema 1 stored rounded MB/s per window and nothing else. Verification found
three ways that record could be wrong without anyone noticing, and all three are
closed here:

  * `os.write()` may write FEWER bytes than requested. Schema 1 assumed it wrote
    them all and computed the rate from the REQUESTED count, so a short write
    inflated the number silently. Now every window loops until its range is
    complete, and records requested bytes, returned bytes and the call count.
  * Nothing recorded how a rate was arrived at. Now each window keeps its
    monotonic start and end at full precision, so every derived figure is
    recomputable from primitives and a corrupted summary cannot hide.
  * `--fill` recorded only that the flag was passed. Now capacity/free/used are
    measured BEFORE the fill, AFTER the fill and AFTER the measurement, and the
    occupancy is derived from those. A flag is not evidence of a filled card.

The measurement file is also kept and its final size recorded, so the bytes the
run claims to have written can be checked against the filesystem afterwards.

`analyse.py` derives every reported figure from these primitives and refuses to
trust a stored summary field. A schema-1 file is still readable, and is labelled
what it is: summary-only, not complete WP-05 A-2 evidence.

PM Decisions 001 section 1 sets the physical conditions, and each one exists to
defeat a way a card looks faster than it is:

  * card filled to ~80%       -- an empty card writes to clean blocks; a full one
                                 must garbage-collect first, which is when it stalls
  * transfer at least as long
    as a real copy             -- SLC write caches are typically a few GB. A short
                                 transfer measures the cache, not the card
  * WORST-CASE windowed rate   -- an average hides the single stall that produces
                                 the dropout. We report the slowest window, because
                                 that is the number the requirement actually needs

Usage:
    sudo ./measure_sustained_write.py /dev/sdX --i-know --json run.json
    ./measure_sustained_write.py /mnt/card --fill --json results/card-run.json

Writing to a raw device DESTROYS its contents. The script refuses to touch a
device that is mounted, and requires --i-know for a raw block device.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2

REQUIRED_MB_S = 21.2       # 635,040,000 B / 30 s -- C-60, the standard tape (ADR-018)
REQUIRED_C90_MB_S = 31.75  # what a C-90 would need. Reported only; C-90 is not open
BAR_MB_S = 23.3            # 10% over the C-60 requirement -- the screening bar
WINDOW_MB = 64             # granularity of the worst-case window
DEFAULT_TRANSFER_MB = 1200  # > one 90-minute cartridge (953 MB)
FILL_TARGET = 0.80

# MB here is 10^6 bytes throughout, in the tool and in the analyser. Stated
# because a rate is meaningless without it and MiB would be 5% different.
BYTES_PER_MB = 1_000_000


def mb(n: int | float) -> float:
    return n / BYTES_PER_MB


def is_mounted(dev: str) -> bool:
    try:
        out = subprocess.run(["findmnt", "-rn", "-S", dev],
                             capture_output=True, text=True, timeout=10)
        return bool(out.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        with open("/proc/mounts") as fh:
            return any(line.split()[0] == dev for line in fh)


def device_size(target: Path) -> int:
    return int(subprocess.run(["blockdev", "--getsize64", str(target)],
                              capture_output=True, text=True,
                              check=True).stdout.strip())


def space(target: Path) -> dict:
    """Total/free/used for the target, and the occupancy derived from them.

    A raw block device has no filesystem accounting, and inventing one would be
    fabricating a fact (P1-R18 part A item 4). It reports its size and says
    plainly that the rest does not apply.
    """
    if target.is_block_device():
        total = device_size(target)
        return {"applies": False,
                "reason": "raw block device: no filesystem free/used accounting",
                "total_bytes": total,
                "free_bytes": None, "used_bytes": None, "occupancy": None}
    st = os.statvfs(target)
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - st.f_bfree * st.f_frsize
    return {"applies": True, "reason": None,
            "total_bytes": total, "free_bytes": free, "used_bytes": used,
            "occupancy": (used / total) if total else None}


def write_fully(fd: int, view: memoryview, writer=os.write) -> tuple[int, int]:
    """Write every byte of `view`, looping over short writes.

    Returns (bytes actually returned by the kernel, number of write calls).
    os.write() is permitted to write less than asked -- on a slow device under
    memory pressure it does. Schema 1 assumed otherwise and counted the
    requested size, which turns a short write into free throughput.
    """
    done = 0
    calls = 0
    while done < len(view):
        n = writer(fd, view[done:])
        calls += 1
        if n <= 0:
            raise OSError(f"write returned {n} after {done} of {len(view)} bytes")
        done += n
    return done, calls


def fill_to(target: Path, fraction: float, writer=os.write) -> dict:
    """Occupy the card up to `fraction` so the controller must garbage-collect.

    Returns what it actually did, measured -- not what it was asked to do.
    """
    before = space(target)
    if not before["applies"]:
        return {"requested_fraction": fraction, "performed": False,
                "reason": "raw block device: the whole device is written anyway",
                "before": before, "after": before, "ballast_bytes": 0,
                "ballast_path": None}

    want_free = int(before["total_bytes"] * (1.0 - fraction))
    have_free = before["free_bytes"]
    ballast = target / "_ballast.bin"
    written = 0
    if have_free > want_free:
        to_write = have_free - want_free
        print(f"  writing {mb(to_write):,.0f} MB of ballast to reach {fraction:.0%} full")
        chunk = memoryview(os.urandom(8 << 20))
        fd = os.open(ballast, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        try:
            while written < to_write:
                n = min(len(chunk), to_write - written)
                got, _ = write_fully(fd, chunk[:n], writer)
                written += got
            os.fsync(fd)
        finally:
            os.close(fd)
    else:
        print(f"  already >= {fraction:.0%} full")

    return {"requested_fraction": fraction, "performed": True, "reason": None,
            "before": before, "after": space(target),
            "ballast_bytes": written,
            "ballast_path": str(ballast) if written else None}


def run(target: Path, transfer_mb: int, window_mb: int, writer=os.write,
        keep: bool = True) -> dict:
    """Write `transfer_mb` and retain the primitives for every window."""
    total = transfer_mb * BYTES_PER_MB
    win = window_mb * BYTES_PER_MB
    # Incompressible, so a controller that compresses cannot cheat the number.
    buf = memoryview(os.urandom(win))

    raw = target.is_block_device()
    path = target if raw else target / "_seqwrite.bin"
    # Deliberately NOT O_DIRECT: it requires block-aligned buffers, and an
    # fsync per window forces the data to the card anyway -- which is exactly
    # the stall we are trying to catch.
    flags = os.O_WRONLY
    if not raw:
        flags |= os.O_CREAT | os.O_TRUNC

    windows: list[dict] = []
    fd = os.open(path, flags)
    try:
        requested_total = 0
        returned_total = 0
        t_first = time.monotonic()
        while returned_total < total:
            n = min(win, total - returned_total)
            t0 = time.monotonic()
            got, calls = write_fully(fd, buf[:n], writer)
            sync_error = None
            try:
                os.fsync(fd)          # the stall we care about happens here
            except OSError as exc:    # recorded, never swallowed
                sync_error = str(exc)
            t1 = time.monotonic()
            windows.append({
                "index": len(windows),
                "offset_bytes": returned_total,
                "requested_bytes": n,
                "returned_bytes": got,
                "write_calls": calls,
                "short_writes": calls - 1,
                "t_start_monotonic_s": t0,
                "t_end_monotonic_s": t1,
                "duration_s": t1 - t0,
                "fsync_ok": sync_error is None,
                "sync_error": sync_error,
            })
            requested_total += n
            returned_total += got
            if len(windows) % 4 == 0:
                rates = [mb(w["returned_bytes"]) / w["duration_s"] for w in windows]
                print(f"  {mb(returned_total):>7,.0f} MB  "
                      f"now {rates[-1]:6.1f} MB/s  "
                      f"worst {min(rates):6.1f} MB/s", flush=True)
        t_last = time.monotonic()
        os.fsync(fd)
        final_size = os.fstat(fd).st_size
    finally:
        os.close(fd)

    kept = keep and not raw
    if not raw and not keep:
        try:
            path.unlink()
        except OSError:
            pass

    return {
        "schema_version": SCHEMA_VERSION,
        "target_kind": "raw-device" if raw else "mounted-filesystem",
        "measurement_path": str(path),
        "measurement_file_retained": kept,
        "transfer_mb": transfer_mb,
        "window_mb": window_mb,
        "bytes_per_mb": BYTES_PER_MB,
        "requested_bytes_total": requested_total,
        "returned_bytes_total": returned_total,
        "expected_final_size_bytes": total,
        "final_size_bytes": final_size,
        "t_first_monotonic_s": t_first,
        "t_last_monotonic_s": t_last,
        "elapsed_s": t_last - t_first,
        "windows": windows,
        "required_mb_s": REQUIRED_MB_S,
        "required_c90_mb_s": REQUIRED_C90_MB_S,
        "bar_mb_s": BAR_MB_S,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", type=Path,
                    help="mountpoint (preferred) or raw block device")
    ap.add_argument("--sku", default="", help="exact manufacturer part number")
    ap.add_argument("--revision", default="", help="card revision, exactly as marked")
    ap.add_argument("--cid", default="", help="CID register, per sample, if readable")
    ap.add_argument("--sample", default="", help="operator label for this physical card")
    ap.add_argument("--reader", default="", help="reader used, so it can be ruled out")
    ap.add_argument("--transfer-mb", type=int, default=DEFAULT_TRANSFER_MB)
    ap.add_argument("--window-mb", type=int, default=WINDOW_MB)
    ap.add_argument("--fill", action="store_true",
                    help="pre-fill to 80 percent of capacity before measuring")
    ap.add_argument("--delete-measurement-file", action="store_true",
                    help="remove the measurement file (its final size can then "
                         "no longer be checked -- schema 1 did this always)")
    ap.add_argument("--json", type=Path, help="write the result here")
    ap.add_argument("--i-know", action="store_true",
                    help="required to write to a raw block device (DESTRUCTIVE)")
    args = ap.parse_args()

    if not args.target.exists():
        sys.exit(f"no such target: {args.target}")
    if args.target.is_block_device():
        if is_mounted(str(args.target)):
            sys.exit(f"{args.target} is mounted -- refusing. Unmount it first.")
        if not args.i_know:
            sys.exit(f"{args.target} is a raw block device and this DESTROYS its "
                     f"contents. Re-run with --i-know if that is what you want.")

    before_any = space(args.target)
    print(f"target      {args.target}")
    print(f"part number {args.sku or '(UNRECORDED -- WP-05 A-1 needs it)'}")
    print(f"revision    {args.revision or '(UNRECORDED)'}")
    print(f"cid         {args.cid or '(UNRECORDED)'}")
    print(f"capacity    {mb(before_any['total_bytes']):,.0f} MB")
    print(f"transfer    {args.transfer_mb:,} MB in {args.window_mb} MB windows")
    print(f"bar         worst window >= {BAR_MB_S} MB/s "
          f"(requirement {REQUIRED_MB_S} MB/s + 10%)")
    print()

    fill = {"requested_fraction": None, "performed": False,
            "reason": "--fill not requested", "before": before_any,
            "after": before_any, "ballast_bytes": 0, "ballast_path": None}
    if args.fill:
        print("filling:")
        fill = fill_to(args.target, FILL_TARGET)
        print()

    print("measuring:")
    result = run(args.target, args.transfer_mb, args.window_mb,
                 keep=not args.delete_measurement_file)
    result |= {
        "sku": args.sku,
        "revision": args.revision,
        "cid": args.cid,
        "sample": args.sample,
        "reader": args.reader,
        "fill": fill,
        "space_after_measurement": space(args.target),
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": platform.platform(),
    }

    rates = [mb(w["returned_bytes"]) / w["duration_s"] for w in result["windows"]]
    worst = min(rates)
    print()
    print(f"  windows       {len(rates)}")
    print(f"  short writes  {sum(w['short_writes'] for w in result['windows'])}")
    print(f"  WORST window  {worst:>7.1f} MB/s   <-- the number")
    print(f"  C-60 headroom {worst / REQUIRED_MB_S:>7.2f}x")
    print(f"  screen        {'PASS' if worst >= BAR_MB_S else 'FAIL'} "
          f"against the {BAR_MB_S} MB/s bar")
    print()
    print("  This is a path measurement, not a card measurement, and not")
    print("  qualification. Run analyse.py on the JSON for the audited figures.")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2) + "\n")
        print(f"\nwrote {args.json}")

    return 0 if worst >= BAR_MB_S else 2


if __name__ == "__main__":
    raise SystemExit(main())
