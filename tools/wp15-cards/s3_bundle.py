#!/usr/bin/env python3
"""#624 S3: Software's actual `tapectl make` observations, packaged as the BUNDLE.json
of tests/wp15_cards_make_r1 (ADAPTER.md "Make (S3)"). It judges nothing; the imported
runner.py does, and Verification disposes.

Every make row runs the real tapectl-test binary on a real device node (a Linux loop
device or a Windows VHD) through the existing TAPECTL_TEST facts seam: the device, its
raw I/O, the flushes and the OS errors are real; only the "is this a memory card?"
facts are supplied. Each injected positive is paired with the SHIPPED tapectl refusing
the same node (`shipped/*`). Events come from the compiled-test trace (host/port/
trace_test.c), mapped one-to-one onto the oracle's journal names:

  write_open -> open(role=authorized, access=readwrite)    make_safety_pass -> safety_pass
  make_phase -> phase(write_callback_null)                  engine_bind -> bind
  read/write/flush -> read/write/flush                      make_media_change -> media_change
  unmount -> unmount(partition=1)                           make_close -> close

The observer is qualified by its own positive control (a standalone provision whose
trace must show the authorized open and its writes). Removal rows pause make at a phase
boundary (TAPECTL_TEST_PAUSE), detach or swap the VHD, and let make's next real I/O
meet the OS error. Rows the imported predicates cannot judge as written are run and
kept under `unjudged/` with the reason, never forced into the bundle.

  s3_bundle.py --platform linux|windows --tapectl BIN --tapectl-test BIN --out DIR [--source SHA]
"""
import argparse, hashlib, json, os, random, re, shutil, struct, subprocess, sys, time
from pathlib import Path

NONCE = "00112233445566778899aabbccddeeff"
IMG_BYTES = 22020096          # 21 MiB: the WP-14 trace self-check geometry, room for --length-s 9
LEN_S = 9
RATE = 44100


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def wav(path, frames, rate=RATE, truncate=0, seed=1):
    r = random.Random(seed)
    data = bytes(r.getrandbits(8) for _ in range(frames * 4))
    hdr = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 2, rate, rate * 4, 4, 16)
    hdr += b"data" + struct.pack("<I", len(data))
    Path(path).write_bytes(hdr + data[:len(data) - truncate])


# ------------------------------------------------------------------ devices

class Linux:
    name = "linux"

    def __init__(self, work):
        self.work = work

    def attach(self, img):
        return subprocess.run(["losetup", "-f", "--show", str(img)], check=True, capture_output=True, text=True).stdout.strip()

    def detach(self, dev):
        subprocess.run(["losetup", "-d", dev], check=True)

    def dm_wrap(self, dev, name):
        size = subprocess.run(["blockdev", "--getsz", dev], check=True, capture_output=True, text=True).stdout.strip()
        subprocess.run(["dmsetup", "create", name, "--table", f"0 {size} linear {dev} 0"], check=True)
        return f"/dev/mapper/{name}", size

    def dm_fail(self, name, size):
        """Replace the live table with an error target: every later I/O is a plain EIO."""
        subprocess.run(["dmsetup", "suspend", "--nolockfs", "--noflush", name], check=True)
        subprocess.run(["dmsetup", "load", name, "--table", f"0 {size} error"], check=True)
        subprocess.run(["dmsetup", "resume", name], check=True)

    def dm_remove(self, name):
        subprocess.run(["dmsetup", "remove", "--force", name], check=False)


class Windows:
    name = "windows"

    def __init__(self, work):
        self.work = work
        self.attached = {}

    def diskpart(self, *lines):
        s = self.work / f"dp-{time.time_ns()}.txt"
        s.write_text("\n".join(lines) + "\n")
        p = subprocess.run(["diskpart", "/s", str(s)], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"diskpart {lines}: {p.stdout}{p.stderr}")

    def create(self, vhd, mb=64):
        self.diskpart(f'create vdisk file="{vhd}" maximum={mb} type=fixed')

    def attach(self, vhd):
        self.diskpart(f'select vdisk file="{vhd}"', "attach vdisk")
        n = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-DiskImage -ImagePath '{vhd}' | Get-Disk).Number"],
                           check=True, capture_output=True, text=True).stdout.strip()
        dev = f"\\\\.\\PhysicalDrive{n}"
        self.attached[dev] = vhd
        return dev

    def detach_file(self, vhd):
        self.diskpart(f'select vdisk file="{vhd}"', "detach vdisk")


# ------------------------------------------------------------------ bundle

