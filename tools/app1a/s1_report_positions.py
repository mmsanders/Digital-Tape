#!/usr/bin/env python3
"""#466: Software's observation of S1 report-write failures at the START, a MIDDLE and
the END record, on a real full filesystem, against the unchanged shipping ingest.
Records follow Verification #209's tests/wp15_report_faults_r1 (oracle.writes /
baseline); it judges nothing. Verification #209 disposes.

Mechanism (real OS, no test seam): FS is a small FAT volume whose allocation unit is
CLUSTER bytes. A filler file takes every free cluster, then is shortened to leave
exactly k free. The report is created on FS (the directory entry needs no cluster),
so the first report write that does not fit in k clusters is refused or shortened by
the OS (ENOSPC / ERROR_DISK_FULL, or a short write). Sources, DEST and its stage live
under --work, on the runner's ordinary disk, at one fixed pathname for every run. k
comes from a no-fault neighbour of the same input:

  start   k = 0;
  middle  k so that the cluster boundary falls inside a progress record;
  end     an input whose report puts a cluster boundary inside the end record
          only (found by trying source counts), k = the clusters before it.

Write attempts are captured by strace on Linux (every write(2) on the report's
descriptor: requested bytes, returned count, error), so those rows can claim
shipping-native. Elsewhere no qualified write tracer is used: the run is kept as a
raw actual-filesystem observation with attempt_capture_complete false, which the
oracle does not accept as a row.

  s1_report_positions.py --bin INGEST --fs DIR --work DIR --out DIR [--strace]
"""
import argparse, hashlib, json, os, platform, re, shutil, struct, subprocess, sys
from pathlib import Path

NONCE = "0123456789abcdef0123456789abcdef"
END_LINE = b'{"t":"end","exit":0}\n'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def cluster_size(fs):
    if os.name == "nt":
        import ctypes
        spc, bps, free, total = (ctypes.c_ulong() for _ in range(4))
        ok = ctypes.windll.kernel32.GetDiskFreeSpaceW(ctypes.c_wchar_p(str(fs)), ctypes.byref(spc), ctypes.byref(bps),
                                                      ctypes.byref(free), ctypes.byref(total))
        assert ok, "GetDiskFreeSpaceW failed"
        return spc.value * bps.value
    st = os.statvfs(fs)
    return st.f_frsize or st.f_bsize


def wav(path, frames, seed):
    data = bytearray()
    for i in range(frames):
        data += struct.pack("<hh", ((i * seed * 7919) % 20000) - 10000, ((i * 31 + seed) % 16000) - 8000)
    Path(path).write_bytes(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt "
                          + struct.pack("<IHHIIHH", 16, 1, 2, 44100, 176400, 4, 16)
                          + b"data" + struct.pack("<I", len(data)) + bytes(data))


def inventory(d, skip=()):
    out = {}
    for p in sorted(Path(d).rglob("*")):
        r = p.relative_to(d).as_posix()
        if r.split("/")[0] in skip:
            continue
        out[r] = sha(p.read_bytes()) if p.is_file() else "dir"
    return out


STRACE_WRITE = re.compile(r'^\d+\s+write\((\d+), "((?:\\x[0-9a-f]{2})*)"(\.\.\.)?, (\d+)\) = (-?\d+)(?: (\w+))?')
STRACE_OPEN = re.compile(r'^\d+\s+openat\((?:AT_FDCWD|\d+), "((?:\\x[0-9a-f]{2})*)", ([A-Z_|]+)(?:, \d+)?\) = (-?\d+)')
STRACE_CLOSE = re.compile(r'^\d+\s+close\((\d+)\)')


def attempts_from(trace, report):
    """Writes on the descriptor whose openat created the report leaf (by path, or
    by name relative to its directory's descriptor): [{requested_hex, written, error}]."""
    fd, created, out = None, False, []
    names = {str(report).encode(), Path(report).name.encode()}
    for line in Path(trace).read_text(errors="replace").splitlines():
        m = STRACE_OPEN.match(line)
        if m and bytes.fromhex(m.group(1).replace("\\x", "")) in names:
            if int(m.group(3)) >= 0:
                fd = int(m.group(3))
                created = "O_CREAT" in m.group(2) and "O_EXCL" in m.group(2)
            continue
        m = STRACE_WRITE.match(line)
        if m and fd is not None and int(m.group(1)) == fd:
            assert not m.group(3), "strace truncated a write buffer"
            req = bytes.fromhex(m.group(2).replace("\\x", ""))
            assert len(req) == int(m.group(4))
            ret = int(m.group(5))
            out.append({"requested_hex": req.hex(), "written": max(ret, 0),
                        "error": m.group(6) if ret < 0 else None})
            continue
        m = STRACE_CLOSE.match(line)
        if m and fd is not None and int(m.group(1)) == fd:
            fd = None
    return created, out


