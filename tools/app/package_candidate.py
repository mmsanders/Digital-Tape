#!/usr/bin/env python3
"""Windows 11 x64 candidate packager (#564 / Verification #307).

Packages ONE newly built digital-tape.exe with the original, unchanged ingest.exe
and tapectl.exe into the five-member layout reviewed under Verification #288
(digital-tape.exe, ingest.exe, tapectl.exe, BUILD.json, README.txt). Nothing is
launched; the children are hash-checked, never rebuilt or invoked. The ZIP is
deterministic: sorted members, fixed timestamp, fixed mode.

  package_candidate.py STAGE_DIR FACTS.json OUT_DIR

STAGE_DIR holds the three executables. FACTS.json carries the build facts the
workflow recorded (source head/trees, toolchain, run id). OUT_DIR must not exist.
"""
import hashlib, json, sys, zipfile
from pathlib import Path

# Original pins that carry without invocation (Verification #283/#288/#307).
INGEST = '3895f3f356c91b8a9fe870c33694da64bf2765df308bef118d657c1be4bb9a20'
TAPECTL = '82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9'
OLD_APP = '05bc85626bfeaaa904f9ec52b2208f18e584d5808916a5e561be762eebac02dc'
S1_SOURCE = '35b23cacae886d9b3693b7104f581d8646ea5667'
CHILD_VERSION = '0.1.1 INGEST-1 arithmetic-profile INGEST1-AP4'
TAPECTL_SOURCE = '5e2df5aaf23e9ed0e230c444a40650da9459ddb2'
ZIP_TIME = (2026, 10, 24, 0, 0, 0)
ARCHIVE = 'Digital-Tape-Windows11-x64-candidate.zip'

GUIDE = '''Digital Tape - unsigned Windows11 x64 candidate (#564)

This is a NEW build of digital-tape.exe from the integrated production screen and
worker bridge (main {source_short}). ingest.exe and tapectl.exe are the original,
unchanged binaries; their hashes are pinned in BUILD.json.

Extract all five members into an ordinary writable folder and keep them together.
It needs the Windows WebView2 runtime that is already installed. There is no
installer, runtime download, signing step or security change.

Nothing has been demonstrated on THIS binary yet. Its startup, native window and
normal close are pending a specific Verification #307 admission. Earlier window
and quit results belong to the older app binary only and do not carry to this one.
Page readiness, label input, folder dropping, Checking, Start over, Problem/Show
details and app-driven ingest remain UNEXECUTED.

Make is disabled. Card writing and discovery are unavailable in this build. Do not
use the bundled tapectl for card work. There is no safe-to-remove claim.

If no usable window appears, close the attempt and keep any error text. Do not
change security settings to run it. This is a candidate for a bounded startup
check, not a qualified family release. Full APP/INGEST/CLI A6/G2 remain held.
'''


def sha(b):
    return hashlib.sha256(b).hexdigest()


def build(stage, facts):
    payload = {n: (stage / n).read_bytes() for n in ('digital-tape.exe', 'ingest.exe', 'tapectl.exe')}
    app = sha(payload['digital-tape.exe'])
    if app == OLD_APP:
        raise SystemExit('digital-tape.exe is the old app; promotion of the old binary is forbidden')
    if sha(payload['ingest.exe']) != INGEST:
        raise SystemExit('ingest.exe is not the original pinned child')
    if sha(payload['tapectl.exe']) != TAPECTL:
        raise SystemExit('tapectl.exe is not the original released CLI')
    meta = dict(
        scope='Windows11 x64 candidate BUILD only; startup/native-window/normal-quit pending Verification #307 admission',
        source_head=facts['source_head'], source_tree=facts['source_tree'],
        host_app_tree=facts['host_app_tree'], tools_app_tree=facts['tools_app_tree'],
        frontend_disposition=facts['frontend_disposition'], bridge_disposition=facts['bridge_disposition'],
        s1_source=S1_SOURCE, child_version=CHILD_VERSION, child_pin=INGEST,
        tapectl_source=TAPECTL_SOURCE, tapectl_pin=TAPECTL,
        packager_source=facts['packager_source'], toolchain=facts['toolchain'],
        run_id=facts['run_id'], run_attempt=facts['run_attempt'],
        candidate=dict(kind='unsigned Windows11 x64 candidate', unsigned=True, make_enabled=False,
                       discovery_enabled=False, elevation=False, installer=False, runtime_download=False,
                       startup_children='none; ingest runs only after a folder drop',
                       actual_ui='UNEXECUTED', startup_observation='PENDING Verification #307 admission',
                       selected_runtime='UNAVAILABLE unless bound from actual own process facts'),
        files=[dict(name=n, bytes=len(b), sha256=sha(b)) for n, b in sorted(payload.items())])
    payload['BUILD.json'] = (json.dumps(meta, indent=2) + '\n').encode()
    payload['README.txt'] = GUIDE.format(source_short=facts['source_head'][:8]).encode()
    return payload


def write(payload, out):
    out.mkdir(parents=True, exist_ok=False)
    bundle = out / 'Digital-Tape'
    bundle.mkdir()
    for n, b in payload.items():
        (bundle / n).write_bytes(b)
    archive = out / ARCHIVE
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for n in sorted(payload):
            info = zipfile.ZipInfo(n, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, payload[n])
    a = archive.read_bytes()
    inv = dict(archive=dict(name=ARCHIVE, bytes=len(a), sha256=sha(a)),
               members=[dict(name=n, bytes=len(b), sha256=sha(b)) for n, b in sorted(payload.items())])
    (out / 'INVENTORY.json').write_text(json.dumps(inv, indent=2) + '\n', encoding='utf-8', newline='\n')
    return inv


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    stage, facts, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    print(json.dumps(write(build(stage, json.loads(facts.read_bytes())), out), indent=2))