def facts_text(bytes_, **kw):
    f = {"whole": 1, "removable": 1, "sd_bus": 0, "bytes": bytes_, "holds_os": 0, "layout_ok": 0}
    mounted = kw.pop("mounted", [])
    f.update(kw)
    return "".join(f"{k}={v}\n" for k, v in f.items()) + "".join(f"mounted={m}\n" for m in mounted)


def oracle_facts(text, erase_matches, unmount_failed=False):
    """A facts file -> make_policy's fact names (missing keys refuse, as the seam does)."""
    kv, mounted = {}, []
    for line in text.splitlines():
        k, _, v = line.partition("=")
        if k == "mounted":
            mounted.append(int(v.split(":")[0]))
        elif k:
            kv[k] = v
    i = lambda k, d: bool(int(kv[k])) if k in kv else d
    return {"whole": i("whole", False), "removable": i("removable", False), "sd_bus": i("sd_bus", False),
            "virtual": False, "bytes": int(kv.get("bytes", 0)), "holds_os": i("holds_os", True), "mounted": mounted,
            "exact_layout": i("layout_ok", False), "unmount_failed": unmount_failed, "erase_matches": erase_matches}


def reason(os_error):
    if os_error in ("ERROR_MEDIA_CHANGED",):
        return "changed"
    if os_error in ("ERROR_DEV_NOT_EXIST", "ERROR_NO_SUCH_DEVICE", "ERROR_DEVICE_NOT_CONNECTED", "ENXIO", "ENODEV"):
        return "disappeared"
    return "removed"


def journal(trace):
    """compiled-test trace -> the oracle's device journal (see module docstring)."""
    ev, phase = [], None
    for e in trace["events"]:
        k = e["kind"]
        if k == "write_open" and e.get("device"):
            ev.append({"op": "open", "role": "authorized", "access": "readwrite", "session": 1, "device": True, "ok": e["ok"]})
        elif k == "open" and e.get("device"):
            ev.append({"op": "open", "role": "query", "access": "read", "session": None, "device": True, "ok": e["ok"]})
        elif k == "make_safety_pass":
            ev.append({"op": "safety_pass", "device": True})
        elif k == "make_phase":
            phase = e["phase"]
            ev.append({"op": "phase", "phase": phase, "write_callback_null": e["write_is_null"], "session": 1, "device": True})
        elif k == "engine_bind":
            ev.append({"op": "bind", "phase": phase, "write_callback_null": e["write_is_null"], "session": 1, "device": True})
        elif k in ("read", "write", "flush"):
            ev.append({"op": k, "session": 1, "device": True, "ok": e.get("success", e.get("ok", True))})
        elif k == "make_media_change":
            ev.append({"op": "media_change", "reason": reason(e["os_error"]), "phase": e["phase"], "os_error": e["os_error"],
                       "session": 1, "device": True, "stdout_bytes": e["stdout_bytes"]})
        elif k == "unmount":
            ev.append({"op": "unmount", "partition": 1, "device": True, "ok": e["os_success"]})
        elif k == "make_close":
            ev.append({"op": "close", "device": True})
    return ev


