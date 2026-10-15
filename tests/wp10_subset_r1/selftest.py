"""Independent finite-state equivalence and causal controls; no engine disposition."""
import hashlib
import itertools
import json
from pathlib import Path
from model import BLOCK, Device, exhaustive, sampled


def b(char):
    return char.encode() * BLOCK


def freeze(image):
    return tuple(sorted(image.items()))


def reject(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError("invalid input was accepted")


def run():
    d = Device({0: b('a'), 1: b('b')})
    d.write(0, b('A') + b('B'))
    images = {freeze(d.crash_image(p['landing_order'])) for p in exhaustive(d.events)}
    missing = freeze({0: b('a'), 1: b('B')})
    prefixes = {freeze(d.crash_image(list(range(i)))) for i in range(3)}
    assert len(images) == 4 and missing in images and missing not in prefixes
    assert {freeze(d.crash_image([])), freeze(d.crash_image([0, 1]))} < images
    assert [e.call for e in d.events] == [0, 0]  # split a single multi-block call
    assert d.remount([1]).read(0, 2) == b('a') + b('B')
    assert d.read(0, 2) == b('A') + b('B')  # source RAM cannot leak into remount
    assert d.remount([1]).events == []

    # Brute force independent reference: all subsets and ALL permutations for N<=5.
    reference_counts = []
    for n in range(6):
        d = Device({i: b('a') for i in range(3)})
        for i, lba in enumerate([0, 1, 0, 2, 1][:n]):
            d.write(lba, bytes([65 + i]) * BLOCK)
        expected = set()
        for k in range(n + 1):
            for order in itertools.permutations(range(n), k):
                values = {i: b('a') for i in range(3)}
                for i in order:
                    values[[0, 1, 0, 2, 1][i]] = bytes([65 + i]) * BLOCK
                expected.add(freeze(values))
        actual = {freeze(d.crash_image(p['landing_order'])) for p in exhaustive(d.events)}
        assert actual == expected
        reference_counts.append(len(actual))

    census = []
    for n in range(9):
        for repeated in (False, True):
            d = Device({0: b('a')})
            for i in range(n):
                d.write(0 if repeated else i, bytes([i + 1]) * BLOCK)
            plans = list(exhaustive(d.events))
            expected = 1 + n * (1 << (n - 1)) if repeated and n else (1 << n)
            assert len(plans) == expected
            assert len({p['mask'] for p in plans}) == 1 << n
            census.append({'events': n, 'repeated_lba': repeated, 'classes': len(plans)})

    d = Device({0: b('a')})
    d.write(0, b('A'))
    d.write(0, b('B'))
    assert d.crash_image([1, 0])[0] == b('A')  # last LANDED, not last logical
    assert d.crash_image([0])[0] == b('A')  # dirty bitmap loses this version
    d.flush(successful=False)
    assert len(d.events) == 2 and d.crash_image([])[0] == b('a')
    d.flush(successful=True)
    assert not d.events and d.crash_image([])[0] == b('B')
    reject(lambda: d.crash_image([0]))  # successful epoch cannot be reselected

    d.write(0, b('C'), acknowledged=False)
    assert not d.events[0].acknowledged and d.crash_image([2])[0] == b('C')
    assert d.crash_image([])[0] == b('B')
    reject(lambda: d.flush(successful=True))
    reject(lambda: d.read(0))
    d.flush(successful=False)
    assert len(d.events) == 1
    d.resolve_working({0: b('B')})
    d.flush(successful=True)
    assert d.crash_image([])[0] == b('B')  # failed attempt is not blindly flushed
    d.write(0, b('D'), acknowledged=False, visible={0})
    d.flush(successful=True)
    assert d.crash_image([])[0] == b('D')
    d.write(1, b('E'), acknowledged=False, visible=set())
    assert d.crash_image([4])[1] == b('E')  # invisible != known non-durable
    d2 = d.remount([4])
    d2.write(0, b('F'))
    assert d2.remount([]).read(0, 2) == b('D') + b('E')  # two interruptions
    reject(lambda: d2.write(0, b'x'))  # torn bytes belong to separate model
    reject(lambda: d2.crash_image([0, 0]))
    reject(lambda: d2.crash_image([99]))

    # Causal toy transaction: header identity must not become visible before data.
    # This is a model control, NOT a TapeFS oracle or a Product defect claim.
    def identity_before_data(image):
        return image[1] != b('H') or image[0] == b('D')
    good = Device({0: b('d'), 1: b('h')})
    good.write(0, b('D'))
    good.flush(successful=True)
    good.write(1, b('H'))
    assert all(identity_before_data(good.crash_image(p['landing_order'])) for p in exhaustive(good.events))
    dropped = Device({0: b('d'), 1: b('h')})
    dropped.write(0, b('D'))
    dropped.write(1, b('H'))
    assert not identity_before_data(dropped.crash_image([1]))
    early = Device({0: b('d'), 1: b('h')})
    early.write(1, b('H'))
    early.flush(successful=True)
    early.write(0, b('D'))
    assert not identity_before_data(early.crash_image([]))

    large = Device({i: bytes(BLOCK) for i in range(8)})
    for i in range(32):
        large.write(i % 8, bytes([i + 1]) * BLOCK)
    reject(lambda: list(exhaustive(large.events)))
    rows = []
    for seed in (1, 183, 0xD96B4245):
        for plan in sampled(large.events, seed):
            selected = set(plan['landing_order'])
            assert len(selected) == len(plan['landing_order'])
            assert int(plan['mask'], 2) == sum(1 << i for i in selected)
            image = large.crash_image(plan['landing_order'])
            plan['image_sha256'] = hashlib.sha256(b''.join(image[i] for i in range(8))).hexdigest()
            rows.append(plan)
    stream = ''.join(json.dumps(r, sort_keys=True, separators=(',', ':')) + '\n' for r in rows)
    expected_path = Path(__file__).with_name('sampled-masks.jsonl')
    if '--record' in __import__('sys').argv:
        expected_path.write_text(stream)
    assert expected_path.read_text() == stream, 'sample masks/orders or byte projections drift'
    return {'result': 'PASS (model only)', 'brute_force_unique_images_N0_to_5': reference_counts,
            'exhaustive_census': census, 'sampled_epoch_events': 32, 'sampled_rows': len(rows),
            'sampled_sha256': hashlib.sha256(stream.encode()).hexdigest(),
            'controls': ['old_modes_and_prefixes_miss_aB', 'multi_block_split', 'repeated_versions',
                         'last_landed_wins', 'failed_write_unknown', 'failed_flush_not_barrier',
                         'successful_barrier_final_state', 'fresh_remount_two_interruptions',
                         'torn_rejected', 'dropped_barrier', 'identity_before_data'],
            'engine_operations_executed': 0}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True, indent=2))