class H:
    def __init__(self, a):
        self.a, self.n = a, 0
        self.out = Path(a.out); self.out.mkdir(parents=True, exist_ok=True)
        self.work = Path(a.work); self.work.mkdir(parents=True, exist_ok=True)
        self.fs = Path(a.fs)
        self.bin = os.path.abspath(a.bin)
        self.bin_sha = sha(Path(self.bin).read_bytes())
        self.version = subprocess.run([self.bin, "--version"], capture_output=True, text=True).stdout.strip()
        self.cluster = cluster_size(self.fs)
        self.strace = a.strace
        (self.fs / "foreign.txt").write_bytes(b"a foreign file on the report volume\n")

    def inputs(self, n, frames, folders=1):
        """`folders` dropped folders f0.., each holding n sources of `frames` frames."""
        d = self.work / "inputs" / f"{folders}x{n}-{frames}"
        if not d.exists():
            for m in range(folders):
                (d / f"f{m}").mkdir(parents=True)
                for k in range(n):
                    wav(d / f"f{m}" / f"{k:02d}.wav", frames, 100 * m + k + 1)
        return d

    def run(self, label, inputs, report, trace_writes=False):
        """One ingest run at the fixed case paths; the report at `report`. With
        trace_writes (and --strace), every write(2) is traced; report records are
        far shorter than the 4096-byte capture, audio writes are cut there."""
        self.n += 1
        case = self.work / "case"
        shutil.rmtree(case, ignore_errors=True)
        shutil.copytree(inputs, case / "src")
        folders = [str(case / "src" / f) for f in sorted(os.listdir(case / "src"))]
        (case / "out").mkdir()
        (case / "out" / "sentinel.txt").write_bytes(b"unrelated\n")
        foreign = lambda: {"out": inventory(case / "out", skip=("DEST",)), "fs": inventory(self.fs, skip=("filler.bin",
                                                                                                         Path(report).name))}
        src_before, foreign_before = inventory(case / "src"), foreign()
        argv = [self.bin, "--out", str(case / "out" / "DEST"), "--length", "3600", *folders,
                "--report", str(report), "--report-nonce", NONCE]
        trace = self.out / f"run{self.n:03d}.strace"
        traced = self.strace and trace_writes
        cmd = (["strace", "-f", "-qq", "-xx", "-s", "4096", "-e", "trace=openat,write,close", "-o", str(trace)]
               if traced else []) + argv
        p = subprocess.run(cmd, capture_output=True)
        dest = case / "out" / "DEST"
        rec = {"run": self.n, "label": label, "argv": argv, "binary_sha256": self.bin_sha, "version": self.version,
               "os": platform.platform(), "exit": p.returncode, "stdout_hex": p.stdout.hex(), "stderr_hex": p.stderr.hex(),
               "report_hex": Path(report).read_bytes().hex() if Path(report).exists() else "",
               "pair": {k: sha((dest / k).read_bytes()) for k in ("audio.wav", "manifest.json")} if dest.is_dir() else {},
               "sources_before": src_before, "sources_after": inventory(case / "src"),
               "foreign_before": foreign_before, "foreign_after": foreign(),
               "unpublished_stage_after": sorted(x.name for x in (case / "out").iterdir() if "stage" in x.name),
               "free_bytes_after": shutil.disk_usage(self.fs).free}
        if traced:
            rec["leaf_created_exclusive"], rec["attempts"] = attempts_from(trace, str(report))
            rec["attempt_capture_complete"] = True
            rec["observer"] = "strace -f -xx -s 4096 -e trace=openat,write,close"
        else:
            rec["leaf_created_exclusive"] = None
            rec["attempts"] = []
            rec["attempt_capture_complete"] = False
            rec["observer"] = "none qualified on this platform"
        return rec

    def fill(self, k):
        """Take every free cluster of FS with a filler, then free exactly k clusters."""
        filler = self.fs / "filler.bin"
        # Unbuffered: a refused write leaves nothing pending for close() to retry.
        # Some filesystems refuse a write while free space is still reported
        # (allocation ahead, delayed accounting), so fill in rounds with shrinking
        # writes and a sync between them until the volume reports nothing free or
        # a whole round adds nothing.
        fd = os.open(filler, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o644)
        try:
            for _ in range(8):
                before = os.fstat(fd).st_size
                for chunk in (1 << 16, self.cluster, 1):
                    try:
                        while os.write(fd, b"\0" * chunk) > 0:
                            pass
                    except OSError:
                        pass
                try:
                    os.fsync(fd)
                except OSError:
                    pass
                if shutil.disk_usage(self.fs).free == 0 or os.fstat(fd).st_size == before:
                    break
        finally:
            os.close(fd)
        os.truncate(filler, max(0, filler.stat().st_size - k * self.cluster))
        return {"cluster": self.cluster, "free_clusters_wanted": k, "free_bytes": shutil.disk_usage(self.fs).free,
                "filler_bytes": filler.stat().st_size}

    def clear(self):
        for nm in ("filler.bin", "report.jsonl"):
            try:
                (self.fs / nm).unlink()
            except FileNotFoundError:
                pass


