#!/usr/bin/env python3
"""BE-1 raw serial capture for the bench (docs/WP17-BE1-INTERFACE.md §6, BE1-IF/3).

    bench_capture.py --port COM5 --out f1-quiet-1.raw --until-digest --send "golden A 0 198450"
    bench_capture.py --port COM5 --out info-1.raw --until-info --send info
    bench_capture.py --port COM5 --out f5-1.raw --until-interrupt

Every byte read from the port is appended to --out unmodified, in arrival order,
and flushed at once. The protocol is parsed only to know when to stop, and the
port is asked for no more than the current element needs, so the file ends at
the stop line's newline. A failed or partial attempt keeps its bytes: --out is
created exclusively and never truncated or deleted.

NEEDS THE BENCH for real evidence (pyserial). Never writes a card, flashes or
provisions. Not part of the offline checker.
"""

import argparse
import hashlib
import json
import os
import struct
import sys
import time

VERSION = "BE1-IF/3"
BAUD = 115200
READ_TIMEOUT = 0.05
DEFAULT_TIMEOUT = {"digest": 600.0, "info": 10.0, "interrupt": None}
STOP_PREFIX = {"digest": (b"SHA256 ", b"ERR "), "info": (b"INFO ", b"FATAL ", b"ERR ")}


class Usage(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Usage(message)


class TimedOut(Exception):
    pass


class Capture:
    def __init__(self, port, out, deadline):
        self.port, self.out, self.deadline = port, out, deadline
        self.sha = hashlib.sha256()
        self.count = 0

    def read(self, n):
        """Up to n bytes, recorded as they arrive; b"" only at the deadline."""
        while True:
            part = self.port.read(n)
            if part:
                self.out.write(part)
                self.out.flush()
                self.sha.update(part)
                self.count += len(part)
                return part
            if self.deadline is not None and time.monotonic() >= self.deadline:
                raise TimedOut()

    def read_exact(self, n):
        got = bytearray()
        while len(got) < n:
            got += self.read(n - len(got))
        return bytes(got)

    def read_line(self):
        line = bytearray()
        while not line.endswith(b"\n"):
            line += self.read(1)
        return bytes(line)

    def until(self, prefixes):
        """Read lines until one starts with a stop prefix (never, for an empty
        tuple); a PCM region is consumed by its framing, never scanned for lines."""
        while True:
            line = self.read_line()
            text = line.rstrip(b"\r\n")
            if text == b"PCM":
                while True:
                    n = struct.unpack("<I", self.read_exact(4))[0]
                    if n == 0:
                        break
                    self.read_exact(4 * n)
                continue
            for p in prefixes:
                if text.startswith(p):
                    return "err" if p == b"ERR " else ("digest" if p == b"SHA256 " else "info")


def main(argv=None):
    ap = Parser(description="BE-1 raw serial capture (bench only)")
    ap.add_argument("--port", required=True)
    ap.add_argument("--out", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--until-digest", dest="mode", action="store_const", const="digest")
    mode.add_argument("--until-info", dest="mode", action="store_const", const="info")
    mode.add_argument("--until-interrupt", dest="mode", action="store_const", const="interrupt")
    ap.add_argument("--send")
    ap.add_argument("--timeout", type=float)
    try:
        a = ap.parse_args(argv)
        if a.send is not None:
            try:
                raw = a.send.encode("ascii")
            except UnicodeEncodeError:
                raise Usage("--send must be ASCII")
            if not 1 <= len(raw) <= 63 or any(c in raw for c in b"\r\n\0"):
                raise Usage("--send must be 1-63 bytes with no CR, LF or NUL")
        if a.timeout is not None and not a.timeout > 0:
            raise Usage("--timeout must be positive")
        if os.path.lexists(a.out):
            raise Usage("--out already exists; an earlier attempt is never overwritten")
    except Usage as e:
        sys.stderr.write("bench_capture: usage error: %s\n" % e)
        return 64

    import serial  # pyserial, or an injected fake with the declared interface

    timeout = a.timeout if a.timeout is not None else DEFAULT_TIMEOUT[a.mode]
    stop, code, port = None, 0, None
    with open(a.out, "xb") as out:
        cap = Capture(None, out, None)
        try:
            port = serial.Serial(a.port, baudrate=BAUD, timeout=READ_TIMEOUT)
            cap.port = port
            if a.send is not None:
                port.reset_input_buffer()
                port.write(a.send.encode("ascii") + b"\n")
                port.flush()
            cap.deadline = None if timeout is None else time.monotonic() + timeout
            stop = cap.until(STOP_PREFIX.get(a.mode, ()))
        except TimedOut:
            stop, code = "timeout", 0 if a.mode == "interrupt" else 3
        except KeyboardInterrupt:
            stop, code = "interrupt", 0 if a.mode == "interrupt" else 130
        except (serial.SerialException, OSError):
            stop, code = "port_error", 4
        finally:
            if port is not None:
                try:
                    port.close()
                except (serial.SerialException, OSError):
                    pass
    print(json.dumps(dict(tool="bench_capture.py", version=VERSION, port=a.port, command=a.send, out=a.out,
                          bytes=cap.count, sha256=cap.sha.hexdigest(), stop=stop, exit=code), sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
