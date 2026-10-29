#!/usr/bin/env python3
"""#624 F364-2: the G3 bridge matrix of tests/c1_closeout_r1/g3.py with REAL children,
on a hosted Windows runner (an administrator without UAC). TEST-ONLY; nothing here ships.

Each child-origin case is prepared here (folders, WAVs, Windows Server VHDs) and then run
by one test of host/app/tests/g3_component.rs inside the production bridge module:

  ingest  the original INGEST child (hash-pinned) on real folders, through the
          production worker closure and completion path
  make    `tapectl-test make` on a VHD, with exactly the argv the bridge built, through
          run_make / make::judge / App::made. The facts seam stands in for "is this a
          card" (a VHD is never one) except where the row is the real probe's own
          answer. Removal and the read-only device are real OS actions at a paused
          phase boundary (TAPECTL_TEST_PAUSE); the child meets them on its next I/O.
  cards   the shipping `tapectl cards` with more disks attached than it can list,
          through discover / judge / publish

The twelve app-origin cases run through the same bridge actions with their typed
launcher/recheck dependency. Rows are assembled in g3.CASES order into G3-RESULT.json and
judged by the imported g3.check, unchanged.

  g3_624.py --ingest EXE --tapectl EXE --tapectl-test EXE --test-exe EXE --out DIR [--source SHA]
"""
import argparse, hashlib, importlib.util, json, math, os, shutil, struct, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NONCE = "00112233445566778899aabbccddeeff"
RATE = 44100
CAPACITY = 3600 * RATE
GAP = 88200


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s3 = load("s3_bundle", ROOT / "tools" / "wp15-cards" / "s3_bundle.py")
g3 = load("c1_g3", ROOT / "tests" / "c1_closeout_r1" / "g3.py")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tone_wav(path, frames, truncate=0):
    """Stereo 16-bit 44.1 kHz, a quiet 441 Hz tone; written a second at a time."""
    second = b"".join(struct.pack("<hh", v, v) for v in
                      (int(3000 * math.sin(2 * math.pi * 441 * i / RATE)) for i in range(RATE)))
    data = frames * 4
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + data) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 2, RATE, RATE * 4, 4, 16))
        f.write(b"data" + struct.pack("<I", data))
        left = data - truncate
        while left > 0:
            n = min(left, len(second))
            f.write(second[:n])
            left -= n


def version_of(exe, command, work):
    """The child's own report version: a USAGE run that touches no device."""
    rep = work / f"version-{command}-{time.time_ns()}.jsonl"
    argv = [exe, command, "--g3-version-probe", "--report", str(rep), "--report-nonce", NONCE]
    subprocess.run(argv, capture_output=True)
    return json.loads(rep.read_bytes().split(b"\n")[0])["version"]