def offsets(report):
    out, pos = [], 0
    for line in report.split(b"\n")[:-1]:
        out.append((pos, pos + len(line) + 1))
        pos += len(line) + 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("bin", "fs", "work", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--strace", action="store_true", help="capture report write attempts with strace (Linux)")
    a = ap.parse_args()
    h = H(a)
    C = h.cluster
    facts = {"os": platform.platform(), "fs": a.fs, "cluster": C, "binary_sha256": h.bin_sha, "version": h.version,
             "write_capture": "strace" if a.strace else None}
    print(json.dumps(facts), flush=True)
    report = h.fs / "report.jsonl"

    def neighbour(n, frames, folders=1):
        """No-fault run with the report on FS and every cluster it needs free (plus one)."""
        h.clear()
        r = h.run(f"neighbour folders={folders} n={n} frames={frames}", h.inputs(n, frames, folders), report)
        assert r["exit"] == 0 and r["pair"], r["stderr_hex"]
        return r

    picks = {}
    base = neighbour(3, 44100)
    ctl = bytes.fromhex(base["report_hex"])
    picks["start"] = (1, 3, 44100, base, 0)
    recs = offsets(ctl)
    mid = next((j for j in range(1, len(ctl) // C + 1) for i, (s, e) in enumerate(recs)
                if 0 < i < len(recs) - 1 and s < j * C < e), None)
    if mid is not None:
        picks["middle"] = (1, 3, 44100, base, mid)
    # Each source adds ~170 report bytes and each extra dropped folder ~50 (its list
    # record), so folders x sources reach many positions inside a cluster quickly.
    # Short inputs only; bounded to 40 runs.
    for folders, n in [(m, s) for m in range(2, 7) for s in range(1, 9)]:
        r = neighbour(n, 4410, folders)
        be = len(bytes.fromhex(r["report_hex"])) - len(END_LINE)
        print(f"end search: {folders} folders x {n} sources: {be} bytes before end, {be % C} into a cluster", flush=True)
        if be % C == 0 or be % C > C - len(END_LINE):
            picks["end"] = (folders, n, 4410, r, -(-be // C))
            break

    rows = []
    for pos in ("start", "middle", "end"):
        if pos not in picks:
            rows.append({"fault_position": pos, "row": "UNEXECUTED",
                         "reason": f"no tried input puts a {C}-byte allocation boundary inside the {pos} record"})
            continue
        folders, n, frames, nb, k = picks[pos]
        h.clear()
        free = h.fill(k)
        free["exact"] = free["free_bytes"] == k * C
        r = h.run(f"{pos} k={k}", h.inputs(n, frames, folders), report, trace_writes=True)
        rec = dict(r, mechanism="actual-filesystem", shipping=True, fault_position=pos,
                   claim="shipping-native" if a.strace else "observation-only",
                   baseline_exit=nb["exit"], baseline_stdout_hex=nb["stdout_hex"], baseline_stderr_hex=nb["stderr_hex"],
                   baseline_pair=nb["pair"], baseline_run=nb["run"], baseline_report_hex=nb["report_hex"], free=free,
                   inputs={"folders": folders, "sources_per_folder": n, "frames_each": frames})
        name = f"{pos}.record.json"
        (h.out / name).write_text(json.dumps(rec, indent=1))
        (h.out / f"{pos}.neighbour.json").write_text(json.dumps(nb, indent=1))
        print(json.dumps({"position": pos, "exit": r["exit"], "report_len": len(r["report_hex"]) // 2,
                          "neighbour_report_len": len(nb["report_hex"]) // 2, "attempts": len(r["attempts"]),
                          "free": free}), flush=True)
        rows.append({"fault_position": pos, "record": name, "neighbour": f"{pos}.neighbour.json"})
    h.clear()
    (h.fs / "foreign.txt").unlink()
    (h.out / "SUMMARY.json").write_text(json.dumps({"facts": facts, "rows": rows}, indent=1))
    print(json.dumps(rows), flush=True)


if __name__ == "__main__":
    main()
