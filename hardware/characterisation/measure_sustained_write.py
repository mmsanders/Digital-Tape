#!/usr/bin/env python3
"""Measure worst-case windowed sustained write on a microSD card.

The 30-second copy criterion (guardrail 10) needs 31.75 MB/s sustained write on
the destination card. No purchasable UHS-I specification guarantees that -- V30's
floor is 30 MB/s and V60/V90 are UHS-II ratings that do not apply on a UHS-I host
(issue #5). So the requirement is met by characterised card models, and this is
the tool that characterises them.

PM Decisions 001 section 1 sets the conditions, and each one exists to defeat a
way a card looks faster than it is:

  * card filled to ~80%       -- an empty card writes to clean blocks; a full one
                                 must garbage-collect first, which is when it stalls
  * transfer at least as long
    as a real copy             -- SLC write caches are typically a few GB. A short
                                 transfer measures the cache, not the card
  * WORST-CASE windowed rate   -- an average hides the single stall that produces
                                 the dropout. We report the slowest window, because
                                 that is the number the requirement actually needs

Reports PASS when the worst window clears the PM's 35 MB/s bar (10% over the
31.75 MB/s requirement).

Usage:
    sudo ./measure_sustained_write.py /dev/sdX --fill
    ./measure_sustained_write.py /mnt/card --json results/samsung-pro-plus-128.json

Writing to a raw device DESTROYS its contents. The script refuses to touch a
device that is mounted, and requires --i-know for a raw block device.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_MB_S = 31.75      # 952,560,000 B / 30 s, guardrail 10 at 90 minutes
BAR_MB_S = 35.0            # PM Decisions 001 section 1: 10% margin over required
WINDOW_MB = 64             # granularity of the worst-case window
DEFAULT_TRANSFER_MB = 1200  # > one 90-minute cartridge (953 MB)
FILL_TARGET = 0.80


def mb(n: int) -> float:
    return n / 1_000_000


def is_mounted(dev: str) -> bool:
    try:
        out = subprocess.run(["findmnt", "-rn", "-S", dev],
                             capture_output=True, text=True, timeout=10)
        return bool(out.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        with open("/proc/mounts") as fh:
            return any(line.split()[0] == dev for line in fh)


def capacity_bytes(target: Path) -> int:
    if target.is_block_device():
        return int(subprocess.run(["blockdev", "--getsize64", str(target)],
                                  capture_output=True, text=True,
                                  check=True).stdout.strip())
    st = os.statvfs(target)
    return st.f_blocks * st.f_frsize


def free_bytes(target: Path) -> int:
    if target.is_block_device():
        return capacity_bytes(target)
    st = os.statvfs(target)
    return st.f_bavail * st.f_frsize


def fill_to(target: Path, fraction: float) -> None:
    """Occupy the card up to `fraction` so the controller must garbage-collect."""
    if target.is_block_device():
        print("  raw device: fill is implicit (the whole device is written)")
        return
    cap = capacity_bytes(target)
    want_free = int(cap * (1.0 - fraction))
    have_free = free_bytes(target)
    if have_free <= want_free:
        print(f"  already >= {fraction:.0%} full")
        return
    ballast = target / "_ballast.bin"
    to_write = have_free - want_free
    print(f"  writing {mb(to_write):,.0f} MB of ballast to reach {fraction:.0%} full")
    chunk = os.urandom(8 << 20)
    written = 0
    with open(ballast, "wb") as fh:
        while written < to_write:
            n = min(len(chunk), to_write - written)
            fh.write(chunk[:n])
            written += n
        fh.flush()
        os.fsync(fh.fileno())


def run(target: Path, transfer_mb: int, window_mb: int) -> dict:
    """Write `transfer_mb` and time every `window_mb` window."""
    total = transfer_mb << 20
    win = window_mb << 20
    # Incompressible, so a controller that compresses cannot cheat the number.
    buf = os.urandom(win)

    raw = target.is_block_device()
    path = target if raw else target / "_seqwrite.bin"
    # Deliberately NOT O_DIRECT: it requires block-aligned buffers, and an
    # fsync per window forces the data to the card anyway -- which is exactly
    # the stall we are trying to catch.
    flags = os.O_WRONLY
    if not raw:
        flags |= os.O_CREAT | os.O_TRUNC

    windows: list[float] = []
    fd = os.open(path, flags)
    try:
        written = 0
        t_start = time.monotonic()
        while written < total:
            t0 = time.monotonic()
            n = min(win, total - written)
            os.write(fd, buf[:n])
            os.fsync(fd)          # the stall we care about happens here
            dt = time.monotonic() - t0
            windows.append(mb(n) / dt)
            written += n
            if len(windows) % 4 == 0:
                print(f"  {mb(written):>7,.0f} MB  "
                      f"now {windows[-1]:6.1f} MB/s  "
                      f"worst {min(windows):6.1f} MB/s", flush=True)
        elapsed = time.monotonic() - t_start
    finally:
        os.close(fd)
        if not raw:
            try:
                path.unlink()
            except OSError:
                pass

    worst = min(windows)
    return {
        "transfer_mb": transfer_mb,
        "window_mb": window_mb,
        "elapsed_s": round(elapsed, 2),
        "mean_mb_s": round(mb(total) / elapsed, 2),
        "median_mb_s": round(statistics.median(windows), 2),
        "p05_mb_s": round(statistics.quantiles(windows, n=20)[0], 2)
        if len(windows) >= 20 else None,
        "worst_window_mb_s": round(worst, 2),
        "windows_mb_s": [round(w, 2) for w in windows],
        "required_mb_s": REQUIRED_MB_S,
        "bar_mb_s": BAR_MB_S,
        "verdict": "PASS" if worst >= BAR_MB_S else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", type=Path,
                    help="mountpoint (preferred) or raw block device")
    ap.add_argument("--sku", default="", help="exact SKU, e.g. MB-MD128SA/AM")
    ap.add_argument("--revision", default="", help="card revision / CID if known")
    ap.add_argument("--reader", default="", help="reader used, so it can be ruled out")
    ap.add_argument("--transfer-mb", type=int, default=DEFAULT_TRANSFER_MB)
    ap.add_argument("--window-mb", type=int, default=WINDOW_MB)
    ap.add_argument("--fill", action="store_true",
                    help="pre-fill to 80 percent of capacity before measuring")
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

    print(f"target      {args.target}")
    print(f"sku         {args.sku or '(unrecorded -- record it, see issue #5)'}")
    print(f"capacity    {mb(capacity_bytes(args.target)):,.0f} MB")
    print(f"transfer    {args.transfer_mb:,} MB in {args.window_mb} MB windows")
    print(f"bar         worst window >= {BAR_MB_S} MB/s "
          f"(requirement {REQUIRED_MB_S} MB/s + 10%)")
    print()

    if args.fill:
        print("filling:")
        fill_to(args.target, FILL_TARGET)
        print()

    print("measuring:")
    result = run(args.target, args.transfer_mb, args.window_mb)
    result |= {
        "sku": args.sku,
        "revision": args.revision,
        "reader": args.reader,
        "filled_to": FILL_TARGET if args.fill else None,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": platform.platform(),
    }

    print()
    print(f"  mean          {result['mean_mb_s']:>7.1f} MB/s")
    print(f"  median window {result['median_mb_s']:>7.1f} MB/s")
    print(f"  WORST window  {result['worst_window_mb_s']:>7.1f} MB/s   <-- the number")
    print(f"  verdict       {result['verdict']}")
    if result["verdict"] == "FAIL":
        print(f"  (worst window is {BAR_MB_S - result['worst_window_mb_s']:.1f} MB/s "
              f"under the bar)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2) + "\n")
        print(f"\nwrote {args.json}")

    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
