#!/usr/bin/env python3
"""Run VT8 public-operation observations and persist a replayable evidence bundle."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from hardened import Media, HASHES, check, make_cases, sha256_bytes, verify_spec_dir

FORMAT = 'VT8-EVIDENCE-1'
OBS_FORMAT = 'VT8-OPS-OBSERVATION-1'
DEFAULT_SPEC_DIR = Path(__file__).resolve().parents[1] / 'mount_draft8' / 'spec'


def file_sha(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def _fresh_dir(path: Path) -> None:
    if path.exists():
        if any(path.iterdir()):
            raise ValueError(f'evidence directory is not empty: {path}')
    else:
        path.mkdir(parents=True)


def _copy_specs(spec_dir: Path, evidence_dir: Path, expected_hashes: dict[str, str]) -> dict[str, dict[str, str]]:
    verified = verify_spec_dir(spec_dir, expected_hashes)
    out = evidence_dir / 'spec'; out.mkdir()
    rec = {}
    for name, digest in verified.items():
        dst = out / name
        shutil.copyfile(Path(spec_dir) / name, dst)
        if file_sha(dst) != digest:
            raise ValueError(f'spec evidence copy drift: {name}')
        rec[name] = {'path': f'spec/{name}', 'sha256': digest}
    return rec


def run_package(*, adapter: Path, evidence_dir: Path, spec_dir: Path,
                adapter_kind: str, adapter_source: str, adapter_build: str,
                verifier_source: str, timeout: int = 60,
                expected_hashes: dict[str, str] | None = None) -> tuple[int, dict]:
    expected_hashes = HASHES if expected_hashes is None else expected_hashes
    adapter = adapter.resolve(); evidence_dir = evidence_dir.resolve(); spec_dir = spec_dir.resolve()
    if not adapter.is_file():
        raise ValueError(f'adapter executable missing: {adapter}')
    if adapter_kind not in {'synthetic', 'product'}:
        raise ValueError('adapter_kind must be synthetic or product')
    if not adapter_source.strip() or not adapter_build.strip() or not verifier_source.strip():
        raise ValueError('adapter source/build provenance and verifier source are required')
    _fresh_dir(evidence_dir)
    specs = _copy_specs(spec_dir, evidence_dir, expected_hashes)

    manifest = {
        'format': FORMAT,
        'verifier_source': verifier_source,
        'oracle_sha256': file_sha(Path(__file__).with_name('oracle.py')),
        'hardening_sha256': file_sha(Path(__file__).with_name('hardened.py')),
        'runner_sha256': file_sha(Path(__file__)),
        'spec_source': str(spec_dir),
        'spec': specs,
        'adapter': {
            'kind': adapter_kind,
            'path': str(adapter),
            'sha256': file_sha(adapter),
            'source': adapter_source,
            'build': adapter_build,
        },
        'cases': [],
    }
    failures = 0
    run_log = evidence_dir / 'run.jsonl'
    with run_log.open('w') as log:
        log.write(json.dumps({'kind':'provenance', **{k:v for k,v in manifest.items() if k != 'cases'}}, sort_keys=True) + '\n')
        for case in make_cases():
            cdir = evidence_dir / 'cases' / case.id; cdir.mkdir(parents=True)
            inp = cdir / 'input.vo08'; out = cdir / 'output.vo08'
            inp_gz = cdir / 'input.vo08.gz'; out_gz = cdir / 'output.vo08.gz'
            stdout_p = cdir / 'stdout.txt'; stderr_p = cdir / 'stderr.txt'
            observation_p = cdir / 'observation.json'; result_p = cdir / 'result.json'
            inp.write_bytes(case.pre.encode())
            errors = []
            events = []; calls = []; returncode = None
            try:
                r = subprocess.run([str(adapter), case.id, str(inp), str(out)], capture_output=True,
                                   text=True, timeout=timeout)
                returncode = r.returncode
                stdout_p.write_text(r.stdout); stderr_p.write_text(r.stderr)
                if r.returncode != 0:
                    errors.append(f'adapter returned {r.returncode}')
                if not out.is_file():
                    errors.append('adapter omitted output media')
                try:
                    observation = json.loads(r.stdout)
                    if not isinstance(observation, dict):
                        raise ValueError('stdout JSON is not an object')
                    _write_json(observation_p, observation)
                    if observation.get('format') != OBS_FORMAT:
                        errors.append('adapter observation format mismatch')
                    if observation.get('adapter_kind') != adapter_kind:
                        errors.append('adapter observation synthetic/product identity mismatch')
                    events = observation.get('events', [])
                    calls = observation.get('calls', [])
                except Exception as exc:
                    observation = {'format': OBS_FORMAT, 'parse_error': str(exc), 'raw_stdout_sha256': sha256_bytes(r.stdout.encode())}
                    _write_json(observation_p, observation)
                    errors.append('adapter observation malformed: ' + str(exc))
                if out.is_file():
                    try:
                        post = Media.decode(out.read_bytes())
                        errors.extend(check(case, post, events, calls))
                    except Exception as exc:
                        errors.append('output/oracle evaluation failed: ' + str(exc))
            except Exception as exc:
                stdout_p.write_text(''); stderr_p.write_text('')
                _write_json(observation_p, {'format': OBS_FORMAT, 'runner_error': str(exc)})
                errors.append('adapter execution failed: ' + str(exc))

            inp_raw = inp.read_bytes()
            inp_gz.write_bytes(gzip.compress(inp_raw, mtime=0)); inp.unlink()
            files = {
                'input': {'path': str(inp_gz.relative_to(evidence_dir)), 'sha256': file_sha(inp_gz),
                          'raw_sha256': sha256_bytes(inp_raw)},
                'stdout': {'path': str(stdout_p.relative_to(evidence_dir)), 'sha256': file_sha(stdout_p)},
                'stderr': {'path': str(stderr_p.relative_to(evidence_dir)), 'sha256': file_sha(stderr_p)},
                'observation': {'path': str(observation_p.relative_to(evidence_dir)), 'sha256': file_sha(observation_p)},
            }
            if out.is_file():
                out_raw = out.read_bytes(); out_gz.write_bytes(gzip.compress(out_raw, mtime=0)); out.unlink()
                files['output'] = {'path': str(out_gz.relative_to(evidence_dir)), 'sha256': file_sha(out_gz),
                                   'raw_sha256': sha256_bytes(out_raw)}
            status = 'FAIL' if errors else 'PASS'
            result = {
                'id': case.id, 'operation': case.operation, 'adapter_kind': adapter_kind,
                'returncode': returncode, 'status': status, 'errors': errors,
                'pre_sha256': files['input']['raw_sha256'],
                'post_sha256': files.get('output', {}).get('raw_sha256'),
            }
            _write_json(result_p, result)
            files['result'] = {'path': str(result_p.relative_to(evidence_dir)), 'sha256': file_sha(result_p)}
            entry = {'id': case.id, 'operation': case.operation, 'status': status, 'errors': errors, 'files': files}
            manifest['cases'].append(entry)
            log.write(json.dumps({'kind':'case', **entry}, sort_keys=True) + '\n'); log.flush()
            failures += bool(errors)
            if errors:
                print(case.id + ': FAIL: ' + '; '.join(errors))
            else:
                print(case.id + ': PASS')

    manifest['run_log'] = {'path': 'run.jsonl', 'sha256': file_sha(run_log)}
    _write_json(evidence_dir / 'manifest.json', manifest)
    print(f'{len(manifest["cases"])} cases; {failures} failed; evidence {evidence_dir}')
    return (1 if failures else 0), manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--adapter', type=Path, required=True)
    ap.add_argument('--evidence-dir', type=Path, required=True)
    ap.add_argument('--spec-dir', type=Path, default=DEFAULT_SPEC_DIR)
    ap.add_argument('--adapter-kind', choices=['synthetic','product'], required=True)
    ap.add_argument('--adapter-source', required=True, help='immutable adapter source identity (commit/tree/artifact)')
    ap.add_argument('--adapter-build', required=True, help='compiler/build command or build artifact provenance')
    ap.add_argument('--verifier-source', required=True, help='immutable verifier source commit')
    ap.add_argument('--timeout', type=int, default=60)
    a = ap.parse_args()
    try:
        rc, _ = run_package(adapter=a.adapter, evidence_dir=a.evidence_dir, spec_dir=a.spec_dir,
                            adapter_kind=a.adapter_kind, adapter_source=a.adapter_source,
                            adapter_build=a.adapter_build, verifier_source=a.verifier_source,
                            timeout=a.timeout)
        return rc
    except Exception as exc:
        print('RUNNER FAIL:', exc)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
