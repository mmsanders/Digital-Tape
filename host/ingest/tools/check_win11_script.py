#!/usr/bin/env python3
"""The Windows 11 packet script (stage1/win11_packet.ps1) pins the transport files
it will run by SHA-256. This proves those pins equal the committed files, so the
script handed to Michael cannot silently go stale.

  check_win11_script.py            check (nonzero exit on any stale or missing pin)
  check_win11_script.py --write    rewrite the pins from the working tree
  check_win11_script.py --selftest the check goes red on a wrong pin and a missing pin
"""
import hashlib, re, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]  # host/ingest
REPO = HERE.parents[1]
SCRIPT = HERE / "stage1" / "win11_packet.ps1"
PIN = re.compile(r'"(host/ingest/stage1/[A-Za-z0-9_.]+)"\s*=\s*"([^"]*)"')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def problems(text):
    pins = PIN.findall(text)
    out = [] if pins else ["no transport pins found"]
    for rel, value in pins:
        want = sha(REPO / rel)
        if value != want:
            out.append(f"{rel}: pinned {value or '<empty>'}, file is {want}")
    return out


def write():
    text = SCRIPT.read_text(encoding="utf-8")
    new = PIN.sub(lambda m: f'"{m.group(1)}" = "{sha(REPO / m.group(1))}"', text)
    SCRIPT.write_bytes(new.encode("utf-8"))
    print(f"pinned {len(PIN.findall(new))} transport files in {SCRIPT.relative_to(REPO)}")


def selftest():
    text = SCRIPT.read_text(encoding="utf-8")
    assert not problems(text), "baseline must be green before the controls mean anything"
    rel, value = PIN.findall(text)[0]
    wrong = text.replace(value, ("0" if value[0] != "0" else "1") + value[1:], 1)
    missing = PIN.sub("", text)
    assert problems(wrong), "a wrong pin was not detected"
    assert problems(missing), "a script with no pins was not detected"
    print("PASS: check goes red on a wrong pin and on missing pins")


if __name__ == "__main__":
    if "--write" in sys.argv:
        write()
    elif "--selftest" in sys.argv:
        selftest()
    p = problems(SCRIPT.read_text(encoding="utf-8"))
    for x in p:
        print("STALE:", x)
    if p:
        sys.exit(1)
    print("PASS: Windows 11 packet script pins equal the committed transport files")
