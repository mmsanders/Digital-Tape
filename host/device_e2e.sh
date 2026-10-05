#!/usr/bin/env bash
# WP-14 on a real device node: a Linux loop device, a macOS disk image attached
# by hdiutil, or a Windows VHD attached by diskpart. CI runs it as root /
# Administrator; see .github/workflows/ci.yml (wp14-device-*).
#
# None of these is removable media, and a loop device is not in §2's Linux
# forms, so the SHIPPED tapectl must refuse each one with exit 3 and leave its
# bytes unchanged. That refusal is the first check. The round trip then runs
# through tapectl-test with injected facts (the TAPECTL_TEST seam, #384 Q2):
# the device node, raw I/O, the partition view and the durable flush are all
# real; only the "is this a memory card?" facts are supplied.
#
#   provision -> partition 1 visible to the OS -> load -> detach and reattach
#   (nothing from cache) -> verify -> dump A and B byte-identical to the source
#
# Usage: device_e2e.sh TAPECTL TAPECTL_TEST SCRATCH_DIR HELPER BACKING
#   HELPER attach BACKING   prints the device path (host/loop_linux.sh,
#                           host/hdiutil_macos.sh, host/vhd_windows.sh)
#   HELPER detach DEVICE
set -uo pipefail
TAPECTL=$1; TAPECTL_T=$2; DIR=$3; HELPER=$4; BACKING=$5
PY=$(command -v python3 || command -v python)
FAILS=0
mkdir -p "$DIR"
fail() { echo "  FAIL  $*"; FAILS=$((FAILS + 1)); }
ok()   { echo "  ok    $*"; }
expect() {
  local want=$1 desc=$2; shift 3
  "$@" >"$DIR/out" 2>"$DIR/err"; local got=$?
  if [ "$got" -eq "$want" ]; then ok "$desc"; else fail "$desc (exit $got, want $want): $(head -c 400 "$DIR/err")"; fi
}
# The first and last 1 MiB of the device, hashed: where provision would write.
edges() {
  "$PY" - "$1" "$2" <<'EOF'
import hashlib, os, sys
p, size = sys.argv[1], int(sys.argv[2])
fd = os.open(p, os.O_RDONLY | getattr(os, 'O_BINARY', 0))
h = hashlib.sha256()
for off in (0, max(0, size - (1 << 20))):
    os.lseek(fd, off, os.SEEK_SET)
    h.update(os.read(fd, 1 << 20))
os.close(fd)
print(h.hexdigest())
EOF
}

"$PY" - "$DIR" <<'EOF'
import struct, sys
data = bytearray()
for i in range(110250):
    data += struct.pack('<HH', ((i * 2654435761) >> 7) & 0xFFFF, (i * 37 - 30000) & 0xFFFF)
open(sys.argv[1] + '/src.wav', 'wb').write(b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' +
    struct.pack('<IHHIIHH', 16, 1, 2, 44100, 176400, 4, 16) + b'data' + struct.pack('<I', len(data)) + bytes(data))
EOF

DEV=$("$HELPER" attach "$BACKING") || { echo "FAIL  cannot attach $BACKING"; exit 1; }
echo "== attached $BACKING as $DEV =="
echo "== the real probe =="
"$TAPECTL_T" probe "$DEV" | tee "$DIR/probe0" | sed 's/^/        /'
grep -q '^refusal=REFUSE_NONE' "$DIR/probe0" && fail "the probe would let this non-card through" || ok "the probe's own verdict refuses it"
grep -q '^holds_os=0' "$DIR/probe0" && ok "probe: does not hold the OS" || fail "probe: holds_os"
SIZE=$(sed -n 's/^bytes=//p' "$DIR/probe0")
[ -n "$SIZE" ] && [ "$SIZE" -gt 4294967296 ] && ok "probe: $SIZE bytes, past 4 GiB (A6)" || fail "probe size '$SIZE'"

echo "== $DEV: the shipped binary refuses it =="
before=$(edges "$DEV" "$SIZE")
expect 3 "shipped provision refuses" -- "$TAPECTL" provision "$DEV" --label e2e --erase "$DEV"
echo "        $(head -1 "$DIR/err")"
expect 3 "shipped load refuses" -- "$TAPECTL" load "$DEV" "$DIR/src.wav"
[ "$(edges "$DEV" "$SIZE")" = "$before" ] && ok "device bytes unchanged by the refusals" || fail "a refusal wrote to the device"

printf '%s\n' whole=1 removable=1 sd_bus=0 "bytes=$SIZE" holds_os=0 layout_ok=0 >"$DIR/facts"
export TAPECTL_TEST_FACTS="$DIR/facts"

echo "== round trip through tapectl-test (injected facts, real device) =="
expect 3 "provision still needs --erase" -- "$TAPECTL_T" provision "$DEV" --label e2e
expect 0 "provision" -- "$TAPECTL_T" provision "$DEV" --label e2e --erase "$DEV"
grep -E '^uuid [0-9a-f]{32}$' "$DIR/out" >/dev/null && ok "generated uuid printed" || fail "uuid: $(cat "$DIR/out")"
grep 'flushes via' "$DIR/err" | sed 's/^/        /'
expect 0 "load" -- "$TAPECTL_T" load "$DEV" "$DIR/src.wav"
grep 'flushes via' "$DIR/err" | sed 's/^/        /'

echo "== detach and reattach: nothing comes from cache =="
"$HELPER" detach "$DEV" || fail "detach"
DEV=$("$HELPER" attach "$BACKING") || fail "reattach"
echo "        reattached as $DEV"
sleep 3
"$TAPECTL_T" probe "$DEV" | tee "$DIR/probe1" | sed 's/^/        /'
grep -q '^layout_ok=1' "$DIR/probe1" || grep -q '^mounted=' "$DIR/probe1" || echo "        (partition 1 not mounted by the OS; layout_ok is read only when it is)"
if grep -q '^mounted=1:' "$DIR/probe1"; then
  grep -q '^layout_ok=1' "$DIR/probe1" && ok "the OS mounted partition 1, and the probe sees our exact layout" || fail "partition 1 mounted but layout_ok=0"
  sed -e "s/^bytes=.*/bytes=$SIZE/" "$DIR/probe1" | grep -v '^refusal=\|^detail=' \
    | sed -e 's/^whole=.*/whole=1/' -e 's/^removable=.*/removable=1/' >"$DIR/facts"
  ok "facts now carry the real mount list (our partition 1)"
fi
expect 0 "verify after reattach" -- "$TAPECTL_T" verify "$DEV"
[ "$(cat "$DIR/out")" = OK ] && ok "verify: OK" || fail "verify: $(cat "$DIR/out")"
expect 0 "dump Side A" -- "$TAPECTL_T" dump "$DEV" --side A -o "$DIR/a.wav"
expect 0 "dump Side B" -- "$TAPECTL_T" dump "$DEV" --side B -o "$DIR/b.wav"
cmp -s "$DIR/src.wav" "$DIR/a.wav" && ok "Side A byte-identical to the source" || fail "Side A differs"
cmp -s "$DIR/src.wav" "$DIR/b.wav" && ok "Side B byte-identical to the source" || fail "Side B differs"
unset TAPECTL_TEST_FACTS
expect 3 "after all that, the shipped binary still refuses it" -- "$TAPECTL" verify "$DEV"
"$HELPER" detach "$DEV" || fail "final detach"

[ "$FAILS" -eq 0 ] && echo "PASS  WP-14 device round trip on $DEV" || { echo "FAIL  WP-14 device round trip: $FAILS"; exit 1; }
