#!/usr/bin/env bash
# Transport self-check for the TAPECTL_TEST observation and fault seam
# (host/port/tseam.h, ADR-164 §5). Software's own check that the adapter
# delivers: every trace is well-formed JSON in the documented shape, the counts
# agree with the events, and each fault control is visible where it claims to
# be. It asserts NOTHING about WP-14 acceptance; Verification's trace_audit
# owns those expectations.
#
# Usage: trace_selfcheck.sh TAPECTL_TEST SCRATCH_DIR [DEVICE]
#   With DEVICE (and TAPECTL_TEST_FACTS already exported by the caller), the
#   same captures run on that device instead of an image.
set -uo pipefail
T=$1; DIR=$2; DEV=${3:-}
PY=$(command -v python3 || command -v python)
rm -rf "$DIR"; mkdir -p "$DIR/traces"
FAILS=0; FAILED=""
fail() { echo "  FAIL  $*"; FAILS=$((FAILS + 1)); FAILED="$FAILED
  FAIL  $*"; }
ok() { echo "  ok    $*"; }

"$PY" - "$DIR/src.wav" <<'EOF'
import struct, sys
data = b''.join(struct.pack('<HH', ((i * 2654435761) >> 7) & 0xFFFF, (i * 37 - 30000) & 0xFFFF) for i in range(110250))
open(sys.argv[1], 'wb').write(b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' +
    struct.pack('<IHHIIHH', 16, 1, 2, 44100, 176400, 4, 16) + b'data' + struct.pack('<I', len(data)) + data)
EOF

if [ -n "$DEV" ]; then TGT=$DEV; PROV=(--erase "$DEV"); else TGT=$DIR/card.img; PROV=(--image-bytes 22020096); fi

# cap NAME FAULT CMD...: run CMD under the trace (and fault), keep its exit code.
cap() {
  local name=$1 fault=$2; shift 2
  TAPECTL_TEST_TRACE="$DIR/traces/$name.json" TAPECTL_TEST_FAULT="$fault" "$@" >"$DIR/$name.out" 2>"$DIR/$name.err"
  echo $? >"$DIR/$name.rc"
}
cap provision ""                   "$T" provision "$TGT" --label trace --length-s 9 --uuid a0a1a2a3a4a5a6a7a8a9aaabacadaeaf --epoch 1759622400 "${PROV[@]}"
cap load ""                        "$T" load "$TGT" "$DIR/src.wav"
cap verify ""                      "$T" verify "$TGT"
cap dump ""                        "$T" dump "$TGT" --side A -o "$DIR/a.wav"
cap noop_flush noop-flush          "$T" load "$TGT" "$DIR/src.wav"
cap hidden_flush hidden-flush-error "$T" load "$TGT" "$DIR/src.wav"
cap nonnull nonnull-binding        "$T" verify "$TGT"
cap read_error read-error:2058     "$T" verify "$TGT"

"$PY" - "$DIR" "${DEV:+device}" <<'EOF'
import json, sys, pathlib
d = pathlib.Path(sys.argv[1]); device = len(sys.argv) > 2 and sys.argv[2] == 'device'
bad = []
def say(ok, msg):
    print(('  ok    ' if ok else '  FAIL  ') + msg)
    if not ok: bad.append(msg)
want_call = {'linux': {'fsync'}, 'windows': {'FlushFileBuffers'},
             'macos': {'F_FULLFSYNC', 'DKIOCSYNCHRONIZECACHE'} if device else {'F_FULLFSYNC'}}
T = {}
for f in sorted((d / 'traces').glob('*.json')):
    try:
        t = json.loads(f.read_text())
    except Exception as e:
        say(False, f'{f.name}: not JSON ({e})'); continue
    T[f.stem] = t
    rc = int((d / (f.stem + '.rc')).read_text())
    keys = {'schema', 'platform', 'build', 'capture', 'fault', 'operation', 'argv', 'events',
            'target', 'target_is_device', 'target_bytes', 'refusal', 'writes', 'flushes', 'exit', 'success'}
    say(keys <= t.keys(), f'{f.stem}: trace has every documented field')
    say(t['exit'] == rc and t['success'] == (rc == 0), f'{f.stem}: exit {t["exit"]} matches the process exit {rc}')
    ev = t['events']
    say(t['writes'] == sum(e['kind'] == 'write' for e in ev) and t['flushes'] == sum(e['kind'] == 'flush' for e in ev),
        f'{f.stem}: write/flush counts agree with the events')
    say(all(e['offset'] + e['bytes'] <= t['target_bytes'] for e in ev if e['kind'] == 'write'),
        f'{f.stem}: every write extent is inside the target')
    say(t['build'] not in ('', 'unknown'), f'{f.stem}: build identity recorded ({t["build"][:12]})')
    if device:
        say(t.get('facts', {}).get('policy') == 'REFUSE_NONE', f'{f.stem}: facts and policy verdict recorded')
p = T['provision']['platform']
for name in ('provision', 'load'):
    fl = [e for e in T[name]['events'] if e['kind'] == 'flush']
    say(fl and all(e['os_call'] in want_call[p] and e['os_success'] and e['success'] for e in fl),
        f'{name}: {len(fl)} flushes, each a native barrier ({sorted({e["os_call"] for e in fl})}) that succeeded')
    say(any(e['kind'] == 'write_open' for e in T[name]['events']), f'{name}: write-mode open recorded')
for name in ('verify', 'dump') if device else ('verify',):
    ev = T[name]['events']
    say(not any(e['kind'] in ('write_open', 'write') for e in ev), f'{name}: no write-mode open, no write')
    b = [e for e in ev if e['kind'] == 'engine_bind']
    say(b and all(e['write_is_null'] for e in b), f'{name}: {len(b)} engine binding(s), all with a NULL write callback')
fl = [e for e in T['noop_flush']['events'] if e['kind'] == 'flush']
say(fl and all(e['os_call'] == 'none' and e['success'] for e in fl), 'control noop-flush: flush reported success with no OS barrier')
fl = [e for e in T['hidden_flush']['events'] if e['kind'] == 'flush']
say(fl and all(not e['os_success'] and e['os_error'] and e['success'] for e in fl), f'control hidden-flush-error: real OS failure ({fl[0]["os_error"] if fl else "?"}) reported as success')
b = [e for e in T['nonnull']['events'] if e['kind'] == 'engine_bind']
say(b and not all(e['write_is_null'] for e in b), 'control nonnull-binding: verify bound a write callback')
rf = [e for e in T['read_error']['events'] if e['kind'] == 'read' and not e['success']]
out = (d / 'read_error.out').read_text()
say(rf and all(e['phase'] == 'service' and e.get('referenced_chunk') and e.get('os_error') for e in rf)
    and [(e['side'], e['frame']) for e in rf] == [('A', 0), ('B', 0)] and T['read_error']['exit'] == 1,
    f'control read-error:2058: real failed OS reads {[(e["side"], e["frame"], e["os_error"]) for e in rf]}; verify printed {out.strip().splitlines()}')
v = T['verify']['events']
mounts = [(e['side'], e['cold'], e['result']) for e in v if e['kind'] == 'engine_mount']
say(mounts == [('A', True, 'TAPE_OK'), ('B', True, 'TAPE_OK')] and [e['side'] for e in v if e['kind'] == 'engine_info'] == ['A', 'B'],
    f'verify: cold engine_mount A then B, engine_info for each ({mounts})')
say(any(e['kind'] == 'read' and e['phase'] == 'service' and e.get('referenced_chunk') for e in v),
    'verify: service reads of referenced chunks observed')
pw = [e for e in T['provision']['events'] if e['kind'] == 'write']
say(pw and all('data_hex' in e and len(e['data_hex']) == 2 * e['bytes'] for e in pw), f'provision: all {len(pw)} writes carry their payload')
say(T['verify'].get('target_kind') in ('image', 'device') and T['verify'].get('engine_used') is True, 'verify: target_kind and engine_used recorded')
sys.exit(1 if bad else 0)
EOF
[ $? -eq 0 ] || fail "trace checks (above)"
[ -n "$FAILED" ] && printf "== failures ==%b\n" "$FAILED"
[ "$FAILS" -eq 0 ] && echo "PASS  observation seam transport on ${DEV:-an image}" || { echo "FAIL  observation seam transport: $FAILS"; exit 1; }
