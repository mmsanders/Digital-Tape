"""Independent WP-05/R374 aggregation regressions. Synthetic; no physical claim."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

OFFSETS = ('-2', '-1', '+1', '+2')
KNOWN_GAPS = {'late-torn', 'late-corrupt'} | {'late-neighbour-' + x for x in OFFSETS}


def pattern(n):
    # Preserved revision-3 public fixture encoding, independent of candidate helpers.
    return struct.pack('<I', n) * 128


def fixture(count=1001):
    plan = dict(plan_version=3, run_id='V380-SIMULATION', sku='SYNTHETIC',
                revision='SIM', card_cid='NOT-A-PHYSICAL-CID', block=1000,
                neighbour_offsets=list(OFFSETS),
                trials=[dict(iteration=n, cut_offset_fraction=0.5)
                        for n in range(1, count + 1)])
    core = {k: plan[k] for k in ('run_id', 'sku', 'revision', 'card_cid', 'block', 'neighbour_offsets')}
    core['trials'] = [[t['iteration'], t['cut_offset_fraction']] for t in plan['trials']]
    plan['plan_digest'] = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    rows = []
    for n in range(1, count + 1):
        neighbours = {off: bytes([i + 17]).hex() * 512 for i, off in enumerate(OFFSETS)}
        rows.append(dict(bus_mode='spi', busy_line='MISO', payload_complete=True,
                         data_response_accepted=True, busy_entry_us=100,
                         busy_sampled_us=149, cut_us=150, iteration=n,
                         **{k: plan[k] for k in ('run_id', 'sku', 'revision', 'card_cid', 'plan_digest')},
                         precondition_ok=True, precondition_readback_hex=pattern(n - 1).hex(),
                         readback_hex=pattern(n).hex(), neighbours=neighbours,
                         neighbour_baseline=copy.deepcopy(neighbours)))
    # A declared known-late miss. It must not count, but all returned data must be audited.
    rows[-1]['busy_deassert_us'] = 149
    return plan, rows


def cases():
    result = []
    def add(name, edit, verdict='FAIL', qualifying=None, evidence=None):
        p, r = fixture()
        edit(p, r)
        result.append((name, p, r, dict(verdict=verdict, qualifying=qualifying, evidence=evidence)))
    add('production-positive-with-late-miss', lambda p, r: None, 'PASS', 1000)
    add('old-is-lawful', lambda p, r: r[0].update(readback_hex=pattern(0).hex()), 'PASS', 1000)
    add('below-production-threshold', lambda p, r: r[0].update(busy_deassert_us=149), qualifying=999)
    add('operator-cannot-lower-threshold', lambda p, r: (p.update(required_qualifying=1), r[0].update(busy_deassert_us=149)), qualifying=999)
    torn = (pattern(1000)[:256] + pattern(1001)[256:]).hex()
    add('late-torn', lambda p, r: r[-1].update(readback_hex=torn), qualifying=1000,
        evidence=('torn_iterations', 1001))
    add('late-corrupt', lambda p, r: r[-1].update(readback_hex='aa' * 512), qualifying=1000,
        evidence=('corrupt_iterations', 1001))
    for off in OFFSETS:
        add('late-neighbour-' + off,
            lambda p, r, off=off: r[-1]['neighbours'].update({off: 'ff' * 512}),
            qualifying=1000, evidence=('neighbour_damage', [1001, off]))
    add('qualifying-torn', lambda p, r: r[0].update(readback_hex=(pattern(0)[:256] + pattern(1)[256:]).hex()),
        qualifying=1000, evidence=('torn_iterations', 1))
    add('missing-planned-row', lambda p, r: r.pop())
    add('duplicate-row', lambda p, r: r.append(copy.deepcopy(r[0])))
    add('unplanned-row', lambda p, r: r.append(dict(r[0], iteration=2000)))
    for field in ('sku', 'revision', 'card_cid', 'run_id', 'plan_digest'):
        add('wrong-' + field, lambda p, r, field=field: r[-1].update({field: 'WRONG'}))
    for field in ('readback_hex', 'precondition_readback_hex'):
        add('truncated-' + field, lambda p, r, field=field: r[-1].update({field: '00'}))
        add('malformed-' + field, lambda p, r, field=field: r[-1].update({field: 'zz' * 512}))
    add('missing-neighbour', lambda p, r: r[-1]['neighbours'].pop('+2'))
    add('missing-neighbour-baseline', lambda p, r: r[-1].pop('neighbour_baseline'))
    add('unproven-precondition', lambda p, r: r[-1].update(precondition_ok=False))
    add('altered-plan', lambda p, r: p.update(block=2000))
    return result


def agrees(observed, expected):
    if observed.get('verdict') != expected['verdict']:
        return False
    if observed.get('required_qualifying') != 1000:
        return False
    if expected['qualifying'] is not None and observed.get('qualifying') != expected['qualifying']:
        return False
    if expected['evidence']:
        key, item = expected['evidence']
        if item not in observed.get(key, []):
            return False
    return True


def controls():
    positive = dict(verdict='PASS', required_qualifying=1000, qualifying=1000)
    exp = dict(verdict='PASS', qualifying=1000, evidence=None)
    assert agrees(positive, exp)
    mutants = [dict(positive, verdict='FAIL'), dict(positive, required_qualifying=1),
               dict(positive, qualifying=1001)]
    assert all(not agrees(x, exp) for x in mutants)
    tear = dict(verdict='FAIL', required_qualifying=1000, qualifying=1000, torn_iterations=[1001])
    exp = dict(verdict='FAIL', qualifying=1000, evidence=('torn_iterations', 1001))
    assert agrees(tear, exp)
    assert not agrees(dict(tear, torn_iterations=[]), exp)
    # Always-PASS and always-FAIL candidate controls must both fail the suite.
    for verdict in ('PASS', 'FAIL'):
        assert any(not agrees(dict(positive, verdict=verdict), e) for _, _, _, e in cases())
    return 6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--judge', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--baseline-known-gaps', action='store_true',
                    help='Only for authenticated old blob 34d014bf; never candidate clearance')
    args = ap.parse_args()
    raw = args.judge.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if args.baseline_known_gaps:
        assert blob == '34d014bff70a4e7421f55a6c4f34bec643e94b22', blob
    spec = importlib.util.spec_from_file_location('v380_judge', args.judge)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    observations = []
    for name, p, r, expected in cases():
        try:
            actual = m.judge([p], r)  # Production policy only; never lower threshold.
            passed = agrees(actual, expected)
            actual.pop('judged_at', None)
        except Exception as exc:
            actual, passed = {'exception': repr(exc)}, False
        observations.append(dict(case=name, expected=expected, observed=actual, passed=passed))
    failed = {x['case'] for x in observations if not x['passed']}
    success = failed == KNOWN_GAPS if args.baseline_known_gaps else not failed
    classifier = m.classify
    m.classify = lambda data, n: 'NEW'
    _, p, r, exp = next(x for x in cases() if x[0] == 'qualifying-torn')
    assert not agrees(m.judge([p], r), exp), 'always-NEW classifier escaped'
    m.classify = classifier
    _, p, r, exp = next(x for x in cases() if x[0] == 'operator-cannot-lower-threshold')
    assert not agrees(m.judge([p], r, m.Policy(1)), exp), 'lowered production minimum escaped'
    report = dict(scope='synthetic aggregation regression, no physical evidence',
                  judge_git_blob=blob, judge_sha256=hashlib.sha256(raw).hexdigest(),
                  mode='historical-baseline' if args.baseline_known_gaps else 'candidate',
                  physical_run=False, candidate_clearance=False, predicate_controls_rejected=controls(),
                  candidate_mutations_rejected=['always-NEW classifier', 'production minimum lowered to 1'],
                  cases=observations, failed_cases=sorted(failed), harness_success=success,
                  deferred='Actual-edge/busy/uncertainty/CID grammar requires Hardware declaration; see EXPECTATIONS.md')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}))
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
