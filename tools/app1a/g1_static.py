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

Scope: the shipped app (src/, ui/, capabilities/, Cargo.toml, tauri.conf.json) and its
examples. Not app code: the integration tests under tests/, and in Rust exactly the one
item each `#[cfg(test)]` attribute applies to (a test module, function or `use`). Code
after that item is shipping code and is checked: the attribute scopes one item, not
the rest of the file. Comments are stripped by a lexer that respects string, raw string
and char literals, so `//` inside a string hides nothing.

A string literal path argument is judged by G1-DEV (every device name anywhere is a
finding), so an ordinary private file opened by literal path stays clean in any module;
any other path argument must be in an allowed module and be that module's own root
(the data-flow rule).

Usage: g1_static.py [--root DIR]   exit 0 clean, 1 with findings printed. The root
defaults to $APP_SOURCE_ROOT, else host/app. `--selftest` plants device opens in the
shapes a first-marker split or line-based comment stripping would hide (and clean
controls) and requires each verdict.
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
TEST_ATTR = '#[cfg(test)]'
LITERAL = re.compile(r'^\s*&?\s*(r#*)?"[^"]*"#*\s*$')


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


def lex(s):
    """Rust source with comments blanked (newlines kept), and a parallel mask that is
    True inside string/char literals. Nested block comments are handled."""
    out, mask, i, n = list(s), [False] * len(s), 0, len(s)

    def blank(a, b):
        for k in range(a, b):
            if out[k] != '\n':
                out[k] = ' '

    while i < n:
        c = s[i]
        if s.startswith('//', i):
            j = s.find('\n', i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif s.startswith('/*', i):
            depth, j = 1, i + 2
            while j < n and depth:
                if s.startswith('/*', j):
                    depth, j = depth + 1, j + 2
                elif s.startswith('*/', j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            blank(i, j)
            i = j
        elif (m := re.compile(r'b?r(#*)"').match(s, i)) and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] == '_')):
            close = '"' + m.group(1)
            j = s.find(close, m.end())
            j = n if j < 0 else j + len(close)
            mask[i:j] = [True] * (j - i)
            i = j
        elif c == '"' or (c == 'b' and s.startswith('b"', i) and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] == '_'))):
            j = i + (2 if c == 'b' else 1)
            while j < n and s[j] != '"':
                j += 2 if s[j] == '\\' else 1
            j = min(j + 1, n)
            mask[i:j] = [True] * (j - i)
            i = j
        elif c == "'" and (m := re.compile(r"'(\\(x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]{1,6}\}|.)|[^\\'\n])'").match(s, i)):
            mask[i:m.end()] = [True] * (m.end() - i)
            i = m.end()
        else:
            i += 1
    return ''.join(out), mask


def item_end(code, mask, i):
    """End of the Rust item starting at or after `i`: skips further attributes, then
    runs to the item's `;` or its matching `}` (literals ignored)."""
    n = len(code)
    while True:
        while i < n and code[i].isspace():
            i += 1
        if code.startswith('#[', i):
            depth, i = 0, i + 1
            while i < n:
                if not mask[i]:
                    depth += code[i] == '['
                    depth -= code[i] == ']'
                    if depth == 0:
                        i += 1
                        break
                i += 1
            continue
        break
    depth = 0
    while i < n:
        if not mask[i]:
            c = code[i]
            if c in '([':
                depth += 1
            elif c in ')]':
                depth -= 1
            elif c == ';' and depth == 0:
                return i + 1
            elif c == '{' and depth == 0:
                d, j = 0, i
                while j < n:
                    if not mask[j]:
                        d += code[j] == '{'
                        d -= code[j] == '}'
                        if d == 0:
                            return j + 1
                    j += 1
                return n
        i += 1
    return n


def shipping(text):
    """Rust source as checked: comments blanked and every `#[cfg(test)]` item blanked,
    newlines kept so line numbers stay true."""
    code, mask = lex(text)
    out = list(code)
    i = 0
    while (k := code.find(TEST_ATTR, i)) >= 0:
        if mask[k]:
            i = k + 1
            continue
        e = item_end(code, mask, k + len(TEST_ATTR))
        for j in range(k, e):
            if out[j] != '\n':
                out[j] = ' '
        i = e
    return ''.join(out)


