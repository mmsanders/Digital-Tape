#!/usr/bin/env python3
"""G1 runtime summary from tracerpt XML (#444): for each control PID, the
FileIo records attributed to it and the ones naming a disk device.
  g1_etw.py TRACE.xml NEGATIVE_PID POSITIVE_PID"""
import json, re, sys
import xml.etree.ElementTree as ET

DEVICE = re.compile(r'\\Device\\Harddisk\d+\\DR\d+|PhysicalDrive\d+|\\Device\\Harddisk\d+\\Partition0', re.I)


def main(path, neg, pos):
    pids = {int(neg): 'negative', int(pos): 'positive'}
    seen = {r: {'records': 0, 'device_names': [], 'other_names': [], 'all': set(), 'events': {}} for r in pids.values()}
    total = 0
    for _, el in ET.iterparse(path):
        if not el.tag.endswith('}Event') and el.tag != 'Event':
            continue
        total += 1
        ex = next((e for e in el.iter() if e.tag.endswith('Execution')), None)
        pid = int(ex.get('ProcessID', '-1'), 0) if ex is not None else -1
        role = pids.get(pid)
        if role:
            seen[role]['records'] += 1
            task = next((e.text for e in el.iter() if e.tag.endswith('Task') and e.text), None) or \
                next((e.get('Name') for e in el.iter() if e.tag.endswith('Provider')), '?')
            op = next((e.text for e in el.iter() if e.tag.endswith('Opcode') and e.text), '')
            k = f'{task}/{op}'
            seen[role]['events'][k] = seen[role]['events'].get(k, 0) + 1
            for d in el.iter():
                if d.tag.endswith('Data') and d.text and ('\\' in d.text or 'Drive' in d.text):
                    seen[role]['all'].add(d.text)
                if d.tag.endswith('Data') and d.get('Name') in ('FileName', 'OpenPath') and d.text:
                    bucket = 'device_names' if DEVICE.search(d.text) else 'other_names'
                    if d.text not in seen[role][bucket] and len(seen[role][bucket]) < 12:
                        seen[role][bucket].append(d.text)
        el.clear()
    only = sorted(seen['negative']['all'] - seen['positive']['all'])
    for r in seen.values():
        r['all'] = len(r['all'])
    print(json.dumps({'events': total, 'controls': seen, 'negative_only_names': only[:30],
                      'negative_detected': bool(seen['negative']['device_names']),
                      'positive_clean': not seen['positive']['device_names']}, indent=1))


if __name__ == '__main__':
    main(*sys.argv[1:4])
