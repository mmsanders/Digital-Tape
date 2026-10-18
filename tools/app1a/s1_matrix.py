#!/usr/bin/env python3
"""#457: Software's execution of the APP-1A S1 process matrix (tests/wp15_app1a_r1/
ADAPTER.md, rows 2-6) and the closed ingest-ID census against the actual binaries.
It judges nothing and accepts nothing: Verification #201 disposes. Row 1 (no-flag
byte identity) is noflag_equivalence.py; row 4's leaf ownership and row 5's create
failure are the package's own ingest_process.py; both run as separate CI steps.

Every run retains argv, executable SHA-256 and version, exit, raw stdout/stderr/report
bytes, and inventories of the case tree and the report folder before and after. A
report is judged by the package's own oracle.parse (bound to the launched tool,
version and nonce, the actual exit and the dropped folders), never by a summary.

  shipping  the shipping binary: invalid flag pairings, every census case with a
            report (row 3's only-created-file rule on every refusal), constructed
            inputs for IDs the census does not reach, the 8467200-frame overage, and
            IO_MEMORY under an OS memory limit;
  seam      the census cases whose setup needs the test-build seam (kill, I/O fault,
            source mutation, concurrent DEST), run by the OBSERVATION build with a
            report, as the census itself runs them;
  fullfs    with --fullfs DIR (an actual small filesystem the caller mounted), report
            writes that fail at start and later, against a control run elsewhere.

Rows a platform cannot set up are UNEXECUTED with the reason, never run weaker. The
closed-ID census lists, for each of the 34 ingest IDs, the runs whose report carried
it, or why none did.

  s1_matrix.py --package DIR --sources DIR --bin SHIPPING --observe OBSERVE --out DIR
               [--fullfs DIR] [--work DIR] [--skip-long]
"""
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, tempfile, time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "host" / "ingest" / "stage1"))
sys.path.insert(0, str(REPO / "tests" / "wp15_app1a_r1"))
import run_packet as rp  # noqa: E402  (the census transport, unchanged)
import oracle  # noqa: E402  (the package's report predicate, unchanged)

NONCE = "0123456789abcdef0123456789abcdef"
IDS = {1: oracle.I1, 2: oracle.I2}
POSIX = os.name == "posix"
ROOT = POSIX and os.geteuid() == 0
SEAMS = ("kill", "write-error", "mutation", "concurrent-dest")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def inventory(d):
    out = {}
    if d.exists():
        for p in sorted(d.rglob("*")):
            r = p.relative_to(d).as_posix()
            if p.is_symlink():
                out[r] = "link:" + os.readlink(p)
            elif p.is_file():
                try:
                    out[r] = sha(p.read_bytes())
                except PermissionError:  # a row's deliberately unreadable input
                    st = p.stat()
                    out[r] = f"unreadable:{oct(st.st_mode)}:{st.st_size}"
            elif p.is_dir():
                out[r] = "dir"
            else:
                out[r] = "special"
    return out


