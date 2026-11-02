#!/usr/bin/env python3
"""F1 on target: ask the bench firmware to render a golden, compare with WP-11.

The Teensy holds a card provisioned by tapectl from the WP-11 sources (see
README.md). This sends one command over USB serial and compares the result
with the reference WAV's data bytes:

    golden  the firmware renders in the deterministic order and prints the
            SHA-256 of the PCM; compared with the reference data's SHA-256;
    stream  the same render, with the PCM streamed back; compared byte for
            byte, and the first differing frame is reported;
    live    the firmware plays through the audio interrupt exactly as heard,
            hashing every frame it renders, to the end of the side.

NEEDS THE BENCH: never run in CI. Requires pyserial.

    golden_serial.py --port COM5 --ref tests/golden/ref/play-1x-quiet.wav \\
                     --mode golden --side A --from 0 --frames 198450
"""

import argparse
import hashlib
import struct
import sys


def wav_data(path):
    b = open(path, "rb").read()
    i = 12
    while i + 8 <= len(b):
        cid, n = b[i:i + 4], struct.unpack_from("<I", b, i + 4)[0]
        if cid == b"data":
            return b[i + 8:i + 8 + n]
        i += 8 + n + (n & 1)
    raise ValueError("no data chunk in " + path)


def read_line(ser):
    line = ser.readline()
    if not line:
        raise TimeoutError("no answer from the firmware")
    return line.decode("ascii", "replace").strip()


def main():
    import serial  # pyserial; imported here so --help works without it

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--mode", choices=("golden", "stream", "live"), default="golden")
    ap.add_argument("--side", default="A")
    ap.add_argument("--from", dest="frm", default="0")
    ap.add_argument("--frames", default="0", help="0 = to the end of the side")
    ap.add_argument("--timeout", type=float, default=120.0)
    a = ap.parse_args()

    want = wav_data(a.ref)
    want_sha = hashlib.sha256(want).hexdigest()
    ser = serial.Serial(a.port, timeout=a.timeout)
    ser.reset_input_buffer()
    ser.write(("%s %s %s %s\n" % (a.mode, a.side, a.frm, a.frames)).encode("ascii"))

    got = None
    if a.mode == "stream":
        while read_line(ser) != "PCM":
            pass
        parts = []
        while True:
            n = struct.unpack("<I", ser.read(4))[0]
            if n == 0:
                break
            parts.append(ser.read(n * 4))
        got = b"".join(parts)
    line = read_line(ser)
    while not line.startswith("SHA256 "):
        print(line)
        line = read_line(ser)
    print(line)
    f = line.split()
    sha, frames, result = f[1], int(f[3]), int(f[5])

    ok = result == 0 and sha == want_sha
    if a.frames == "0" or a.mode == "live":
        ok = ok and frames * 4 == len(want)
    if got is not None:
        if got != want:
            ok = False
            first = next((i for i in range(min(len(got), len(want))) if got[i] != want[i]), min(len(got), len(want)))
            print("first difference at byte %d (frame %d); got %d bytes, want %d" % (first, first // 4, len(got), len(want)))
        if hashlib.sha256(got).hexdigest() != sha:
            print("streamed bytes do not match the firmware's own digest")
            ok = False
    print("%s  %s %s: firmware %s, reference %s" % ("PASS" if ok else "FAIL", a.mode, a.ref, sha, want_sha))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
