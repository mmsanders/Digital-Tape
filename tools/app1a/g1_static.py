#!/usr/bin/env python3
"""APP-1 §1 / WP-15 G1 static check (#452 S4): the app never opens a block device, raw
disk or partition. Every device access is a tapectl child.

The check reads the app tree (Rust, page, capabilities, config, manifest) and fails on:

  G1-DEV    a device name or device API anywhere in app code (raw disk paths, ioctls,
            DeviceIoControl, IOKit, DiskArbitration, platform storage bindings);
  G1-FS     a file-system call outside the modules allowed to make one, a call in an
            allowed module that is not on that module's list, or a path argument whose
            source is not that module's own app-owned/derived root (the data-flow rule);
  G1-CHILD  a process launch anywhere but the ingest runner, or launching anything but
            the pinned, resolved child;
  G1-PAGE   page code with file, shell, process or plugin access;
  G1-CAP    a capability, plugin or dependency that would give the page file, shell,
            dialog or process access.

Scope: the shipped app (src/, ui/, capabilities/, Cargo.toml, tauri.conf.json); unit-test
blocks after `#[cfg(test)]` and the integration tests under tests/ are not app code.

Usage: g1_static.py [--root host/app]   exit 0 clean, 1 with findings printed.
The negative control is tools/app1a/fixtures/g1-negative (a copy of the tree with one
planted violation per rule); CI requires the check to FAIL on it.
"""
import json, re, sys
from pathlib import Path

DEVICE = [
    r'/dev/', r'\\\\\.\\', r'\\\\\\\\\.\\\\', r'PhysicalDrive', r'Harddisk\d', r'\brdisk', r'\bDKIOC', r'\bioctl\b',
    r'DeviceIoControl', r'IOKit', r'DiskArbitration', r'IOServiceMatching', r'\bCreateFileW?\b',
    r'windows_sys', r'windows::Win32::Storage', r'\blibc::(open|openat|ioctl)\b', r'\bnix::', r'BlockDevice',
]
FS_CALL = re.compile(r'\b(?:std::)?fs::(\w+)\s*\(|\bFile::(open|create)\s*\(|\bOpenOptions::new\s*\(\)|\.open\s*\(')
CHILD = re.compile(r'\b(?:std::process::)?Command::new\s*\(([^)]*)\)')

# Module -> (allowed fs functions, regex every path argument must match).
FS_ALLOW = {
    'jobdir.rs': ({'create_dir_all', 'create_dir', 'remove_dir_all', 'read_dir', 'read', 'symlink_metadata', 'open'},
                  r'^\s*(&?\s*(root|dir|data|p|m|job\.dir|dir\.join\(MARKER\)|jobs_root\(data\)|&control|&out))\s*$|^\s*&?(control|out|root|dir|p|m)\s*$|^\s*dir\.join\(MARKER\)\s*$|^\s*jobs_root\(data\)\s*$|^\s*&?job\.dir\s*$|^\s*&?(root|dir)\s*$'),
    'drops.rs': ({'symlink_metadata', 'metadata'}, r'^\s*&?p\s*$'),
    'children.rs': ({'read'}, r'^\s*&?p\s*$'),
    'ingest_job.rs': ({'read_dir', 'read'}, r'^\s*&?(dest|report_path|dest\.join\("manifest\.json"\))\s*$'),
}
# Unit tests may build scratch trees under the temp directory.
TEST_SPLIT = re.compile(r'^#\[cfg\(test\)\]', re.M)


def args_of(src, start):
    """The argument text of the call whose '(' is at or after `start`."""
    i = src.index('(', start)
    depth, j = 0, i
    while j < len(src):
        c = src[j]
        depth += c == '('
        depth -= c == ')'
        if depth == 0:
            return src[i + 1:j]
        j += 1
    return src[i + 1:]


def first_arg(a):
    depth, out = 0, ''
    for c in a:
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif c == ',' and depth == 0:
            break
        out += c
    return out