class B:
    def __init__(self, a, plat):
        self.a, self.plat, self.out = a, plat, Path(a.out)
        self.files, self.rows, self.unjudged, self.n = {}, [], [], 0
        self.control_seen = False

    def keep(self, name, data):
        p = self.out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, Path):
            shutil.copyfile(data, p)
        else:
            p.write_bytes(data if isinstance(data, bytes) else data.encode())
        self.files[name] = sha(p)
        return name

    def process(self, argv, env=None, pause=None, on_ready=None, facts=None):
        """Run one command; stdout to a file (so the trace can mark stdout positions)."""
        self.n += 1
        base = self.out / "raw" / f"{self.n:03d}"
        base.parent.mkdir(parents=True, exist_ok=True)
        env = dict(env or {k: v for k, v in os.environ.items() if not k.startswith("TAPECTL_TEST")})
        trace = Path(str(base) + ".trace.json")
        env["TAPECTL_TEST_TRACE"] = str(trace)
        if facts is not None:
            fp = Path(str(base) + ".facts")
            fp.write_text(facts)
            env["TAPECTL_TEST_FACTS"] = str(fp)
        gate = None
        if pause:
            gate = Path(str(base) + ".gate")
            gate.mkdir()
            env["TAPECTL_TEST_PAUSE"] = f"{pause}:{gate}"
        with open(str(base) + ".stdout", "wb") as so, open(str(base) + ".stderr", "wb") as se:
            p = subprocess.Popen(argv, stdout=so, stderr=se, env=env)
            if gate is not None:
                for _ in range(1200):
                    if (gate / "ready").exists() or p.poll() is not None:
                        break
                    time.sleep(0.1)
                if (gate / "ready").exists():
                    on_ready()
                (gate / "go").write_text("go")
            rc = p.wait(timeout=600)
        res = {"argv": argv, "exit": rc, "executable_sha256": sha(argv[0]),
               "stdout": Path(str(base) + ".stdout").read_bytes(), "stderr": Path(str(base) + ".stderr").read_bytes(),
               "trace": json.loads(trace.read_text()) if trace.exists() else None, "base": base,
               "paused": bool(gate and (gate / "ready").exists())}
        return res

    def make(self, dev, label="Make", wav_path=None, erase=None, extra=(), report=True, binary=None):
        ctrl = self.out / "control" / f"{self.n + 1:03d}"
        ctrl.mkdir(parents=True, exist_ok=True)
        rep = ctrl / "make.jsonl"
        argv = [binary or self.a.tapectl_test, "make", dev, "--label", label, "--length-s", str(LEN_S),
                "--wav", str(wav_path), "--erase", erase if erase is not None else dev] + list(extra)
        if report:
            argv += ["--report", str(rep), "--report-nonce", NONCE]
        return argv, rep

    def session_row(self, name, scope, res, rep, facts, foreign_before, foreign_after, equivalence=None):
        base = f"rows/{len(self.rows):03d}"
        ev = journal(res["trace"]) if res["trace"] else []
        change = [e for e in ev if e["op"] == "media_change"]
        after = res["stdout"][change[0]["stdout_bytes"]:] if change else b""
        report = rep.read_bytes() if rep.exists() else b""
        version = json.loads(report.split(b"\n")[0])["version"] if report else None
        rec = {"exit": res["exit"], "argv": res["argv"], "executable_sha256": res["executable_sha256"],
               "trace_complete": res["trace"] is not None, "observer": "compiled-test",
               "positive_control_seen": self.control_seen, "events": ev, "facts": facts,
               "version": version, "nonce": NONCE, "foreign_before": foreign_before, "foreign_after": foreign_after,
               "stdout_after_change_hex": after.hex(), "paused_at_boundary": res["paused"], "scope": scope,
               "trace": self.keep(base + ".trace.json", json.dumps(res["trace"], indent=1))}
        row = {"name": name, "kind": "session", "scope": scope,
               "record": self.keep(base + ".record.json", json.dumps(rec, indent=1)),
               "stdout": self.keep(base + ".stdout", res["stdout"]), "stderr": self.keep(base + ".stderr", res["stderr"]),
               "report": self.keep(base + ".report.jsonl", report)}
        if equivalence:
            row["equivalence"] = equivalence
        self.rows.append(row)
        term = report.decode(errors="replace").split("\n")
        refusal = next((l for l in term if '"t":"refusal"' in l), "")
        print(f"{name:44} exit {res['exit']}  {refusal[:110]}", flush=True)

    def parent_row(self, name, scope, rec, res, rep):
        base = f"rows/{len(self.rows):03d}"
        rec = dict(rec, exit=res["exit"], argv=res["argv"], scope=scope)
        row = {"name": name, "kind": "parent", "scope": scope,
               "record": self.keep(base + ".record.json", json.dumps(rec, indent=1)),
               "stdout": self.keep(base + ".stdout", res["stdout"]), "stderr": self.keep(base + ".stderr", res["stderr"])}
        if rep is not None and rep.is_file() and not rep.is_symlink():
            row["report"] = self.keep(base + ".report.jsonl", rep.read_bytes())
        self.rows.append(row)
        print(f"{name:44} exit {res['exit']}  device_work={rec['device_work']}", flush=True)

    def unjudged_row(self, name, why, res, rep):
        base = f"unjudged/{len(self.unjudged):03d}"
        self.keep(base + ".stdout", res["stdout"])
        self.keep(base + ".stderr", res["stderr"])
        if rep is not None and rep.exists():
            self.keep(base + ".report.jsonl", rep.read_bytes())
        if res["trace"]:
            self.keep(base + ".trace.json", json.dumps(res["trace"], indent=1))
        self.unjudged.append({"name": name, "why": why, "exit": res["exit"], "argv": res["argv"], "files": base})
        print(f"{name:44} exit {res['exit']}  (unjudged: {why})", flush=True)


