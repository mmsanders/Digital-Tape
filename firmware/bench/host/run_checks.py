#!/usr/bin/env python3
"""Off-target checks of the WP-17 firmware's portable modules (FW-1 §4, F1 host half).

Runs fwhost (the firmware's fw_part and fw_play over engine/port/dev_file) and
judges it:

  part      partition view on the WP-14 image fixtures: every fixture built
            whole (tests/wp14_r1/fixtures.py, MBR + partition 2) mounts through
            the firmware's view exactly as the bare fixture mounts directly;
            non-§3.1 layouts are refused; writes land one block per card call
            at partition 2's offset and nowhere else; read-only binds no write.
  golden    every WP-11 golden at 1.0x (tests/golden/MANIFEST rows whose last
            step is `play --rate 1` or `dump`): tapectl builds the cartridge on
            a provisioned whole image from the WP-11 sources, the firmware
            render loop plays it in both its deterministic and its live
            (interrupt + main loop) form, and the PCM must equal the reference
            WAV's data bytes exactly.
  controls  F1 negative controls: one altered sample, and rate 1.0x + 1, must
            each FAIL the same comparison, in both forms.

Reads the verifier's packages (tests/wp14_r1, tests/golden); never writes them.
Exit 0 all pass, 1 any check failed, 2 the harness could not run.

    run_checks.py --fwhost build/fwhost/fwhost --tapectl build/host/tapectl --out DIR
"""

import argparse
import hashlib
import json
import os
import shlex
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WP14 = os.path.join(ROOT, "tests", "wp14_r1")
GOLDEN = os.path.join(ROOT, "tests", "golden")

P2_START = 34816
# A provisioned image big enough for the WP-11 goldens' 60 s cartridge.
IMAGE_SECTORS = 100352

results = []


def check(name, ok, **detail):
    results.append({"check": name, "pass": bool(ok), **detail})
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        "" if ok else "  " + json.dumps(detail, sort_keys=True)))
    return ok


def fwhost(args):
    p = subprocess.run([A.fwhost] + args, capture_output=True, text=True)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1]), p.returncode
    except (ValueError, IndexError):
        return {"raw": p.stdout, "stderr": p.stderr}, p.returncode


