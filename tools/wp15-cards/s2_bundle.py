#!/usr/bin/env python3
"""#465 S2: Software's actual `cards` observations, packaged as Verification #208's
BUNDLE.json (tests/wp15_cards_make_r1/ADAPTER.md). Linux only (strace). It judges
nothing; the imported runner.py does, and Verification #208 disposes.

Rows (kind=cards):
  vector/*   the fixed discovery vectors of CASE-MATRIX.json, serialized into a
             TAPECTL_TEST_CARDS_VECTOR file and run through tapectl-test cards: the
             actual policy and printing code, compiled-test enumeration scope;
  actual/*   the SHIPPED tapectl cards on this runner, unelevated, with no seam
             environment, with and without a report; probes are this runner's disks
             as `tapectl-test discover` reports them, mapped to the oracle's fact names.
Every run is traced with strace (open/openat/ioctl/umount2/mount). The observer is
qualified by a positive control: the same trace of a one-sector read of a loop
device must show that open. lsblk and mountinfo are kept as independent raw facts.

  s2_bundle.py --tapectl BIN --tapectl-test BIN --package DIR --out DIR --control-dev DEV [--source SHA]
"""
import argparse, hashlib, json, os, re, subprocess, sys
from pathlib import Path

NONCE = "0123456789abcdef0123456789abcdef"
BENIGN = re.compile(r'"/dev/(null|tty|urandom|random|pts/\d+)"|ioctl\([012], TCGETS')
DEVLINE = re.compile(r'(open(at)?\(.*"(/dev/[^"]+)", ([A-Z_|]+)|ioctl\(|umount2?\(|mount\()')


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class B:
    def __init__(self, a):
        self.a, self.out = a, Path(a.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.files, self.rows, self.n = {}, [], 0

    def keep(self, name, data):
        p = self.out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        self.files[name] = sha_file(p)
        return name

    def traced(self, argv, env=None):
        """Run argv under strace; returns (proc, events, raw trace)."""
        self.n += 1
        tr = self.out / f"trace/{self.n:03d}.strace"
        tr.parent.mkdir(parents=True, exist_ok=True)
        p = subprocess.run(["strace", "-f", "-qq", "-e", "trace=open,openat,ioctl,umount2,mount", "-o", str(tr)] + argv,
                           capture_output=True, env=env)
        text = tr.read_text(errors="replace")
        events = []
        for line in text.splitlines():
            m = DEVLINE.search(line)
            if not m or BENIGN.search(line):
                continue
            if m.group(3):
                flags = m.group(4)
                access = "readwrite" if ("O_RDWR" in flags or "O_WRONLY" in flags) else "read"
                events.append({"op": "open", "path": m.group(3), "access": access, "device": True, "raw": line})
            elif "umount" in line:
                events.append({"op": "unmount", "device": True, "raw": line})
            else:
                events.append({"op": "ioctl" if "ioctl" in line else "mount", "device": True, "raw": line})
        self.files[self.keep(f"trace/{self.n:03d}.strace", text)] = sha_file(tr)
        return p, events, f"trace/{self.n:03d}.strace"

    def row(self, name, scope, argv, probes, env=None, report=None, control_seen=True):
        p, events, trace = self.traced(argv, env)
        base = f"rows/{len(self.rows):03d}"
        rec = {"exit": p.returncode, "elevated": os.geteuid() == 0, "probes": probes, "events": events,
               "trace_complete": True, "observer": "qualified-native", "positive_control_seen": control_seen,
               "argv": argv, "executable_sha256": sha_file(argv[0]), "trace": trace,
               "scope": scope}
        r = {"name": name, "kind": "cards", "scope": scope,
             "record": self.keep(base + ".record.json", json.dumps(rec, indent=1)),
             "stdout": self.keep(base + ".stdout", p.stdout), "stderr": self.keep(base + ".stderr", p.stderr)}
        if report and Path(report).exists():
            r["report"] = self.keep(base + ".report.jsonl", Path(report).read_bytes())
        self.rows.append(r)
        print(f"{name:44} exit {p.returncode} device-events {len(events)}  {p.stdout.decode()[-60:].strip()}", flush=True)
        return p


def tri(v):
    return -1 if v is None else int(bool(v))


def vector_line(path, f):
    """CASE-MATRIX facts -> one TAPECTL_TEST_CARDS_VECTOR line (input transport only)."""
    mounts = f.get("mounts")
    view = f.get("partition_view")
    parts = []
    if view is not None:
        def b(sec):
            return -1 if sec is None else sec * 512
        if view.get("p1_type") is not None or view.get("p1_start") is not None or True:
            parts.append((1, view.get("p1_type"), b(view.get("p1_start")), None if view.get("p1_sectors") is None else view["p1_sectors"] * 512))
        p2s = view.get("p2_start")
        end = view.get("p2_end_bytes")
        parts.append((2, view.get("p2_type"), b(p2s), None if p2s is None or end is None else end - p2s * 512))
        for k in (3, 4):
            if view.get(f"p{k}"):
                parts.append((k, 0x83, 0, 512))
    n_parts = -1 if view is not None and (view.get("p3") is None or view.get("p4") is None) else len(parts)
    mbr = -1 if view is None or view.get("style") is None else int(view["style"] == "MBR")
    if mounts is None:
        n_mounted, unattr = -1, -1
    else:
        n_mounted = len(mounts)
        unattr = int(any(m not in [p[0] for p in parts] for m in mounts))
    if view is None and mounts:
        n_parts, mbr = -1, -1
    s = (f"path={path} whole={tri(f.get('whole'))} removable_or_sd={tri(f.get('removable_or_sd'))} "
         f"virtual={-1 if f.get('nonvirtual') is None else int(not f['nonvirtual'])} "
         f"holds_os={-1 if f.get('not_system_boot_swap') is None else int(not f['not_system_boot_swap'])} "
         f"bytes={-1 if f.get('bytes') is None else f['bytes']} n_mounted={n_mounted} mbr={mbr} "
         f"mounted_unattributed={unattr} n_parts={n_parts}")
    if n_parts >= 0:
        for idx, typ, st, ln in parts:
            m = -1 if mounts is None else int(idx in mounts)
            s += f" p={idx},{-1 if typ is None else typ},{-1 if st is None else st},{-1 if ln is None else ln},{m}"
    return s


def oracle_facts(d):
    """A `tapectl-test discover` record -> the oracle's candidate fact names."""
    def t(v):
        return None if v == -1 else bool(v)
    parts = {p["index"]: p for p in d["parts"]}
    mounted = None if d["n_mounted"] == -1 else sorted(
        [p["index"] for p in d["parts"] if p["mounted"] == 1] + ([0] if d["mounted_unattributed"] == 1 else []))
    view = None
    if d["n_parts"] != -1 and d["mbr"] != -1:
        def sec(v):
            return None if v == -1 else (v // 512 if v % 512 == 0 else {"bytes": v})
        p1, p2 = parts.get(1), parts.get(2)
        view = {"style": "MBR" if d["mbr"] == 1 else "other",
                "p1_type": None if not p1 or p1["type"] == -1 else p1["type"],
                "p1_start": None if not p1 else sec(p1["start"]), "p1_sectors": None if not p1 else sec(p1["length"]),
                "p2_type": None if not p2 or p2["type"] == -1 else p2["type"],
                "p2_start": None if not p2 else sec(p2["start"]),
                "p2_end_bytes": None if not p2 or -1 in (p2["start"], p2["length"]) else p2["start"] + p2["length"],
                "p3": 3 in parts, "p4": 4 in parts}
    return {"whole": t(d["whole"]), "removable_or_sd": t(d["removable_or_sd"]),
            "nonvirtual": None if d["virtual"] == -1 else not d["virtual"],
            "bytes": d["bytes"] if d["bytes_known"] else None,
            "not_system_boot_swap": None if d["holds_os"] == -1 else not d["holds_os"],
            "mounts": mounted, "partition_view": view}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("tapectl", "tapectl-test", "package", "out", "control-dev"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--source", default=None, help="the source commit the binaries were built from")
    a = ap.parse_args()
    b = B(a)
    T, TT = os.path.abspath(a.tapectl), os.path.abspath(a.tapectl_test)
    env0 = {k: v for k, v in os.environ.items() if not k.startswith("TAPECTL_TEST")}

    # Observer qualification: the same trace sees a real device open.
    _, ev, ctrl = b.traced(["head", "-c", "512", a.control_dev])
    control_seen = any(e["op"] == "open" and e["path"] == a.control_dev for e in ev)
    print(f"positive control ({a.control_dev}): {'seen' if control_seen else 'NOT SEEN'} in {ctrl}", flush=True)

    # Fixed discovery vectors through the actual policy/printing code.
    cases = json.loads(Path(a.package, "CASE-MATRIX.json").read_text())["discovery"]
    paths = [f"/dev/sdv{i:02d}" for i in range(len(cases))]
    vec_scope = "compiled-test: tapectl-test cards with TAPECTL_TEST_CARDS_VECTOR (fixed CASE-MATRIX facts), actual policy and printing"
    def vector(name, sel):
        f = b.out / f"vectors/{name.replace('/', '_')}.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("".join(vector_line(paths[i], cases[i]["facts"]) + "\n" for i in sel))
        b.files[str(f.relative_to(b.out))] = sha_file(f)
        probes = [{"path": paths[i], "facts": cases[i]["facts"]} for i in sel]
        b.row(f"vector/{name}", vec_scope, [TT, "cards"], probes, env=dict(env0, TAPECTL_TEST_CARDS_VECTOR=str(f)),
              control_seen=control_seen)
    vector("complete-empty", [])
    for i, c in enumerate(cases):
        vector(f"single/{c['name']}", [i])
    vector("complete-many", list(range(len(cases))))

    # The shipped binary on this runner's real disks, unelevated, no seam.
    act_scope = f"actual shipped tapectl cards on {os.uname().sysname} {os.uname().release} hosted runner, unelevated, real OS enumeration"
    dump = subprocess.run([TT, "discover"], capture_output=True, env=env0)
    b.keep("raw/discover.jsonl", dump.stdout)
    for name, argv in (("lsblk.json", ["lsblk", "-J", "-b", "-O"]), ("mountinfo", ["cat", "/proc/self/mountinfo"]),
                       ("swaps", ["cat", "/proc/swaps"])):
        b.keep(f"raw/{name}", subprocess.run(argv, capture_output=True).stdout)
    probes = [{"path": d["path"], "facts": oracle_facts(d)} for d in map(json.loads, dump.stdout.decode().splitlines())]
    b.row("actual/no-report", act_scope, [T, "cards"], probes, env=env0, control_seen=control_seen)
    rep = b.out / "actual-report.jsonl"
    rep.unlink(missing_ok=True)
    b.row("actual/with-report", act_scope, [T, "cards", "--report", str(rep), "--report-nonce", NONCE], probes,
          env=env0, report=rep, control_seen=control_seen)

    src = a.source or subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    bundle = {"source_sha": src, "binary_sha256": sha_file(T), "test_binary_sha256": sha_file(TT),
              "observer": {"kind": "strace", "version": subprocess.run(["strace", "-V"], capture_output=True, text=True).stdout.splitlines()[0],
                           "positive_control": ctrl, "positive_control_seen": control_seen},
              "files": b.files, "rows": b.rows}
    (b.out / "BUNDLE.json").write_text(json.dumps(bundle, indent=1))
    print(f"{len(b.rows)} rows, {len(b.files)} files -> {b.out / 'BUNDLE.json'}")
    sys.exit(0 if control_seen else 1)


if __name__ == "__main__":
    main()
