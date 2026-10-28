"""Software612: judge the controlled P1-P6 cards evidence with Verification352's own oracle.

  python -B tools/app/cards612_check.py --evidence DIR [--out summary.json]

DIR is what the c612_ component tests wrote with DT_DIAG_EVIDENCE. Every session envelope
goes through the imported tests/windows_cards_receipts_r1/receipts.py validate() with the
binding the test measured (app, pinned child path/hash/label, private root) and the
expectation its test declared. Where the test kept the child's own observation
(external-<tag>.json), the last launch and its blobs must equal it. The unmodified
production positive must pass, then each mutation of it must be rejected. This script
adds no receipt predicate of its own: it only routes originals to the frozen oracle.
"""
import argparse, base64, copy, hashlib, json, sys, traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tests' / 'windows_cards_receipts_r1'))
import receipts  # noqa: E402

def unpack(env):
    return {k: base64.b64decode(v) for k, v in env['files'].items()}

def where(e):
    at = traceback.extract_tb(e.__traceback__)[-1]
    return f'{Path(at.filename).name}:{at.lineno} {at.line.strip()[:80]}' + (f' ({type(e).__name__} {e})' if str(e) else '')

def judge(files, binding, expect):
    try:
        receipts.validate(files, binding, expect == 'complete')
        return 'valid-' + expect if expect in ('complete', 'incomplete') else 'UNEXPECTED-valid'
    except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
        return 'rejected at ' + where(e)

def external(files, observed):
    """The child's own observation against the last launch and that run's blobs."""
    rows = [json.loads(l) for l in files['records.jsonl'].splitlines()]
    launch = [r['data'] for r in rows if r['kind'] == 'cards-launch'][-1]
    for k in ('pid', 'os_start_ns', 'argv', 'cwd'):
        assert launch[k] == observed[k], k
    assert observed['console_window'] is False
    for r in rows:
        if r['kind'] == 'cards-blob' and r['data']['run_id'] == launch['run_id']:
            assert hashlib.sha256(files[r['data']['leaf']]).hexdigest() == observed['sha256'][r['data']['role']], r['data']['role']
    return 'PASS'

def mutations(files, binding):
    rows = [json.loads(l) for l in files['records.jsonl'].splitlines()]
    at = lambda k: next(i for i, r in enumerate(rows) if r['kind'] == k)
    def reseq(r):
        for i, row in enumerate(r): row['seq'] = i
    def move(src, dst):
        def f(r): r.insert(at(dst), r.pop(at(src)))
        return f
    muts = {
        'wrongNonce': lambda r: r[at('cards-launch')]['data'].update(nonce='0' * 32),
        'wrongPID': lambda r: r[at('cards-terminal')]['data'].update(pid=r[at('cards-terminal')]['data']['pid'] + 1),
        'wrongHash': lambda r: r[at('cards-launch')]['data'].update(exe_sha256_observed='0' * 64),
        'mislabelledVersion': lambda r: r[at('cards-launch')]['data'].update(pin_version_label='tapectl-wp15-s2+000000000000'),
        'wrongPath': lambda r: r[at('cards-launch')]['data'].update(exe='C:\\elsewhere\\tapectl.exe'),
        'consoleFlags': lambda r: r[at('cards-launch')]['data'].update(creation_flags=0x10),
        'droppedTerminal': lambda r: r.pop(at('cards-terminal')),
        'droppedCleanup': lambda r: r.pop(at('cards-cleanup')),
        'cleanupBeforeCapture': move('cards-cleanup', 'cards-blob'),
        'captureBeforePublication': move('cards-blob', 'cards-publication-attempt'),
        'blobHash': lambda r: r[at('cards-blob')]['data'].update(sha256='0' * 64),
        'ticketSwap': lambda r: r[at('cards-terminal')]['data'].update(ticket=r[at('cards-terminal')]['data']['ticket'] + 1),
        'cleanupFailedAsRemoved': lambda r: r[at('cards-cleanup')]['data'].update(result='failed'),
    }
    out = {}
    for name, mutate in muts.items():
        r = copy.deepcopy(rows)
        mutate(r)
        reseq(r)
        f = dict(files); f['records.jsonl'] = receipts.encode(r)
        try:
            receipts.validate(f, binding, True)
            out[name] = 'SURVIVED'
        except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
            out[name] = 'rejected at ' + where(e)
    wrong = dict(binding, sha256='0' * 64)
    try:
        receipts.validate(files, wrong, True); out['wrongBinding'] = 'SURVIVED'
    except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
        out['wrongBinding'] = 'rejected at ' + where(e)
    return out

def main():
    p = argparse.ArgumentParser(); p.add_argument('--evidence', type=Path, required=True); p.add_argument('--out', type=Path); a = p.parse_args()
    summary, ok, seen = {'oracle_package': 'tests/windows_cards_receipts_r1', 'cases': {}}, True, 0
    for case in sorted(d for d in a.evidence.iterdir() if d.is_dir()):
        res = summary['cases'][case.name] = {}
        for env in sorted(case.glob('envelope-*.json')):
            tag = env.stem[len('envelope-'):]
            files = unpack(json.loads(env.read_text(encoding='utf-8')))
            binding = json.loads((case / f'binding-{tag}.json').read_text(encoding='utf-8'))
            expect = (case / f'expect-{tag}.txt').read_text().strip()
            v = judge(files, binding, expect)
            r = res[tag] = {'expect': expect, 'oracle': v, 'records_sha256': hashlib.sha256(files['records.jsonl']).hexdigest()}
            good = v == 'valid-' + expect
            ext = case / f'external-{tag}.json'
            if ext.exists():
                try: r['external'] = external(files, json.loads(ext.read_text(encoding='utf-8')))
                except (AssertionError, KeyError, IndexError) as e: r['external'] = 'MISMATCH at ' + where(e); good = False
            if tag == 'production':
                m = r['mutations'] = mutations(files, binding)
                good &= all(x.startswith('rejected') for x in m.values())
            ok &= good; seen += 1
            if not good: print(f'{case.name}/{tag}: expected {expect}, oracle says {v}')
    ok &= seen > 0 and 'production' in {t for c in summary['cases'].values() for t in c}
    summary['envelopes'] = seen
    summary['result'] = 'PASS' if ok else 'FAIL'
    text = json.dumps(summary, indent=1) + '\n'
    if a.out: a.out.write_text(text, encoding='utf-8')
    print(text)
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
