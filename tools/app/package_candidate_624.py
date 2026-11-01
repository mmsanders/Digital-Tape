#!/usr/bin/env python3
"""Windows 11 x64 Make candidate packager (#624, C1-SW).

  package_candidate_624.py STAGE_DIR FACTS.json OUT_DIR

STAGE_DIR holds digital-tape.exe, tapectl.exe and ingest.exe. Writes OUT_DIR/
Digital-Tape-Windows11-x64-make-candidate.zip (five members: the three executables,
BUILD.json and README.txt, fixed timestamps, sorted) and OUT_DIR/INVENTORY.json with
every hash. Each member's embedded manifest execution level is recorded: the app and
ingest are asInvoker; tapectl carries no manifest (also asInvoker) and is elevated only
by the app's ShellExecuteExW "runas" for `tapectl make`. Nothing is launched here.
"""
import hashlib, json, re, sys, zipfile
from pathlib import Path

ARCHIVE = 'Digital-Tape-Windows11-x64-make-candidate.zip'
ZIP_TIME = (2026, 10, 28, 0, 0, 0)
MEMBERS = ('digital-tape.exe', 'tapectl.exe', 'ingest.exe')

README = '''Digital Tape - unsigned Windows 11 x64 candidate with Make cartridge (#624)

Built from {source} in Actions run {run}. Not yet cleared by Verification: do not
use it with a card until Verification has cleared this exact build and Michael's C2
checklist says to.

What is new: the Make cartridge button. With one card in, music dropped and a label
typed, Make cartridge checks the card again, asks "Everything on this card will be
replaced with your music." (Replace / Keep card), checks the card once more, and then
asks Windows for permission to run tapectl.exe as administrator. That is the only
elevated program: one prompt per Make. If you answer No, nothing is written.
digital-tape.exe and ingest.exe always run as you, unelevated.

The expected Windows prompt (not yet seen on Windows 11; Verification observes it in
C2): "User Account Control - Do you want to allow this app from an unknown publisher
to make changes to your device? tapectl.exe - Publisher: Unknown - File origin: Hard
drive on this computer" with Yes / No. On an account that is not an administrator,
Windows asks for an administrator's password instead.

Extract all five files into one new, ordinary folder you own and keep them together.
digital-tape.exe is the app; it needs Windows 11 x64 and the Microsoft Edge WebView2
runtime that Windows 11 already has. tapectl.exe and ingest.exe are run only by the
app, which checks their SHA-256 (in BUILD.json) before it runs them. Do not run them
yourself. There is no installer, signing step or security change.

Tested in CI, not on this machine: tapectl make on Linux loop devices and Windows
Server VHDs (including a VHD detached mid-write), the app's Make flow through its
component tests, and the G1 static check. Unexecuted until C2: this app binary's
window, the real UAC prompt and its decline, and any real card or card reader.
'''


def sha(b):
    return hashlib.sha256(b).hexdigest()


def manifest_level(b):
    m = re.search(rb'requestedExecutionLevel\s+level=["\'](\w+)["\']', b)
    return m.group(1).decode() if m else None


def main():
    stage, facts_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    facts = json.loads(facts_path.read_text(encoding='utf-8-sig'))
    blobs = {n: (stage / n).read_bytes() for n in MEMBERS}
    members = {n: {'sha256': sha(b), 'bytes': len(b), 'manifest_execution_level': manifest_level(b) or 'none (asInvoker)'}
               for n, b in blobs.items()}
    for n in ('digital-tape.exe', 'ingest.exe'):
        if members[n]['manifest_execution_level'] not in ('asInvoker', 'none (asInvoker)'):
            raise SystemExit(f'{n} would run elevated: {members[n]["manifest_execution_level"]}')
    pins = facts['compile_env']
    if pins['DT_TAPECTL_SHA256'] != members['tapectl.exe']['sha256'] or pins['DT_INGEST_SHA256'] != members['ingest.exe']['sha256']:
        raise SystemExit('the pins compiled into the app are not the bundled children')
    build = {'candidate': '624', 'scope': 'BUILD only; nothing launched; not cleared', 'members': members, **facts}
    files = {**blobs,
             'BUILD.json': (json.dumps(build, indent=2) + '\n').encode(),
             'README.txt': README.format(source=facts['source_head'], run=facts['run_id']).replace('\n', '\r\n').encode()}
    out.mkdir(parents=True, exist_ok=True)
    zpath = out / ARCHIVE
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in sorted(files):
            info = zipfile.ZipInfo('Digital-Tape/' + n, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, files[n])
    inventory = {'archive': ARCHIVE, 'archive_sha256': sha(zpath.read_bytes()), 'archive_bytes': zpath.stat().st_size,
                 'members': {n: {'sha256': sha(b), 'bytes': len(b)} for n, b in files.items()},
                 'source_head': facts['source_head'], 'run_id': facts['run_id']}
    (out / 'INVENTORY.json').write_text(json.dumps(inventory, indent=2) + '\n')
    (out / 'BUILD.json').write_text(json.dumps(build, indent=2) + '\n')
    print(json.dumps(inventory, indent=2))


if __name__ == '__main__':
    main()