def tapectl(args):
    p = subprocess.run([A.tapectl] + args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("tapectl %s: %s" % (" ".join(args), p.stderr.strip()))


def wav_data(path):
    b = open(path, "rb").read()
    i = 12
    while i + 8 <= len(b):
        cid, n = b[i:i + 4], struct.unpack_from("<I", b, i + 4)[0]
        if cid == b"data":
            return b[i + 8:i + 8 + n]
        i += 8 + n + (n & 1)
    raise ValueError("no data chunk in " + path)


# ---- partition view --------------------------------------------------------

def part_checks(out):
    sys.path.insert(0, WP14)
    import catalog
    import fixtures

    d = os.path.join(out, "part")
    os.makedirs(d, exist_ok=True)

    for m in catalog.MUTATIONS:
        whole, bare = os.path.join(d, m + "-whole.img"), os.path.join(d, m + "-bare.img")
        fixtures.build(whole, m, whole=True)
        fixtures.build(bare, m)
        pv, _ = fwhost(["part", whole])
        ref, _ = fwhost(["bare", bare])
        mounts = {k: v for k, v in pv.items() if k.split("_")[0] in ("mount", "frames", "entries", "side", "needs")}
        ref_mounts = {k: v for k, v in ref.items() if k.split("_")[0] in ("mount", "frames", "entries", "side", "needs")}
        check("part/fixture-%s" % m,
              pv.get("part") == "OK" and pv.get("base") == P2_START and pv.get("blocks") == ref.get("blocks")
              and mounts == ref_mounts and pv.get("card_writes") == 0 and pv.get("write_bound") is False,
              view=pv, bare=ref)

    # The real producer: a card image tapectl provisioned.
    prov = os.path.join(d, "tapectl-provisioned.img")
    if os.path.exists(prov):
        os.remove(prov)
    tapectl(["provision", prov, "--label", "FW17", "--length-s", "60",
             "--uuid", "00112233445566778899aabbccddeeff", "--epoch", "1",
             "--image-bytes", str(IMAGE_SECTORS * 512)])
    pv, _ = fwhost(["part", prov])
    check("part/tapectl-provisioned", pv.get("part") == "OK" and pv.get("base") == P2_START
          and pv.get("blocks") == IMAGE_SECTORS - P2_START and pv.get("mount_A") == 0, view=pv)

    # Refusals: not the §3.1 layout for this card.
    clean = os.path.join(d, "clean-whole.img")
    base = bytearray(open(clean, "rb").read())

    def variant(name, mutate):
        path = os.path.join(d, "refuse-" + name + ".img")
        b = bytearray(base)
        b = mutate(b) or b
        open(path, "wb").write(b)
        pv, rc = fwhost(["part", path])
        check("part/refuse-%s" % name, pv.get("part") == "NOT_PROVISIONED" and rc == 2, view=pv)

    def set_byte(off, val):
        def f(b):
            b[off] = val
        return f

    variant("bare-image-as-card", lambda b: bytearray(open(os.path.join(d, "clean-bare.img"), "rb").read()))
    variant("p2-type-0x83", set_byte(446 + 16 + 4, 0x83))
    variant("p1-type-0x0c", set_byte(446 + 4, 0x0C))
    variant("entry3-nonzero", set_byte(446 + 32 + 4, 0x83))
    variant("no-55aa", set_byte(511, 0x00))
    variant("card-one-block-larger", lambda b: b + bytearray(512))
    variant("card-one-block-smaller", lambda b: b[:-512])
    variant("p2-start-moved", lambda b: b.__setitem__(slice(446 + 16 + 8, 446 + 16 + 12),
                                                      struct.pack("<I", P2_START + 8)))

    empty = os.path.join(d, "refuse-empty.img")
    open(empty, "wb").close()
    pv, rc = fwhost(["part", empty])
    check("part/refuse-unreadable-block0", pv.get("part") in ("IO",) or pv.get("open") == "FAILED", view=pv,
          note="a zero-length card: block 0 cannot be read")

    # Writes through the view: one block per card call, at base + lba, and nothing else changes.
    w = os.path.join(d, "write.img")
    open(w, "wb").write(base)
    before = open(w, "rb").read()
    pv, _ = fwhost(["write", w, "5", "3"])
    after = open(w, "rb").read()
    changed = [i // 512 for i in range(0, len(before), 512) if before[i:i + 512] != after[i:i + 512]]
    expect = [bytes((0xA5 ^ k) for _ in range(512)) for k in range(3)]
    landed = [after[(P2_START + 5 + k) * 512:(P2_START + 6 + k) * 512] for k in range(3)]
    check("part/write-one-block-per-call", pv.get("write") == 0 and pv.get("card_writes") == 3
          and pv.get("card_max_count") == 1 and pv.get("card_flushes") == 1
          and changed == [P2_START + 5, P2_START + 6, P2_START + 7] and landed == expect,
          view=pv, changed_blocks=changed)

    open(w, "wb").write(base)
    blocks = len(base) // 512 - P2_START
    pv, _ = fwhost(["write", w, str(blocks - 1), "2"])
    check("part/write-past-end-refused", pv.get("write") not in (0, None) and pv.get("card_writes") == 0
          and open(w, "rb").read() == base, view=pv)

    pv, _ = fwhost(["part", clean])
    check("part/read-only-binds-no-write", pv.get("write_bound") is False, view=pv)
    pv, _ = fwhost(["part", w, "--writable"])
    check("part/writable-binds-write", pv.get("write_bound") is True, view=pv)


# ---- F1 goldens ------------------------------------------------------------

def golden_rows():
    rows = []
    for line in open(os.path.join(GOLDEN, "MANIFEST"), encoding="utf-8"):
        if not line.strip() or line.startswith("#"):
            continue
        name, ref, cmd = line.split(" ", 2)
        steps = [shlex.split(s) for s in cmd.strip().split(" && ")]
        last = steps[-1]
        op = last[1]
        if op == "play" and last[last.index("--rate") + 1] == "1":
            rows.append((name, ref, steps))
        elif op == "dump":
            rows.append((name, ref, steps))
    return rows


def opt(step, name, default=None):
    return step[step.index(name) + 1] if name in step else default


def golden_checks(out):
    d = os.path.join(out, "golden")
    os.makedirs(d, exist_ok=True)
    rows = golden_rows()
    check("golden/manifest-rows-at-1x", len(rows) == 7, rows=[r[0] for r in rows])
    for name, ref, steps in rows:
        img = os.path.join(d, name + ".img")
        if os.path.exists(img):
            os.remove(img)
        fmt = steps[0]
        assert fmt[1] == "format", fmt
        tapectl(["provision", img, "--label", opt(fmt, "--label"), "--length-s", opt(fmt, "--length-s"),
                 "--uuid", opt(fmt, "--uuid"), "--epoch", opt(fmt, "--epoch"),
                 "--image-bytes", str(IMAGE_SECTORS * 512)])
        for s in steps[1:-1]:
            args = [img if a.endswith(".img") else (os.path.join(ROOT, a) if a.startswith("tests/") else a)
                    for a in s[1:]]
            tapectl(args)
        last = steps[-1]
        side = opt(last, "--side", "A")
        frm = opt(last, "--from", "0") if last[1] == "play" else "0"
        frames = opt(last, "--frames", "0") if last[1] == "play" else "0"
        want = wav_data(os.path.join(ROOT, ref))
        for mode in ("det", "live"):
            pcm = os.path.join(d, "%s-%s.pcm" % (name, mode))
            res, _ = fwhost(["golden", img, "--side", side, "--from", frm, "--frames", frames,
                             "--mode", mode, "-o", pcm])
            got = open(pcm, "rb").read()
            check("golden/%s/%s" % (name, mode),
                  res.get("result") == 0 and got == want and res.get("underruns") == 0
                  and res.get("card_writes") == 0 and res.get("sha256") == hashlib.sha256(want).hexdigest(),
                  fwhost=res, want_frames=len(want) // 4, want_sha256=hashlib.sha256(want).hexdigest())
            if name == "play-1x-fortissimo":
                for control in ("flip", "rate"):
                    cpcm = os.path.join(d, "%s-%s-control-%s.pcm" % (name, mode, control))
                    cres, _ = fwhost(["golden", img, "--side", side, "--from", frm, "--frames", frames,
                                      "--mode", mode, "-o", cpcm, "--control", control])
                    cgot = open(cpcm, "rb").read()
                    # A control passes when the comparison it feeds goes red.
                    check("control/%s/%s/%s-must-mismatch" % (name, mode, control),
                          cgot != want and cres.get("sha256") != hashlib.sha256(want).hexdigest(),
                          fwhost=cres)


def main():
    global A
    ap = argparse.ArgumentParser()
    ap.add_argument("--fwhost", required=True)
    ap.add_argument("--tapectl", required=True)
    ap.add_argument("--out", required=True)
    A = ap.parse_args()
    A.fwhost, A.tapectl = os.path.abspath(A.fwhost), os.path.abspath(A.tapectl)
    os.makedirs(A.out, exist_ok=True)
    try:
        p = subprocess.run([A.fwhost, "sha-selftest"], capture_output=True, text=True)
        check("sha256/selftest", p.returncode == 0, out=p.stdout.strip())
        part_checks(A.out)
        golden_checks(A.out)
    except Exception as e:  # a harness that cannot run is never a pass
        print("FAIL  harness could not run: %r" % e)
        return 2
    failed = [r for r in results if not r["pass"]]
    summary = {"checks": len(results), "failed": len(failed), "results": results}
    with open(os.path.join(A.out, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=1, sort_keys=True)
        f.write("\n")
    print("%d checks, %d failed" % (len(results), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
