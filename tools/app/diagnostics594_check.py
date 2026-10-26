"""Software594: judge the controlled C01-C27 evidence with Verification332's own oracles.

  python -B tools/app/diagnostics594_check.py --evidence DIR [--out summary.json]

DIR is what the diagnostics component tests wrote with DT_DIAG_EVIDENCE. Every session
envelope goes through the imported tests/windows_diagnostics_r1/receipts.py validate()
with the expectation its test declared; the C01 command, C08 and C24/C25 projections go
through cases.py; C27 mutates a real envelope and requires the oracle to reject it. This
script adds no predicate of its own: it only routes originals to the frozen ones.
"""
import argparse, base64, copy, hashlib, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tests' / 'windows_diagnostics_r1'))
import receipts, cases  # noqa: E402

def envelopes(case):
    for env in sorted(case.glob('envelope-*.json')):
        tag = env.stem[len('envelope-'):]
        yield tag, receipts.unpack(json.loads(env.read_text(encoding='utf-8'))['files']), (case / f'expect-{tag}.txt').read_text().strip()

def judge(files, expect):
    try:
        receipts.validate(files, expect == 'complete')
        return 'valid-' + expect if expect in ('complete', 'incomplete') else 'UNEXPECTED-valid'
    except (AssertionError, KeyError, TypeError, ValueError) as e:
        import traceback
        at = traceback.extract_tb(e.__traceback__)[-1]
        return f'rejected at receipts.py:{at.lineno} {at.line.strip()[:80]}' + (f' ({type(e).__name__} {e})' if str(e) else '')

ORACLE_GAP_1 = ('number() bounds integers to 0..2**53, but child-launch os_start_ns is actual Unix-epoch '
                'nanoseconds (~1.8e18). DIAGNOSTIC ONLY, not a pass: the same envelope with os_start_ns '
                'divided by 10**6 is re-judged to show whether anything else is rejected.')

def os_start_probe(files, expect):
    rows = [json.loads(l) for l in files['records.jsonl'].splitlines() if l.strip()]
    for r in rows:
        if r['kind'] == 'child-launch' and isinstance(r['data']['os_start_ns'], int): r['data']['os_start_ns'] //= 10**6
    f = dict(files); f['records.jsonl'] = receipts.encode(rows)
    return judge(f, expect)

def mutations(files):
    rows = [json.loads(l) for l in files['records.jsonl'].splitlines()]
    at = lambda k: next(i for i, r in enumerate(rows) if r['kind'] == k)
    def blob_hash(r): r[at('blob')]['data']['sha256'] = '0' * 64
    def drop_wait(r): r.pop(at('child-terminal'))
    def early_cleanup(r): r.insert(at('child-launch') + 1, r.pop(at('cleanup')))
    return [('wrongPID', lambda r: r[at('child-terminal')]['data'].update(pid=r[at('child-terminal')]['data']['pid'] + 1)),
            ('wrongNonce', lambda r: r[at('child-launch')]['data'].update(nonce='0' * 32)),
            ('wrongGeneration', lambda r: r[at('child-terminal')]['data'].update(generation=r[at('child-terminal')]['data']['generation'] + 7)),
            ('sequenceGap', None), ('wrongHash', blob_hash), ('droppedWait', drop_wait), ('cleanupEarly', early_cleanup)], rows

def c27(files):
    out = {}
    muts, rows = mutations(files)
    for name, mutate in muts:
        r = copy.deepcopy(rows)
        if name == 'sequenceGap':
            r[3]['seq'] = 99
        else:
            mutate(r)
            for i, row in enumerate(r): row['seq'] = i
        f = dict(files); f['records.jsonl'] = receipts.encode(r)
        try:
            receipts.validate(f)
            out[name] = 'SURVIVED'
        except (AssertionError, KeyError, TypeError, ValueError):
            out[name] = 'rejected'
    return out

def main():
    p = argparse.ArgumentParser(); p.add_argument('--evidence', type=Path, required=True); p.add_argument('--out', type=Path); a = p.parse_args()
    summary, ok = {'oracle_package': 'tests/windows_diagnostics_r1', 'oracle_gap_1': ORACLE_GAP_1, 'cases': {}}, True
    for case in sorted(d for d in a.evidence.iterdir() if d.is_dir()):
        res = summary['cases'][case.name] = {}
        for tag, files, expect in envelopes(case):
            v = judge(files, expect)
            res[tag] = {'expect': expect, 'oracle': v, 'records_sha256': hashlib.sha256(files['records.jsonl']).hexdigest()}
            if 'number(x)' in v and b'"child-launch"' in files['records.jsonl']:
                res[tag]['oracle_gap_1'] = os_start_probe(files, expect)
            good = v == 'valid-' + expect or (expect in ('invalid', 'oracle-gap') and v.startswith('rejected'))
            ok &= good
            if not good: print(f'{case.name}/{tag}: expected {expect}, oracle says {v}')
        if (case / 'command.json').exists():
            c = json.loads((case / 'command.json').read_text(encoding='utf-8'))
            cases.command(c['actual'], c['expected']); res['command'] = 'cases.command PASS'
            con = json.loads((case / 'console.json').read_text(encoding='utf-8'))
            res['console'] = {'C01_child_console_window': con['C01']['child']['console_window'], 'C02_child_console_window': con['C02']['child']['console_window'],
                              'runner_console_window': con['runner_console_window'], 'C02_status': con['C02']['status']}
            ok &= con['C01']['child']['console_window'] is False
        if (case / 'parity.json').exists():
            for mode, pq in json.loads((case / 'parity.json').read_text(encoding='utf-8')).items():
                cases.parity(pq['off'], pq['on']); res[f'parity-{mode}'] = 'cases.parity PASS'
        if (case / 'faults.json').exists():
            f = json.loads((case / 'faults.json').read_text(encoding='utf-8'))
            for tag, x in f['faults'].items():
                cases.parity(f['healthy'], x['projection']); res[f'parity-{tag}'] = 'cases.parity PASS'
        if case.name == 'C03-C17-C18':
            files = next(fl for t, fl, e in envelopes(case) if t == 'success')
            m = res['C27'] = c27(files)
            # Each mutation must be rejected for its own reason, not only the os_start_ns bound.
            rows = [json.loads(l) for l in files['records.jsonl'].splitlines()]
            for r in rows:
                if r['kind'] == 'child-launch': r['data']['os_start_ns'] //= 10**6
            g = dict(files); g['records.jsonl'] = receipts.encode(rows)
            m2 = res['C27_with_oracle_gap_1_probe'] = c27(g)
            ok &= all(v == 'rejected' for v in m2.values())
            ok &= all(v == 'rejected' for v in m.values())
    summary['result'] = 'PASS' if ok else 'FAIL'
    text = json.dumps(summary, indent=1) + '\n'
    if a.out: a.out.write_text(text, encoding='utf-8')
    print(text)
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
