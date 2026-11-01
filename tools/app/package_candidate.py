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

  package_candidate.py --profile 585 STAGE_DIR FACTS.json OUT_DIR

The #585 discovery candidate (Verification #325): S2 tapectl, four compiled child
pins, diagnostics default OFF. OUT_DIR also gets the external INVENTORY.json and
manual sheet, plus RECORD.json and a producer DRAFT registry for the r2 judge.
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


def write(payload, out, archive_name=ARCHIVE):
    out.mkdir(parents=True, exist_ok=False)
    bundle = out / 'Digital-Tape'
    bundle.mkdir()
    for n, b in payload.items():
        (bundle / n).write_bytes(b)
    archive = out / archive_name
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for n in sorted(payload):
            info = zipfile.ZipInfo(n, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, payload[n])
    a = archive.read_bytes()
    inv = dict(archive=dict(name=archive_name, bytes=len(a), sha256=sha(a)),
               members=[dict(name=n, bytes=len(b), sha256=sha(b)) for n, b in sorted(payload.items())])
    (out / 'INVENTORY.json').write_text(json.dumps(inv, indent=2) + '\n', encoding='utf-8', newline='\n')
    return inv


# --- #585 profile (Verification #325 r1/r2): the discovery-enabled candidate. -------------
# Selected with `--profile 585`; the #564 profile above is unchanged. Same five members,
# with the S2 tapectl child and all four child pins compiled into the app.
APP564 = 'ee4c84acb03655c4fb1344db1548ab283054eabe9caea9c2482b0181b39fa250'
TAPECTL_S2 = '44ef26869ba2d01a8a183660a2c7a050d0e7e9ff37c40b727131512739ea6ded'
TAPECTL_S2_SOURCE = 'f9306c2c5a42ebd039edd67b0b7cef6a7d434b2b'
TAPECTL_S2_VERSION = 'tapectl-wp15-s2+f9306c2c5a42'
S1_TREE = '835078995d4e9cc2424f9ea8d6f11304b45f783f'
PINS = dict(DT_INGEST_SHA256=INGEST, DT_INGEST_VERSION=CHILD_VERSION,
            DT_TAPECTL_SHA256=TAPECTL_S2, DT_TAPECTL_VERSION=TAPECTL_S2_VERSION)
WAV = '48f1b3c7ce7fe27a90469364f841803087a9d274a4af9a4ec8ee195a2846ac18'
ARCHIVE_585 = 'Digital-Tape-Windows11-x64-discovery-candidate.zip'
SHEET_585 = 'MANUAL-TEST-SHEET.txt'
# Independent publications per component: the V338 clearance of the final app source,
# the 288 registry's S1 publication, and the corrected discovery #318 PASS for S2 tapectl.
PUBLICATIONS = {'digital-tape.exe': 'fcad6b0cba06478a54294ea7298e7d3dc0da5819',
                'ingest.exe': '81033e2a20b4fed377fdbbb82963693b10c9b79b',
                'tapectl.exe': 'fdffea5759c2cf48b37a6960c5ed36d09ab91b98'}
DEMONSTRATED = ['direct ingest positive', 'direct ingest empty-folder refusal']
EXCLUSIONS = ['actual UI', 'app-driven child', 'fullAPP', 'fullINGEST', 'CLI A6', 'native session',
              'shipping Make', 'G2', 'startup, native window and normal quit of this app binary',
              'discovery poller session', 'card handling', 'diagnostic receipt session']

