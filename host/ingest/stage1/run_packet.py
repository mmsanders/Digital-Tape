#!/usr/bin/env python3
"""Software's observation transport for the imported INGEST-1 Stage1 package
(tests/wp16_ingest_stage1, INTERFACE.md). It runs the actual ingest commands and
writes one native packet: INDEX.json, the profile file, and per case the record,
stdout/stderr, native record and raw observer trace, plus outputs and the isolated
pre-gain observations for successes.

It judges nothing. Exit codes, PASS decisions and receipts are Verification's
(review.py / campaign.py with Verification's own receipts). Standard library only.

Native observer: Linux uses strace (complete syscall trace of the process tree);
other platforms are recorded as observer "none" with complete=false and
observer_selftest=false, which the published review rejects -- an honest gap,
never a substitute.

usage: run_packet.py --package DIR --sources DIR --observe-bin BIN --shipping-bin BIN
                     --profile-dir DIR --out PACKET --candidate-sha SHA [--jobs N] [--only S]
"""
import argparse, concurrent.futures as cf, hashlib, json, os, platform, re, shutil, signal
import subprocess, sys, tempfile, time, unicodedata
from pathlib import Path

CUTS_KILL = {"before-stage", "audio-open", "audio-flush", "manifest-open", "manifest-flush",
             "before-publish", "after-publish"}
STRACE_SET = ("openat,open,creat,mkdir,mkdirat,rename,renameat,renameat2,fsync,fdatasync,"
              "close,unlink,unlinkat,rmdir,newfstatat,statx,stat,lstat,execve,exit_group,"
              "clone,clone3,fork,vfork")


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def platform_id():
    s = sys.platform
    m = platform.machine().lower()
    arch = "arm64" if m in ("arm64", "aarch64") else "x64" if m in ("x86_64", "amd64") else m
    if s.startswith("linux"):
        return "linux", arch
    if s == "darwin":
        return "macos", arch
    if s.startswith("win"):
        return "windows11", arch  # caller must confirm the host really is Windows 11
    return s, arch


# ---- native observer ---------------------------------------------------------------------

class Observer:
    def __init__(self, kind):
        self.kind = kind

    def wrap(self, argv, trace):
        if self.kind == "strace":
            return ["strace", "-f", "-q", "-tt", "-y", "-s", "4096", "-e", "trace=" + STRACE_SET,
                    "-o", str(trace), "--"] + argv
        return argv

    def selftest(self, root):
        """Positive visibility, a deliberate forbidden device open, child processes,
        record completeness and process completion, on this host's native method."""
        d = root / "observer-selftest"
        d.mkdir(parents=True, exist_ok=True)
        if self.kind != "strace":
            (d / "result.json").write_bytes(canonical({"observer": self.kind, "qualified": False,
                                                       "reason": "no native observer implemented on this platform"}))
            return False
        probe = d / "probe.txt"
        probe.write_text("probe\n")
        script = ("cat '%s' >/dev/null; (cat '%s' >/dev/null); "
                  ": > '%s/created.txt'; (exec 3</dev/loop0) 2>/dev/null; true") % (probe, probe, d)
        trace = d / "trace.txt"
        p = subprocess.run(self.wrap(["sh", "-c", script], trace), capture_output=True)
        text = trace.read_text(errors="replace")
        opens = [l for l in text.splitlines() if "probe.txt" in l and "openat(" in l]
        pids = {l.split()[0] for l in opens}
        checks = {
            "process_exit_zero": p.returncode == 0,
            "two_probe_opens_seen": len(opens) >= 2,
            "child_process_followed": len(pids) >= 2,
            "creation_seen": "created.txt" in text and "O_CREAT" in text,
            "forbidden_device_open_seen": "/dev/loop0" in text,
            "process_completion_seen": "+++ exited with 0 +++" in text,
        }
        ok = all(checks.values())
        for name, passed in checks.items():
            if not passed:
                print(f"observer selftest check failed: {name}", file=sys.stderr)
        (d / "result.json").write_bytes(canonical({"observer": "strace", "qualified": ok, "checks": checks,
                                                   "trace_sha256": sha_file(trace)}))
        return ok


LINE = re.compile(r"^(\d+)\s+\S+\s+(\w+)\((.*)\)\s+=\s+(-?\d+|\?)")
DEVICE = re.compile(r'"/dev/(sd[a-z]|nvme|mmcblk|loop|disk|rdisk|hd[a-z]|vd[a-z]|xvd|sr)')


