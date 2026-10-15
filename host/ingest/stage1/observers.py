"""Native observers for the Stage1 packet runner (run_packet.py). Software transport
only: each observer records the complete raw native trace of the observed process
tree, maps it to INTERFACE.md's normalized ops, and states the integrity checks it
applied. It decides no PASS; Verification reviews the raw traces and mappings.

  linux    strace -f -C   ptrace; the trailing -C call tally is the tracer's own count
                          of every traced syscall, so a dropped record or a truncated
                          trace no longer matches it.
  macos    fs_usage -w    kdebug, one root session per case (runs are serial). A start
                          and end gate process bracket each window, so the window is
                          known to cover the whole run.
  windows  Process Monitor one capture-filtered session for the whole packet; the PML
                          is exported to CSV by Procmon itself and the two are aligned
                          row by row. Every PML event is assigned to exactly one owner,
                          so a record dropped from any case extract is detectable.

Common to all: the observation build stats `.mark/<seq>-<op>` at each milestone and
also logs the same marks to its own events.jsonl. The native trace must show every
mark, in order, contiguous from 0, and identical to that independent log.
"""
import csv, gzip, hashlib, json, os, re, shutil, signal, subprocess, sys, threading, time
from pathlib import Path


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


MARK = re.compile(r"[/\\]\.mark[/\\](\d+)-([a-z_]+)")
STAGE_SEP = ".ingest-stage-"


def norm(p):
    return os.path.normcase(os.path.normpath(p)) if p else p


# ---- common mapping ----------------------------------------------------------------------
# A raw op is a dict: kind in mark|mkdir|create|open|flush|close|rename|device, plus
# path / key / dst / ok / noreplace / line. Each observer's parser yields these.

def to_events(rawops, dest, stage_prefix, obsdir):
    events, failed = [], []
    flushed, preflight_done = set(), False
    dest_n, obs_n = norm(str(dest)), norm(str(obsdir))
    dest_parent = os.path.dirname(dest_n)

    def ev(op, r, **kw):
        events.append(dict(seq=len(events), op=op, line=r.get("line"), **kw))

    for r in rawops:
        k, path = r["kind"], r.get("path") or ""
        if k == "mark":
            if r["op"] in ("preflight_complete", "sources_revalidated", "source_mutation_detected"):
                ev(r["op"], r)
                preflight_done = preflight_done or r["op"] == "preflight_complete"
            continue
        if k == "device":
            ev("device_open", r, path=path)
            continue
        if path and norm(path).startswith(obs_n):
            continue  # the observation build's own output
        in_stage = stage_prefix in os.path.basename(os.path.dirname(path)) if path else False
        if k == "mkdir" and r.get("ok"):
            if os.path.basename(path).startswith(stage_prefix):
                ev("stage_create", r, exclusive=True, adjacent=os.path.dirname(norm(path)) == dest_parent)
            elif not preflight_done:
                ev("preflight_disk_scratch", r, path=path)
        elif k == "create" and r.get("ok"):
            if in_stage:
                ev("output_open", r, file=os.path.basename(path))
            elif not preflight_done:
                ev("preflight_disk_scratch", r, path=path)
        elif k == "flush" and r.get("ok"):
            flushed.add(r["key"])
        elif k == "close":
            if r["key"] in flushed and in_stage and os.path.basename(path) in ("audio.wav", "manifest.json"):
                ev(os.path.basename(path).split(".")[0] + "_flush_close", r)
        elif k == "rename":
            src_stage = os.path.basename(path).startswith(stage_prefix)
            dst = r.get("dst")
            into_dest = (dst is None and src_stage) or (dst is not None and norm(dst) == dest_n)
            if not into_dest:
                continue
            op = "publish_dir_noreplace" if (src_stage and r.get("noreplace")) else "publish_file"
            if r.get("ok"):
                ev(op, r, **({"destination_shown": False} if dst is None else {}))
            else:
                failed.append({"op": op, "line": r.get("line"), "result": r.get("result")})
    return events, failed


def marks_check(rawops, seam):
    native = [(int(r["seq"]), r["op"]) for r in rawops if r["kind"] == "mark"]
    logged = [(int(e["seq"]), e["op"]) for e in seam]
    return {
        "marks_contiguous": [s for s, _ in native] == list(range(len(native))),
        "marks_match_seam_log": native == logged,
    }


def mark_of(path):
    m = MARK.search(path or "")
    return (m.group(1), m.group(2)) if m else None


# ---- Linux: strace -----------------------------------------------------------------------

STRACE_SET = ("openat,open,creat,mkdir,mkdirat,rename,renameat,renameat2,fsync,fdatasync,"
              "close,unlink,unlinkat,rmdir,newfstatat,statx,stat,lstat,execve,exit_group,"
              "clone,clone3,fork,vfork")
S_LINE = re.compile(r"^(\d+)\s+\S+\s+(\w+)\((.*)\)\s+=\s+(-?\d+|\?)")
S_RESUMED = re.compile(r"^(\d+)\s+\S+\s+<\.\.\. (\w+) resumed>")
S_UNFIN = re.compile(r"^(\d+)\s+\S+\s+(\w+)\(.*<unfinished \.\.\.>$")
S_DEVICE = re.compile(r'"/dev/(sd[a-z]|nvme|mmcblk|loop|disk|rdisk|hd[a-z]|vd[a-z]|xvd|sr)')