class M:
    def __init__(self, a):
        self.a, self.rows, self.n = a, [], 0
        self.out = Path(a.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.ver = {k: subprocess.run([v, "--version"], capture_output=True, text=True).stdout.strip()
                    for k, v in (("shipping", a.bin), ("observe", a.observe))}
        self.version = self.ver["shipping"].split(" ", 1)[1]

    def run(self, row, name, argv, w, folders, report=True, env=None, binary=None, limit=None, timeout=1800,
            expect=None, report_path=None, seam=None):
        """One actual process. `expect` is a dict of required facts; the row's verdict is
        PASS only if every one holds."""
        binary = binary or self.a.bin
        self.n += 1
        d = self.out / "runs" / f"{self.n:04d}"
        d.mkdir(parents=True)
        ctl = w / "control"
        ctl.mkdir(exist_ok=True)
        rpath = report_path or (ctl / "report.jsonl")
        flags = ["--report", str(rpath), "--report-nonce", NONCE] if report else []
        tree = w / "case"
        before, cbefore = inventory(tree), inventory(ctl)  # the process runs in ctl: a stray file shows
        cmd = [binary, *flags, *argv]
        job = None
        if limit is not None and platform.system() == "Linux":
            cmd = ["prlimit", f"--as={limit}", "--"] + cmd
        e = None
        if env is not None:
            # The census seam, exactly as run_packet.invoke drives it.
            obs = w / "observe"
            (obs / ".mark").mkdir(parents=True, exist_ok=True)
            e = dict(os.environ, INGEST_OBSERVE_DIR=str(obs), **env)
        t0 = time.time()
        try:
            win_job = limit is not None and os.name == "nt"
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e, cwd=ctl,
                                 creationflags=0x4 if win_job else 0)
            if win_job:
                job = rp.windows_memory_job(limit)
                rp.windows_job_assign_and_resume(job, p)
            if env and "INGEST_PAUSE_AT" in env:
                waiting = Path(env["INGEST_PAUSE_FILE"] + ".waiting")
                deadline = time.time() + 600
                while not waiting.exists() and p.poll() is None and time.time() < deadline:
                    time.sleep(0.02)
                if seam.get("scenario") == "mutation":
                    with open(rp.case_input(tree, 0, seam["folders"][0][0]["name"]), "ab") as f:
                        f.write(b"\0")
                else:
                    dest = Path(argv[argv.index("--out") + 1])
                    dest.mkdir()
                    (dest / "competitor.txt").write_text("concurrent writer\n")
                Path(env["INGEST_PAUSE_FILE"]).write_text("")
            so, se = p.communicate(timeout=timeout)
            code = p.returncode
        except subprocess.TimeoutExpired:
            p.kill()
            return self.unexecuted(row, name, f"did not finish within {timeout} s")
        after, cafter = inventory(tree), inventory(ctl)
        rbytes = rpath.read_bytes() if rpath.exists() and rpath.is_file() else None
        (d / "stdout").write_bytes(so)
        (d / "stderr").write_bytes(se)
        if rbytes is not None:
            (d / "report.jsonl").write_bytes(rbytes)
        parsed = oracle.parse(rbytes, "ingest", self.version, NONCE, code, folders) if rbytes is not None else None
        rec = {
            "row": row, "name": name, "run": d.name, "seconds": round(time.time() - t0, 2),
            "argv": [os.path.basename(binary)] + [str(x).replace(str(w), "<W>") for x in flags + list(argv)],
            "binary_sha256": sha(Path(binary).read_bytes()), "binary": "observe" if binary == self.a.observe else "shipping",
            "version": self.ver["observe" if binary == self.a.observe else "shipping"],
            "env": env or {}, "limit_bytes": limit, "exit": code,
            "stdout_sha256": sha(so), "stderr_sha256": sha(se), "stderr_head": se[:300].decode("utf-8", "replace"),
            "report_sha256": sha(rbytes) if rbytes is not None else None,
            "report_valid": parsed is not None,
            "refusal_id": (parsed or {}).get("refusal", {}) and parsed["refusal"]["id"] if parsed else None,
            "tree_changes": {k: [before.get(k), after.get(k)] for k in sorted(set(before) | set(after))
                             if before.get(k) != after.get(k)},
            "control_created": sorted(set(cafter) - set(cbefore)),
        }
        bad = []
        for k, v in (expect or {}).items():
            got = {"exit": code, "report": rbytes is not None, "valid": parsed is not None,
                   "id": rec["refusal_id"], "stdout_empty": so == b"",
                   "only_report": not rec["tree_changes"] and rec["control_created"] == [rpath.name] if report else None,
                   "nothing": not rec["tree_changes"] and not rec["control_created"],
                   "valid_if_present": rbytes is None or parsed is not None}[k]
            if (got not in v) if isinstance(v, (list, tuple, set)) else got != v:
                bad.append(f"{k}: expected {v!r}, got {got!r}")
        rec["verdict"] = "FAIL: " + "; ".join(bad) if bad else "PASS"
        (d / "process.json").write_text(json.dumps(rec, indent=1) + "\n")
        self.rows.append(rec)
        print(f"{row:4} {name:42} exit {code!s:>4} id {rec['refusal_id']!s:24} {rec['verdict'][:90]}", flush=True)
        return rec

    def unexecuted(self, row, name, why):
        rec = {"row": row, "name": name, "verdict": "UNEXECUTED", "reason": why}
        self.rows.append(rec)
        print(f"{row:4} {name:42} UNEXECUTED: {why}", flush=True)
        return rec

    def case_dir(self):
        # Case trees go under --work: setup_case hard-links sources, so they must share a
        # volume with --sources (on Windows runners the default temp is another drive).
        w = Path(tempfile.mkdtemp(prefix="s1m-", dir=self.a.work))
        (w / "case").mkdir()
        return w


