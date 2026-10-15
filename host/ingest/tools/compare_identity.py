#!/usr/bin/env python3
"""Require identical identity-run output from every qualified platform (contract I6).

usage: compare_identity.py FILE [FILE ...]   (each from tools/identity_run.sh)
       compare_identity.py --selftest        (proves a one-byte difference goes red)
"""
import os, sys, tempfile


def compare(paths):
    seen = {}
    for p in paths:
        seen[p] = open(p, encoding="utf-8").read()
    ref = next(iter(seen.values()))
    bad = [p for p, v in seen.items() if v != ref or not v.strip()]
    return bad


def main():
    if sys.argv[1:] == ["--selftest"]:
        with tempfile.TemporaryDirectory() as t:
            a, b = os.path.join(t, "a.txt"), os.path.join(t, "b.txt")
            open(a, "w").write("audio.wav 00\nmanifest.json 11\n")
            open(b, "w").write("audio.wav 00\nmanifest.json 11\n")
            if compare([a, b]):
                print("SELFTEST FAIL: identical inputs reported different"); return 1
            open(b, "w").write("audio.wav 01\nmanifest.json 11\n")
            if not compare([a, b]):
                print("SELFTEST FAIL: a differing hash was not detected"); return 1
        print("selftest: identical accepted, differing detected"); return 0
    if len(sys.argv) < 3:
        print("need at least two platform results"); return 1
    bad = compare(sys.argv[1:])
    for p in sys.argv[1:]:
        print(p, "\n ", open(p).read().strip().replace("\n", "\n  "))
    if bad:
        print("FAIL: outputs differ:", ", ".join(bad)); return 1
    print("PASS: byte-identical audio.wav and manifest.json on", len(sys.argv) - 1, "platforms"); return 0


if __name__ == "__main__":
    sys.exit(main())