GUIDE_585 = '''Digital Tape - unsigned Windows11 x64 developer preview: discovery candidate (#585)

This is a NEW build of digital-tape.exe from main {source_short}. It includes the
cleared card discovery (#578), label and details interactions (#584) and the INGEST
console-window fix with opt-in diagnostic receipts (#594). ingest.exe is the
original, unchanged INGEST child. tapectl.exe is the accepted S2 discovery child.
Both are pinned by hash in BUILD.json, and both pins are compiled into the app.

Extract all five members into a new, ordinary folder you own and keep them
together. digital-tape.exe is the app. It needs Windows 11 x64 and the Microsoft
Edge WebView2 runtime that is normally already present on Windows 11; this bundle
does not install it. There is no installer, runtime download, signing step or
security change. Do not change security settings to run it.

What has been shown: only the bundled ingest.exe's direct checks (a music folder
accepted, an empty folder refused), run directly against that exact file and not
through this app. Nothing has been demonstrated on THIS app binary. Its startup,
window, page, label input, folder drops, Checking, Start over, Problem/Show
details, card discovery and normal close are all UNEXECUTED.

When started, this app looks for cards by itself in the background (the discovery
poller). Running it has not been admitted yet: a separate final-candidate
admission is needed first. Card discovery is a hint only. It makes no claim that a
card is safe, ready or removable.

Make cartridge is intentionally disabled. Card writing is not part of this build.
Do not run the bundled tapectl.exe or ingest.exe yourself.

Diagnostics default OFF. The app writes no diagnostic receipts unless it is started
with its single opt-in switch, and no session using that switch has been admitted.
When enabled, receipts stay in the app's private per-user CONTROL folder, capped at
16 MiB per session.

If no usable window appears, close the attempt and keep any error text. This is a
developer preview, not a qualified family release. Full APP/INGEST/CLI A6/G2 remain
held.
'''

SHEET_TEXT_585 = '''Digital Tape - optional no-card UI test sheet for the 585 discovery candidate

This sheet is OPTIONAL and gives no permission to start any app. The new 585 app
starts a card-discovery poller as soon as it opens, so these rows may be done only
after a separate final-candidate admission is issued for it. It is not a list of
required captures and does not replace your separate card procedure. There is no
Make, raw-card or card-handling test here: Make cartridge is disabled in 585.

Which bundle each test concerns:
- Original 564 (app ee4c84ac..., from main 266bdcaa): 564 completed partial on
  26 Oct under Verification328. Those results belong to 564 only. No repeat of 564
  is needed, and its passed startup/metadata checks are not repeated for paperwork.
- New 585 (this artifact): every row below concerns 585 only. Nothing is pre-filled.
  Tick Observed only for what you actually saw on 585; otherwise tick Unexecuted.

Fixtures: the frozen 317 rows and the existing DigitalTape-590-kit fixtures (Music
folder with two-seconds.wav, Empty folder, Not a song.txt, labels/2.txt-7.txt).
Source WAV: 352844 bytes, 88200 frames,
SHA256 {wav}.

Row 1 - Initial page (585). Start the app normally, once.
  Frozen expectation: one window, empty label, "0 min 0 s of 60 min", Make disabled,
  no music or folder list. The card area shows a discovery hint, not a safety claim.
  [ ] Observed   [ ] Unexecuted   Notes:

Row 2 - Label (585), the eight frozen 317 label cases:
  1 empty -> type A -> A
  2 clear -> paste 32 x (labels/2.txt) -> 32 x
  3 keep 32 x, select all -> paste 33 x (labels/3.txt) -> previous 32 x unchanged
  4 clear -> paste 16 e-acute (labels/4.txt) -> 16 e-acute
  5 keep, select all -> paste 16 e-acute + x (labels/5.txt) -> previous unchanged
  6 clear -> paste 8 emoji (labels/6.txt) -> 8 emoji
  7 keep, select all -> paste 8 emoji + x (labels/7.txt) -> previous unchanged
  8 literal NUL -> not possible naturally: Unexecuted, never injected
  [ ] Observed   [ ] Unexecuted   Notes:

Row 3 - Rejected drops (585). Drag "Not a song.txt" alone, then that file and Music
  together as one batch.
  Frozen expectation: "Drop a folder of music, not single songs." each time.
  [ ] Observed   [ ] Unexecuted   Notes:

Row 4 - Music (585). Drag the Music folder once.
  Frozen expectation: "Checking the music..." (may be too quick to see), then
  "0 min 2 s of 60 min". No console window appears.
  [ ] Observed   [ ] Unexecuted   Notes:

Row 5 - Empty (585). Click Start over, then drag the Empty folder once. If a problem
  shows, click Show details and try to select/copy the text.
  Frozen expectation: a message naming the folder; copyable details. No console window.
  [ ] Observed   [ ] Unexecuted   Notes:

Row 6 - Reset and close (585). Click Start over, then close the app normally.
  Frozen expectation: cleared label/details/length, Make still disabled, window closes.
  [ ] Observed   [ ] Unexecuted   Notes:

What you see is visible evidence only. It does not prove child processes, exit
codes or cleanup, and a missed short state is recorded as missing, not repeated.

Signed / date (Michael): ____________________
'''