def folder_args(tail):
    """The FOLDER operands of an ingest argv tail."""
    out, i = [], 0
    while i < len(tail):
        x = tail[i]
        if x in ("--out", "--length"):
            i += 2
            continue
        if x == "--":
            return out + list(tail[i + 1:])
        if not str(x).startswith("-"):
            out.append(x)
        i += 1
    return out


def census_case(m, case, binary, row):
    """A census case's own inputs (setup_case), run with a report."""
    w = m.case_dir()
    try:
        tail, dest, env, notes, cap = rp.setup_case(case, w / "case", Path(m.a.sources) / "assets")
        folders = folder_args(tail)
        limit = None
        if case["id"] == "resources/exhaustion":
            ex_ = rp.EXHAUST[rp.platform_id()[0]]
            if ex_["method"].startswith("INGEST_HEAP_LIMIT"):
                env = dict(env or {}, INGEST_HEAP_LIMIT=str(ex_["bytes"]))
            else:
                limit = ex_["bytes"]
            env = env or {}
        ex = case["expected_exit"]
        expect = {"exit": ex if isinstance(ex, list) else [ex]} if ex is not None else {}
        if ex not in (0, None):
            expect.update(valid=True)
            if not env:
                expect.update(only_report=True)  # a seam case's runner may itself create DEST
        elif ex == 0:
            expect.update(valid_if_present=True, id=None)
        if env and case.get("scenario") == "kill":
            expect = {"valid": False}  # killed at a cut: no end record, so no ID-specific selection
        return m.run(row, case["id"], tail, w, folders, env=env if env or limit else None, binary=binary,
                     expect=expect, limit=limit, seam=case)
    finally:
        shutil.rmtree(w, ignore_errors=True)


def asset(m, name):
    return Path(m.a.sources) / "assets" / name


def simple(m, row, name, folders_setup, extra=(), length="3600", expect=None, posix_only=False, nonroot=False,
           out_setup=None):
    if posix_only and not POSIX:
        return m.unexecuted(row, name, "needs a POSIX-only file type or name")
    if nonroot and ROOT:
        return m.unexecuted(row, name, "permission bits do not bind the root user running this job")
    w = m.case_dir()
    try:
        case = w / "case"
        ins = []
        for i, setup in enumerate(folders_setup):
            p = case / f"f{i}"
            setup(p)
            ins.append(p)
        dest = (out_setup or (lambda c: c / "out" / "DEST"))(case)
        dest.parent.mkdir(parents=True, exist_ok=True) if out_setup is None else None
        argv = ["--out", str(dest), "--length", length, *extra, *[str(x) for x in ins]]
        r = m.run(row, name, argv, w, [p.name for p in ins], expect=expect)
        return r
    finally:
        for p in (w / "case").rglob("*") if (w / "case").exists() else []:
            try:
                os.chmod(p, 0o700) if p.is_dir() and not p.is_symlink() else None
                os.chmod(p, 0o600) if p.is_file() and not p.is_symlink() else None
            except OSError:
                pass
        shutil.rmtree(w, ignore_errors=True)


