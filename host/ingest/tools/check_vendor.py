#!/usr/bin/env python3
"""Vendored-decoder integrity for INGEST-1's arithmetic profile.

1. Every vendored crate tree hashes to the value recorded in vendor/PATCHES.sha256
   (same construction as build.rs), so a silent edit cannot change the profile.
2. No vendored or ingest source calls a transcendental float method of `std`
   (sin/cos/tan/powf/powi/exp/ln/log*/cbrt/atan*/hypot/mul_add): those route to the
   platform C library and differ between Linux, macOS and Windows.

--selftest proves both checks go red on a mutated copy.
"""
import hashlib, os, re, shutil, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRATES = ["symphonia-bundle-mp3", "symphonia-codec-aac", "symphonia-common", "symphonia-core"]
BAD = re.compile(r"(\.(sin|cos|tan|sin_cos|powf|powi|exp|exp2|ln|log|log2|log10|cbrt|atan|atan2|asin|acos|hypot|mul_add)\(|\b(f32|f64)::(sin|cos|tan|powf|powi|exp|exp2|ln|log|log2|log10|cbrt|atan|atan2|asin|acos|hypot|mul_add)\b)")


def tree(root):
    rel = []
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            rel.append((os.path.relpath(p, root).replace(os.sep, "/"), p))
    h = hashlib.sha256()
    for name, p in sorted(rel):
        b = open(p, "rb").read()
        h.update(name.encode() + b"\0" + len(b).to_bytes(8, "little") + b)
    return h.hexdigest()


def scan(roots):
    bad = []
    for r in roots:
        for d, _, fs in os.walk(r):
            for f in fs:
                if not f.endswith(".rs"):
                    continue
                p = os.path.join(d, f)
                for i, line in enumerate(open(p, encoding="utf-8"), 1):
                    code = line.split("//")[0]
                    if BAD.search(code):
                        bad.append(f"{p}:{i}: {line.strip()}")
    return bad


def check(base):
    errs = []
    rec = {}
    for line in open(os.path.join(base, "vendor", "PATCHES.sha256")):
        h, n = line.split()
        rec[n] = h
    for c in CRATES:
        got = tree(os.path.join(base, "vendor", c))
        if rec.get(c) != got:
            errs.append(f"vendor/{c}: tree {got} != recorded {rec.get(c)}")
    errs += scan([os.path.join(base, "vendor", c, "src") for c in CRATES] + [os.path.join(base, "src")])
    return errs


def main():
    if "--record" in sys.argv:
        with open(os.path.join(HERE, "vendor", "PATCHES.sha256"), "w", newline="\n") as f:
            for c in CRATES:
                f.write(f"{tree(os.path.join(HERE, 'vendor', c))}  {c}\n")
        return 0
    errs = check(HERE)
    for e in errs:
        print("FAIL", e)
    if errs:
        return 1
    print("vendor integrity OK:", ", ".join(CRATES))
    if "--selftest" in sys.argv:
        for mutation in ("edit", "std-math"):
            with tempfile.TemporaryDirectory() as t:
                shutil.copytree(os.path.join(HERE, "vendor"), os.path.join(t, "vendor"))
                shutil.copytree(os.path.join(HERE, "src"), os.path.join(t, "src"))
                f = os.path.join(t, "vendor", "symphonia-core", "src", "dsp", "mdct.rs")
                s = open(f, encoding="utf-8").read()
                if mutation == "edit":
                    s += "\n// drift\n"
                else:
                    s = s.replace("libm::cos(theta)", "theta.cos()", 1)
                open(f, "w", encoding="utf-8", newline="\n").write(s)
                if not check(t):
                    print("SELFTEST FAIL: mutation", mutation, "was not detected")
                    return 1
                print("selftest: mutation", mutation, "detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
