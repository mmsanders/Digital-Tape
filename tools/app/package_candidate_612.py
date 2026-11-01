#!/usr/bin/env python3
"""Windows 11 x64 replacement candidate packager (#612 / Verification #352 candidate.py).

  package_candidate_612.py STAGE_DIR FACTS.json OUT_DIR
  package_candidate_612.py --judge ARCHIVE REGISTRY.json RECORD.json

The NEW PM611/612 replacement candidate: package_candidate.py's 585 layout, member
checks and sidecars, unchanged and reused, with the cards-1 receipt app, the 612 guide
and sheet, and the attempt history and budget record that candidate.py judges.
package_candidate.py itself stays byte-unchanged, so its 564/585 build workflows do
not run again. Nothing is launched; the children are hash-checked, never rebuilt.
"""
import importlib.util, json, sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location('package_candidate', Path(__file__).resolve().parent / 'package_candidate.py')
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

APP585 = 'cc7f0e9bd996437b574559184cecb7e63f988e635ff8bb23c5e66aacdcf6f3f9'
ARCHIVE_612 = 'Digital-Tape-Windows11-x64-replacement-candidate.zip'
# The app's own publication is the V352 correction1 SOURCE PASS of the integrated source.
PUBLICATIONS_612 = dict(pc.PUBLICATIONS, **{'digital-tape.exe': '6fa36426d865f212174d3df1108766d9902dc435'})

GUIDE_612 = '''Digital Tape - unsigned Windows11 x64 developer preview: replacement candidate (#612)

This is a NEW build of digital-tape.exe from main {source_short}. It replaces the
585 discovery candidate, which was never run. It includes the cleared card
discovery (#578), label and details interactions (#584), the INGEST console-window
fix with opt-in diagnostic receipts (#594) and, new here, opt-in receipts for the
card-discovery poller (#612). ingest.exe is the original, unchanged INGEST child.
tapectl.exe is the accepted S2 discovery child. Both are pinned by hash in
BUILD.json, both pins are compiled into the app, and neither was rebuilt.

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

Diagnostics default OFF. The app writes no diagnostic receipts, for INGEST or for
the card poller, unless it is started with its single opt-in switch, and no
session using that switch has been admitted. When enabled, receipts stay in the
app's private per-user CONTROL folder, capped at 16 MiB per session. Receipts are
the app's own record; they are not proof that no device was touched.

If no usable window appears, close the attempt and keep any error text. This is a
developer preview, not a qualified family release. Full APP/INGEST/CLI A6/G2 remain
held.
'''

SHEET_TEXT_612 = '''Digital Tape - optional no-card UI test sheet for the 612 replacement candidate

This sheet is OPTIONAL and gives no permission to start any app. The new 612 app
starts a card-discovery poller as soon as it opens, so these rows may be done only
after a separate final-candidate admission is issued for it. It is not a list of
required captures and does not replace your separate card procedure. There is no
Make, raw-card or card-handling test here: Make cartridge is disabled in 612.

Which bundle each test concerns:
- Original 564 (app ee4c84ac..., from main 266bdcaa): 564 completed partial on
  26 Oct under Verification328. Those results belong to 564 only. No repeat of 564
  is needed, and its passed startup/metadata checks are not repeated for paperwork.
- 585 discovery candidate (app cc7f0e9b...): never run, and replaced by 612. Do not
  run 585 for this sheet.
- New 612 (this artifact): every row below concerns 612 only. Nothing is pre-filled.
  Tick Observed only for what you actually saw on 612; otherwise tick Unexecuted.

Fixtures: the frozen 317 rows and the existing DigitalTape-590-kit fixtures (Music
folder with two-seconds.wav, Empty folder, Not a song.txt, labels/2.txt-7.txt).
Source WAV: 352844 bytes, 88200 frames,
SHA256 {wav}.

Row 1 - Initial page (612). Start the app normally, once.
  Frozen expectation: one window, empty label, "0 min 0 s of 60 min", Make disabled,
  no music or folder list. The card area shows a discovery hint, not a safety claim.
  [ ] Observed   [ ] Unexecuted   Notes:

Row 2 - Label (612), the eight frozen 317 label cases:
  1 empty -> type A -> A
  2 clear -> paste 32 x (labels/2.txt) -> 32 x
  3 keep 32 x, select all -> paste 33 x (labels/3.txt) -> previous 32 x unchanged
  4 clear -> paste 16 e-acute (labels/4.txt) -> 16 e-acute
  5 keep, select all -> paste 16 e-acute + x (labels/5.txt) -> previous unchanged
  6 clear -> paste 8 emoji (labels/6.txt) -> 8 emoji
  7 keep, select all -> paste 8 emoji + x (labels/7.txt) -> previous unchanged
  8 literal NUL -> not possible naturally: Unexecuted, never injected
  [ ] Observed   [ ] Unexecuted   Notes:

Row 3 - Rejected drops (612). Drag "Not a song.txt" alone, then that file and Music
  together as one batch.
  Frozen expectation: "Drop a folder of music, not single songs." each time.
  [ ] Observed   [ ] Unexecuted   Notes:

Row 4 - Music (612). Drag the Music folder once.
  Frozen expectation: "Checking the music..." (may be too quick to see), then
  "0 min 2 s of 60 min". No console window appears.
  [ ] Observed   [ ] Unexecuted   Notes:

Row 5 - Empty (612). Click Start over, then drag the Empty folder once. If a problem
  shows, click Show details and try to select/copy the text.
  Frozen expectation: a message naming the folder; copyable details. No console window.
  [ ] Observed   [ ] Unexecuted   Notes:

Row 6 - Reset and close (612). Click Start over, then close the app normally.
  Frozen expectation: cleared label/details/length, Make still disabled, window closes.
  [ ] Observed   [ ] Unexecuted   Notes:

What you see is visible evidence only. It does not prove child processes, exit
codes or cleanup, and a missed short state is recorded as missing. The opt-in
diagnostic switch is not part of this sheet; a receipt session needs its own
admission.

Signed / date (Michael): ____________________
'''


