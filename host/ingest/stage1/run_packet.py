#!/usr/bin/env python3
"""Software's observation transport for the imported INGEST-1 Stage1 package
(tests/wp16_ingest_stage1, INTERFACE.md). It runs the actual ingest commands and
writes one native packet: INDEX.json, the profile file, and per case the record,
stdout/stderr, native record and raw observer trace, plus outputs and the isolated
pre-gain observations for successes.

It judges nothing. Exit codes, PASS decisions and receipts are Verification's
(review.py / campaign.py with Verification's own receipts). Standard library only.

Native observers (stage1/observers.py): Linux strace, macOS fs_usage, Windows
Process Monitor. Each is qualified by its own selftest with positive probes and
deliberate dropped/truncated-record false-pass controls; a host without one records
observer "none", which the published review rejects -- an honest gap, never a
substitute.

usage: run_packet.py --package DIR --sources DIR --observe-bin BIN --shipping-bin BIN
                     --profile-dir DIR --out PACKET --candidate-sha SHA [--jobs N] [--only S]
"""
import argparse, concurrent.futures as cf, hashlib, json, os, platform, re, shutil, signal
import subprocess, sys, tempfile, threading, time, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import observers  # noqa: E402

CUTS_KILL = {"before-stage", "audio-open", "audio-flush", "manifest-open", "manifest-flush",
             "before-publish", "after-publish"}
def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def raw_arg(a):
    """One argv element as JSON. Valid Unicode stays a string; an element that is not (an
    APFS invalid-UTF-8 boundary argument, decoded by os.fsdecode with surrogateescape)
    keeps its exact native bytes, since a JSON string cannot hold them."""
    try:
        a.encode("utf-8")
        return a
    except UnicodeEncodeError:
        return {"bytes_hex": os.fsencode(a).hex(), "ascii": ascii(a)}


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def tree_sha(d):
    """sha256 over sorted (posix relative path, file sha256) lines of a directory."""
    lines = sorted(f"{p.relative_to(d).as_posix()} {sha_file(p)}" for p in Path(d).rglob("*") if p.is_file())
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def tool_out(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True).stdout.strip()
    except OSError as e:
        return f"unavailable: {e}"


def platform_id():
    s = sys.platform
    m = platform.machine().lower()
    arch = "arm64" if m in ("arm64", "aarch64") else "x64" if m in ("x86_64", "amd64") else m
    if s.startswith("linux"):
        return "linux", arch
    if s == "darwin":
        return "macos", arch
    if s.startswith("win"):
        # Only a Windows 11 client is the required platform; a Server edition (GitHub's
        # windows-latest) is not a substitute and must not carry that label.
        edition = (platform.win32_edition() or "").lower()
        build = int(platform.version().split(".")[-1] or 0)
        if "server" in edition or build < 22000:
            return "windows-server-" + (edition or "unknown"), arch
        return "windows11", arch
    return s, arch


# ---- Windows bounded memory (Job object) --------------------------------------------------

