#!/usr/bin/env python3
"""APP-1 annex proposal (#444): map every INGEST-1 refusal and I/O failure site
to one proposed closed reason ID, by source site. Exits 1 if any site is left
unmapped or a rule maps nothing, so a new site cannot slip past the list.

  reason_map.py SRC_DIR [--markdown]

SRC_DIR is host/ingest/src at the bound candidate head. Text in the table is the
current stderr wording, which is diagnostic only: the app keys on the ID."""
import os, re, sys

# Proposed ID, report subject kind, §6 row, and the site patterns (regex over the
# message text) it covers. First match wins; order matters only where noted.
RULES = [
    # --- usage and request shape (exit 2, no subject) ------------------------
    ('INGEST_LENGTH_INVALID', 'none', 'other', [r'--length is too large', r'total length overflows']),
    # --- folder level (subject: folder "i/") ---------------------------------
    ('FOLDER_SYMLINK', 'folder', 'not-music', [r'the folder is a symbolic link']),
    ('FOLDER_UNREADABLE', 'folder', 'other', [r'folder does not exist or cannot be read']),
    ('FOLDER_NOT_FOLDER', 'folder', 'other', [r'^\{\}: not a folder']),
    ('FOLDER_DUPLICATE', 'folder', 'other', [r'is the same folder as folder']),
    ('FOLDER_EMPTY', 'folder', 'not-music', [r'the folder is empty']),
    ('FOLDER_NAME_COLLISION', 'folder', 'source-named', [r'collide after Unicode normalization']),
    ('FOLDER_NAME_NOT_UNICODE', 'folder', 'source-named', [r'a file name is not valid Unicode']),
    # --- entry level, from listing (subject: source "i/name") ----------------
    ('ENTRY_SYMLINK', 'source', 'not-music', [r'symbolic links are not followed; refusing']),
    ('ENTRY_NESTED_FOLDER', 'source', 'not-music', [r'nested folders are not allowed']),
    ('ENTRY_NOT_REGULAR', 'source', 'not-music', [r'not a regular file']),
    ('ENTRY_NAME_INVALID', 'source', 'source-named', [r'the name \{why\}']),
    ('INTERNAL', 'none', 'other', [r'^internal:', r'internal: ', r'did not converge', r'decoder init failed']),
    # --- per-source content (subject: source) --------------------------------
    ('SOURCE_CORRUPT', 'source', 'unusable', [r'\(corrupt\)', r'header is truncated', r'residual is out of range', r'frame count overflows']),
    ('SOURCE_LEVEL', 'source', 'unusable', [r'no valid true-peak measurement', r'16-bit quantization would overflow']),
    ('SOURCE_PROTECTED', 'source', 'protected', [r'protected \(encrypted\)']),
    ('SOURCE_NOT_AUDIO', 'source', 'not-music', [r'not a supported audio format \(unrecognised bytes\)',
                                                 r'^the file is empty$']),
    ('SOURCE_TOO_SHORT', 'source', 'source-named', [r'too short to produce one 44\.1 kHz frame',
                                                    r'decodes to zero frames', r'holds zero samples',
                                                    r'declares zero sample frames', r'holds no (audio )?frames',
                                                    r'holds no audio frames after']),
    ('SOURCE_CHANGED', 'source', 'source-named', [r'the file changed while ingest was running']),
    ('SOURCE_NON_FINITE', 'source', 'unusable', [r'non-finite']),
    ('SOURCE_TRIM_UNSUPPORTED', 'source', 'unusable', [
        r'iTunSMPB', r'LAME', r'VBRI', r'[Xx]ing', r'edit list', r'\bedit\b', r'trim', r'shortened final sample',
        r'presentation interval', r'^\{what\} is out of range$', r'gapless', r'whole 1024-frame', r'fractional trim']),
    ('SOURCE_OUTSIDE_INGEST1', 'source', 'unusable', [
        r'outside INGEST-1', r'is not supported', r'unsupported', r'not native FLAC', r'only mono or stereo',
        r'not mono or stereo', r'ambiguous channel mask', r'not supported', r'accepts audio-only', r'more than one audio stream', r'no audio stream',
        r'^compressed or unknown WAV format tag', r'valid bits in a', r'zero channels',
        r'not a WAVE format code', r'sample rate is not an integer', r'sample rate is out of range',
        r'sample rate is zero', r'STREAMINFO sample rate is zero', r'changes mid-stream',
        r'is out of range$', r'more than one sample description', r'960-sample']),
    ('SOURCE_CORRUPT', 'source', 'unusable', [
        r'corrupt', r'truncated', r'mismatch', r'invalid', r'reserved', r'runs past', r'too short',
        r'^no ', r'more than one', r'disagree', r'precedes', r'not zero', r'not the first', r'wrong length',
        r'exceeds', r'overflow', r'not cover', r'names more samples', r'does not begin with', r'lacks',
        r'negative LPC', r'decoded to an unexpected', r'is set$', r'discontinuous', r'not found',
        r'not text', r'has no data', r'decoder refused', r'is missing its', r'is empty$', r'ends inside', r'out of range', r'no \'stsz\'', r'no chunk-offset',
        r'has no \'', r'is ambiguous', r'size 0', r'is not stereo']),
    # --- whole request (subject: none, or a boundary) ------------------------
    ('INGEST_TOO_LONG', 'none', 'overage', [r'the sources and folder gaps total']),
    ('INGEST_RIFF_LIMIT', 'none', 'other', [r'canonical RIFF size limit']),
    ('JOIN_PEAK', 'boundary', 'other', [r'the join between']),
    ('JOINED_PEAK', 'none', 'other', [r'the joined output reaches']),
    # --- destination (exit 2 refusals, no subject) ---------------------------
    ('DEST_EXISTS', 'none', 'other', [r'already exists; ingest never overwrites']),
    ('DEST_APPEARED', 'none', 'other', [r'appeared while ingest ran']),
    ('DEST_NAME_INVALID', 'none', 'other', [r'not a usable destination name']),
    # --- I/O (exit 1) --------------------------------------------------------
    ('IO_SOURCE', 'source', 'unusable', [r'cannot open: \{e\}', r'cannot read: \{e\}']),
    ('IO_FOLDER', 'folder', 'other', [r'cannot read folder', r'^\{disp\}/\{raw\}: \{e\}$', r'^\{\}: \{e\}$']),
    ('IO_DEST', 'none', 'other', [r'^\{what\} \{\}: \{e\}$', r'cannot create', r'cannot write', r'cannot flush', r'cannot open',
                                  r'parent folder does not exist', r'cannot publish', r'fresh stage folder']),
    ('IO_MEMORY', 'none', 'other', [r'out of memory']),
]