def device_work(trace):
    return bool(trace) and any(e["kind"] in ("write_open", "open", "write", "read") for e in trace["events"])


def inventory(d):
    d = Path(d)
    out = {}
    for p in sorted(d.rglob("*")) if d.exists() else []:
        out[str(p.relative_to(d))] = sha(p) if p.is_file() and not p.is_symlink() else ("link" if p.is_symlink() else "dir")
    return out


# ------------------------------------------------------------------ rows

def linux_rows(b, a):
    plat, work = b.plat, b.work
    T, TT = a.tapectl, a.tapectl_test
    w = {n: work / f"w{n}.wav" for n in (1, 1023, 1024, 1025)}
    for n, p in w.items():
        wav(p, n, seed=n)
    wav(work / "fit.wav", LEN_S * RATE)
    wav(work / "over.wav", LEN_S * RATE + 1)
    wav(work / "bad48k.wav", 1024, rate=48000)
    wav(work / "trunc.wav", 1024, truncate=4 * 100)

    def pristine(name, fill):
        p = work / f"{name}.img"
        p.write_bytes(fill if isinstance(fill, bytes) else bytes(IMG_BYTES))
        return p

    zero = bytes(IMG_BYTES)
    rnd = random.Random(7).randbytes(IMG_BYTES)
    crc = bytearray(IMG_BYTES); crc[510:512] = b"\x55\xaa"

    # Observer positive control: a standalone provision must show its open and writes.
    img = pristine("ctl", zero); dev = plat.attach(img)
    res = b.process([TT, "provision", dev, "--label", "ctl", "--length-s", str(LEN_S), "--erase", dev],
                    facts=facts_text(IMG_BYTES))
    plat.detach(dev)
    ev = [e["kind"] for e in res["trace"]["events"]]
    b.control_seen = res["exit"] == 0 and "write_open" in ev and "write" in ev
    b.keep("control/positive.trace.json", json.dumps(res["trace"], indent=1))
    print(f"observer positive control: {'seen' if b.control_seen else 'NOT SEEN'}", flush=True)

    scope = "compiled-test: tapectl-test make on a Linux loop device (real raw I/O; injected card facts)"

    def equivalence_pair(name, fill, wavp, label="Make"):
        a_img, s_img = pristine(name + "-make", fill), pristine(name + "-separate", fill)
        da, ds = plat.attach(a_img), plat.attach(s_img)
        argv, rep = b.make(da, label=label, wav_path=wavp)
        before = sha(a_img)
        mk = b.process(argv, facts=facts_text(IMG_BYTES))
        m = re.match(rb"uuid ([0-9a-f]{32})\nepoch ([0-9]+)\n", mk["stdout"])
        stages = []
        if m:
            f = facts_text(IMG_BYTES)
            p1 = b.process([TT, "provision", ds, "--label", label, "--length-s", str(LEN_S), "--uuid", m.group(1).decode(),
                            "--epoch", m.group(2).decode(), "--erase", ds], facts=f)
            stages.append(p1)
            if p1["exit"] == 0:
                p2 = b.process([TT, "load", ds, str(wavp)], facts=f)
                stages.append(p2)
                if p2["exit"] == 0:
                    stages.append(b.process([TT, "verify", ds], facts=f))
        plat.detach(da); plat.detach(ds)
        facts = oracle_facts(facts_text(IMG_BYTES), True)
        base = f"equivalence/{name}"
        procs, outs = [], []
        for i, s in enumerate([mk] + stages + [None] * (3 - len(stages))):
            desc = {"exit": None, "argv": None} if s is None else {"exit": s["exit"], "argv": s["argv"], "executable_sha256": s["executable_sha256"]}
            procs.append(b.keep(f"{base}/p{i}.json", json.dumps(desc)))
            outs.append(b.keep(f"{base}/p{i}.stdout", b"" if s is None else s["stdout"]))
        eq = {"processes": procs, "stdout": outs, "make_image": b.keep(f"{base}/make.img", a_img),
              "separate_image": b.keep(f"{base}/separate.img", s_img)}
        b.session_row(name, scope + "; byte/output equivalence against standalone provision/load/verify", mk, rep, facts,
                      before, sha(a_img), equivalence=eq if m else None)

    for n in (1, 1023, 1024, 1025):
        equivalence_pair(f"equivalent-{n}-frames", zero, w[n])
    equivalence_pair("raw-unmounted-positive", rnd, w[1024])
    lab = "Ünïcødé ✓ "
    equivalence_pair("label-32-UTF8-bytes", zero, w[1024], label=lab + "x" * (32 - len(lab.encode())))
    equivalence_pair("exact-fit", zero, work / "fit.wav")
    equivalence_pair("one-frame-over", zero, work / "over.wav")
    equivalence_pair("bad-WAV", zero, work / "bad48k.wav")
    equivalence_pair("WAV-truncated-after-start", zero, work / "trunc.wav")

    # Policy: one refusal per ordered rule, combined faults, unknown facts, mounted hints.
    good = {}
    policy = [
        ("refuse-not-whole", dict(whole=0), None),
        ("refuse-not-removable", dict(removable=0, sd_bus=0), None),
        ("refuse-too-large", dict(bytes=2**37 + 512), None),
        ("refuse-system-disk", dict(holds_os=1), None),
        ("refuse-foreign-mount", dict(mounted=["2:/media/other"]), None),
        ("refuse-erase-not-confirmed", {}, "/dev/not-this-one"),
        ("combined-not-whole-and-not-removable", dict(whole=0, removable=0), None),
        ("combined-system-and-foreign", dict(holds_os=1, mounted=["2:/media/other"]), None),
        ("OS-own-hint-byte-invalid", dict(mounted=["1:/media/DIGITALTAPE"], layout_ok=0), None),
        ("bare-CRC-55AA-mounted", dict(mounted=["1:/media/DIGITALTAPE"], layout_ok=0), None),
        # Own partition 1 of an exact layout may be unmounted, and only it; here the OS
        # unmount itself fails (the existing unmount-error control: a real failed call).
        ("own-p1-unmount-failed", dict(mounted=["1:/media/DIGITALTAPE"], layout_ok=1), None),
    ]
    for name, kw, erase in policy:
        img = pristine(name, bytes(crc) if "55AA" in name else rnd)
        dev = plat.attach(img)
        kw = dict(kw)
        nbytes = kw.pop("bytes", IMG_BYTES)
        ftxt = facts_text(nbytes, **kw)
        argv, rep = b.make(dev, wav_path=w[1024], erase=erase)
        before = sha(img)
        env = {k: v for k, v in os.environ.items() if not k.startswith("TAPECTL_TEST")}
        if name == "own-p1-unmount-failed":
            env["TAPECTL_TEST_FAULT"] = "unmount-error"
        res = b.process(argv, env=env, facts=ftxt)
        plat.detach(dev)
        b.session_row(name, scope + "; policy refusal, zero writes", res, rep,
                      oracle_facts(ftxt, erase is None, unmount_failed=name == "own-p1-unmount-failed"), before, sha(img))
    # Unknown facts: an empty facts file keeps every refusing default.
    img = pristine("unknown-facts", rnd); dev = plat.attach(img)
    argv, rep = b.make(dev, wav_path=w[1024]); before = sha(img)
    res = b.process(argv, facts="")
    plat.detach(dev)
    b.session_row("unknown-facts-refuse", scope + "; empty facts file", res, rep, oracle_facts("", True), before, sha(img))

    # Paired real shipped refusal: the shipped binary, no seam, the same kind of node.
    img = pristine("shipped", rnd); dev = plat.attach(img)
    argv, rep = b.make(dev, wav_path=w[1024], binary=T); before = sha(img)
    res = b.process(argv)
    plat.detach(dev)
    b.unjudged_row("shipped/loop-refused", f"shipped tapectl, real probe, no seam: exit {res['exit']}; "
                   f"bytes {'unchanged' if before == sha(img) else 'CHANGED'}; probe facts are not the oracle's injected facts", res, rep)

    # Geometry before write: too small for partition 2's geometry; one open, zero writes.
    small = work / "small.img"; small.write_bytes(bytes(34816 * 512 + 64 * 512))
    dev = plat.attach(small)
    argv, rep = b.make(dev, wav_path=w[1024]); before = sha(small)
    res = b.process(argv, facts=facts_text(small.stat().st_size))
    plat.detach(dev)
    b.session_row("geometry-before-write", scope + "; GEOMETRY refused before any write", res, rep,
                  oracle_facts(facts_text(small.stat().st_size), True), before, sha(small))

    # Verify findings: one real failed OS read of the first chunk (partition LBA 2048,
    # tapefs §3), during verify only.
    img = pristine("verify-findings", zero); dev = plat.attach(img)
    argv, rep = b.make(dev, wav_path=w[1024]); before = sha(img)
    env = {k: v for k, v in os.environ.items() if not k.startswith("TAPECTL_TEST")}
    env["TAPECTL_TEST_FAULT"] = "read-error:2048@verify"
    res = b.process(argv, env=env, facts=facts_text(IMG_BYTES))
    plat.detach(dev)
    b.session_row("verify-findings", scope + "; real failed OS read during verify (read-error:2048@verify)", res, rep,
                  oracle_facts(facts_text(IMG_BYTES), True), before, sha(img))

    # Generic EIO is not a card change: a device-mapper error target swapped in mid-load.
    img = pristine("eio", zero); loop = plat.attach(img)
    dm, size = plat.dm_wrap(loop, "dt624eio")
    argv, rep = b.make(dm, wav_path=w[1024])
    res = b.process(argv, pause="load", on_ready=lambda: plat.dm_fail("dt624eio", size), facts=facts_text(IMG_BYTES))
    plat.dm_remove("dt624eio"); plat.detach(loop)
    b.session_row("generic-EIO-not-card-changed", scope + "; dm error target at the load boundary: plain EIO", res, rep,
                  oracle_facts(facts_text(IMG_BYTES), True), None, None)

    # Rows the imported predicates cannot judge as written (reasons recorded).
    img = pristine("label33", zero); dev = plat.attach(img)
    argv, rep = b.make(dev, label="x" * 33, wav_path=w[1024]); before = sha(img)
    res = b.process(argv, facts=facts_text(IMG_BYTES)); plat.detach(dev)
    b.unjudged_row("label-33-UTF8-bytes", "LABEL_INVALID exits 2 before any device open; session() requires either a "
                   f"policy refusal or one authorized open. Bytes {'unchanged' if before == sha(img) else 'CHANGED'}", res, rep)

    # Judge negative control: a write callback during verify must fail the imported oracle.
    img = pristine("neg", zero); dev = plat.attach(img)
    argv, rep = b.make(dev, wav_path=w[1024])
    env = {k: v for k, v in os.environ.items() if not k.startswith("TAPECTL_TEST")}
    env["TAPECTL_TEST_FAULT"] = "nonnull-binding"
    neg = b.process(argv, env=env, facts=facts_text(IMG_BYTES)); plat.detach(dev)
    return (neg, rep)