def map_strace(trace, dest, stage_prefix, observe_dir):
    """Normalize a raw strace trace into ordered INTERFACE ops (the mapping is
    published with the packet; Verification reviews it against the raw trace)."""
    events, failed, notes = [], [], []
    flushed = set()
    preflight_done = False
    root_pid = None
    completion = None
    obs = str(observe_dir)
    for n, l in enumerate(Path(trace).read_text(errors="replace").splitlines()):
        if root_pid is None and l.split():
            root_pid = l.split()[0]
        if l.startswith(root_pid + " ") and "+++ exited with" in l:
            completion = "exited"
        if l.startswith(root_pid + " ") and "+++ killed by" in l:
            completion = "killed"
        m = LINE.match(l)
        if not m:
            continue
        pid, call, args, ret = m.groups()
        ok = ret not in ("?",) and int(ret) >= 0

        def ev(op, **kw):
            events.append(dict(seq=len(events), op=op, line=n, **kw))

        mark = re.search(r"/\.mark/\d+-([a-z_]+)\"", args)
        if mark and call in ("statx", "newfstatat", "stat", "lstat"):
            op = mark.group(1)
            if op in ("preflight_complete", "sources_revalidated", "source_mutation_detected"):
                ev(op)
                preflight_done = preflight_done or op == "preflight_complete"
            continue
        if obs in args:
            continue  # the test build's own instrumentation output
        if call in ("mkdir", "mkdirat"):
            path = re.search(r'"([^"]*)"', args).group(1)
            if Path(path).name.startswith(stage_prefix) and ok:
                ev("stage_create", exclusive=True,
                   adjacent=os.path.dirname(os.path.abspath(path)) == os.path.dirname(os.path.abspath(dest)))
            elif ok and not preflight_done:
                ev("preflight_disk_scratch", path=path)
        elif call in ("openat", "open", "creat"):
            if DEVICE.search(args):
                ev("device_open")
            creating = "O_CREAT" in args or call == "creat"
            q = re.findall(r'"([^"]*)"', args)
            path = q[0] if q else ""
            if creating and ok:
                if stage_prefix in path:
                    ev("output_open", file=os.path.basename(path))
                elif not preflight_done:
                    ev("preflight_disk_scratch", path=path)
        elif call in ("fsync", "fdatasync") and ok:
            fd = re.search(r"<([^>]*)>", args)
            if fd:
                flushed.add(fd.group(1))
        elif call == "close" and ok:
            fd = re.search(r"<([^>]*)>", args)
            if fd and fd.group(1) in flushed and stage_prefix in fd.group(1):
                base = os.path.basename(fd.group(1))
                if base in ("audio.wav", "manifest.json"):
                    ev(base.split(".")[0].replace("audio", "audio") + "_flush_close")
        elif call in ("rename", "renameat", "renameat2"):
            q = re.findall(r'"([^"]*)"', args)
            into_dest = len(q) == 2 and os.path.abspath(q[1]).startswith(os.path.abspath(dest))
            noreplace = "RENAME_NOREPLACE" in args
            if into_dest and noreplace and stage_prefix in q[0]:
                if ok:
                    ev("publish_dir_noreplace")
                else:
                    failed.append({"op": "publish_dir_noreplace", "line": n, "result": ret})
            elif into_dest:
                ev("publish_file") if ok else failed.append({"op": "publish_file", "line": n, "result": ret})
    for e in events:
        if e["op"] == "audio_flush_close":
            pass
    return events, failed, completion


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
    cid, env, notes = case["id"], {}, []
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
        if sys.platform.startswith("linux"):
            shutil.copyfile(os.path.join(folders[0], "short.wav"), os.path.join(os.fsencode(folders[0]), b"bad\xff.wav"))
        else:
            raise Unavailable("this filesystem stores only valid Unicode names; the native invalid-name boundary is not creatable here")
    elif cid == "native/nfc-collision":
        src = os.path.join(folders[0], "short.wav")
        shutil.copyfile(src, os.path.join(folders[0], "\u00e9.wav"))  # precomposed
        try:
            shutil.copyfile(src, os.path.join(folders[0], "e\u0301.wav"))  # e + combining acute
        except OSError as x:
            raise Unavailable(f"filesystem refused the second normalized name: {x}")
        if len(os.listdir(folders[0])) < 3:
            raise Unavailable("normalization-insensitive filesystem: both spellings name one file; that exclusion is the filesystem's")
    elif cid == "native/case-unrepresentable":
        src = os.path.join(folders[0], "short.wav")
        shutil.copyfile(src, os.path.join(folders[0], "a.wav"))
        shutil.copyfile(src, os.path.join(folders[0], "A.wav"))
        if len(os.listdir(folders[0])) < 3:
            raise Unavailable("case-insensitive filesystem: a.wav and A.wav cannot coexist; that exclusion is the filesystem's, not ingest's")
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
    return head + tail, dest, env, notes


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

    def invoke(self, argv_tail, dest, env, w, tag, case, exhaust_limit=None):
        obsdir = w / f"obs-{tag}"
        (obsdir / ".mark").mkdir(parents=True)
        trace = w / f"trace-{tag}.txt"
        argv = [self.a.observe_bin] + argv_tail
        cmd = argv
        if exhaust_limit:
            cmd = ["prlimit", f"--as={exhaust_limit}", "--"] + cmd
        cmd = self.obs.wrap(cmd, trace)
        e = dict(os.environ, INGEST_OBSERVE_DIR=str(obsdir), **env)
        stage_prefix = "." + dest.name + ".ingest-stage-"
        unrelated = dest.parent / "unrelated.txt"
        before_unrel = sha_file(unrelated)
        dest_before, dest_before_sha = snapshot(dest)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e)
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
        if code is not None and code < 0:
            code = None  # killed by a signal
        if (obsdir / "events.jsonl").exists() and '"op":"kill"' in (obsdir / "events.jsonl").read_text():
            code = None  # the seam aborted at a kill cut (Windows reports a fail-fast status)
        if not self.obs.kind == "strace":
            trace.write_bytes(b"")
        dest_after, dest_after_sha = snapshot(dest)
        stage_left = [x.name for x in dest.parent.iterdir() if x.name.startswith(stage_prefix)]
        events, failed, completion = ([], [], None)
        if self.obs.kind == "strace":
            events, failed, completion = map_strace(trace, dest, stage_prefix, obsdir)
        seam = []
        if (obsdir / "events.jsonl").exists():
            seam = [json.loads(l) for l in (obsdir / "events.jsonl").read_text().splitlines() if l.strip()]
        native = {
            "scenario": None, "exit": code, "complete": completion is not None,
            "raw_trace_sha256": sha_file(trace), "observer": self.obs.kind,
            "observer_selftest": self.selftest_ok, "events": events, "failed_ops": failed,
            "seam_events": seam, "dest_after": dest_after, "owned_stage_after": bool(stage_left),
            "unrelated_unchanged": sha_file(unrelated) == before_unrel,
            "binary_sha256": sha_file(self.a.observe_bin), "argv": argv, "env": env,
            "process_completion": completion,
        }
        if dest_before:
            native["dest_before"] = dest_before
            native["dest_before_sha256"] = dest_before_sha
            native["dest_after_sha256"] = dest_after_sha
        if competitor is not None:
            native["competitor_unchanged"] = (dest / "competitor.txt").exists() and sha_file(dest / "competitor.txt") == competitor
        return code, out, err, trace, native, obsdir

    def run_case(self, n, case):
        a = self.a
        cdir = self.root / "cases" / f"{n:04d}"
        if (cdir / "record.json").exists():
            return case["id"], f"cases/{n:04d}/record.json"
        cdir.mkdir(parents=True, exist_ok=True)
        w = Path(tempfile.mkdtemp(dir=a.work))
        try:
            try:
                tail, dest, env, notes = setup_case(case, w, self.assets)
                if case["id"] == "resources/exhaustion" and not shutil.which("prlimit"):
                    raise Unavailable("no bounded-memory method implemented on this platform (Linux uses prlimit RLIMIT_AS)")
            except (Unavailable, OSError) as x:
                return case["id"], self.unavailable(n, cdir, case, str(x))
            limit = a.exhaust_limit if case["id"] == "resources/exhaustion" else None
            code, out, err, trace, native, obsdir = self.invoke(tail, dest, env, w, "main", case, limit)
            sc = case.get("scenario") or ("success" if code == 0 else "preflight-refusal" if code == 2 else "write-error")
            native["scenario"] = sc
            native["diagnostic_ok"] = bool(err.strip()) and err.decode("utf-8", "replace").startswith("ingest:")
            native["setup_notes"] = notes
            if case["id"] == "resources/exhaustion":
                native["resource_limit"] = {"method": "prlimit RLIMIT_AS", "bytes": a.exhaust_limit}
            (cdir / "stdout.txt").write_bytes(out)
            (cdir / "stderr.txt").write_bytes(err)
            shutil.move(str(trace), cdir / "trace.txt")
            (cdir / "native.json").write_bytes(canonical(native))
            rec = {"exit": code, "argv": [os.path.basename(a.observe_bin)] + tail, "config_sha256": self.config_sha,
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
        p = subprocess.run(argv, capture_output=True)
        res = {"shipping_binary_sha256": sha_file(self.a.shipping_bin), "exit": p.returncode,
               "argv": [os.path.basename(self.a.shipping_bin)] + argv[1:]}
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
        (sub / "native.json").write_bytes(canonical(native))
        if code == 0:
            shutil.move(str(d2 / "audio.wav"), sub / "audio.wav")
            shutil.move(str(d2 / "manifest.json"), sub / "manifest.json")
        base = f"cases/{n:04d}/comparisons/0"
        out.append({"mode": mode, "exit": code, "argv": [os.path.basename(self.a.observe_bin)] + argv,
                    "manifest": base + "/manifest.json", "wav": base + "/audio.wav",
                    "raw_trace": base + "/trace.txt", "native_record": base + "/native.json"})
        return out


class Unavailable(Exception):
    pass


def case_input(w, folder, name):
    return os.path.join(os.fsencode(str(w / "in" / f"f{folder}")), os.fsencode(name))


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
    ap.add_argument("--observer", default=None, choices=["strace", "none"])
    ap.add_argument("--exhaust-limit", default=str(6 << 20), help="RLIMIT_AS bytes for resources/exhaustion")
    a = ap.parse_args()
    a.observe_bin = os.path.abspath(a.observe_bin)
    a.shipping_bin = os.path.abspath(a.shipping_bin)
    root = Path(a.out)
    root.mkdir(parents=True, exist_ok=True)
    a.work = a.work or tempfile.mkdtemp(prefix="ingest-packet-")
    os.makedirs(a.work, exist_ok=True)
    plat, arch = platform_id()
    kind = a.observer or ("strace" if plat == "linux" and shutil.which("strace") else "none")
    obs = Observer(kind)
    selftest_ok = obs.selftest(root)
    shutil.copytree(a.profile_dir, root / "profile", dirs_exist_ok=True)
    ver = subprocess.run([a.shipping_bin, "--version"], capture_output=True, text=True).stdout.split()
    tool_version, profile = ver[1], ver[-1]
    config = {
        "build": "cargo build --release --locked (shipping); cargo build --release --locked --features observe (observation build)",
        "cargo_lock_sha256": sha_file(Path(__file__).resolve().parents[1] / "Cargo.lock"),
        "rust_toolchain": (Path(__file__).resolve().parents[1] / "rust-toolchain.toml").read_text(),
        "shipping_binary_sha256": sha_file(a.shipping_bin), "observe_binary_sha256": sha_file(a.observe_bin),
        "observer": kind, "profile": profile, "tool_version": tool_version,
        "runner_sha256": sha_file(__file__),
    }
    (root / "config.json").write_bytes(canonical(config))
    r = Runner(a, obs, selftest_ok)
    r.config_sha = sha_file(root / "config.json")
    census = json.loads(Path(a.package, "CENSUS.json").read_text(encoding="utf-8"))["cases"]
    todo = [(n, c) for n, c in enumerate(census) if not a.only or a.only in c["id"]]
    cases = {}
    if (root / "INDEX.json").exists():  # resume / accumulate development subsets
        prior = json.loads((root / "INDEX.json").read_text(encoding="utf-8"))
        if prior.get("binary_sha256") == sha_file(a.observe_bin):
            cases.update(prior["cases"])
    big = [x for x in todo if x[1]["seconds"] > 3600]
    small = [x for x in todo if x[1]["seconds"] <= 3600]
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for cid, path in ex.map(lambda x: r.run_case(*x), small):
            cases[cid] = path
    for n, c in big:  # one at a time: these are the multi-GiB boundaries
        cid, path = r.run_case(n, c)
        cases[cid] = path
    index = {
        "candidate_sha": a.candidate_sha, "binary_sha256": sha_file(a.observe_bin),
        "shipping_binary_sha256": sha_file(a.shipping_bin), "tool_version": tool_version, "profile": profile,
        "platform": plat, "architecture": arch, "config_sha256": r.config_sha,
        "profile_file": "profile/profile.json", "observer": kind, "cases": dict(sorted(cases.items())),
    }
    (root / "INDEX.json").write_bytes(canonical(index))
    print(f"{len(cases)} case records; observer {kind}; selftest {'qualified' if selftest_ok else 'NOT qualified'}")


if __name__ == "__main__":
    main()