def strip_comments(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return '\n'.join(l.split('//')[0] if not l.lstrip().startswith('//') else '' for l in s.splitlines())


def check(root):
    root = Path(root)
    bad = []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or 'target' in p.parts or 'gen' in p.parts or p.suffix not in ('.rs', '.js', '.html', '.json', '.toml'):
            continue
        rel = p.relative_to(root).as_posix()
        if rel.split('/')[0] == 'tests':
            continue  # integration tests drive the real child from scratch trees; not shipped app code
        text = p.read_text(encoding='utf-8')
        code = strip_comments(text) if p.suffix in ('.rs', '.js') else text
        if p.suffix == '.rs':
            body = TEST_SPLIT.split(code)[0]
            for pat in DEVICE:
                for m in re.finditer(pat, body):
                    bad.append(('G1-DEV', rel, body.count('\n', 0, m.start()) + 1, m.group(0)))
            allow = FS_ALLOW.get(p.name)
            for m in FS_CALL.finditer(body):
                fn = m.group(1) or m.group(2) or 'open'
                line = body.count('\n', 0, m.start()) + 1
                if m.group(0).startswith('OpenOptions'):
                    continue  # judged at its `.open(` call
                if allow is None:
                    bad.append(('G1-FS', rel, line, f'fs call {fn} outside the allowed modules'))
                    continue
                fns, path_re = allow
                if fn not in fns:
                    bad.append(('G1-FS', rel, line, f'fs call {fn} not allowed in {p.name}'))
                    continue
                arg = first_arg(args_of(body, m.start())).strip()
                if not re.match(path_re, arg):
                    bad.append(('G1-FS', rel, line, f'{fn}({arg}): path argument is not this module\'s own root'))
            for m in CHILD.finditer(body):
                line = body.count('\n', 0, m.start()) + 1
                if p.name != 'ingest_job.rs' or m.group(1).strip() != 'bin':
                    bad.append(('G1-CHILD', rel, line, f'process launch {m.group(0)}'))
        elif p.suffix in ('.js', '.html'):
            for pat in [r'plugin:', r'__TAURI__\.(fs|shell|dialog|process|opener|http)', r'file://', r'/dev/', r'PhysicalDrive',
                        r'\bfetch\s*\(', r'XMLHttpRequest', r'WebSocket']:
                for m in re.finditer(pat, code):
                    bad.append(('G1-PAGE', rel, code.count('\n', 0, m.start()) + 1, m.group(0)))
            for m in re.finditer(r'invoke\(\s*"([^"]+)"', code):
                if m.group(1) not in ('view', 'set_label', 'start_over', 'details'):
                    bad.append(('G1-PAGE', rel, code.count('\n', 0, m.start()) + 1, f'invoke {m.group(1)}'))
        elif p.suffix == '.json' and 'capabilities' in p.parts:
            caps = json.loads(text)
            for perm in caps.get('permissions', []):
                name = perm if isinstance(perm, str) else perm.get('identifier', '')
                if name not in ('core:event:allow-listen', 'core:event:allow-unlisten'):
                    bad.append(('G1-CAP', rel, 0, f'permission {name}'))
        elif p.name == 'Cargo.toml':
            for m in re.finditer(r'^\s*(tauri-plugin-[\w-]+|windows-sys|windows|nix|libc|rusb|udev|sysinfo)\s*=', text, re.M):
                bad.append(('G1-CAP', rel, text.count('\n', 0, m.start()) + 1, f'dependency {m.group(1)}'))
            for m in re.finditer(r'tauri\s*=\s*\{[^}]*features\s*=\s*\[([^\]]*)\]', text):
                if m.group(1).strip():
                    bad.append(('G1-CAP', rel, 0, f'tauri features {m.group(1).strip()}'))
        elif p.name == 'tauri.conf.json':
            conf = json.loads(text)
            if conf.get('plugins'):
                bad.append(('G1-CAP', rel, 0, f'plugins {list(conf["plugins"])}'))
            if conf.get('app', {}).get('security', {}).get('assetProtocol', {}).get('enable'):
                bad.append(('G1-CAP', rel, 0, 'asset protocol enabled'))
    return bad


def main(argv):
    root = argv[argv.index('--root') + 1] if '--root' in argv else 'host/app'
    bad = check(root)
    if '--require-rules' in argv:
        # Negative control: every listed rule must fire on the planted tree.
        want = argv[argv.index('--require-rules') + 1].split(',')
        fired = {b[0] for b in bad}
        missing = [r for r in want if r not in fired]
        for rule, f, line, what in bad:
            print(f'{rule}  {f}:{line}  {what}')
        print(f'G1 negative control on {root}: ' + (f'MISSING {missing}' if missing else f'all of {want} fired'))
        return 1 if missing else 0
    for rule, f, line, what in bad:
        print(f'{rule}  {f}:{line}  {what}')
    print(f'G1 static: {"FAIL" if bad else "PASS"} ({len(bad)} findings) on {root}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
