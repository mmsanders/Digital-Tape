#!/usr/bin/env python3
"""retained-win11.py — run a6check.py on Michael's retained Windows 11 off-card capture.

Software #439 (Verification #146/#185 WIN-A6-001/002). Not acceptance: it reports what the
corrected parser finds in the capture Verification already authenticated, with exactly the
arguments Verification's own replay (findings/P2-R1-WP14-WIN-REHEARSAL-2026-10-15-evidence/
check_stream.py) gave the unchanged parser, so the two results compare field for field.

    python3 tools/wp14-capture/retained-win11.py ORIGINAL.zip --out result.json [--work DIR]

ORIGINAL.zip is a6-rh-win-a00d8c054a0d41ccb1e026d735f97dbc.zip (98,602,972 bytes, SHA-256
9b23466b…d755). Every member used is checked against Verification's original-members.json
pins before use; the 1.77 GB verify.xml is extracted to --work (about 1.8 GB free needed)
and streamed, never loaded whole. No Windows binary is executed; tapectl.exe is hashed only.
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
ZIP_SHA = '9b23466b502f386bc3c12ac8a6674710d0caf9491358c2c654bb5717d7cbd755'
# Verification original-members.json (evidence subtree 2e338f9, Verification main a9d407c).
MEMBERS = {
    'verify.xml': 'e50da0d54c0ab406e49431ff23f189ce28475670358e19dc4978232899f834d8',
    'verify.etl': '8241f5560b5d5e367d1d9b6e954ef34d26db630824bad72d7e23874a033872cc',
    'tapectl.exe': '82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9',
    'geometry.txt': '869d638d624a307d24df91c2428f4f578eeb4174a6d4e9b5372f4fa5957a9762',
    'verify-out.txt': 'a12b7cb43c9d9134b5bb1b35e9096b66775d9e92e7611d1cc92b02edd6782a87',
    'verify-exit.txt': '13bf7b3039c63bf5a50491fa3cfd8eb4e699d1ba1436315aef9cbe5711530354',
    'verify-pid.txt': '0665c611f70c7d5c2541edbb58c79ec893af8303b64b53881fc07f4c6c4a8139',
    'tracer-exits.txt': '37dd58cb1c236c53d618d1e412e2185e59a31f72e0c4dd68acbe31c7b984df9a',
    'wpr-stop-err.txt': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    'wpr-stop-out.txt': '56f7594e4d60953c950db6c9a06253129b7d11f145d55c129ff61fe31f466486',
    'tracerpt-err.txt': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    'tracerpt-out.txt': '7add796ce54039ed9ff9d569a2aebaeec739b7d54c2025b9648b06dc42892a2c',
}
DIAG = ['wpr-stop-err.txt', 'wpr-stop-out.txt', 'tracerpt-err.txt', 'tracerpt-out.txt']


def sha_stream(f):
    h = hashlib.sha256()
    for b in iter(lambda: f.read(1 << 20), b''):
        h.update(b)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('archive', type=pathlib.Path)
    p.add_argument('--out', type=pathlib.Path, required=True)
    p.add_argument('--work', type=pathlib.Path)
    a = p.parse_args()
    with open(a.archive, 'rb') as f:
        got = sha_stream(f)
    if got != ZIP_SHA:
        sys.exit('archive SHA-256 is %s, not %s' % (got, ZIP_SHA))
    work = pathlib.Path(tempfile.mkdtemp(dir=a.work))
    try:
        with zipfile.ZipFile(a.archive) as z:
            names = {n.split('/')[-1]: n for n in z.namelist()}
            for m, want in MEMBERS.items():
                with z.open(names[m]) as src:
                    if m == 'verify.etl':
                        got = sha_stream(src)       # pinned for the record; not extracted
                    else:
                        with open(work / m, 'wb') as dst:
                            shutil.copyfileobj(src, dst, 1 << 20)
                        with open(work / m, 'rb') as f:
                            got = sha_stream(f)
                if got != want:
                    sys.exit('member %s is %s, not %s' % (m, got, want))
        args = ['--format', 'etw-xml', '--trace', 'verify.xml', '--pid', '4596', '--capacity', '4296015872',
                '--geometry', 'geometry.txt', '--target', 'rehearsal.img', '--disk', '0',
                '--exe', 'tapectl.exe', '--sha256', MEMBERS['tapectl.exe'],
                '--stdout', 'verify-out.txt', '--tracer-log', 'tracer-exits.txt', '--exit-code', '0']
        for d in DIAG:
            args += ['--diagnostics', d]
        r = subprocess.run([sys.executable, '-B', str(HERE / 'a6check.py')] + args, cwd=work,
                           capture_output=True, text=True)
        try:
            res = json.loads(r.stdout)
        except ValueError:
            sys.exit('a6check.py produced no JSON (exit %d): %s' % (r.returncode, (r.stdout + r.stderr)[-2000:]))
        res['archive'] = {'name': a.archive.name, 'sha256': ZIP_SHA, 'members': MEMBERS}
        res['a6check_sha256'] = hashlib.sha256((HERE / 'a6check.py').read_bytes()).hexdigest()
        res['exit_status'] = r.returncode
        a.out.write_text(json.dumps(res, indent=2, sort_keys=True) + '\n')
        print(json.dumps({k: res.get(k) for k in ('verdict', 'fail', 'held', 'last_sector_reads',
                                                  'target_calls', 'exit_status')}, indent=1))
        print('notes:', *res.get('notes', []), sep='\n  ')
        return r.returncode
    finally:
        shutil.rmtree(work)


if __name__ == '__main__':
    sys.exit(main())
