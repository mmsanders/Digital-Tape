#!/usr/bin/env python3
"""G1 static gate (APP-1 §1): app code never opens a block device, raw disk or partition.

Scans the app's own source (APP_SOURCE_ROOT, default host/app: src/**/*.rs and
frontend/**) and fails on any of:

  device-path   a device or raw-disk path written anywhere in app source:
                \\\\.\\ or \\\\?\\ prefixes, PhysicalDrive, HarddiskN, GLOBALROOT, \\Device\\,
                /dev/, rdiskN, Volume{GUID}
  device-api    a raw-device API outside a comment: DeviceIoControl, CreateFileA/W,
                NtOpenFile, IOCTL_/FSCTL_ codes, ioctl(, libc::open
  card-flow     the discovered card path (Hint.paths, cards.card, make_card, the make
                `dev`) reaching any file-system call, or named outside the four files that
                carry it to the make child's argv (discovery.rs, state.rs, bridge.rs, make.rs)

Every device access is a `tapectl` child. Verification's
tests/wp15_app1a_r1/static_controls.py is this gate's negative control: it appends
literal, aliased and data-flow device opens to a copy and requires this gate to fail
each, and an ordinary private-file open to pass. A static check is not a runtime G1
proof or complete data-flow analysis.

  g1_static.py [--json OUT]        exit 0 clean, 1 findings
"""
import json, os, re, sys
from pathlib import Path

DEVICE_PATH = re.compile(r'\\\\\\\\\.\\\\|\\\\\.\\|\\\\\\\\\?\\\\|\\\\\?\\|PhysicalDrive|Harddisk\d|GLOBALROOT|\\\\Device\\\\|/dev/|\brdisk\d|Volume\{', re.I)
DEVICE_API = re.compile(r'\bDeviceIoControl\b|\bCreateFile[AW]?\b|\bNtOpenFile\b|\bIOCTL_[A-Z_]+|\bFSCTL_[A-Z_]+|\bioctl\s*\(|\blibc::open\b')
CARD = re.compile(r'\.paths\b|\bcards\.card\b|\bmake_card\b|(?<![.\w])dev\b(?!\s*\()')
COMMENT = re.compile(r'^\s*(//|/\*|\*)')
FS_CALL = re.compile(r'File::(open|create)|OpenOptions|\bfs::\w+\s*\(|symlink_metadata|read_dir|create_dir|remove_(file|dir)|\brename\b|\bcopy\b')
CARD_FILES = {"src/discovery.rs", "src/state.rs", "src/bridge.rs", "src/make.rs"}


def sources(root):
    for sub, pattern in (("src", "*.rs"), ("frontend", "*")):
        base = root / sub
        if base.is_dir():
            yield from (p for p in sorted(base.rglob(pattern)) if p.is_file())


def scan(root):
    findings = []
    for p in sources(root):
        rel = p.relative_to(root).as_posix()
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            hit = lambda rule, why: findings.append({"file": rel, "line": n, "rule": rule, "why": why, "text": line.strip()[:200]})
            if DEVICE_PATH.search(line):
                hit("device-path", "a device or raw-disk path in app source")
            if DEVICE_API.search(line) and not COMMENT.match(line):
                hit("device-api", "a raw-device API in app source")
            if p.suffix == ".rs" and CARD.search(line):
                if FS_CALL.search(line):
                    hit("card-flow", "the card path reaches a file-system call")
                elif rel not in CARD_FILES:
                    hit("card-flow", "the card path is named outside the files that pass it to the make child")
    return findings


def main():
    root = Path(os.environ.get("APP_SOURCE_ROOT") or Path(__file__).resolve().parents[2] / "host" / "app").resolve()
    findings = scan(root)
    out = {"root": str(root), "files": [p.relative_to(root).as_posix() for p in sources(root)], "findings": findings,
           "verdict": "clean" if not findings else "device access in app source"}
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, indent=1) + "\n")
    for f in findings:
        print(f"G1 {f['rule']}: {f['file']}:{f['line']}: {f['why']}: {f['text']}")
    print(f"G1 static gate: {len(out['files'])} files, {len(findings)} findings: {out['verdict']}")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