def _job_structs():
    import ctypes
    from ctypes import wintypes

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rt", "wt", "ot")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class EXT(ctypes.Structure):
        _fields_ = [("Basic", BASIC), ("Io", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]
    return ctypes, wintypes, EXT


def windows_memory_job(limit):
    """A Job object with JOB_OBJECT_LIMIT_PROCESS_MEMORY: the OS fails commits beyond it."""
    ctypes, wintypes, EXT = _job_structs()
    k = ctypes.windll.kernel32
    k.CreateJobObjectW.restype = wintypes.HANDLE
    job = k.CreateJobObjectW(None, None)
    info = EXT()
    info.Basic.LimitFlags = 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
    info.ProcessMemoryLimit = int(limit)
    if not k.SetInformationJobObject(wintypes.HANDLE(job), 9, ctypes.byref(info), ctypes.sizeof(info)):
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
    return job


def windows_job_assign_and_resume(job, p):
    ctypes, wintypes, _ = _job_structs()
    h = wintypes.HANDLE(int(p._handle))
    if not ctypes.windll.kernel32.AssignProcessToJobObject(wintypes.HANDLE(job), h):
        p.kill()
        raise OSError("AssignProcessToJobObject failed")
    ctypes.windll.ntdll.NtResumeProcess(h)


def windows_job_peak(job):
    ctypes, wintypes, EXT = _job_structs()
    info = EXT()
    ctypes.windll.kernel32.QueryInformationJobObject(wintypes.HANDLE(job), 9, ctypes.byref(info),
                                                     ctypes.sizeof(info), None)
    ctypes.windll.kernel32.CloseHandle(wintypes.HANDLE(job))
    return int(info.PeakProcessMemoryUsed)


# ---- case setup --------------------------------------------------------------------------

def place(src, dst):
    """Copy small sources (a mutation scenario must never touch the pack); link huge ones."""
    if os.path.getsize(src) > 64 << 20:
        os.link(src, dst)
    else:
        shutil.copyfile(src, dst)


def setup_case(case, w, assets):
    """Build the case's inputs under w; return (argv_tail, dest, env, notes)."""
    inp, outp = w / "in", w / "out"
    inp.mkdir()
    outp.mkdir()
    (outp / "unrelated.txt").write_text("unrelated sentinel\n")
    dest = outp / "DEST"
    folders = []
    for i, f in enumerate(case["folders"]):
        d = inp / f"f{i}"
        d.mkdir()
        for e in f:
            place(assets / e["asset"], os.path.join(os.fsencode(d), os.fsencode(e["name"])))
        folders.append(str(d))
    cid, env, notes, capability = case["id"], {}, [], {}
    length = str(case["seconds"])
    head = ["--out", str(dest), "--length", length]
    tail = folders
    if cid == "native/folder-missing":
        shutil.rmtree(folders[0]); notes.append("folder removed before the run")
    elif cid == "native/folder-empty":
        for x in Path(folders[0]).iterdir():
            x.unlink()
    elif cid == "native/folder-duplicate":
        tail = [folders[0], folders[0] + "/../f0"]
    elif cid == "native/folder-symlink":
        os.rename(folders[0], str(inp / "real")); os.symlink(str(inp / "real"), folders[0])
    elif cid == "native/file-symlink":
        os.symlink("short.wav", os.path.join(folders[0], "link.wav"))
    elif cid == "native/nested-directory":
        os.mkdir(os.path.join(folders[0], "sub"))
    elif cid == "native/hidden-file":
        Path(folders[0], ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1" + bytes(64))
    elif cid == "native/artwork":
        Path(folders[0], "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + bytes(64) + b"\xff\xd9")
    elif cid == "native/invalid-unicode":
        # The literal case: a file whose native name is not valid Unicode. Linux names
        # are bytes; NTFS names are UTF-16 and keep a lone surrogate. APFS refuses such
        # a name itself; that refusal is recorded, and the corresponding native
        # boundary -- an invalid-Unicode path argument -- is exercised instead.
        src = os.path.join(folders[0], "short.wav")
        if sys.platform.startswith("linux"):
            shutil.copyfile(src, os.path.join(os.fsencode(folders[0]), b"bad\xff.wav"))
        elif sys.platform == "win32":
            shutil.copyfile(src, os.path.join(folders[0], "bad\ud800.wav"))
            listing = os.listdir(folders[0])
            capability["created"] = [ascii(n) for n in listing]
            if not any("\ud800" in n for n in listing):
                raise Unavailable("filesystem did not keep a lone-surrogate name: " + ascii(listing))
        else:
            target = os.path.join(os.fsencode(folders[0]), b"bad\xff.wav")
            try:
                shutil.copyfile(src, target)
                capability["created"] = True
            except OSError as x:
                capability.update(attempt=ascii(target), refused_errno=x.errno, refused=os.strerror(x.errno or 0),
                                  listing=sorted(os.listdir(folders[0])))
                boundary = os.fsdecode(os.fsencode(folders[0]) + b"/bad\xff")
                tail = [folders[0], boundary]
                notes.append("APFS refuses a non-UTF-8 file name (errno recorded); boundary run passes an "
                             "invalid-UTF-8 folder argument beside the real folder")
    elif cid == "native/nfc-collision":
        src = os.path.join(folders[0], "short.wav")
        shutil.copyfile(src, os.path.join(folders[0], "\u00e9.wav"))  # precomposed
        shutil.copyfile(src, os.path.join(folders[0], "e\u0301.wav"))  # e + combining acute
        listing = sorted(os.listdir(folders[0]))
        capability.update(listing=[ascii(n) for n in listing])
        if len(listing) < 3:
            # Normalization-insensitive filesystem: both spellings name ONE file. Remove
            # it, and exercise the same exclusion at the folder level: one folder named
            # with NFC, passed once as NFC and once as NFD (same native identity).
            capability["normalization_insensitive"] = True
            for n in listing:
                if n != "short.wav":
                    os.remove(os.path.join(folders[0], n))
            nfc = inp / "f\u00e9"
            os.rename(folders[0], nfc)
            tail = [str(nfc), str(inp / "fe\u0301")]
            notes.append("normalization-insensitive filesystem kept one file for both spellings; boundary run "
                         "passes one folder spelled NFC and NFD")
    elif cid == "native/case-unrepresentable":
        src = os.path.join(folders[0], "short.wav")
        shutil.copyfile(src, os.path.join(folders[0], "a.wav"))
        shutil.copyfile(src, os.path.join(folders[0], "A.wav"))
        listing = sorted(os.listdir(folders[0]))
        capability.update(listing=listing)
        if len(listing) < 3:
            capability["case_insensitive"] = True
            for n in listing:
                if n.lower() == "a.wav":
                    os.remove(os.path.join(folders[0], n))
            cased = inp / "Case"
            os.rename(folders[0], cased)
            tail = [str(cased), str(inp / "CASE")]
            notes.append("case-insensitive filesystem kept one file for a.wav/A.wav; boundary run passes one "
                         "folder spelled Case and CASE")
    elif cid == "native/dest-exists":
        dest.mkdir(); (dest / "keep.txt").write_text("existing data\n")
    elif cid == "native/syntax-missing-out":
        head = ["--length", length]
    elif cid == "native/syntax-zero-length":
        head = ["--out", str(dest), "--length", "0"]
    elif cid == "native/syntax-negative-length":
        head = ["--out", str(dest), "--length", "-1"]
    elif cid == "native/syntax-fractional-length":
        head = ["--out", str(dest), "--length", "1.5"]
    elif cid == "native/syntax-overflow-length":
        head = ["--out", str(dest), "--length", "9" * 40]
    elif cid == "native/unknown-option":
        head = head + ["--bogus"]
    elif cid in ("cli/help", "cli/version"):
        head, tail = ["--" + cid.split("/")[1]], []
    sc = case.get("scenario")
    if sc == "kill":
        env["INGEST_KILL_AT"] = case.get("cut") or "audio-flush"
    elif sc == "write-error" and cid != "resources/exhaustion":
        env["INGEST_FAULT"] = case.get("cut") or "audio-write"
    elif sc == "mutation":
        env["INGEST_PAUSE_AT"] = "preflight_complete"
        env["INGEST_PAUSE_FILE"] = str(w / "resume")
    elif sc == "concurrent-dest":
        env["INGEST_PAUSE_AT"] = "before-publish"
        env["INGEST_PAUSE_FILE"] = str(w / "resume")
    return head + tail, dest, env, notes, capability


def snapshot(d):
    if not d.exists():
        return [], None
    names = sorted(x.name for x in d.iterdir())
    h = hashlib.sha256()
    for n in names:
        p = d / n
        h.update(n.encode() + b"\0" + (sha_file(p).encode() if p.is_file() else b"<dir>") + b"\n")
    return names, h.hexdigest()


# ---- one run -----------------------------------------------------------------------------

class Runner:
    def __init__(self, a, observer, selftest_ok):
        self.a, self.obs, self.selftest_ok = a, observer, selftest_ok
        self.assets = Path(a.sources) / "assets"
        self.root = Path(a.out)
        self.config_sha = None
        self.lock = threading.Lock()
        self.launches, self.pending, self.unobserved = {}, [], []
        self.exhaust = None

    def launch(self, cmd, env, job=None, **kw):
        """Start an ingest process and register it: on Windows the observer attributes
        process instances by (pid, n-th launch of that pid), so every ingest launch --
        observation or shipping -- is registered in start order."""
        flags = 0x4 if job is not None else 0  # CREATE_SUSPENDED until it is in the job
        p = subprocess.Popen(cmd, env=env, creationflags=flags, **kw) if os.name == "nt" else \
            subprocess.Popen(cmd, env=env, **kw)
        if job is not None:
            windows_job_assign_and_resume(job, p)
        with self.lock:
            k = self.launches.get(p.pid, 0)
            self.launches[p.pid] = k + 1
        return p, k

    def invoke(self, argv_tail, dest, env, w, tag, case, exhaust=None):
        obsdir = w / f"obs-{tag}"
        (obsdir / ".mark").mkdir(parents=True)
        trace = w / f"trace-{tag}.txt"
        argv = [self.a.observe_bin] + argv_tail
        cmd = argv
        e = dict(os.environ, INGEST_OBSERVE_DIR=str(obsdir), **env)
        job = None
        if exhaust is not None:
            if exhaust["method"].startswith("prlimit"):
                cmd = ["prlimit", f"--as={exhaust['bytes']}", "--"] + cmd
            elif exhaust["method"].startswith("INGEST_HEAP_LIMIT"):
                e["INGEST_HEAP_LIMIT"] = str(exhaust["bytes"])
            else:
                job = windows_memory_job(exhaust["bytes"])
        cmd = self.obs.wrap(cmd, trace)
        stage_prefix = "." + dest.name + ".ingest-stage-"
        unrelated = dest.parent / "unrelated.txt"
        before_unrel = sha_file(unrelated)
        dest_before, dest_before_sha = snapshot(dest)
        ctx = {}
        self.obs.before(trace, ctx)
        p, k = self.launch(cmd, e, job, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        competitor = None
        if "INGEST_PAUSE_AT" in env:
            waiting = Path(env["INGEST_PAUSE_FILE"] + ".waiting")
            deadline = time.time() + 600
            while not waiting.exists() and p.poll() is None and time.time() < deadline:
                time.sleep(0.02)
            if case.get("scenario") == "mutation":
                src = os.fsdecode(case_input(w, 0, case["folders"][0][0]["name"]))
                with open(src, "ab") as f:
                    f.write(b"\0")
            else:
                dest.mkdir()
                (dest / "competitor.txt").write_text("concurrent writer\n")
                competitor = sha_file(dest / "competitor.txt")
            Path(env["INGEST_PAUSE_FILE"]).write_text("")
        out, err = p.communicate()
        code = p.returncode
        peak = windows_job_peak(job) if job is not None else None
        if code is not None and code < 0:
            code = None  # killed by a signal
        if (obsdir / "events.jsonl").exists() and '"op":"kill"' in (obsdir / "events.jsonl").read_text():
            code = None  # the seam aborted at a kill cut (Windows reports a fail-fast status)
        ctx["exit"] = p.returncode
        self.obs.after(trace, ctx)
        dest_after, dest_after_sha = snapshot(dest)
        stage_left = [x.name for x in dest.parent.iterdir() if x.name.startswith(stage_prefix)]
        seam = []
        if (obsdir / "events.jsonl").exists():
            seam = [json.loads(l) for l in (obsdir / "events.jsonl").read_text().splitlines() if l.strip()]
        native = {
            "scenario": None, "exit": code, "raw_trace_sha256": None, "observer": self.obs.kind,
            "observer_selftest": self.selftest_ok, "seam_events": seam, "dest_after": dest_after,
            "owned_stage_after": bool(stage_left), "unrelated_unchanged": sha_file(unrelated) == before_unrel,
            "binary_sha256": sha_file(self.a.observe_bin), "argv": [raw_arg(x) for x in argv], "env": env,
            "process_exit_status": p.returncode,
        }
        if self.obs.deferred:
            Path(trace).write_bytes(b"")
            native.update(events=[], failed_ops=[], complete=False, process_completion=None,
                          integrity={"session_pending": False})
            native["_pending"] = {"pid": p.pid, "k": k, "dest": str(dest), "stage_prefix": stage_prefix,
                                  "obsdir": str(obsdir), "seam": seam, "argv": cmd}
        else:
            events, failed, completion, checks = self.obs.normalize(trace, dest, stage_prefix, obsdir, seam, ctx)
            native.update(events=events, failed_ops=failed, process_completion=completion, integrity=checks,
                          complete=completion is not None and all(checks.values()))
        native["raw_trace_sha256"] = sha_file(trace)
        if peak is not None:
            native["job_peak_process_memory"] = peak
        if dest_before:
            native["dest_before"] = dest_before
            native["dest_before_sha256"] = dest_before_sha
            native["dest_after_sha256"] = dest_after_sha
        if competitor is not None:
            native["competitor_unchanged"] = (dest / "competitor.txt").exists() and sha_file(dest / "competitor.txt") == competitor
        return code, out, err, trace, native, obsdir

    def write_native(self, native, native_path, trace_path):
        pend = native.pop("_pending", None)
        native_path.write_bytes(canonical(native))
        if pend is not None:
            with self.lock:
                self.pending.append((native_path, trace_path, pend))

    def run_case(self, n, case):
        a = self.a
        cdir = self.root / "cases" / f"{n:04d}"
        if (cdir / "record.json").exists():
            return case["id"], f"cases/{n:04d}/record.json"
        cdir.mkdir(parents=True, exist_ok=True)
        w = Path(tempfile.mkdtemp(dir=a.work))
        try:
            try:
                tail, dest, env, notes, capability = setup_case(case, w, self.assets)
            except (Unavailable, OSError) as x:
                return case["id"], self.unavailable(n, cdir, case, str(x))
            exhaust = self.exhaust if case["id"] == "resources/exhaustion" else None
            code, out, err, trace, native, obsdir = self.invoke(tail, dest, env, w, "main", case, exhaust)
            sc = case.get("scenario") or ("success" if code == 0 else "preflight-refusal" if code == 2 else "write-error")
            native["scenario"] = sc
            native["diagnostic_ok"] = bool(err.strip()) and err.decode("utf-8", "replace").startswith("ingest:")
            native["setup_notes"] = notes
            if capability:
                native["filesystem_capability"] = capability
            if exhaust is not None:
                native["resource_limit"] = exhaust
            (cdir / "stdout.txt").write_bytes(out)
            (cdir / "stderr.txt").write_bytes(err)
            shutil.move(str(trace), cdir / "trace.txt")
            self.write_native(native, cdir / "native.json", cdir / "trace.txt")
            rec = {"exit": code, "argv": [raw_arg(x) for x in [os.path.basename(a.observe_bin)] + tail],
                   "config_sha256": self.config_sha,
                   "stdout_file": f"cases/{n:04d}/stdout.txt", "stderr_file": f"cases/{n:04d}/stderr.txt",
                   "native_record": f"cases/{n:04d}/native.json", "raw_trace": f"cases/{n:04d}/trace.txt"}
            if native["dest_after"] == ["audio.wav", "manifest.json"]:
                self.collect(rec, cdir, n, dest, obsdir, out)
                if code == 0:
                    rec["shipping_equivalence"] = self.shipping_equivalence(tail, dest, w, cdir)
            if case.get("relation") and code == 0:
                rec["comparisons"] = self.compare(case, w, n, cdir, tail, dest)
            (cdir / "record.json").write_bytes(canonical(rec))
            return case["id"], f"cases/{n:04d}/record.json"
        finally:
            shutil.rmtree(w, ignore_errors=True)

    def unavailable(self, n, cdir, case, why):
        """A case this platform cannot set up faithfully: recorded, never run in a
        weakened form. The published review fails it; it is an honest gap."""
        for name in ("stdout.txt", "stderr.txt", "trace.txt"):
            (cdir / name).write_bytes(b"")
        native = {"scenario": case.get("scenario") or "unavailable", "exit": None, "complete": False,
                  "raw_trace_sha256": sha_file(cdir / "trace.txt"), "observer": self.obs.kind,
                  "observer_selftest": self.selftest_ok, "events": [], "dest_after": [],
                  "owned_stage_after": False, "unrelated_unchanged": True, "unavailable": why}
        (cdir / "native.json").write_bytes(canonical(native))
        rec = {"exit": None, "argv": [], "config_sha256": self.config_sha, "unavailable": why,
               "stdout_file": f"cases/{n:04d}/stdout.txt", "stderr_file": f"cases/{n:04d}/stderr.txt",
               "native_record": f"cases/{n:04d}/native.json", "raw_trace": f"cases/{n:04d}/trace.txt"}
        (cdir / "record.json").write_bytes(canonical(rec))
        return f"cases/{n:04d}/record.json"

    def finalize(self):
        """Session observers (Procmon): after the session ends, give every pending run
        its extract as raw trace, normalize it, and partition the whole session."""
        obs = self.obs
        owners = {}
        for native_path, trace_path, pend in self.pending:
            # Two independent bindings must name the same process instance: the runner's
            # (pid, n-th launch of that pid) and the exact command line Procmon recorded.
            insts = obs.instances_for(pend["pid"], pend["k"])
            by_cmd = obs.instances_for_cmdline(subprocess.list2cmdline(pend["argv"]))
            agrees = bool(insts) and len(by_cmd) == 1 and insts[0] is by_cmd[0]
            if not agrees:
                insts = []
            idx = obs.extract(trace_path, insts)
            owners[str(native_path.relative_to(self.root))] = idx
            native = json.loads(native_path.read_text(encoding="utf-8"))
            events, failed, completion, checks = obs.normalize(
                trace_path, Path(pend["dest"]), pend["stage_prefix"], Path(pend["obsdir"]), pend["seam"],
                {"instances": insts})
            native.update(events=events, failed_ops=failed, process_completion=completion, integrity=checks,
                          complete=completion is not None and all(checks.values()),
                          raw_trace_sha256=sha_file(trace_path), observer_selftest=self.selftest_ok,
                          session_record_indices=idx, session_binding_agrees=agrees,
                          session_binding={k: pend[k] for k in ("pid", "k", "dest", "stage_prefix", "obsdir")})
            native_path.write_bytes(canonical(native))
        for pid, k, tag in self.unobserved:
            owners[tag] = [i for x in obs.instances_for(pid, k) for i in x["rows"]]
        return owners

    def collect(self, rec, cdir, n, dest, obsdir, out):
        shutil.move(str(dest / "audio.wav"), cdir / "audio.wav")
        shutil.move(str(dest / "manifest.json"), cdir / "manifest.json")
        rec["wav"], rec["manifest"] = f"cases/{n:04d}/audio.wav", f"cases/{n:04d}/manifest.json"
        bd = obsdir / "before"
        (cdir / "before").mkdir(exist_ok=True)
        files = sorted(bd.iterdir(), key=lambda p: int(p.stem)) if bd.exists() else []
        big = [p for p in files if p.suffix == ".json"]
        # The compact entire-zero form is INTERFACE's for capacity/riff-largest-legal only;
        # every other silent source gets its zero floats written out.
        if len(files) == 1 and big and json.loads(big[0].read_text())["frames"] > (1 << 26):
            rec["before"] = json.loads(big[0].read_text())
        else:
            rec["before"] = []
            for p in files:
                if p.suffix == ".json":
                    frames = json.loads(p.read_text())["frames"]
                    with open(cdir / "before" / f"{p.stem}.f64", "wb") as f:
                        f.truncate(frames * 16)
                else:
                    shutil.move(str(p), cdir / "before" / p.name)
                rec["before"].append(f"cases/{n:04d}/before/{p.stem}.f64")
        j = json.loads((obsdir / "joined.json").read_text())
        rec["joined_dbtp"] = j["joined_dbtp"]
        m = re.search(rb"peak-limited (\d+), unmeasurable (\d+), gapless-unknown (\d+)", out)
        rec["summary"] = {"peak_limited": int(m.group(1)), "unmeasurable": int(m.group(2)),
                          "gapless_unknown": int(m.group(3))} if m else None

    def shipping_equivalence(self, tail, dest, w, cdir):
        """Rerun the same inputs with the SHIPPING binary (no seam, no observer) and
        compare published bytes with the observation build's."""
        d2 = dest.parent / "SHIPPING"
        argv = [self.a.shipping_bin, "--out", str(d2)] + tail[2:]
        p, k = self.launch(argv, None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()
        with self.lock:
            self.unobserved.append((p.pid, k, f"shipping:{cdir.name}"))
        res = {"shipping_binary_sha256": sha_file(self.a.shipping_bin), "exit": p.returncode,
               "argv": [raw_arg(x) for x in [os.path.basename(self.a.shipping_bin)] + argv[1:]]}
        if p.returncode == 0:
            for name in ("audio.wav", "manifest.json"):
                res[name] = {"shipping_sha256": sha_file(d2 / name),
                             "observe_sha256": sha_file(cdir / name)}
            res["identical"] = all(res[k]["shipping_sha256"] == res[k]["observe_sha256"] for k in ("audio.wav", "manifest.json"))
        else:
            res["identical"] = False
        shutil.rmtree(d2, ignore_errors=True)
        return res

    def compare(self, case, w, n, cdir, tail, dest):
        mode = case["relation"]
        if mode == "cross-os":
            return []
        out = []
        tag = mode
        if mode == "repeat":
            argv = ["--out", str(w / "out" / "DEST2"), "--length", str(case["seconds"])] + tail[4:]
        elif mode == "relocate":
            moved = w / "elsewhere" / "deeper"
            shutil.copytree(w / "in", moved)
            argv = ["--out", str(w / "out" / "DEST2"), "--length", str(case["seconds"])] + \
                   [str(moved / Path(t).name) for t in tail[4:]]
        elif mode == "different-target":
            argv = ["--out", str(w / "out" / "DEST2"), "--length", str(case["seconds"] + 600)] + tail[4:]
        else:  # standalone-versus-batch: this source inside a larger batch
            b = w / "in" / "batch"
            b.mkdir()
            for x in Path(tail[4]).iterdir():
                shutil.copyfile(x, b / x.name)
            shutil.copyfile(self.assets / "short.wav", b / "zz-neighbour.wav")
            argv = ["--out", str(w / "out" / "DEST2"), "--length", str(case["seconds"])] + [str(b), tail[4]]
        d2 = w / "out" / "DEST2"
        code, o, e, trace, native, obsdir = self.invoke(argv, d2, {}, w, tag, case)
        sub = cdir / "comparisons" / "0"
        sub.mkdir(parents=True)
        shutil.move(str(trace), sub / "trace.txt")
        (sub / "stdout.txt").write_bytes(o)
        (sub / "stderr.txt").write_bytes(e)
        native["scenario"] = "success" if code == 0 else "comparison-failed"
        self.write_native(native, sub / "native.json", sub / "trace.txt")
        if code == 0:
            shutil.move(str(d2 / "audio.wav"), sub / "audio.wav")
            shutil.move(str(d2 / "manifest.json"), sub / "manifest.json")
        base = f"cases/{n:04d}/comparisons/0"
        out.append({"mode": mode, "exit": code, "argv": [raw_arg(x) for x in [os.path.basename(self.a.observe_bin)] + argv],
                    "manifest": base + "/manifest.json", "wav": base + "/audio.wav",
                    "raw_trace": base + "/trace.txt", "native_record": base + "/native.json"})
        return out


class Unavailable(Exception):
    pass


def case_input(w, folder, name):
    return os.path.join(os.fsencode(str(w / "in" / f"f{folder}")), os.fsencode(name))


EXHAUST = {
    "linux": {"method": "prlimit RLIMIT_AS", "bytes": 6 << 20},
    "macos": {"method": "INGEST_HEAP_LIMIT: observation-build allocator cap (macOS does not enforce RLIMIT_AS)",
              "bytes": 1000000},
    "windows": {"method": "Job object JOB_OBJECT_LIMIT_PROCESS_MEMORY", "bytes": 3 << 20},
}


def choose_observer(plat, requested, procmon):
    if requested:
        return requested
    if plat == "linux":
        return "strace" if shutil.which("strace") else "none"
    if plat == "macos":
        ok = subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode == 0
        return "fs_usage" if ok and shutil.which("fs_usage") else "none"
    if plat.startswith("windows"):
        return "procmon" if procmon and os.path.exists(procmon) else "none"
    return "none"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--observe-bin", required=True)
    ap.add_argument("--shipping-bin", required=True)
    ap.add_argument("--profile-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidate-sha", required=True)
    ap.add_argument("--work", default=None)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--only", default=None, help="case-id substring (development runs only)")
    ap.add_argument("--observer", default=None, choices=["strace", "fs_usage", "procmon", "none"])
    ap.add_argument("--procmon", default=os.environ.get("PROCMON"), help="Procmon64.exe (Windows)")
    a = ap.parse_args()
    a.observe_bin = os.path.abspath(a.observe_bin)
    a.shipping_bin = os.path.abspath(a.shipping_bin)
    root = Path(a.out)
    root.mkdir(parents=True, exist_ok=True)
    a.work = a.work or tempfile.mkdtemp(prefix="ingest-packet-")
    os.makedirs(a.work, exist_ok=True)
    plat, arch = platform_id()
    ver = subprocess.run([a.shipping_bin, "--version"], capture_output=True, text=True).stdout.split()
    tool_version, profile = ver[1], ver[-1]
    kind = choose_observer(plat, a.observer, a.procmon)
    obs = observers.make(kind, a.procmon)
    obs.observe_bin = a.observe_bin
    obs.start(root)
    if obs.deferred:
        obs.selftest_run(root)
        selftest_ok = None  # judged once the session has ended
    else:
        selftest_ok = obs.selftest(root)
    shutil.copytree(a.profile_dir, root / "profile", dirs_exist_ok=True)
    # config.json is the platform-independent identity every same-profile packet
    # shares (campaign.py requires one config_sha256): build commands, lockfile,
    # toolchain pin, profile and its declared filters, and this runner. Binary
    # hashes, observer and host facts differ truthfully per platform and live in
    # platform.json, bound by sha256 from INDEX.json.
    here = Path(__file__).resolve().parent
    config = {
        "build": "cargo build --release --locked (shipping); cargo build --release --locked --features observe (observation build)",
        "cargo_lock_sha256": sha_file(here.parent / "Cargo.lock"),
        "rust_toolchain": (here.parent / "rust-toolchain.toml").read_text(),
        "profile": profile, "tool_version": tool_version,
        "profile_tree_sha256": tree_sha(root / "profile"),
        "transport_sha256": {f: sha_file(here / f) for f in ("run_packet.py", "observers.py")},
    }
    (root / "config.json").write_bytes(canonical(config))
    r = Runner(a, obs, selftest_ok)
    r.config_sha = sha_file(root / "config.json")
    r.exhaust = EXHAUST.get("windows" if plat.startswith("windows") else plat)
    census = json.loads(Path(a.package, "CENSUS.json").read_text(encoding="utf-8"))["cases"]
    todo = [(n, c) for n, c in enumerate(census) if not a.only or a.only in c["id"]]
    cases = {}
    if (root / "INDEX.json").exists() and not obs.deferred:  # resume / accumulate development subsets
        prior = json.loads((root / "INDEX.json").read_text(encoding="utf-8"))
        if prior.get("binary_sha256") == sha_file(a.observe_bin):
            cases.update(prior["cases"])
    big = [x for x in todo if x[1]["seconds"] > 3600]
    small = [x for x in todo if x[1]["seconds"] <= 3600]
    t0, done = time.time(), 0

    def progress(cid):  # one line per finished case, so a slow host shows where time goes
        nonlocal done
        done += 1
        print(f"[{done}/{len(todo)}] {time.time() - t0:8.1f}s {cid}", file=sys.stderr, flush=True)
    with cf.ThreadPoolExecutor(1 if obs.serial else a.jobs) as ex:
        for cid, path in ex.map(lambda x: r.run_case(*x), small):
            cases[cid] = path
            progress(cid)
    for n, c in big:  # one at a time: these are the multi-GiB boundaries
        cid, path = r.run_case(n, c)
        cases[cid] = path
        progress(cid)
    obs.stop()
    if obs.deferred:
        owners = r.finalize()
        selftest_ok = obs.selftest_finish(root, owners)
        for nat in list(root.glob("cases/*/native.json")) + list(root.glob("cases/*/comparisons/*/native.json")):
            d = json.loads(nat.read_text(encoding="utf-8"))
            d["observer_selftest"] = selftest_ok
            nat.write_bytes(canonical(d))
        obs.compress()
        obs.drop_tools()
    host = {
        "platform": plat, "architecture": arch,
        "shipping_binary_sha256": sha_file(a.shipping_bin), "observe_binary_sha256": sha_file(a.observe_bin),
        "observer": kind, "observer_version": obs.version(), "observer_selftest_qualified": selftest_ok,
        "resource_limit_method": r.exhaust,
        "os": platform.platform(), "os_release": platform.release(), "os_version": platform.version(),
        "machine": platform.machine(), "python": sys.version,
        "rustc": tool_out(["rustc", "-vV"]), "cargo": tool_out(["cargo", "--version"]),
    }
    if plat.startswith("windows"):
        host["windows_edition"] = platform.win32_edition()
    if plat == "macos":
        host["sw_vers"] = tool_out(["sw_vers"])
    (root / "platform.json").write_bytes(canonical(host))
    index = {
        "candidate_sha": a.candidate_sha, "binary_sha256": sha_file(a.observe_bin),
        "shipping_binary_sha256": sha_file(a.shipping_bin), "tool_version": tool_version, "profile": profile,
        "platform": plat, "architecture": arch, "config_sha256": r.config_sha,
        "profile_file": "profile/profile.json", "observer": kind,
        "platform_file": "platform.json", "platform_sha256": sha_file(root / "platform.json"),
        "cases": dict(sorted(cases.items())),
    }
    (root / "INDEX.json").write_bytes(canonical(index))
    print(f"{len(cases)} case records; observer {kind}; selftest {'qualified' if selftest_ok else 'NOT qualified'}")


if __name__ == "__main__":
    main()