def build_612(stage, facts):
    """The 585 member checks and BUILD.json, re-scoped to the 612 profile and its clearances."""
    payload = pc.build_585(stage, facts)
    if pc.sha(payload['digital-tape.exe']) == APP585:
        raise SystemExit('digital-tape.exe is the 585 app; the replacement must be a new build')
    meta = json.loads(payload['BUILD.json'])
    meta['scope'] = 'Windows11 x64 replacement candidate (#612) BUILD/ARCHIVE only; nothing launched or invoked'
    meta['profile'] = '612'
    meta['cards_receipt_clearance'] = facts['cards_receipt_clearance']
    meta['preview']['exclusions'] = pc.EXCLUSIONS + ['cards receipt session']
    meta['preview']['component_publications'] = PUBLICATIONS_612
    payload['BUILD.json'] = (json.dumps(meta, indent=2) + '\n').encode()
    payload['README.txt'] = GUIDE_612.format(source_short=facts['source_head'][:8]).encode()
    return payload


def write_612(payload, facts, out):
    """The 585 sidecars and record, with the 612 sheet, budget record and attempt history."""
    pc.write_585(payload, facts, out)
    (out / pc.ARCHIVE_585).rename(out / ARCHIVE_612)
    inv = json.loads((out / 'INVENTORY.json').read_bytes())
    inv['archive']['name'] = ARCHIVE_612
    (out / 'INVENTORY.json').write_text(json.dumps(inv, indent=2) + '\n', encoding='utf-8', newline='\n')
    sheet = SHEET_TEXT_612.format(wav=pc.WAV)
    (out / pc.SHEET_585).write_text(sheet, encoding='utf-8', newline='\n')
    record = json.loads((out / 'RECORD.json').read_bytes())
    registry = json.loads((out / 'REGISTRY.draft.json').read_bytes())
    registry['authority'] = 'Software612 producer DRAFT for the CI self-check only; not Verification clearance'
    for n, p in PUBLICATIONS_612.items():
        registry['components'][n]['publication'] = p
    app = registry['components']['digital-tape.exe']
    current = dict(facts['attempt'], attempt=len(facts['prior_attempts']) + 1,
                   artifacts=[dict(name='digital-tape.exe', bytes=app['bytes'], sha256=app['sha256'],
                                   ref=facts['attempt_artifact_ref'])])
    attempts = facts['prior_attempts'] + [current]
    record.update(
        artifact_refs=[ARCHIVE_612, 'INVENTORY.json', pc.SHEET_585], manual_sheet=sheet,
        candidate_authorization='PM611/Software612 NEW replacement',
        cards_receipt_clearance=facts['cards_receipt_clearance'],
        source_correction_responses=facts['source_correction_responses'], functional_scope_unchanged=True,
        candidate_attempts=attempts, final_build_count=len(attempts), uploaded_candidates=1,
        children_rebuilt=0, old585_rebuilt=False, budget_exhausted_retry=False,
        candidate_compilation_refs=[a['log_ref'] for a in attempts], ci_build_inventory=facts['ci_build_inventory'],
        zip_sha256=inv['archive']['sha256'])
    record['diagnostics']['published_schema_refs'] = record['diagnostics']['published_schema_refs'] + [
        'tests/windows_cards_receipts_r1 tree c3b0d52cc6dc30b8ee6dfc17250bef914e8e9b27']
    for name, data in (('RECORD.json', record), ('REGISTRY.draft.json', registry)):
        (out / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return inv


def with_attempts(facts, evidence):
    """The attempt history and this attempt's own timing and exit, read as written by the build
    step (prior-attempts.json, attempt.json beside FACTS.json), never re-serialized by the shell."""
    timing = json.loads((evidence / 'attempt.json').read_bytes())
    facts['prior_attempts'] = json.loads((evidence / 'prior-attempts.json').read_bytes())
    facts['attempt'] = dict(facts['attempt'], **{k: timing[k] for k in ('started_at', 'finished_at', 'exit')})
    return facts


def judge(archive, registry, record):
    """Verification #352's own candidate.check, unchanged, on the produced archive and record."""
    tests = Path(__file__).resolve().parents[2] / 'tests' / 'windows_cards_receipts_r1'
    sys.path.insert(0, str(tests))
    import candidate
    return candidate.check(archive.read_bytes(), json.loads(registry.read_text(encoding='utf-8-sig')),
                           json.loads(record.read_text(encoding='utf-8-sig')))


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--judge':
        print(judge(*map(Path, sys.argv[2:])))
        raise SystemExit(0)
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    stage, facts_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    facts = with_attempts(json.loads(facts_path.read_bytes()), facts_path.parent)
    print(json.dumps(write_612(build_612(stage, facts), facts, out), indent=2))
