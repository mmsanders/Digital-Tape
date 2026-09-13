#!/usr/bin/env python3
"""Offline replay of a VT8 evidence bundle. No engine or adapter execution occurs."""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path

from hardened import HASHES, Media, check, make_cases, sha256_bytes, verify_spec_dir

FORMAT = 'VT8-EVIDENCE-1'
OBS_FORMAT = 'VT8-OPS-OBSERVATION-1'


def _load_json(path: Path):
    return json.loads(path.read_text())


def _checked_file(root: Path, desc: dict, label: str) -> Path:
    if not isinstance(desc, dict) or not isinstance(desc.get('path'), str) or not isinstance(desc.get('sha256'), str):
        raise ValueError(f'{label}: invalid file descriptor')
    p = root / desc['path']
    if not p.is_file():
        raise ValueError(f'{label}: missing evidence file {desc["path"]}')
    digest = sha256_bytes(p.read_bytes())
    if digest != desc['sha256']:
        raise ValueError(f'{label}: evidence hash mismatch for {desc["path"]}')
    return p


def _checked_media(root: Path, desc: dict, label: str) -> bytes:
    p = _checked_file(root, desc, label)
    if not isinstance(desc.get('raw_sha256'), str):
        raise ValueError(f'{label}: missing raw media hash')
    try:
        raw = gzip.decompress(p.read_bytes())
    except Exception as exc:
        raise ValueError(f'{label}: invalid gzip media archive: {exc}') from exc
    if sha256_bytes(raw) != desc['raw_sha256']:
        raise ValueError(f'{label}: decompressed raw media hash mismatch')
    return raw


def replay_bundle(root: Path, expected_hashes: dict[str, str] | None = None) -> tuple[int, list[str]]:
    expected_hashes = HASHES if expected_hashes is None else expected_hashes
    root = root.resolve(); failures = []
    manifest_p = root / 'manifest.json'
    if not manifest_p.is_file():
        return 1, ['missing manifest.json']
    try:
        manifest = _load_json(manifest_p)
        if manifest.get('format') != FORMAT:
            raise ValueError('manifest format mismatch')
        if not manifest.get('verifier_source'):
            raise ValueError('missing verifier source provenance')
        adapter = manifest.get('adapter')
        if not isinstance(adapter, dict) or adapter.get('kind') not in {'synthetic','product'}:
            raise ValueError('missing synthetic/product adapter identity')
        for k in ('sha256','source','build'):
            if not adapter.get(k):
                raise ValueError(f'missing adapter {k} provenance')
        spec_dir = root / 'spec'
        got = verify_spec_dir(spec_dir, expected_hashes)
        for name, want in got.items():
            desc = manifest.get('spec', {}).get(name)
            p = _checked_file(root, desc, 'spec')
            if p != spec_dir / name or desc['sha256'] != want:
                raise ValueError(f'spec descriptor mismatch for {name}')
        _checked_file(root, manifest.get('run_log'), 'run log')
        case_map = {c.id: c for c in make_cases()}
        entries = manifest.get('cases')
        if not isinstance(entries, list) or {e.get('id') for e in entries if isinstance(e,dict)} != set(case_map):
            raise ValueError('manifest case set differs from oracle case set')
        for entry in entries:
            cid = entry['id']; case = case_map[cid]
            try:
                files = entry.get('files', {})
                inp_raw = _checked_media(root, files.get('input'), cid+' input')
                out_raw = _checked_media(root, files.get('output'), cid+' output')
                obs_p = _checked_file(root, files.get('observation'), cid+' observation')
                _checked_file(root, files.get('stdout'), cid+' stdout')
                _checked_file(root, files.get('stderr'), cid+' stderr')
                result_p = _checked_file(root, files.get('result'), cid+' result')
                if Media.decode(inp_raw) != case.pre:
                    raise ValueError('input media differs from independently generated fixture')
                post = Media.decode(out_raw)
                obs = _load_json(obs_p)
                if obs.get('format') != OBS_FORMAT:
                    raise ValueError('observation format mismatch')
                if obs.get('adapter_kind') != adapter['kind']:
                    raise ValueError('observation adapter identity mismatch')
                errors = check(case, post, obs.get('events', []), obs.get('calls', []))
                result = _load_json(result_p)
                expected_status = 'FAIL' if errors else 'PASS'
                if result.get('status') != expected_status or result.get('errors') != errors:
                    raise ValueError('saved verdict does not match offline recomputation')
                if entry.get('status') != expected_status or entry.get('errors') != errors:
                    raise ValueError('manifest verdict does not match offline recomputation')
                if result.get('pre_sha256') != files['input']['raw_sha256'] or result.get('post_sha256') != files['output']['raw_sha256']:
                    raise ValueError('saved media hash binding mismatch')
                print(cid + ': REPLAY ' + expected_status)
                if errors:
                    failures.append(cid + ': ' + '; '.join(errors))
            except Exception as exc:
                failures.append(cid + ': ' + str(exc))
    except Exception as exc:
        failures.append(str(exc))
    if failures:
        for f in failures:
            print('REPLAY FAIL:', f)
        return 1, failures
    print('REPLAY PASS: evidence complete, hash-bound, DRAFT-8 authenticated, verdicts recomputed offline')
    return 0, []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('evidence_dir', type=Path)
    a = ap.parse_args()
    rc, _ = replay_bundle(a.evidence_dir)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