def parent_rows(b, a, dev, nbytes, wavp, junction):
    """Report leaf and parent binding (APP-1A §1). Passing facts on a real device, so a
    refusal that did any device work would show it in the trace."""
    work = b.work / "parent"
    work.mkdir(exist_ok=True)
    foreign = work / "foreign"
    foreign.mkdir(exist_ok=True)
    (foreign / "sentinel.txt").write_bytes(b"foreign sentinel\n")
    scope = f"actual {b.plat.name} filesystem; tapectl-test make with passing facts on a real device node"

    def run(name, ctrl_parent_setup, substituted, leaf_setup=None):
        rep = ctrl_parent_setup(work / name)

        if leaf_setup:
            leaf_setup(rep)
        fb = inventory(foreign)
        argv = [a.tapectl_test, "make", dev, "--label", "Make", "--length-s", str(LEN_S), "--wav", str(wavp), "--erase", dev,
                "--report", str(rep), "--report-nonce", NONCE]
        ftxt = facts_text(nbytes, whole=0) if not substituted else facts_text(nbytes)
        res = b.process(argv, facts=ftxt)
        fa = inventory(foreign)
        made = rep.is_file() and not rep.is_symlink() and rep.read_bytes().startswith(b'{"t":"start","tool":"tapectl make"')
        rec = {"substituted": substituted, "device_work": device_work(res["trace"]),
               "foreign_before": fb, "foreign_after": fa,
               "foreign_leaf_created": any(k not in fb for k in fa), "foreign_deleted": any(k not in fa for k in fb),
               "exclusive_leaf": made and not substituted, "parent_identity_bound": made and not substituted}
        b.parent_row(name, scope, rec, res, rep if not substituted else None)

    def plain(ctrl):
        ctrl.mkdir(parents=True)
        return ctrl / "make.jsonl"

    run("ordinary-exclusive-report", plain, False)
    run("existing-leaf", plain, True, lambda rep: rep.write_bytes(b"already here\n"))
    if b.plat.name == "linux":
        run("dangling-link-leaf", plain, True, lambda rep: os.symlink(foreign / "would-be-created", rep))
        run("symlink-leaf", plain, True, lambda rep: os.symlink(foreign / "sentinel.txt", rep))

    def substituted_parent(ctrl):
        link(foreign, ctrl, junction)
        return ctrl / "make.jsonl"

    def reparse_ancestor(ctrl):
        mid = work / (ctrl.name + "-real")
        if mid.exists():
            shutil.rmtree(mid)
        (mid / "control").mkdir(parents=True)
        link(mid, ctrl, junction)
        return ctrl / "control" / "make.jsonl"

    run("substituted-parent", substituted_parent, True)
    run("reparse-parent", reparse_ancestor, True)