class Runner:
    def __init__(self, a):
        self.a, self.out = a, Path(a.out)
        self.work = self.out.parent / (self.out.name + "-work")
        self.work.mkdir(parents=True, exist_ok=True)
        self.win = s3.Windows(self.work)
        self.rows = {}

    def test(self, name, env, out, pause=None, on_ready=None, timeout=1800):
        env = dict({k: v for k, v in os.environ.items() if not k.startswith(("TAPECTL_TEST", "DT_G3"))}, **env)
        with open(out / "test.stdout", "wb") as so, open(out / "test.stderr", "wb") as se:
            p = subprocess.Popen([self.a.test_exe, f"bridge::g3::{name}", "--exact", "--nocapture", "--test-threads=1"],
                                 stdout=so, stderr=se, env=env)
            acted = False
            if pause is not None:
                for _ in range(int(timeout * 10)):
                    if (pause / "ready").exists() or p.poll() is not None:
                        break
                    time.sleep(0.1)
                if (pause / "ready").exists():
                    on_ready()
                    acted = True
                (pause / "go").write_text("go")
            rc = p.wait(timeout=timeout)
        if rc != 0:
            print((out / "test.stdout").read_text(errors="replace")[-3000:], (out / "test.stderr").read_text(errors="replace")[-3000:])
            raise RuntimeError(f"{name} failed ({rc}) in {out}")
        return acted

    def child(self, case, pause=None, on_ready=None):
        out = self.out / "cases" / case["id"]
        out.mkdir(parents=True, exist_ok=True)
        case = dict(case, out=str(out))
        (out / "case.json").write_text(json.dumps(case, indent=1))
        acted = self.test(f"g3_child_{case['tool']}", {"DT_G3_CASE": str(out / "case.json")}, out, pause, on_ready)
        row = json.loads((out / "row.json").read_text())
        row["case"] = str(out / "case.json")
        row["raw_sha256"] = {Path(p).name: sha(p) for p in row["raw_refs"] if Path(p).is_file()}
        if pause is not None:
            row["boundary_action_performed"] = acted
        self.rows[case["id"]] = row
        print(f"{case['id']:28} exit {row['exit']:>3}  {row['message']!r}", flush=True)
        return row

    # ------------------------------------------------------------- ingest
    def ingest_cases(self):
        base = self.work / "ingest"
        if base.exists():
            shutil.rmtree(base)

        def folder(case, name="Music"):
            d = base / case / name
            d.mkdir(parents=True)
            return d

        m = folder("overage-one"); tone_wav(m / "one-hour-and-a-frame.wav", CAPACITY + 1)
        a, b = folder("overage-192", "Side A"), folder("overage-192", "Side B")
        half = (CAPACITY + 8467200 - GAP) // 2
        tone_wav(a / "a.wav", half); tone_wav(b / "b.wav", CAPACITY + 8467200 - GAP - half)
        m = folder("protected")
        mp4 = bytearray((ROOT / "host" / "ingest" / "tests" / "fixtures" / "tone.m4a").read_bytes())
        at = mp4.find(b"mp4a", mp4.find(b"stsd"))
        assert at > 0, "tone.m4a has no stsd mp4a entry"
        mp4[at:at + 4] = b"drms"          # the sample entry of a FairPlay-protected track
        (m / "locked.m4a").write_bytes(bytes(mp4))
        m = folder("corrupt"); (m / "broken.wav").write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + b"\x00" * 7)
        m = folder("nonmusic"); (m / "notes.txt").write_text("not music\n")
        folder("empty")
        m = folder("source-short"); tone_wav(m / "short.wav", 0)
        for case, folders in [("overage-one", ["Music"]), ("overage-192", ["Side A", "Side B"]), ("protected", ["Music"]),
                              ("corrupt", ["Music"]), ("nonmusic", ["Music"]), ("empty", ["Music"]), ("source-short", ["Music"])]:
            self.child({"id": case, "tool": "ingest", "ingest": self.a.ingest, "folders": [str(base / case / f) for f in folders]})

    # --------------------------------------------------------------- make
    def make_cases(self):
        w = self.win
        version = version_of(self.a.tapectl_test, "make", self.work)
        wav = self.work / "make.wav"; tone_wav(wav, 1024)
        trunc = self.work / "truncated.wav"; tone_wav(trunc, 1024, truncate=400)
        subprocess.run(["mountvol", "/N"], check=False)

        def vhd(name, mb):
            p = self.work / f"g3-{name}.vhd"
            if p.exists():
                p.unlink()
            w.diskpart(f'create vdisk file="{p}" maximum={mb} type=expandable')
            dev = w.attach(p)
            probe = subprocess.run([self.a.tapectl_test, "probe", dev], capture_output=True, text=True).stdout
            nbytes = int(next(l for l in probe.splitlines() if l.startswith("bytes="))[6:])
            return p, dev, nbytes

        def run(case, mb=1024, facts=True, fault=None, pause=None, during=None, label="C1 Music", audio=wav):
            p, dev, nbytes = vhd(case, mb)
            out = self.out / "cases" / case
            out.mkdir(parents=True, exist_ok=True)
            env = {"TAPECTL_TEST_TRACE": str(out / "child.trace.json")}
            if facts:
                (out / "child.facts").write_text(s3.facts_text(nbytes))
                env["TAPECTL_TEST_FACTS"] = str(out / "child.facts")
            if fault:
                env["TAPECTL_TEST_FAULT"] = fault
            gate = None
            if pause:
                gate = out / "gate"
                if gate.exists():
                    shutil.rmtree(gate)
                gate.mkdir()
                env["TAPECTL_TEST_PAUSE"] = f"{pause}:{gate}"
            row = self.child({"id": case, "tool": "make", "tapectl": self.a.tapectl_test, "version": version, "dev": dev,
                              "bytes": nbytes, "wav": str(audio), "label": label, "env": env},
                             pause=gate, on_ready=(lambda: during(p, dev)) if during else None)
            if during is not None and during.__name__ == "read_only":
                try:
                    w.diskpart(f"select disk {dev.rsplit('PhysicalDrive', 1)[1]}", "attributes disk clear readonly")
                except RuntimeError:
                    pass
            try:
                w.detach_file(p)
            except RuntimeError:
                pass
            row["target"] = {"vhd": str(p), "mb": mb, "device": dev, "bytes": nbytes, "facts_seam": facts, "fault": fault, "pause": pause}

        def detach(p, dev):
            w.detach_file(p)

        def read_only(p, dev):
            # Writes now fail in the OS (write protect), not as a removal.
            w.diskpart(f"select disk {dev.rsplit('PhysicalDrive', 1)[1]}", "attributes disk set readonly")

        run("small", mb=64)
        run("removed", pause="load", during=detach)
        run("device-io", pause="load", during=read_only)
        run("host-query", facts=False, fault="query-error:disk-length")
        run("verify-findings", fault="read-error:2048@verify")
        run("wav-truncated", audio=trunc)
        run("safety-refusal", facts=False)
        run("generic-make", label="x" * 33)

    # -------------------------------------------------------------- cards
    def cards_case(self):
        """More disks than tapectl cards lists (DISC_MAX_DISKS 64): the census really fails."""
        w = self.win
        version = version_of(self.a.tapectl, "cards", self.work)
        attached = []
        try:
            while True:
                n = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-Disk | Measure-Object -Property Number -Maximum).Maximum"],
                                   capture_output=True, text=True).stdout.strip()
                if int(n) >= 64:
                    break
                batch = []
                for _ in range(min(16, 64 - int(n))):
                    p = self.work / f"g3-many-{len(attached)}.vhd"
                    if p.exists():
                        p.unlink()
                    batch += [f'create vdisk file="{p}" maximum=3 type=expandable', f'select vdisk file="{p}"', "attach vdisk"]
                    attached.append(p)
                w.diskpart(*batch)
            print(f"disks attached for the census: {len(attached)} (highest disk number {n})", flush=True)
            self.child({"id": "discovery-unavailable", "tool": "cards", "tapectl": self.a.tapectl, "version": version})
            self.rows["discovery-unavailable"]["target"] = {"vhds_attached": len(attached), "highest_disk_number": int(n)}
        finally:
            for i in range(0, len(attached), 16):
                try:
                    w.diskpart(*[x for p in attached[i:i + 16] for x in (f'select vdisk file="{p}"', "detach vdisk")])
                except RuntimeError:
                    pass

    def app_cases(self):
        out = self.out / "app"
        out.mkdir(parents=True, exist_ok=True)
        self.test("g3_app_origin", {"DT_G3_APP_OUT": str(out)}, out)
        for r in json.loads((out / "app-rows.json").read_text()):
            self.rows[r["id"]] = r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("ingest", "tapectl", "tapectl-test", "test-exe", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--source", default=None)
    ap.add_argument("--only", default=None, help="comma-separated groups: app,ingest,make,cards")
    a = ap.parse_args()
    for k in ("ingest", "tapectl", "tapectl_test", "test_exe"):
        setattr(a, k, os.path.abspath(getattr(a, k)))
    r = Runner(a)
    groups = (a.only or "app,ingest,make,cards").split(",")
    for g in groups:
        getattr(r, {"app": "app_cases", "ingest": "ingest_cases", "make": "make_cases", "cards": "cards_case"}[g])()
    src = a.source or subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    rows = [r.rows.get(c["id"], {"id": c["id"], "missing": True}) for c in g3.CASES]
    result = {"source_sha": src, "platform": "windows", "children": {"ingest": {"path": a.ingest, "sha256": sha(a.ingest)},
              "tapectl": {"path": a.tapectl, "sha256": sha(a.tapectl)}, "tapectl_test": {"path": a.tapectl_test, "sha256": sha(a.tapectl_test)},
              "test_exe": {"path": a.test_exe, "sha256": sha(a.test_exe)}},
              "adapter": {"orchestrator": "tools/app/g3_624.py", "bridge_tests": "host/app/tests/g3_component.rs"}, "rows": rows}
    (r.out / "G3-RESULT.json").write_text(json.dumps(result, indent=1))
    print("\n== against g3.CASES ==")
    bad = 0
    for c, row in zip(g3.CASES, rows):
        ok = (row.get("message") == c["message"]) if c["message"] is not None else row.get("card_line_current") is True
        extra = [k for k in ("details_copyable",) if not row.get(k)]
        if c["origin"] == "child" and row.get("message_changed_stderr") != row.get("message"):
            extra.append("stderr-changed-message")
        bad += (not ok) or bool(extra)
        print(f"{'ok ' if ok and not extra else 'NO '} {c['id']:44} {row.get('message')!r}{'  ' + ','.join(extra) if extra else ''}")
    def check(rs):
        try:
            return {"result": "PASS", "rows": g3.check(rs)}
        except (AssertionError, KeyError) as e:
            return {"result": "FAIL", "assertion": repr(e)}
    verdict = {"g3_check": check(rows), "rows_not_matching": bad}
    # A rejected drop starts no child and is not a Problem state (APP-1 §6 gives Show
    # details to Problem states), so the app has no diagnostics to copy for it. Returned
    # for disposition; the same check with only that one field excused is shown beside it.
    no_diag = [r["id"] for r in rows if r["id"] in ("drop-file", "drop-mixed") and not r.get("details_copyable")]
    if no_diag:
        excused = [dict(r, details_copyable=True) if r["id"] in no_diag else r for r in rows]
        verdict["g3_check_if_rejected_drop_needs_no_details"] = dict(check(excused), excused_rows=no_diag, excused_field="details_copyable")
    verdict["g3_check"] = verdict["g3_check"]["result"] if verdict["g3_check"]["result"] == "PASS" else verdict["g3_check"]
    (r.out / "G3-VERDICT.json").write_text(json.dumps(verdict, indent=1))
    print(json.dumps(verdict))
    passed = verdict["g3_check"] == "PASS" or verdict.get("g3_check_if_rejected_drop_needs_no_details", {}).get("result") == "PASS"
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