SITE = re.compile(r'(Fail::(Refuse|Io)\(|\brefuse\()\s*(?:format!\()?\s*"((?:[^"\\]|\\.)*)"', re.S)
WRAP = re.compile(r'^\{(logical|disp|m|\}\:?)?\}: \{m\}$|^\{\}: \{m\}$|^\{logical\}: \{m\}$')


def sites(src):
    for fn in sorted(os.listdir(src)):
        if not fn.endswith('.rs'):
            continue
        text = open(os.path.join(src, fn), encoding='utf-8').read()
        for m in SITE.finditer(text):
            kind = 'Io' if m.group(2) == 'Io' else 'Refuse'
            msg = m.group(3)
            # Pass-through wrappers prefix a subject onto an inner failure; not a site.
            if re.fullmatch(r'\{[a-z_.]*\}: \{m\}', msg):
                continue
            yield fn, text.count('\n', 0, m.start()) + 1, kind, msg


def classify(msg):
    body = re.sub(r'^\{(logical|disp|[a-z_.]*)\}(/\{raw\})?: ', '', msg)
    body = re.sub(r'^\{\}: ', '', body) if not body.startswith('{}: not a folder') else body
    for rid, subj, row, pats in RULES:
        for p in pats:
            if re.search(p, msg) or re.search(p, body):
                return rid, subj, row
    return None


def main(argv):
    src = argv[0]
    rows, unmapped, used = [], [], set()
    for fn, line, kind, msg in sites(src):
        c = classify(msg)
        if c is None:
            unmapped.append((fn, line, msg))
            continue
        used.add(c[0])
        exit_code = 1 if kind == 'Io' else 2
        if c[0].startswith(('IO_', 'INTERNAL')) and kind != 'Io':
            unmapped.append((fn, line, f'{msg}  [I/O ID on a Refuse site]'))
        if not c[0].startswith(('IO_', 'INTERNAL')) and kind == 'Io':
            unmapped.append((fn, line, f'{msg}  [refusal ID on an Io site]'))
        rows.append((c[0], exit_code, c[1], c[2], fn, line, msg))
    unused = [r[0] for r in RULES if r[0] not in used]
    if '--markdown' in argv:
        print('| ID | Exit | Subject | §6 row | Site | Current stderr text (diagnostic only) |')
        print('|---|---|---|---|---|---|')
        for rid, ec, subj, row, fn, line, msg in sorted(rows, key=lambda r: ([x[0] for x in RULES].index(r[0]), r[4], r[5])):
            print(f'| `{rid}` | {ec} | {subj} | {row} | `{fn}:{line}` | {msg.replace("|", "\\|")} |')
    else:
        from collections import Counter
        for rid, n in Counter(r[0] for r in rows).most_common():
            print(f'{n:4} {rid}')
        print(f'{len(rows)} sites, {len(used)} IDs')
    for u in unmapped:
        print('UNMAPPED', *u, file=sys.stderr)
    for u in unused:
        print('UNUSED RULE', u, file=sys.stderr)
    return 1 if unmapped or unused else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