def strip_comments(s):
    """Page code (JS): comments removed. Rust goes through `shipping`."""
    return lex(s)[0]


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
        code = shipping(text) if p.suffix == '.rs' else strip_comments(text) if p.suffix == '.js' else text
        if p.suffix == '.rs':
            body = code
            for pat in DEVICE:
                for m in re.finditer(pat, body):
                    bad.append(('G1-DEV', rel, body.count('\n', 0, m.start()) + 1, m.group(0)))
            allow = FS_ALLOW.get(p.name)
            for m in FS_CALL.finditer(body):
                fn = m.group(1) or m.group(2) or 'open'
                line = body.count('\n', 0, m.start()) + 1
                if m.group(0).startswith('OpenOptions'):
                    continue  # judged at its `.open(` call
                arg = first_arg(args_of(body, m.start())).strip()
                if LITERAL.match(arg):
                    continue  # a literal path: any device name in it is a G1-DEV finding
                if allow is None:
                    bad.append(('G1-FS', rel, line, f'fs call {fn} outside the allowed modules'))
                    continue
                fns, path_re = allow
                if fn not in fns:
                    bad.append(('G1-FS', rel, line, f'fs call {fn} not allowed in {p.name}'))
                    continue
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


SELFTEST = [
    # (Rust source of src/x.rs, whether a finding must fire). Each "fire" case is a device
    # open that the old first-marker split or line-based comment stripping would hide.
    ('#[cfg(test)]\nmod tests {\n    fn t() {}\n}\nfn f() { let _ = std::fs::File::open("/dev/rdisk9"); }\n', True),
    ('#[cfg(test)]\nfn t() { let s = "}"; }\nfn f() { let _ = std::fs::File::open("/dev/rdisk9"); }\n', True),
    ('#[cfg(test)]\nuse std::fs;\nfn f() { let _ = std::fs::File::open("/dev/rdisk9"); }\n', True),
    ('#[cfg(test)]\n#[allow(dead_code)]\nmod t { fn c() { let _ = \'{\'; } }\nfn f() { let _ = std::fs::File::open("/dev/rdisk9"); }\n', True),
    ('fn f() { let u = "http://x"; let _ = std::fs::File::open("/dev/rdisk9"); }\n', True),
    ('const S: &str = "#[cfg(test)]";\nfn f() { let _ = std::fs::File::open("/dev/rdisk9"); }\n', True),
    ('#[cfg(test)]\nmod t { const R: &str = r#"}"#; }\nfn f() { let _ = std::fs::File::open("/dev/rdisk9"); }\n', True),
    ('#[cfg(not(test))]\nfn f() { let _ = std::fs::File::open("/dev/rdisk9"); }\n', True),
    ('fn f(p: &std::path::Path) { let _ = std::fs::File::open(p); }\n', True),  # data flow outside allowed modules
    # Not shipping code, or not code: must stay clean.
    ('#[cfg(test)]\nmod t {\n    fn f() { let _ = std::fs::File::open("/dev/rdisk9"); }\n}\n', False),
    ('/* outer /* inner */ std::fs::File::open("/dev/rdisk9") */\nfn f() {}\n', False),
    ('fn f() { let _ = std::fs::File::open("owned-report.jsonl"); }\n', False),
]


def selftest():
    import tempfile
    bad = 0
    for i, (src, fire) in enumerate(SELFTEST):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / 'src').mkdir()
            (Path(t) / 'src' / 'x.rs').write_text(src)
            got = bool(check(t))
        ok = got == fire
        bad += not ok
        print(f'{"ok  " if ok else "FAIL"} selftest {i}: expected {"a finding" if fire else "clean"}, got {"a finding" if got else "clean"}')
    print(f'G1 selftest: {"FAIL" if bad else "PASS"} ({len(SELFTEST)} cases)')
    return 1 if bad else 0


def main(argv):
    import os
    if '--selftest' in argv:
        return selftest()
    root = argv[argv.index('--root') + 1] if '--root' in argv else os.environ.get('APP_SOURCE_ROOT', 'host/app')
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