class Strace:
    kind = "strace"
    deferred = False
    serial = False

    def version(self):
        try:
            return subprocess.run(["strace", "-V"], capture_output=True, text=True).stdout.splitlines()[0]
        except (OSError, IndexError):
            return "unavailable"

    def start(self, root):
        pass

    def stop(self):
        pass

    def wrap(self, argv, trace):
        return ["strace", "-f", "-q", "-C", "-tt", "-y", "-s", "4096", "-e", "trace=" + STRACE_SET,
                "-o", str(trace), "--"] + argv

    def before(self, trace, ctx):
        pass

    def after(self, trace, ctx):
        pass

    @staticmethod
    def parse(text):
        """-> rawops, integrity checks, root pid, completion."""
        lines = text.splitlines()
        tally_at = next((i for i, l in enumerate(lines) if l.startswith("% time")), None)
        body = lines if tally_at is None else lines[:tally_at]
        tally = {}
        if tally_at is not None:
            for l in lines[tally_at + 2:]:
                t = l.split()
                if len(t) >= 5 and not l.startswith("---") and t[-1] != "total":
                    tally[t[-1]] = int(t[3])
        counted, unfinished, orphans, ended = {}, {}, [], set()
        rawops, root, completion = [], None, None
        for n, l in enumerate(body):
            t = l.split()
            if not t:
                continue
            root = root or t[0]
            if "+++ exited with" in l or "+++ killed by" in l:
                ended.add(t[0])
            if t[0] == root and "+++ exited with" in l:
                completion = "exited " + l.rsplit("exited with", 1)[1].strip(" +")
            if t[0] == root and "+++ killed by" in l:
                completion = "killed " + l.rsplit("killed by", 1)[1].strip(" +")
            u = S_UNFIN.match(l)
            if u:
                unfinished[u.group(1)] = (u.group(2), l[:l.rindex("<unfinished ...>")].rstrip())
                continue
            rs = S_RESUMED.match(l)
            if rs:
                head = unfinished.pop(rs.group(1), None)
                if head is None or head[0] != rs.group(2):
                    orphans.append(n)
                    continue
                l = head[1] + l.split("resumed>", 1)[1]
            m = S_LINE.match(l)
            if not m:
                continue
            pid, call, args, ret = m.groups()
            if ret != "?":  # a call that never returned (exit_group, killed) is not in the tally
                counted[call] = counted.get(call, 0) + 1
            ok = ret != "?" and int(ret) >= 0
            q = re.findall(r'"([^"]*)"', args)
            if call in ("statx", "newfstatat", "stat", "lstat"):
                mk = mark_of(args)
                if mk:
                    rawops.append({"kind": "mark", "seq": mk[0], "op": mk[1], "line": n})
                continue
            if call in ("openat", "open", "creat"):
                if S_DEVICE.search(args):
                    rawops.append({"kind": "device", "path": q[0] if q else "", "line": n})
                creating = "O_CREAT" in args or call == "creat"
                rawops.append({"kind": "create" if creating else "open", "path": q[0] if q else "", "ok": ok, "line": n})
            elif call in ("mkdir", "mkdirat"):
                rawops.append({"kind": "mkdir", "path": q[0] if q else "", "ok": ok, "line": n})
            elif call in ("fsync", "fdatasync"):
                fd = re.search(r"<([^>]*)>", args)
                if fd:
                    rawops.append({"kind": "flush", "key": fd.group(1), "path": fd.group(1), "ok": ok, "line": n})
            elif call == "close":
                fd = re.search(r"<([^>]*)>", args)
                if fd:
                    rawops.append({"kind": "close", "key": fd.group(1), "path": fd.group(1), "ok": ok, "line": n})
            elif call in ("rename", "renameat", "renameat2"):
                rawops.append({"kind": "rename", "path": q[0] if q else "", "dst": q[1] if len(q) > 1 else None,
                               "noreplace": "RENAME_NOREPLACE" in args, "ok": ok, "line": n, "result": ret})
        # exit_group never returns: strace counts the call but prints "= ?".
        checks = {
            "tally_present": bool(tally),
            "tally_matches_records": bool(tally) and all(counted.get(c, 0) == v for c, v in tally.items())
                                     and all(c in tally for c in counted),
            # a call cut off by its process's own termination never resumes; any other
            # unfinished call means the trace lost its completion record
            "no_unresumed_calls": not orphans and all(pid in ended for pid in unfinished),
            "root_completion_seen": completion is not None,
        }
        return rawops, checks, root, completion

    def normalize(self, trace, dest, stage_prefix, obsdir, seam, ctx):
        rawops, checks, _, completion = self.parse(Path(trace).read_text(errors="replace"))
        checks.update(marks_check(rawops, seam))
        events, failed = to_events(rawops, dest, stage_prefix, obsdir)
        return events, failed, completion, checks

    def selftest(self, root):
        d = root / "observer-selftest"
        d.mkdir(parents=True, exist_ok=True)
        probe = d / "probe.txt"
        probe.write_text("probe\n")
        script = ("cat '%s' >/dev/null; (cat '%s' >/dev/null); "
                  ": > '%s/created.txt'; (exec 3</dev/loop0) 2>/dev/null; true") % (probe, probe, d)
        trace = d / "trace.txt"
        p = subprocess.run(self.wrap(["sh", "-c", script], trace), capture_output=True)
        text = trace.read_text(errors="replace")
        rawops, integ, _, completion = self.parse(text)
        opens = [l for l in text.splitlines() if "probe.txt" in l and "openat(" in l]
        checks = {
            "process_exit_zero": p.returncode == 0,
            "two_probe_opens_seen": len(opens) >= 2,
            "child_process_followed": len({l.split()[0] for l in opens}) >= 2,
            "creation_seen": "created.txt" in text and "O_CREAT" in text,
            "forbidden_device_open_seen": any(r["kind"] == "device" for r in rawops),
            "process_completion_seen": completion == "exited 0",
            "positive_trace_integrity": all(integ.values()),
        }
        lines = text.splitlines()
        tally_at = next(i for i, l in enumerate(lines) if l.startswith("% time"))
        dev = next(i for i, l in enumerate(lines) if "/dev/loop0" in l)
        probe_open = next(i for i, l in enumerate(lines) if "probe.txt" in l and "openat(" in l)
        mutations = {
            "drop_forbidden_device_open": lines[:dev] + lines[dev + 1:],
            "drop_probe_open": lines[:probe_open] + lines[probe_open + 1:],
            "truncate_before_tally": lines[:tally_at],
            "truncate_mid_trace": lines[:tally_at // 2],
            "drop_root_exit": [l for l in lines if not (l.startswith(lines[0].split()[0] + " ") and "+++ exited" in l)],
        }
        controls = write_controls(d, mutations, lambda txt: all(self.parse(txt)[1].values()))
        return finish_selftest(d, "strace", checks, controls, {"trace": "trace.txt", "trace_sha256": sha_file(trace)})


def write_controls(d, mutations, accepts):
    """Each deliberate mutation of a qualified positive trace must be REJECTED by the
    observer's own integrity checks; the mutated bytes are kept for review."""
    cd = d / "controls"
    cd.mkdir(exist_ok=True)
    out = {}
    for name, lines in mutations.items():
        body = "\n".join(lines) + "\n"
        (cd / f"{name}.txt").write_text(body)
        out[name] = {"file": f"controls/{name}.txt", "sha256": sha_file(cd / f"{name}.txt"),
                     "rejected": not accepts(body)}
    return out


def finish_selftest(d, kind, checks, controls, extra):
    ok = all(checks.values()) and all(c["rejected"] for c in controls.values())
    for name, passed in checks.items():
        if not passed:
            print(f"observer selftest check failed: {name}", file=sys.stderr)
    for name, c in controls.items():
        if not c["rejected"]:
            print(f"observer false-pass control NOT rejected: {name}", file=sys.stderr)
    (d / "result.json").write_bytes(canonical(dict(observer=kind, qualified=ok, checks=checks,
                                                   false_pass_controls=controls, **extra)))
    return ok


# ---- macOS: fs_usage ---------------------------------------------------------------------

F_LINE = re.compile(r"^(\d\d:\d\d:\d\d\.\d+)\s+(\S+)\s+(.*?)\s+(\d+\.\d+)\s+W?\s*(\S+)\s*$")
F_DEVICE = re.compile(r"(^|\s)/dev/(r?disk\d|sd|nvme)")
GATE = "ingestgate"


class FsUsage:
    """One fs_usage session per run, filtered to the observed command names. fs_usage
    runs on a pty so it line-buffers; a gate process stat-ing a unique path marks the
    start (session is live) and the end (everything up to after the run's exit has
    been emitted)."""
    kind = "fs_usage"
    deferred = False
    serial = True
    names = ["ingest", GATE, "probe-parent", "probe-child"]

    def __init__(self):
        self.tools = None
        self.n = 0
        self.diagnosed = False

    def version(self):
        return "fs_usage (macOS " + subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True).stdout.strip() + ")"

    def start(self, root):
        self.tools = root / "observer-tools"
        self.tools.mkdir(parents=True, exist_ok=True)
        for src, name in (("/bin/sh", GATE), ("/bin/sh", "probe-parent"), ("/bin/cat", "probe-child")):
            # contents and mode only: system binaries carry flags a user may not copy
            shutil.copyfile(src, self.tools / name)
            os.chmod(self.tools / name, 0o755)

    def stop(self):
        # keep identities, not copies of system binaries
        rec = {p.name: {"copied_from": src, "sha256": sha_file(p)} for p, src in
               ((self.tools / GATE, "/bin/sh"), (self.tools / "probe-parent", "/bin/sh"), (self.tools / "probe-child", "/bin/cat"))}
        (self.tools / "tools.json").write_bytes(canonical(rec))
        for name in (GATE, "probe-parent", "probe-child"):
            (self.tools / name).unlink()

    def wrap(self, argv, trace):
        return argv

    def _gate(self, tag):
        self.n += 1
        token = str(self.tools / f"gate-{tag}-{os.getpid()}-{self.n}")
        subprocess.run([str(self.tools / GATE), "-c", f"test -e '{token}'; true"])
        return token

    def before(self, trace, ctx):
        import pty
        master, slave = pty.openpty()
        out = open(trace, "wb")
        p = subprocess.Popen(["sudo", "-n", "fs_usage", "-w", "-f", "filesys", "-f", "exec"] + self.names,
                             stdout=slave, stderr=slave, stdin=subprocess.DEVNULL)
        os.close(slave)

        def pump():
            while True:
                try:
                    b = os.read(master, 65536)
                except OSError:
                    break
                if not b:
                    break
                out.write(b)
                out.flush()
        t = threading.Thread(target=pump, daemon=True)
        t.start()
        ctx.update(proc=p, master=master, out=out, pump=t)
        ctx["start_gate"] = self._wait_gate("start", trace)
        if not ctx["start_gate"] and not self.diagnosed:
            self.diagnosed = True
            raw = Path(trace).read_bytes()
            print(f"fs_usage start gate not seen; fs_usage running={p.poll() is None} rc={p.returncode} "
                  f"bytes={len(raw)}; first lines:", file=sys.stderr)
            for l in raw.decode("utf-8", "replace").splitlines()[:40]:
                print("  | " + l, file=sys.stderr)

    def _wait_gate(self, tag, trace, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            token = self._gate(tag)
            if token in Path(trace).read_bytes().decode("utf-8", "replace"):
                return token
            time.sleep(0.05)
        return None

    def after(self, trace, ctx):
        ctx["end_gate"] = self._wait_gate("end", trace)
        p = ctx["proc"]
        p.send_signal(signal.SIGINT)
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            subprocess.run(["sudo", "-n", "kill", "-9", str(p.pid)])
            p.wait()
        ctx["pump"].join(timeout=5)
        os.close(ctx["master"])
        ctx["out"].close()
        for k in ("proc", "master", "out", "pump"):
            ctx.pop(k, None)

    @staticmethod
    def parse(text, names=("ingest",)):
        rawops, fds, warn = [], {}, []
        for n, l in enumerate(text.replace("\r", "").splitlines()):
            if re.search(r"wrap|drop|lost", l, re.I) and not F_LINE.match(l):
                warn.append(l)
            m = F_LINE.match(l)
            if not m:
                continue
            _, call, mid, _, who = m.groups()
            cmd = who.rsplit(".", 1)[0]
            if cmd not in names:
                continue
            errno = re.search(r"\[\s*(\d+)\]", mid)
            ok = errno is None
            fd = re.search(r"F=(\d+)", mid)
            flags = re.search(r"\(([A-Z_]+)\)", mid)
            path = re.search(r"(/\S.*)$", mid.strip())
            path = path.group(1).strip() if path else ""
            key = f"{who}:{fd.group(1)}" if fd else None
            mk = mark_of(path)
            if mk and call.startswith(("stat", "lstat", "getattrlist", "fstatat")):
                rawops.append({"kind": "mark", "seq": mk[0], "op": mk[1], "line": n})
                continue
            if call.startswith("open"):
                if F_DEVICE.search(" " + path):
                    rawops.append({"kind": "device", "path": path, "line": n})
                creating = bool(flags and "C" in flags.group(1))
                rawops.append({"kind": "create" if creating else "open", "path": path, "ok": ok, "line": n})
                if ok and key:
                    fds[key] = path
            elif call.startswith("mkdir"):
                rawops.append({"kind": "mkdir", "path": path, "ok": ok, "line": n})
            elif call.startswith("fsync") or (call.startswith("fcntl") and "FULLFSYNC" in mid):
                if key:
                    rawops.append({"kind": "flush", "key": key, "path": fds.get(key, ""), "ok": ok, "line": n})
            elif call.startswith("close"):
                if key:
                    rawops.append({"kind": "close", "key": key, "path": fds.pop(key, ""), "ok": ok, "line": n})
            elif call.startswith("rename"):
                rawops.append({"kind": "rename", "path": path, "dst": None,
                               "noreplace": call.startswith(("renamex_np", "renameatx_np")), "ok": ok, "line": n,
                               "result": errno.group(1) if errno else "0"})
        return rawops, fds, warn

    def normalize(self, trace, dest, stage_prefix, obsdir, seam, ctx):
        text = Path(trace).read_bytes().decode("utf-8", "replace")
        rawops, open_fds, warn = self.parse(text)
        exited = ctx.get("exit") is not None
        checks = {
            "start_gate_seen": bool(ctx.get("start_gate")) and ctx["start_gate"] in text,
            "end_gate_seen_after_exit": bool(ctx.get("end_gate")) and ctx["end_gate"] in text,
            "no_tracer_loss_warning": not warn,
            "every_open_closed": not [k for k in open_fds if k.split(".")[0] == "ingest"] or not exited,
        }
        checks.update(marks_check(rawops, seam))
        events, failed = to_events(rawops, dest, stage_prefix, obsdir)
        completion = ("exited %s" % ctx["exit"]) if (exited and checks["end_gate_seen_after_exit"]) else None
        return events, failed, completion, checks

    def selftest(self, root):
        d = root / "observer-selftest"
        d.mkdir(parents=True, exist_ok=True)
        probe = d / "probe.txt"
        probe.write_text("probe\n")
        child = self.tools / "probe-child"
        script = (f"'{child}' '{probe}' >/dev/null; ('{child}' '{probe}' >/dev/null); "
                  f": > '{d}/created.txt'; (exec 3</dev/disk0) 2>/dev/null; true")
        trace = d / "trace.txt"
        ctx = {}
        self.before(trace, ctx)
        p = subprocess.run([str(self.tools / "probe-parent"), "-c", script], capture_output=True)
        ctx["exit"] = p.returncode
        self.after(trace, ctx)
        text = trace.read_bytes().decode("utf-8", "replace")
        names = ("probe-parent", "probe-child")
        rawops, fds, warn = self.parse(text, names)
        lines = text.replace("\r", "").splitlines()
        probe_lines = [l for l in lines if "probe.txt" in l and F_LINE.match(l) and F_LINE.match(l).group(2).startswith("open")]
        checks = {
            "process_exit_zero": p.returncode == 0,
            "start_and_end_gates_seen": bool(ctx.get("start_gate")) and bool(ctx.get("end_gate")),
            "two_probe_opens_seen": len(probe_lines) >= 2,
            "child_process_seen": any(F_LINE.match(l).group(5).startswith("probe-child.") for l in probe_lines),
            "creation_seen": any(r["kind"] == "create" and r["path"].endswith("created.txt") for r in rawops),
            "forbidden_device_open_seen": any(r["kind"] == "device" for r in rawops),
            "no_tracer_loss_warning": not warn,
        }

        def accepts(txt):
            ro, _, w = self.parse(txt, names)
            return (not w and bool(ctx.get("start_gate")) and ctx["start_gate"] in txt
                    and bool(ctx.get("end_gate")) and ctx["end_gate"] in txt
                    and any(r["kind"] == "device" for r in ro)
                    and sum(1 for l in txt.splitlines() if "probe.txt" in l) >= 2)
        dev = next((i for i, l in enumerate(lines) if "/dev/disk0" in l), None)
        end = next((i for i, l in enumerate(lines) if ctx.get("end_gate") and ctx["end_gate"] in l), len(lines))
        probe_i = next((i for i, l in enumerate(lines) if "probe.txt" in l), None)
        mutations = {
            "drop_forbidden_device_open": lines[:dev] + lines[dev + 1:] if dev is not None else lines,
            "drop_probe_open": lines[:probe_i] + lines[probe_i + 1:] if probe_i is not None else lines,
            "truncate_before_end_gate": lines[:end],
            "truncate_mid_trace": lines[:max(1, end // 2)],
        }
        controls = write_controls(d, mutations, accepts)
        # The device-open drop cannot be caught by any fs_usage-internal count (it has
        # none); `accepts` here demands the deliberately planted open, so this control
        # shows the positive is load-bearing, not that an arbitrary drop is detectable.
        controls["drop_forbidden_device_open"]["detectable_without_planted_expectation"] = False
        return finish_selftest(d, "fs_usage", checks, controls,
                               {"trace": "trace.txt", "trace_sha256": sha_file(trace),
                                "limitation": "fs_usage carries no per-record sequence or call tally; dropped "
                                              "isolated unpaired records are not self-detectable"})


# ---- Windows: Process Monitor ------------------------------------------------------------

# raw disk (\\.\PhysicalDriveN, \Device\HarddiskN) or volume (\\.\C:, shown by Procmon as "C:")
W_DEVICE = re.compile(r"^(\\\\\.\\PhysicalDrive\d+|\\\\\.\\[A-Za-z]:\\?$|\\Device\\Harddisk|[A-Za-z]:\\?$)", re.I)


class Procmon:
    """One capture-filtered Procmon session for the whole packet. Cases run normally;
    after the session ends the PML is exported to CSV by Procmon, aligned with the
    PML's own records (procmon-parser), partitioned by process instance, and each
    case's extract becomes its raw trace."""
    kind = "procmon"
    deferred = True
    serial = False

    def __init__(self, exe):
        self.exe = exe
        self.session = None
        self.pending = []

    def version(self):
        try:
            import win32api  # noqa: F401  (not required)
        except ImportError:
            pass
        return f"Process Monitor ({Path(self.exe).name}, sha256 {sha_file(self.exe)})"

    def start(self, root):
        from procmon_parser import Rule, dump_configuration
        self.session = root / "observer-session"
        self.session.mkdir(parents=True, exist_ok=True)
        self.tools = root / "observer-tools"
        self.tools.mkdir(parents=True, exist_ok=True)
        py = Path(sys.executable)
        for name in ("probe-parent.exe", "probe-child.exe"):
            shutil.copy2(py, py.parent / name)
        self.probe_dir = py.parent
        rules = [Rule("Process_Name", "is", "ingest.exe", "include"),
                 Rule("Process_Name", "begins_with", "probe-", "include")]
        with open(self.session / "filter.pmc", "wb") as f:
            dump_configuration({"FilterRules": rules, "DestructiveFilter": 1}, f)
        self.pml = self.session / "session.pml"
        subprocess.Popen([self.exe, "/AcceptEula", "/Quiet", "/Minimized", "/LoadConfig",
                          str(self.session / "filter.pmc"), "/BackingFile", str(self.pml)])
        subprocess.run([self.exe, "/AcceptEula", "/WaitForIdle"], timeout=120)
        time.sleep(3)

    def stop(self):
        subprocess.run([self.exe, "/AcceptEula", "/Terminate"], timeout=600)
        time.sleep(3)
        self.csv = self.session / "session.csv"
        subprocess.run([self.exe, "/AcceptEula", "/Quiet", "/Minimized", "/OpenLog", str(self.pml),
                        "/SaveAs", str(self.csv)], timeout=3600)
        self._load()

    def _load(self):
        rows = list(csv.reader(open(self.csv, encoding="utf-8-sig", errors="replace", newline="")))
        self.header, self.rows = rows[0], rows[1:]
        col = {n: i for i, n in enumerate(self.header)}
        self.col = col
        self.align = {"csv_rows": len(self.rows)}
        try:
            from procmon_parser import ProcmonLogsReader
            with open(self.pml, "rb") as f:
                r = ProcmonLogsReader(f, should_get_stacktrace=False, should_get_details=False)
                self.align["pml_events"] = len(r)
                mism, samples = 0, []
                self.parent = {}
                for i in range(min(len(r), len(self.rows))):
                    e = r[i]
                    row = self.rows[i]
                    diff = [k for k, a, b in (("pid", row[col["PID"]], str(e.process.pid)),
                                              ("name", row[col["Process Name"]], e.process.process_name),
                                              ("path", row[col["Path"]] or "", e.path or "")) if a != b]
                    if diff:
                        mism += 1
                        if len(samples) < 8:
                            samples.append({"index": i, "fields": diff, "csv": row[:6],
                                            "pml": [e.process.process_name, e.process.pid, str(e.operation), e.path]})
                    self.parent[i] = e.process.parent_pid
                self.align["row_mismatches"] = mism
                self.align["mismatch_samples"] = samples
        except Exception as x:  # recorded, and it fails every case's integrity
            self.align["pml_error"] = f"{type(x).__name__}: {x}"
        self.align["aligned"] = (self.align.get("pml_events") == len(self.rows)
                                 and self.align.get("row_mismatches") == 0)
        # process instances: a PID's rows from its Process Start to its Process Exit
        self.instances = []
        live = {}
        for i, row in enumerate(self.rows):
            pid, op = row[col["PID"]], row[col["Operation"]]
            if op == "Process Start":
                live[pid] = {"pid": pid, "name": row[col["Process Name"]], "rows": [], "detail": row[col["Detail"]]}
                self.instances.append(live[pid])
            inst = live.get(pid)
            if inst is None:
                inst = live[pid] = {"pid": pid, "name": row[col["Process Name"]], "rows": [], "detail": "", "no_start": True}
                self.instances.append(inst)
            inst["rows"].append(i)
            if op == "Process Exit":
                inst["exit"] = row[col["Detail"]]
                live.pop(pid, None)

    def wrap(self, argv, trace):
        return argv

    def before(self, trace, ctx):
        pass

    def after(self, trace, ctx):
        pass

    def instances_for(self, pid, k):
        """The k-th ingest.exe instance of pid in session order (the runner registers
        every launch in start order), plus any process it created."""
        same = [x for x in self.instances if x["pid"] == str(pid) and x["name"].lower() == "ingest.exe"]
        if k >= len(same):
            return []
        return self._with_children([same[k]])

    def _with_children(self, roots):
        out = list(roots)
        col = self.col
        for r in roots:
            for i in r["rows"]:
                row = self.rows[i]
                if row[col["Operation"]] == "Process Create":
                    m = re.search(r"PID: (\d+)", row[col["Detail"]])
                    if m:
                        out += [x for x in self.instances if x["pid"] == m.group(1) and x["rows"] and x["rows"][0] > i][:1]
        return out

    def owner_of(self, token):
        """Instances whose Process Start command line carries token (a unique work path),
        plus any instance they created."""
        roots = [x for x in self.instances if token in x["detail"]]
        out = list(roots)
        col = self.col
        for r in roots:
            for i in r["rows"]:
                row = self.rows[i]
                if row[col["Operation"]] == "Process Create":
                    m = re.search(r"PID: (\d+)", row[col["Detail"]])
                    if m:
                        out += [x for x in self.instances if x["pid"] == m.group(1) and x["rows"] and x["rows"][0] > i][:1]
        return out

    def extract(self, trace, insts):
        idx = sorted(i for x in insts for i in x["rows"])
        with open(trace, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Index"] + self.header)
            for i in idx:
                w.writerow([i] + self.rows[i])
        return idx

    @staticmethod
    def parse_rows(rows, col):
        rawops, opened, open_ok = [], {}, {}
        for n, row in enumerate(rows):
            op, path, res, det = row[col["Operation"]], row[col["Path"]], row[col["Result"]], row[col["Detail"]]
            ok = res == "SUCCESS"
            mk = mark_of(path)
            if mk:
                rawops.append({"kind": "mark", "seq": mk[0], "op": mk[1], "line": n})
                continue
            if op == "CreateFile":
                if W_DEVICE.search(path):
                    rawops.append({"kind": "device", "path": path, "line": n})
                disp = re.search(r"Disposition: (\w+)", det)
                creating = bool(disp and disp.group(1) in ("Create", "OverwriteIf", "OpenIf", "Supersede")) and "OpenResult: Opened" not in det
                is_dir = "Directory File" in det and "Non-Directory File" not in det
                rawops.append({"kind": "mkdir" if (creating and is_dir) else ("create" if creating else "open"),
                               "path": path, "ok": ok, "line": n})
                if ok:
                    open_ok[path] = open_ok.get(path, 0) + 1
            elif op == "FlushBuffersFile":
                rawops.append({"kind": "flush", "key": path, "path": path, "ok": ok, "line": n})
            elif op == "CloseFile":
                rawops.append({"kind": "close", "key": path, "path": path, "ok": ok, "line": n})
                open_ok[path] = open_ok.get(path, 0) - 1
            elif op == "SetRenameInformationFile":
                dst = re.search(r"FileName: (.*?)(?:, \w+: |$)", det)
                rawops.append({"kind": "rename", "path": path, "dst": dst.group(1) if dst else None,
                               "noreplace": "ReplaceIfExists: False" in det, "ok": ok, "line": n, "result": res})
                if ok and dst:  # the renaming handle now carries the new name; its close is logged there
                    open_ok[path] = open_ok.get(path, 0) - 1
                    open_ok[dst.group(1)] = open_ok.get(dst.group(1), 0) + 1
        return rawops, open_ok

    def normalize(self, trace, dest, stage_prefix, obsdir, seam, ctx):
        insts = ctx["instances"]
        col = {n: i + 1 for i, n in enumerate(self.header)}
        rows = list(csv.reader(open(trace, encoding="utf-8", newline="")))[1:]
        rawops, open_ok = self.parse_rows(rows, col)
        root = insts[0] if insts else {}
        checks = {
            "session_pml_csv_aligned": bool(self.align.get("aligned")),
            "root_instance_found": bool(insts),
            "root_process_start_seen": bool(root) and not root.get("no_start"),
            "root_process_exit_seen": bool(root.get("exit")),
            "every_success_open_closed": all(v <= 0 for p, v in open_ok.items() if stage_prefix in p),
        }
        checks.update(marks_check(rawops, seam))
        events, failed = to_events(rawops, dest, stage_prefix, obsdir)
        completion = None
        if root.get("exit"):
            m = re.search(r"Exit Status: (-?\d+)", root["exit"])
            completion = "exited " + (m.group(1) if m else "?")
        return events, failed, completion, checks

    def selftest_run(self, root):
        """Runs inside the live session; judged in selftest_finish after stop()."""
        d = root / "observer-selftest"
        d.mkdir(parents=True, exist_ok=True)
        (d / "probe.txt").write_text("probe\n")
        child = self.probe_dir / "probe-child.exe"
        code = ("import ctypes,subprocess,sys;p=sys.argv[1];open(p).read();"
                "subprocess.run([sys.argv[2],'-c','import sys;open(sys.argv[1]).read()',p]);"
                "open(sys.argv[3],'w').close();"
                "k=ctypes.windll.kernel32;k.CreateFileW.restype=ctypes.c_void_p;"
                "[k.CloseHandle(ctypes.c_void_p(h)) for d in ('\\\\\\\\.\\\\PhysicalDrive0','\\\\\\\\.\\\\C:')"
                " for h in [k.CreateFileW(d,0,3,None,3,0,None)] if h not in (None,ctypes.c_void_p(-1).value)]")
        self.selftest_token = str(d / "probe.txt")
        p = subprocess.run([str(self.probe_dir / "probe-parent.exe"), "-c", code, str(d / "probe.txt"), str(child),
                            str(d / "created.txt")], capture_output=True)
        self.selftest_exit = p.returncode
        (d / "probe-stderr.txt").write_bytes(p.stderr)

    def selftest_finish(self, root, owners):
        d = root / "observer-selftest"
        col = self.col
        insts = [x for x in self.instances if x["name"].lower() in ("probe-parent.exe", "probe-child.exe")
                 and self.selftest_token in x["detail"]]
        parents = [x for x in insts if x["name"].lower() == "probe-parent.exe"]
        trace = d / "trace.txt"
        idx = self.extract(trace, insts)
        rows = [self.rows[i] for i in idx]
        rawops, _ = self.parse_rows(rows, col)
        probe_opens = [r for r in rows if r[col["Operation"]] == "CreateFile" and r[col["Path"]].endswith("probe.txt")]
        owners = dict(owners, **{"observer-selftest": idx})
        full = self.partition(owners)
        checks = {
            "process_exit_zero": self.selftest_exit == 0,
            "session_pml_csv_aligned": bool(self.align.get("aligned")),
            "session_fully_partitioned": full["unowned_count"] == 0 and full["multiply_owned"] == 0,
            "two_probe_opens_seen": len(probe_opens) >= 2,
            "child_process_seen": any(r[col["Process Name"]].lower() == "probe-child.exe" for r in probe_opens),
            "creation_seen": any(r["kind"] == "create" and r["path"].endswith("created.txt") and r["ok"] for r in rawops),
            "forbidden_device_open_seen": any(r["kind"] == "device" for r in rawops),
            "process_completion_seen": bool(parents) and bool(parents[0].get("exit")),
        }
        dev = next((i for i in idx if W_DEVICE.search(self.rows[i][col["Path"]])), None)
        probe_i = next((i for i in idx if self.rows[i][col["Path"]].endswith("probe.txt")), None)
        mut = {
            "drop_forbidden_device_open": [i for i in idx if i != dev],
            "drop_probe_open": [i for i in idx if i != probe_i],
            "truncate_tail": idx[: max(1, len(idx) * 2 // 3)],
            "truncate_mid_trace": idx[: max(1, len(idx) // 2)],
        }
        cd = d / "controls"
        cd.mkdir(exist_ok=True)
        controls = {}
        for name, kept in mut.items():
            p = cd / f"{name}.csv"
            with open(p, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Index"] + self.header)
                for i in kept:
                    w.writerow([i] + self.rows[i])
            res = self.partition(dict(owners, **{"observer-selftest": kept}), write=False)
            controls[name] = {"file": f"controls/{name}.csv", "sha256": sha_file(p),
                              "unowned_after_mutation": res["unowned_count"],
                              "rejected": res["unowned_count"] > 0 or res["multiply_owned"] > 0}
        self.partition(owners)
        device_like = [[i] + self.rows[i][1:6] for i in idx
                       if re.search(r"Physical|Harddisk|\\\\\.\\|\\Device\\", self.rows[i][col["Path"]], re.I)][:20]
        probe_err = (d / "probe-stderr.txt").read_bytes().decode("utf-8", "replace")[-2000:]
        pydir = str(self.probe_dir).lower()
        probe_paths = sorted({(self.rows[i][col["Operation"]], self.rows[i][col["Path"]], self.rows[i][col["Result"]])
                              for i in idx if not self.rows[i][col["Path"]].lower().startswith(pydir)})[:80]
        return finish_selftest(d, "procmon", checks, controls,
                               {"trace": "trace.txt", "trace_sha256": sha_file(trace), "session_alignment": self.align,
                                "device_like_rows": device_like, "probe_stderr_tail": probe_err,
                                "probe_paths_outside_python": probe_paths,
                                "detection": "every captured session record has exactly one owner (a case run, a "
                                             "shipping rerun or this selftest); an extract missing any record "
                                             "leaves that session index unowned"})

    def partition(self, owners, write=True):
        """owners: {owner: [session indices]} -> the session-wide assignment."""
        seen = {}
        for o, idx in owners.items():
            for i in idx:
                seen.setdefault(i, []).append(o)
        unowned = [i for i in range(len(self.rows)) if i not in seen]
        dup = {i: o for i, o in seen.items() if len(o) > 1}
        rec = {"records": len(self.rows), "owned": len(seen), "unowned_count": len(unowned),
               "unowned": [[i] + self.rows[i] for i in unowned[:200]], "multiply_owned": len(dup),
               "alignment": self.align, "owners": {o: len(v) for o, v in owners.items()}}
        if write:
            (self.session / "partition.json").write_bytes(canonical(rec))
        return rec

    def compress(self):
        for p in (self.pml, self.csv):
            with open(p, "rb") as a, gzip.open(str(p) + ".gz", "wb") as b:
                shutil.copyfileobj(a, b)
            (Path(str(p) + ".sha256")).write_text(sha_file(p) + "\n")
            os.remove(p)


class NoObserver:
    kind = "none"
    deferred = False
    serial = False

    def version(self):
        return "none"

    def start(self, root):
        pass

    def stop(self):
        pass

    def wrap(self, argv, trace):
        return argv

    def before(self, trace, ctx):
        pass

    def after(self, trace, ctx):
        Path(trace).write_bytes(b"")

    def normalize(self, trace, dest, stage_prefix, obsdir, seam, ctx):
        return [], [], None, {"native_observer": False}

    def selftest(self, root):
        d = root / "observer-selftest"
        d.mkdir(parents=True, exist_ok=True)
        (d / "result.json").write_bytes(canonical({"observer": "none", "qualified": False,
                                                   "reason": "no native observer on this host"}))
        return False


def make(kind, procmon=None):
    if kind == "strace":
        return Strace()
    if kind == "fs_usage":
        return FsUsage()
    if kind == "procmon":
        return Procmon(procmon)
    return NoObserver()