def folder_of(*files):
    def make(p):
        p.mkdir(parents=True)
        for name, src in files:
            shutil.copyfile(src, p / name)
    return make


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--bin", required=True)
    ap.add_argument("--observe", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fullfs", default=None)
    ap.add_argument("--work", default=None)
    ap.add_argument("--skip-long", action="store_true")
    a = ap.parse_args()
    a.bin, a.observe = os.path.abspath(a.bin), os.path.abspath(a.observe)
    if a.work:
        os.makedirs(a.work, exist_ok=True)
    m = M(a)
    census = json.loads(Path(a.package, "CENSUS.json").read_text(encoding="utf-8"))["cases"]
    ordinary = asset(m, "ordinary.wav")
    one = lambda p: folder_of(("song.wav", ordinary))(p)

    # Row 2: invalid report flags never create FILE (stdout empty, exit 2, nothing written).
    bad = [("missing-nonce", ["--report", "R"]), ("missing-report", ["--report-nonce", NONCE]),
           ("repeat-report", ["--report", "R", "--report", "R2", "--report-nonce", NONCE]),
           ("repeat-nonce", ["--report", "R", "--report-nonce", NONCE, "--report-nonce", NONCE]),
           ("nonce-31", ["--report", "R", "--report-nonce", NONCE[:31]]),
           ("nonce-33", ["--report", "R", "--report-nonce", NONCE + "0"]),
           ("nonce-upper", ["--report", "R", "--report-nonce", NONCE.upper()]),
           ("nonce-nonhex", ["--report", "R", "--report-nonce", "g" * 32]),
           ("report-no-file", None)]
    for name, fl in bad:
        w = m.case_dir()
        try:
            one(w / "case" / "f0")
            (w / "case" / "out").mkdir()
            rest = ["--out", str(w / "case" / "out" / "DEST"), "--length", "3600", str(w / "case" / "f0")]
            if fl is None:  # --report as the last argument, with no FILE after it
                argv = rest + ["--report-nonce", NONCE, "--report"]
            else:
                argv = [str(w / "control" / x) if x in ("R", "R2") else x for x in fl] + rest
            m.run("R2", "flags/" + name, argv, w, ["f0"], report=False,
                  expect={"exit": 2, "stdout_empty": True, "nothing": True})
        finally:
            shutil.rmtree(w, ignore_errors=True)
    # Valid flags plus another usage refusal: the report may exist and must say INGEST_USAGE.
    w = m.case_dir()
    try:
        one(w / "case" / "f0")
        m.run("R2", "flags/valid-plus-missing-length", ["--out", str(w / "case" / "DEST"), str(w / "case" / "f0")],
              w, ["f0"], expect={"exit": 2, "valid": True, "id": "INGEST_USAGE", "only_report": True})
    finally:
        shutil.rmtree(w, ignore_errors=True)

    # Row 3 / row 6: every census case that needs no seam, with a report (shipping).
    for case in census:
        if case.get("scenario") in SEAMS:
            continue
        if case["seconds"] > 3600 and (a.skip_long or case["expected_exit"] == 0):
            m.unexecuted("R3", case["id"], "a success over an hour (a 4 GiB pair) belongs to the AP4 base campaign, not "
                         "an impacted report scope" if case["expected_exit"] == 0 else "longer than an hour; --skip-long")
            continue
        census_case(m, case, a.bin, "R3")

    # Seam cases: the observation build, as the census runs them.
    for case in census:
        if case.get("scenario") in SEAMS:
            census_case(m, case, a.observe, "SEAM")

    # Constructed inputs for IDs the census does not reach (shipping).
    simple(m, "R3", "construct/INGEST_LENGTH_INVALID", [one], length=str(2**64 - 1),
           expect={"exit": 2, "valid": True, "id": "INGEST_LENGTH_INVALID", "only_report": True})

    def not_folder(p):
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ordinary, p)
    simple(m, "R3", "construct/FOLDER_NOT_FOLDER", [not_folder],
           expect={"exit": 2, "valid": True, "id": "FOLDER_NOT_FOLDER", "only_report": True})

    def fifo(p):
        one(p)
        os.mkfifo(p / "pipe.wav")
    simple(m, "R3", "construct/ENTRY_NOT_REGULAR", [fifo], posix_only=True,
           expect={"exit": 2, "valid": True, "id": "ENTRY_NOT_REGULAR", "only_report": True})
    simple(m, "R3", "construct/ENTRY_NAME_INVALID", [folder_of(("a:b.wav", ordinary))], posix_only=True,
           expect={"exit": 2, "valid": True, "id": "ENTRY_NAME_INVALID", "only_report": True})

    def unreadable_folder(p):
        one(p)
        os.chmod(p, 0)
    simple(m, "R3", "construct/IO_FOLDER", [unreadable_folder], posix_only=True, nonroot=True,
           expect={"exit": 1, "valid": True, "id": "IO_FOLDER", "only_report": True})

    def unreadable_source(p):
        one(p)
        os.chmod(p / "song.wav", 0)
    simple(m, "R3", "construct/IO_SOURCE", [unreadable_source], posix_only=True, nonroot=True,
           expect={"exit": 1, "valid": True, "id": "IO_SOURCE", "only_report": True})
    simple(m, "R3", "construct/IO_DEST-missing-parent", [one], out_setup=lambda c: c / "absent" / "DEST",
           expect={"exit": 1, "valid": True, "id": "IO_DEST", "only_report": True})
    simple(m, "R3", "construct/DEST_NAME_INVALID-dotdot", [one], out_setup=lambda c: c / "f0" / "..",
           expect={"exit": 2, "valid": True})

    # Exact overage including gaps: 2 folders x 100 exact seconds + one 2 s gap = 202 s
    # against a 10 s label: 192 s = 8467200 frames over.
    exact = asset(m, "exact-one-second.wav")
    hundred = folder_of(*[(f"{i:03d}.wav", exact) for i in range(100)])
    r = simple(m, "R3", "construct/overage-8467200", [hundred, hundred], length="10",
               expect={"exit": 2, "valid": True, "id": "INGEST_TOO_LONG", "only_report": True})
    if r.get("run"):
        rows = [json.loads(x) for x in (m.out / "runs" / r["run"] / "report.jsonl").read_text().splitlines()]
        ref = [x for x in rows if x["t"] == "refusal"][0]
        r["overage"] = {k: ref[k] for k in ("total_frames", "capacity_frames", "excess_frames")}
        if r["overage"]["excess_frames"] != 8467200:
            r["verdict"] = f"FAIL: excess {r['overage']['excess_frames']}"

    # IO_MEMORY: the shipping binary under an OS memory limit (Linux RLIMIT_AS, Windows job).
    if platform.system() == "Darwin":
        m.unexecuted("R5", "memory/IO_MEMORY", "macOS enforces no ordinary-process memory limit (see #451/#457)")
    else:
        for mib in (6, 7, 8):
            w = m.case_dir()
            try:
                one(w / "case" / "f0")
                (w / "case" / "out").mkdir()
                m.run("R5", f"memory/IO_MEMORY-{mib}MiB", ["--out", str(w / "case" / "out" / "DEST"), "--length", "3600",
                                                          str(w / "case" / "f0")], w, ["f0"], limit=mib << 20,
                      expect={"exit": 1, "valid": True, "id": "IO_MEMORY", "only_report": True})
            finally:
                shutil.rmtree(w, ignore_errors=True)

    # Row 5: report writes that fail on an actual full filesystem.
    if not a.fullfs:
        m.unexecuted("R5", "fullfs/start-write-fails", "no small filesystem mounted on this platform (--fullfs)")
        m.unexecuted("R5", "fullfs/later-write-fails", "no small filesystem mounted on this platform (--fullfs)")
    else:
        fullfs(m, Path(a.fullfs), hundred)

    write_census(m)


