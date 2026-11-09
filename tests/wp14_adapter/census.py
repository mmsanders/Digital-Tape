#!/usr/bin/env python3
"""Restore authenticated retained files for the unchanged independent census.

Original request/response JSON, hashes, observations and assertions stay intact.
Only file IO resolves relocated runner paths to downloaded capture artifacts.

Without --platforms the three-platform census runs exactly as before. With
--platforms (ADR-206, Software658 comment 6640086870) the named platforms are
validated by the imported companion oracle (tests/wp14_supported_r1) before
any evidence is read (usage errors exit 64); its retained-byte audit and
audit_platforms then run unchanged over the named platforms only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'wp14_r1'))
sys.path.append(str(HERE.parent / 'wp14_supported_r1'))
import native
import oracle
import qualification
import runner


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def retained(original, captures, platform, checked):
    normalized = original.replace('\\', '/')
    marker = '/wp14-evidence/'
    if marker not in normalized:
        raise ValueError('not a retained capture path: ' + original)
    root = (captures / ('wp14-native-evidence-' + platform)).resolve()
    path = (root / normalized.split(marker, 1)[1]).resolve()
    if not path.is_relative_to(root):
        raise ValueError('capture path escapes artifact root')
    if not path.exists():
        restore(path, checked)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def restore(path, checked):
    """Mechanically restore a logical file from its retained .zst or sparse form."""
    compressed = Path(str(path) + '.zst')
    extents = Path(str(path) + '.extents.json')
    if compressed.exists():
        subprocess.run(['zstd', '-q', '-d', str(compressed), '-o', str(path)], check=True)
    elif extents.exists():
        subprocess.run([sys.executable, str(HERE / 'unsparse.py'),
                        str(extents), str(path)], check=True, stdout=sys.stderr)
        # unsparse authenticated the full logical bytes, not only extents.
        checked[path] = json.loads(extents.read_text())['sha256']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--head', required=True)
    parser.add_argument('--captures', required=True, type=Path)
    parser.add_argument('--relocations', required=True, type=Path)
    parser.add_argument('--platforms', nargs='?', const='',
                        help='sorted unique list including linux and windows; '
                             'omitted means the original linux,macos,windows census')
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    selected = None
    if args.platforms is not None:
        # Validated before any evidence is read; never a fallback to fewer platforms.
        import qualification_supported
        import retained as retained_oracle
        try:
            selected = qualification_supported.parse_platforms(args.platforms)
        except ValueError as error:
            print('usage: --platforms: ' + str(error), file=sys.stderr)
            raise SystemExit(64)
    platforms = selected or ('linux', 'macos', 'windows')
    images = {p: json.loads((args.bundle / ('image-' + p + '.json')).read_text()) for p in platforms}
    natives = {p: json.loads((args.bundle / ('native-' + p + '.json')).read_text()) for p in platforms}
    paths, proof, checked = {}, [], {}
    if selected is not None:
        # The companion oracle's retained-byte audit over every named capture,
        # index, snapshot and dump; this adapter only restores files for it.
        proof.extend(retained_oracle.audit_retained(
            natives, args.captures, selected, resolver=lambda path: restore(path, checked)))
        ignored = retained_oracle.ignored_inputs(args.bundle, args.captures, selected)
    c60 = args.bundle / 'authenticated-c60.wav'

    def bind(original, path, expected, platform):
        path = path.resolve()
        if path not in checked:
            checked[path] = digest(path)
        if checked[path] != expected:
            raise ValueError('retained file hash mismatch: ' + original)
        if original in paths and paths[original] != path:
            raise ValueError('ambiguous original path: ' + original)
        paths[original] = path
        proof.append({'platform': platform, 'original': original,
                      'retained': str(path), 'sha256': expected})

    for platform, document in natives.items():
        for row in document['results']:
            request, response = row['request'], row['response']
            # Authentication uses the original strings before any IO binding.
            native.capture_identity(request, response)
            captured = {a['path']: a['sha256'] for a in response['capture_artifacts']}
            for original in list(captured):
                if original.replace('\\', '/').endswith('/large-artifacts.json'):
                    path = retained(original, args.captures, platform, checked)
                    bind(original, path, captured[original], platform)
                    captured.update({a['path']: a['sha256'] for a in json.loads(path.read_text())})
            if request.get('required_os_readme'):
                original = response['snapshot']
                meta_name = original + '.extents.json'
                blocks_name = original + '.blocks'
                meta = retained(meta_name, args.captures, platform, checked)
                bind(meta_name, meta, captured[meta_name], platform)
                bind(blocks_name, retained(blocks_name, args.captures, platform, checked),
                     captured[blocks_name], platform)
                expected = json.loads(meta.read_text())['sha256']
                bind(original, retained(original, args.captures, platform, checked), expected, platform)
            if request.get('roundtrip'):
                name = request['source_name']
                if name == 'c60.wav':
                    if not c60.exists():
                        runner.make_c60(c60)
                    source = c60
                else:
                    if Path(name).name != name:
                        raise ValueError('invalid golden source name')
                    source = HERE.parent / 'golden' / 'ref' / name
                bind(request['source'], source, request['source_sha256'], platform)
                for original in response['dumps'].values():
                    bind(original, retained(original, args.captures, platform, checked), captured[original], platform)

    # Preserve every original assertion. These two bindings only translate IO
    # paths; request digests and the JSON handed to qualification.audit are unchanged.
    native.Path = lambda value: Path(paths.get(str(value), value))
    oracle.Path = native.Path
    compare = runner.compare_wav
    runner.compare_wav = lambda source, output: compare(paths[str(source)], paths[str(output)])
    args.relocations.write_text(json.dumps(proof, indent=2) + '\n')
    if selected is None:
        print(json.dumps(qualification.audit(images, natives, args.head), indent=2))
    else:
        result = qualification_supported.audit_platforms(images, natives, args.head, selected)
        result['ignored'] = ignored
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