def build_585(stage, facts):
    payload = {n: (stage / n).read_bytes() for n in ('digital-tape.exe', 'ingest.exe', 'tapectl.exe')}
    app = sha(payload['digital-tape.exe'])
    if app in (OLD_APP, APP564):
        raise SystemExit('digital-tape.exe is an older app; promotion of an old binary is forbidden')
    if sha(payload['ingest.exe']) != INGEST:
        raise SystemExit('ingest.exe is not the original pinned child')
    if sha(payload['tapectl.exe']) != TAPECTL_S2:
        raise SystemExit('tapectl.exe is not the accepted S2 child')
    if facts['compile_env'] != PINS:
        raise SystemExit('the recorded compile environment is not the four child pins')
    meta = dict(
        scope='Windows11 x64 discovery candidate BUILD/ARCHIVE only; nothing launched or invoked',
        source_head=facts['source_head'], source_tree=facts['source_tree'],
        host_app_tree=facts['host_app_tree'], tools_app_tree=facts['tools_app_tree'],
        engine_tree=facts['engine_tree'], current_base=facts['current_base'],
        interaction_clearance=facts['interaction_clearance'],
        console_receipt_clearance=facts['console_receipt_clearance'],
        s1_source=S1_SOURCE, s1_tree=S1_TREE, child_version=CHILD_VERSION, child_pin=INGEST,
        tapectl_source=TAPECTL_S2_SOURCE, tapectl_pin=TAPECTL_S2, tapectl_version=TAPECTL_S2_VERSION,
        compile_pins=PINS, diagnostics_default='OFF',
        packager_source=facts['packager_source'], toolchain=facts['toolchain'],
        run_id=facts['run_id'], run_attempt=facts['run_attempt'],
        preview=dict(kind='unsigned Windows11 x64 developer preview', unsigned=True, make_enabled=False,
                     installer=False, runtime_download=False,
                     working_paths='per-user app private; children relative to executable',
                     demonstrated=DEMONSTRATED, exclusions=EXCLUSIONS, ui_status='UNEXECUTED',
                     startup_failure_guidance='If no usable window appears, close the attempt and keep any '
                                              'error text; no Problem page or Show details is promised before a page opens.',
                     raw_details_scope='Show details shows the INGEST child raw stderr for a refused folder, '
                                       'only after the page has opened; UNEXECUTED on this binary.',
                     component_publications=PUBLICATIONS),
        files=[dict(name=n, bytes=len(b), sha256=sha(b)) for n, b in sorted(payload.items())])
    payload['BUILD.json'] = (json.dumps(meta, indent=2) + '\n').encode()
    payload['README.txt'] = GUIDE_585.format(source_short=facts['source_head'][:8]).encode()
    return payload