def fullfs(m, fs, hundred):
    """Fill `fs`, leaving `free` bytes, then run a success case whose report lives on it.
    Its stdout, exit and published pair must equal a control run reporting elsewhere,
    and stderr must be the control's plus exactly one report warning line."""
    for name, free in (("start-write-fails", 0), ("later-write-fails", 4096)):
        filler = fs / "filler"
        with open(filler, "wb") as f:
            try:
                while True:
                    f.write(b"\0" * 65536)
                    f.flush()
            except OSError:
                pass
        try:
            with open(filler, "ab") as f:
                while True:
                    f.write(b"\0")
                    f.flush()
        except OSError:
            pass
        if free:
            size = filler.stat().st_size
            os.truncate(filler, max(0, size - free))
        res = {}
        for mode in ("control", "full"):
            w = m.case_dir()
            try:
                hundred(w / "case" / "f0")
                (w / "case" / "out").mkdir()
                rp_ = (w / "control" / "report.jsonl") if mode == "control" else fs / f"{name}.jsonl"
                r = m.run("R5", f"fullfs/{name}/{mode}", ["--out", str(w / "case" / "out" / "DEST"), "--length", "3600",
                                                         str(w / "case" / "f0")], w, ["f0"], report_path=rp_,
                          expect={"exit": 0})
                pair = {k: sha((w / "case" / "out" / "DEST" / k).read_bytes()) for k in ("audio.wav", "manifest.json")} \
                    if (w / "case" / "out" / "DEST").exists() else None
                res[mode] = (r, pair, (m.out / "runs" / r["run"] / "stdout").read_bytes().replace(str(w).encode(), b"<W>"),
                             (m.out / "runs" / r["run"] / "stderr").read_bytes())
            finally:
                shutil.rmtree(w, ignore_errors=True)
        (rc, pc, oc, ec), (rf, pf, of, ef) = res["control"], res["full"]
        extra = ef.decode("utf-8", "replace").splitlines()
        base = ec.decode("utf-8", "replace").splitlines()
        warn = [x for x in extra if x not in base]
        facts = {"same_exit": rc["exit"] == rf["exit"] == 0, "same_stdout": oc == of, "same_pair": pc == pf and pc is not None,
                 "one_warning": len(warn) == 1 and warn[0].startswith("ingest: warning: report:"),
                 "report_bytes_written": (fs / f"{name}.jsonl").stat().st_size if (fs / f"{name}.jsonl").exists() else None}
        rf["fullfs_facts"] = facts
        if not all(v for k, v in facts.items() if k != "report_bytes_written"):
            rf["verdict"] = f"FAIL: {facts}"
        print(f"     fullfs/{name}: {facts}", flush=True)
        for p in fs.iterdir():
            p.unlink()