def link(target, at, junction):
    if junction:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(at), str(target)], check=True, capture_output=True)
    else:
        os.symlink(target, at, target_is_directory=True)


def windows_rows(b, a):
    plat, work = b.plat, b.work
    T, TT = a.tapectl, a.tapectl_test
    wav(work / "w.wav", 1024, seed=3)
    wavp = work / "w.wav"
    scope = "compiled-test: tapectl-test make on a Windows Server VHD (real raw I/O and OS errors; injected card facts)"
    # Keep Windows from mounting the new partition 1 and writing to it between runs.
    subprocess.run(["mountvol", "/N"], check=False)

    def vhd(name):
        p = work / f"{name}.vhd"
        if p.exists():
            p.unlink()
        plat.create(p)
        return p

    # Observer positive control.
    v = vhd("ctl"); dev = plat.attach(v)
    probe = subprocess.run([TT, "probe", dev], capture_output=True, text=True).stdout
    nbytes = int(next(l for l in probe.splitlines() if l.startswith("bytes="))[6:])
    res = b.process([TT, "provision", dev, "--label", "ctl", "--length-s", str(LEN_S), "--erase", dev], facts=facts_text(nbytes))
    plat.detach_file(v)
    ev = [e["kind"] for e in res["trace"]["events"]]
    b.control_seen = res["exit"] == 0 and "write_open" in ev and "write" in ev
    b.keep("control/positive.trace.json", json.dumps(res["trace"], indent=1))
    print(f"observer positive control: {'seen' if b.control_seen else 'NOT SEEN'}; VHD {nbytes} bytes", flush=True)
    facts = oracle_facts(facts_text(nbytes), True)

    def session(name, pause=None, during=None, note=""):
        v = vhd(name)
        dev = plat.attach(v)
        argv, rep = b.make(dev, wav_path=wavp)
        state = {"dev": dev}
        res = b.process(argv, pause=pause, on_ready=(lambda: during(v, state)) if during else None, facts=facts_text(nbytes))
        try:
            plat.detach_file(v)
        except RuntimeError:
            pass
        for other in state.get("extra", []):
            try:
                plat.detach_file(other)
            except RuntimeError:
                pass
        b.session_row(name, scope + note, res, rep, facts, None, None)
        return res

    def remove(v, state):
        plat.detach_file(v)

    def reinsert(v, state):
        plat.detach_file(v)
        state["again"] = plat.attach(v)

    def swap(v, state):
        plat.detach_file(v)
        other = vhd(v.stem + "-B")
        state["swapped_to"] = plat.attach(other)
        state["extra"] = [other]

    def raw(dev, path):
        """The attached disk's bytes, read through the OS as they are now."""
        with open(dev, "rb", buffering=0) as d, open(path, "wb") as f:
            left = nbytes
            while left:
                chunk = d.read(min(left, 1 << 20))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        return path

    def equivalence(name):
        va, vs = vhd(name + "-make"), vhd(name + "-separate")
        da, ds = plat.attach(va), plat.attach(vs)
        argv, rep = b.make(da, wav_path=wavp)
        mk = b.process(argv, facts=facts_text(nbytes))
        m = re.match(rb"uuid ([0-9a-f]{32})\nepoch ([0-9]+)\n", mk["stdout"])
        stages = []
        if m:
            p1 = b.process([TT, "provision", ds, "--label", "Make", "--length-s", str(LEN_S), "--uuid", m.group(1).decode(),
                            "--epoch", m.group(2).decode(), "--erase", ds], facts=facts_text(nbytes))
            stages.append(p1)
            if p1["exit"] == 0:
                p2 = b.process([TT, "load", ds, str(wavp)], facts=facts_text(nbytes))
                stages.append(p2)
                if p2["exit"] == 0:
                    stages.append(b.process([TT, "verify", ds], facts=facts_text(nbytes)))
        ia, isep = raw(da, work / f"{name}-make.img"), raw(ds, work / f"{name}-separate.img")
        plat.detach_file(va); plat.detach_file(vs)
        base = f"equivalence/{name}"
        procs, outs = [], []
        for i, s in enumerate([mk] + stages + [None] * (3 - len(stages))):
            desc = {"exit": None, "argv": None} if s is None else {"exit": s["exit"], "argv": s["argv"], "executable_sha256": s["executable_sha256"]}
            procs.append(b.keep(f"{base}/p{i}.json", json.dumps(desc)))
            outs.append(b.keep(f"{base}/p{i}.stdout", b"" if s is None else s["stdout"]))
        eq = {"processes": procs, "stdout": outs, "make_image": b.keep(f"{base}/make.img", ia),
              "separate_image": b.keep(f"{base}/separate.img", isep)}
        b.session_row(name, scope + "; success, one retained session, NULL-write verify; raw disk bytes compared with "
                      "standalone provision/load/verify (automount off)", mk, rep, facts, None, None, equivalence=eq if m else None)

    equivalence("no-change")
    session("detected-remove-load", "load", remove, "; VHD detached at the load boundary")
    session("detected-remove-commit", "commit", remove, "; VHD detached at the commit boundary")
    session("remove-reinsert-load", "load", reinsert, "; VHD detached and re-attached (same path) at the load boundary")
    session("equal-size-change-detected", "verify", swap, "; VHD A detached, equal-size VHD B attached at the same path, during verify")
    session("CARD_CHANGED-precedence", "verify", remove, "; detach during verify: CARD_CHANGED, never READ_ERROR findings")

    # Paired real shipped refusal on the same kind of node.
    v = vhd("shipped"); dev = plat.attach(v)
    argv, rep = b.make(dev, wav_path=wavp, binary=T)
    before = sha(v)
    res = b.process(argv)
    plat.detach_file(v)
    b.unjudged_row("shipped/vhd-refused", f"shipped tapectl, real probe, no seam: exit {res['exit']}; VHD file "
                   f"{'unchanged' if before == sha(v) else 'CHANGED'}; probe facts are not the oracle's injected facts", res, rep)

    v = vhd("parent"); dev = plat.attach(v)
    parent_rows(b, a, dev, nbytes, wavp, junction=True)
    plat.detach_file(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--platform", required=True, choices=["linux", "windows"])
    for k in ("tapectl", "tapectl-test", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--source", default=None)
    a = ap.parse_args()
    a.tapectl, a.tapectl_test = os.path.abspath(a.tapectl), os.path.abspath(a.tapectl_test)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    work = out.parent / (out.name + "-work")
    work.mkdir(parents=True, exist_ok=True)
    plat = Linux(work) if a.platform == "linux" else Windows(work)
    b = B(a, plat)
    b.work = work
    neg = None
    if a.platform == "linux":
        neg = linux_rows(b, a)
        img = work / "parent.img"; img.write_bytes(bytes(IMG_BYTES)); dev = plat.attach(img)
        wav(work / "p.wav", 1024)
        parent_rows(b, a, dev, IMG_BYTES, work / "p.wav", junction=False)
        plat.detach(dev)
    else:
        windows_rows(b, a)
    src = a.source or subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    head = {"source_sha": src, "binary_sha256": sha(a.tapectl), "test_binary_sha256": sha(a.tapectl_test),
            "platform": a.platform,
            "observer": {"kind": "compiled-test trace (host/port/trace_test.c)", "positive_control": "control/positive.trace.json",
                         "positive_control_seen": b.control_seen},
            "unjudged": b.unjudged}
    (out / "BUNDLE.json").write_text(json.dumps(dict(head, files=b.files, rows=b.rows), indent=1))
    print(f"{len(b.rows)} rows, {len(b.unjudged)} unjudged, {len(b.files)} files -> {out / 'BUNDLE.json'}")
    if neg is not None:
        # The same transport, one row with a write callback during verify: the judge must refuse it.
        nb = B(a, plat); nb.out = out.parent / (out.name + "-negative"); nb.control_seen = b.control_seen
        nb.out.mkdir(parents=True, exist_ok=True)
        res, rep = neg
        nb.session_row("NEGATIVE-nonnull-binding", "judge negative control: TAPECTL_TEST_FAULT=nonnull-binding", res, rep,
                       oracle_facts(facts_text(IMG_BYTES), True), None, None)
        (nb.out / "BUNDLE.json").write_text(json.dumps(dict(head, unjudged=[], files=nb.files, rows=nb.rows), indent=1))
        print(f"negative bundle -> {nb.out / 'BUNDLE.json'}")
    sys.exit(0 if b.control_seen else 1)


if __name__ == "__main__":
    main()
