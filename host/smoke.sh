#!/usr/bin/env bash
# tapectl smoke: format -> load -> dump round trip (#366 Stage 1).
#
# A deterministic stereo source is loaded onto a fresh 9 s / 4-chunk cartridge;
# dumping Side A and Side B at 1.0x must give back the source byte for byte
# (load mirrors Side A onto Side B, and at rate 1.0 the §8 fraction is zero).
# Also checks determinism (a second identical run gives identical images), the
# exit-status contract, and that a 48 kHz source is refused with exit 2.
#
# Usage: smoke.sh TAPECTL SCRATCH_DIR
set -euo pipefail
TAPECTL=$1
DIR=$2
rm -rf "$DIR"; mkdir -p "$DIR"

fail() { echo "  FAIL  $*"; exit 1; }
ok()   { echo "  ok    $*"; }

# 2.5 s of a deterministic two-channel pattern, canonical 44-byte header.
python3 - "$DIR/src.wav" "$DIR/src48k.wav" <<'EOF'
import struct, sys
n = 110250
data = bytearray()
for i in range(n):
    l = ((i * 2654435761) >> 7) & 0xFFFF
    r = (i * 37 - 30000) & 0xFFFF
    data += struct.pack('<HH', l, r)
def wav(rate):
    return (b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' +
            struct.pack('<IHHIIHH', 16, 1, 2, rate, rate * 4, 4, 16) + b'data' +
            struct.pack('<I', len(data)) + bytes(data))
open(sys.argv[1], 'wb').write(wav(44100))
open(sys.argv[2], 'wb').write(wav(48000))
EOF

run_once() {
  local img=$1
  "$TAPECTL" format "$img" --blocks 6145 --uuid a0a1a2a3a4a5a6a7a8a9aaabacadaeaf \
      --epoch 0 --label smoke --length-s 9
  "$TAPECTL" load "$img" "$DIR/src.wav"
}

echo "== tapectl smoke: format -> load -> dump =="
run_once "$DIR/a.img" || fail "format/load exited non-zero"
ok "format and load"
"$TAPECTL" dump "$DIR/a.img" --side A -o "$DIR/a.wav" || fail "dump A"
"$TAPECTL" dump "$DIR/a.img" --side B -o "$DIR/b.wav" || fail "dump B"
cmp -s "$DIR/src.wav" "$DIR/a.wav" || fail "Side A dump differs from the source"
ok "Side A dump is byte-identical to the source"
cmp -s "$DIR/src.wav" "$DIR/b.wav" || fail "Side B dump differs from the source"
ok "Side B dump is byte-identical to the source (load mirrors A onto B)"

run_once "$DIR/a2.img" || fail "second format/load"
cmp -s "$DIR/a.img" "$DIR/a2.img" || fail "two identical runs gave different images"
ok "deterministic: identical arguments give a byte-identical image"

"$TAPECTL" play "$DIR/a.img" --side A --from 100 --frames 1000 --rate 1.0 -o "$DIR/p.wav" || fail "play"
python3 - "$DIR/src.wav" "$DIR/p.wav" <<'EOF' || fail "play --from 100 --frames 1000 is not source frames 100..1099"
import sys
s = open(sys.argv[1], 'rb').read()[44:]
p = open(sys.argv[2], 'rb').read()[44:]
sys.exit(0 if p == s[100 * 4:1100 * 4] else 1)
EOF
ok "play from 100 for 1000 frames at 1.0 is exactly source frames 100..1099"

set +e
"$TAPECTL" load "$DIR/a.img" "$DIR/src48k.wav" 2>/dev/null; rc=$?
"$TAPECTL" frobnicate "$DIR/a.img" 2>/dev/null; rc2=$?
"$TAPECTL" dump "$DIR/missing.img" --side A -o "$DIR/x.wav" 2>/dev/null; rc3=$?
"$TAPECTL" play "$DIR/a.img" --side A --from 0 --frames 1 --rate 1.0x -o "$DIR/x.wav" 2>/dev/null; rc4=$?
"$TAPECTL" format "$DIR/g.img" --blocks 10 --uuid a0a1a2a3a4a5a6a7a8a9aaabacadaeaf \
    --epoch 0 --label g --length-s 9 2>"$DIR/g.err"; rc5=$?
set -e
[ $rc -eq 2 ] || fail "48 kHz load exited $rc, want 2"
ok "48 kHz source refused with exit 2"
[ $rc2 -eq 2 ] && [ $rc3 -eq 2 ] && [ $rc4 -eq 2 ] || fail "usage errors exited $rc2/$rc3/$rc4, want 2"
ok "usage errors exit 2"
[ $rc5 -eq 1 ] && grep -q TAPE_ERR_GEOMETRY "$DIR/g.err" || fail "impossible geometry exited $rc5, want 1 with TAPE_ERR_GEOMETRY"
ok "engine refusal exits 1 and names TAPE_ERR_GEOMETRY"
echo "PASS  tapectl smoke"