def write_census(m):
    seen = defaultdict(list)
    for r in m.rows:
        if r.get("refusal_id") and r.get("report_valid"):
            seen[r["refusal_id"]].append(r["name"])
    why = {
        "SOURCE_LEVEL": "not constructed: gain never exceeds the source's own peak bound, so 16-bit overflow and a zero "
                        "true peak on a non-silent admitted source have no known input; no restriction added to force it",
        "JOINED_PEAK": "not constructed: every boundary is refused first as JOIN_PEAK and each source is limited alone; no "
                       "input found that exceeds only the whole-stream measurement",
        "INTERNAL": "genuine internal inconsistency only; never triggered artificially (ADAPTER.md)",
        "DEST_NAME_INVALID": "a DEST with no file name is either an existing folder (DEST_EXISTS) or has a missing parent "
                             "(IO_DEST) on this platform's path rules; see construct/DEST_NAME_INVALID-dotdot",
    }
    census = []
    for e, ids in IDS.items():
        for i in ids:
            if seen.get(i):
                census.append({"id": i, "exit": e, "status": "OBSERVED", "runs": seen[i][:10], "count": len(seen[i])})
            else:
                census.append({"id": i, "exit": e, "status": "NOT OBSERVED", "reason": why.get(i, "no run on this platform "
                               "reached it; see UNEXECUTED rows")})
    summary = {
        "platform": platform.platform(), "root": ROOT, "versions": m.ver,
        "shipping_sha256": sha(Path(m.a.bin).read_bytes()), "observe_sha256": sha(Path(m.a.observe).read_bytes()),
        "runs": sum(1 for r in m.rows if r.get("run")),
        "pass": sum(1 for r in m.rows if r.get("verdict") == "PASS"),
        "fail": [{"name": r["name"], "verdict": r["verdict"]} for r in m.rows if str(r.get("verdict", "")).startswith("FAIL")],
        "unexecuted": [{"name": r["name"], "reason": r["reason"]} for r in m.rows if r.get("verdict") == "UNEXECUTED"],
        "closed_id_census": census,
        "observed_ids": sum(1 for c in census if c["status"] == "OBSERVED"),
    }
    (m.out / "S1-MATRIX.json").write_text(json.dumps({"summary": summary, "rows": m.rows}, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "closed_id_census"}, indent=1))
    for c in census:
        print(f"  {c['exit']} {c['id']:26} {c['status']:13} {c.get('count', '')} {c.get('reason', '')[:80]}")
    sys.exit(1 if summary["fail"] else 0)


if __name__ == "__main__":
    main()