def write_585(payload, facts, out):
    """The ZIP plus its external sidecars, then the record and a DRAFT registry for the r2 judge."""
    inv = write(payload, out, ARCHIVE_585)
    sheet = SHEET_TEXT_585.format(wav=WAV)
    (out / SHEET_585).write_text(sheet, encoding='utf-8', newline='\n')
    files = {f['name']: f for f in json.loads(payload['BUILD.json'])['files']}
    sources = {'digital-tape.exe': facts['source_head'], 'ingest.exe': S1_SOURCE, 'tapectl.exe': TAPECTL_S2_SOURCE}
    registry = dict(
        authority='Software585 producer DRAFT for the CI self-check only; not Verification clearance',
        components={n: dict(bytes=f['bytes'], sha256=f['sha256'], source=sources[n], publication=PUBLICATIONS[n])
                    for n, f in files.items()},
        allowed_claims=['native-window readiness', 'normal quit', 'direct ingest positive',
                        'direct ingest empty-folder refusal'],
        required_exclusions=['actual UI', 'app-driven child', 'fullAPP', 'fullINGEST', 'CLI A6',
                             'native session', 'shipping Make', 'G2'])
    ev = facts['evidence']
    record = dict(
        scope='BUILD/ARCHIVE ONLY', app_launches=0, child_invocations=0, metadata_runs=0,
        readiness='BUILD/ARCHIVE READY, UI METHOD HELD',
        ui_method_missing=['no issued method or admission for launching the new binary, whose discovery poller '
                           'starts automatically', 'no admitted actor/gesture/context for this binary'],
        **{k: facts[k] for k in ('source_head', 'source_tree', 'host_app_tree', 'tools_app_tree',
                                 'current_base', 'engine_tree', 'interaction_clearance',
                                 'console_receipt_clearance', 'compile_env', 'build_argv',
                                 'ingest_transport')},
        tapectl_artifact=facts['tapectl_transport']['artifact_id'],
        tapectl_build_run=facts['tapectl_transport']['build_run'],
        tapectl_bytes=len(payload['tapectl.exe']), tapectl_version=TAPECTL_S2_VERSION,
        compiler_refs=ev['compiler'], lock_refs=ev['lock'], pin_source_refs=ev['pin_source'],
        actual_build_log_refs=ev['build_log'], artifact_refs=[ARCHIVE_585, 'INVENTORY.json', SHEET_585],
        member_hash_refs=['INVENTORY.json', 'BUILD.json'], source_crosswalk_refs=ev['source_crosswalk'],
        negative_mismatch_control_refs=['negative-mismatch.txt'], guide_refs=['README.txt', SHEET_585],
        old564_unchanged=True, shipping_fake_route=False, make_or_elevation_enabled=False,
        inventory_location='outside five-member ZIP', readme=payload['README.txt'].decode(),
        manual_sheet=sheet, manual_sheet_is_optional=True, claims_old_startup_for_new_app=False,
        claims_native_ui=False,
        diagnostics=dict(default='OFF', control_root='private per-user CONTROL', max_session_bytes=16777216,
                         default_config_source_refs=ev['diagnostics_source'],
                         published_schema_refs=['tests/windows_diagnostics_r2 tree 338796182b0e3979b97a1411c1552848e6649a0b'],
                         opt_in_omitted_from_build_environment=facts['opt_in_omitted_from_build_environment'],
                         native_session_admission='UNISSUED', packaged_private_session_data=False),
        final_build_count=1, receipt_availability_is_native_acceptance=False,
        zip_sha256=inv['archive']['sha256'])
    for name, data in (('RECORD.json', record), ('REGISTRY.draft.json', registry)):
        (out / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return inv


if __name__ == '__main__':
    if len(sys.argv) == 6 and sys.argv[1:3] == ['--profile', '585']:
        stage, facts, out = Path(sys.argv[3]), json.loads(Path(sys.argv[4]).read_bytes()), Path(sys.argv[5])
        print(json.dumps(write_585(build_585(stage, facts), facts, out), indent=2))
        raise SystemExit(0)
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    stage, facts, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    print(json.dumps(write(build(stage, json.loads(facts.read_bytes())), out), indent=2))
