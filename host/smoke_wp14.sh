#!/usr/bin/env bash
# WP-14 image smoke (docs/WP14-CLI-CONTRACT.md), runnable on Linux, macOS and
# Windows (Git Bash). Images only: devices are exercised by the loop-device and
# disk-image jobs in CI. Every refusal is paired with a case that passes it.
#
#   provision -> exact §3.1 MBR, FAT partition 1 with README.TXT, determinism
#   load / dump / verify on a provisioned image, A7 capacity refusal
#   verify findings on damaged copies, each with the clean original as control
#   disk safety through the TAPECTL_TEST facts seam, every §5 rule
#   the shipped binary refuses this machine's own disks and ignores the seam
#
# Usage: smoke_wp14.sh TAPECTL TAPECTL_TEST SCRATCH_DIR
set -uo pipefail
TAPECTL=$1
TAPECTL_T=$2
DIR=$3
rm -rf "$DIR"; mkdir -p "$DIR"
PY=$(command -v python3 || command -v python)
UNAME=$(uname -s)
FAILS=0

fail() { echo "  FAIL  $*"; FAILS=$((FAILS + 1)); }
ok()   { echo "  ok    $*"; }
# expect CODE DESC -- CMD...: run CMD, require exit CODE; stderr kept in $DIR/err.
expect() {
  local want=$1 desc=$2; shift 3
  "$@" >"$DIR/out" 2>"$DIR/err"; local got=$?
  if [ "$got" -eq "$want" ]; then ok "$desc"; else fail "$desc (exit $got, want $want): $(head -c 300 "$DIR/err")"; fi
}
has() { grep -q -- "$1" "$2" && ok "$3" || fail "$3: '$1' not in $(head -c 300 "$2")"; }
hash() { "$PY" -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }

UUID=a0a1a2a3a4a5a6a7a8a9aaabacadaeaf
EPOCH=1759622400                      # 2025-10-05T00:00:00Z
BYTES=22020096                        # 21 MiB: 16 MiB partition 1 + a 9 s cartridge
IMG=$DIR/card.img

"$PY" - "$DIR" <<'EOF'
import struct, sys
d = sys.argv[1]
def wav(path, n):
    data = bytearray()
    for i in range(n):
        data += struct.pack('<HH', ((i * 2654435761) >> 7) & 0xFFFF, (i * 37 - 30000) & 0xFFFF)
    open(path, 'wb').write(b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' +
        struct.pack('<IHHIIHH', 16, 1, 2, 44100, 176400, 4, 16) + b'data' + struct.pack('<I', len(data)) + bytes(data))
wav(d + '/src.wav', 110250)          # 2.5 s
wav(d + '/long.wav', 44100 * 12)     # 12 s: 3 s too long for a 9 s cartridge
EOF

echo "== provision =="
expect 0 "provision an image" -- "$TAPECTL" provision "$IMG" --label smoke --length-s 9 --uuid $UUID --epoch $EPOCH --image-bytes $BYTES
[ -s "$DIR/out" ] && fail "provision with --uuid/--epoch printed: $(cat "$DIR/out")" || ok "nothing printed when --uuid/--epoch are given"
expect 0 "provision again" -- "$TAPECTL" provision "$DIR/card2.img" --label smoke --length-s 9 --uuid $UUID --epoch $EPOCH --image-bytes $BYTES
[ "$(hash "$IMG")" = "$(hash "$DIR/card2.img")" ] && ok "byte-deterministic with --uuid/--epoch" || fail "two provisions differ"
"$PY" - "$IMG" $BYTES <<'EOF' && ok "LBA 0 is the exact §3.1 layout" || fail "LBA 0 layout"
import struct, sys
b = open(sys.argv[1], 'rb').read(512); n = int(sys.argv[2]) // 512
ent = lambda i: b[446 + 16 * i: 462 + 16 * i]
e1, e2 = ent(0), ent(1)
assert b[510:512] == b'\x55\xaa', 'sig'
assert b[440:444] == bytes.fromhex('a0a1a2a3'), 'disk signature'
assert e1 == bytes([0, 0xFE, 0xFF, 0xFF, 0x0E, 0xFE, 0xFF, 0xFF]) + struct.pack('<II', 2048, 32768), e1.hex()
assert e2 == bytes([0, 0xFE, 0xFF, 0xFF, 0xDA, 0xFE, 0xFF, 0xFF]) + struct.pack('<II', 34816, n - 34816), e2.hex()
assert ent(2) == bytes(16) and ent(3) == bytes(16)
assert b[:440] == bytes(440)
EOF
"$PY" -c 'import sys;d=open(sys.argv[1],"rb").read();open(sys.argv[2],"wb").write(d[2048*512:34816*512])' "$IMG" "$DIR/p1.img"
printf 'This is a Digital Tape cartridge.\r\nLabel: smoke\r\nPlease do not format or erase this card on a computer.\r\nUse the Digital Tape app to load music onto it.\r\n' >"$DIR/readme.want"
if command -v fsck.fat >/dev/null; then
  fsck.fat -n "$DIR/p1.img" >"$DIR/fsck" 2>&1 && ok "fsck.fat: partition 1 is a clean FAT volume" || fail "fsck.fat: $(cat "$DIR/fsck")"
  grep -q "16 bit entries" <(fsck.fat -v -n "$DIR/p1.img" 2>&1) && ok "fsck.fat reads it as FAT16 (16-bit entries)" || fail "fsck.fat type"
else
  echo "  skip  fsck.fat not installed"
fi
if command -v mtype >/dev/null; then
  MTOOLS_SKIP_CHECK=1 mtype -i "$DIR/p1.img" ::README.TXT >"$DIR/readme.got" 2>/dev/null
  cmp -s "$DIR/readme.want" "$DIR/readme.got" && ok "README.TXT bytes read back by mtools" || fail "README.TXT via mtools"
  MTOOLS_SKIP_CHECK=1 mlabel -s -i "$DIR/p1.img" :: 2>/dev/null | grep -q DIGITALTAPE && ok "volume label DIGITALTAPE" || fail "volume label"
else
  echo "  skip  mtools not installed"
fi
expect 0 "provision without --uuid/--epoch" -- "$TAPECTL" provision "$DIR/rand.img" --label r --length-s 9 --image-bytes $BYTES
grep -Eq '^uuid [0-9a-f]{32}$' "$DIR/out" && grep -Eq '^epoch [0-9]+$' "$DIR/out" && [ "$(wc -l <"$DIR/out" | tr -d ' ')" = 2 ] \
  && ok "generated uuid and epoch printed (#384 Q5)" || fail "generated uuid/epoch: $(cat "$DIR/out")"
expect 2 "--uuid without --epoch" -- "$TAPECTL" provision "$DIR/x.img" --label r --uuid $UUID --image-bytes $BYTES
expect 2 "label of 33 bytes is refused, not truncated" -- "$TAPECTL" provision "$DIR/x.img" --label 123456789012345678901234567890123 --image-bytes $BYTES
expect 0 "control: label of 32 bytes" -- "$TAPECTL" provision "$DIR/x.img" --label 12345678901234567890123456789012 --length-s 9 --image-bytes $BYTES
expect 2 "invalid UTF-8 label" -- "$TAPECTL" provision "$DIR/x.img" --label $'\xff\xfe' --image-bytes $BYTES
expect 0 "control: multi-byte UTF-8 label" -- "$TAPECTL" provision "$DIR/x.img" --label "Grieg – Åse" --length-s 9 --image-bytes $BYTES
expect 2 "image without --image-bytes" -- "$TAPECTL" provision "$DIR/x.img" --label r
expect 2 "--image-bytes not a multiple of 512" -- "$TAPECTL" provision "$DIR/x.img" --label r --image-bytes 22020097
rm -f "$DIR/small.img"
expect 1 "geometry too small for the length" -- "$TAPECTL" provision "$DIR/small.img" --label r --length-s 3600 --image-bytes $BYTES
has TAPE_ERR_GEOMETRY "$DIR/err" "names TAPE_ERR_GEOMETRY"
[ -e "$DIR/small.img" ] && fail "geometry refusal created the image" || ok "geometry refusal wrote nothing"

echo "== load, dump, verify on a provisioned image =="
expect 0 "load" -- "$TAPECTL" load "$IMG" "$DIR/src.wav"
expect 0 "dump Side A" -- "$TAPECTL" dump "$IMG" --side A -o "$DIR/a.wav"
expect 0 "dump Side B" -- "$TAPECTL" dump "$IMG" --side B -o "$DIR/b.wav"
cmp -s "$DIR/src.wav" "$DIR/a.wav" && ok "Side A is the source, byte for byte" || fail "Side A differs"
cmp -s "$DIR/src.wav" "$DIR/b.wav" && ok "Side B is the source, byte for byte" || fail "Side B differs"
"$PY" -c 'import sys;a=open(sys.argv[1],"rb").read(34816*512);b=open(sys.argv[2],"rb").read(34816*512);sys.exit(a!=b)' "$IMG" "$DIR/card2.img" \
  && ok "load wrote nothing below partition 2" || fail "load touched the MBR or partition 1"
expect 0 "verify a clean card" -- "$TAPECTL" verify "$IMG"
[ "$(cat "$DIR/out")" = OK ] && ok "verify prints OK" || fail "verify output: $(cat "$DIR/out")"
before=$(hash "$IMG")
expect 2 "A7: 12 s onto a 9 s cartridge" -- "$TAPECTL" load "$IMG" "$DIR/long.wav"
has "Too long by 3 s for a 9-second cartridge" "$DIR/err" "A7 message in plain words"
[ "$(hash "$IMG")" = "$before" ] && ok "A7 refusal wrote nothing" || fail "A7 refusal changed the card"
expect 2 "format refuses a provisioned image" -- "$TAPECTL" format "$IMG" --blocks 6145 --uuid $UUID --epoch 0 --label x --length-s 9

echo "== verify findings (each against the clean card above) =="
damage() { # damage NAME PYTHON-BODY: copy the card and edit bytes `d`
  cp "$IMG" "$DIR/$1.img"
  "$PY" - "$DIR/$1.img" <<EOF
import sys
f = sys.argv[1]; d = bytearray(open(f, 'rb').read())
$2
open(f, 'wb').write(d)
EOF
}
damage type 'd[450] = 0x0C'
expect 1 "wrong partition 1 type" -- "$TAPECTL" verify "$DIR/type.img"
has PARTITION_TYPE "$DIR/out" "PARTITION_TYPE"
damage layout 'd[454:458] = (4096).to_bytes(4, "little")'
expect 1 "partition 1 moved" -- "$TAPECTL" verify "$DIR/layout.img"
has MBR_LAYOUT "$DIR/out" "MBR_LAYOUT"
damage trunc 'd = d[:len(d) - 1024 * 512]'
expect 1 "truncated partition 2" -- "$TAPECTL" verify "$DIR/trunc.img"
has PARTITION_TRUNCATED "$DIR/out" "PARTITION_TRUNCATED"
damage sb 'd[34816 * 512 + 40] ^= 0xFF'
expect 1 "one superblock copy damaged" -- "$TAPECTL" verify "$DIR/sb.img"
has NEEDS_REPAIR "$DIR/out" "NEEDS_REPAIR"
before=$(hash "$DIR/sb.img"); "$TAPECTL" verify "$DIR/sb.img" >/dev/null 2>&1
[ "$(hash "$DIR/sb.img")" = "$before" ] && ok "verify repaired nothing (read-only binding)" || fail "verify wrote to the card"
expect 1 "other commands keep exact recognition: a near miss is a bare image, and fails to mount" -- "$TAPECTL" dump "$DIR/type.img" --side A -o "$DIR/t.wav"
expect 0 "control: verify on a bare WP-11 image" -- bash -c "'$TAPECTL' format '$DIR/bare.img' --blocks 6145 --uuid $UUID --epoch 0 --label b --length-s 9 && '$TAPECTL' load '$DIR/bare.img' '$DIR/src.wav' && '$TAPECTL' verify '$DIR/bare.img'"

echo "== disk safety through the TAPECTL_TEST facts seam (tapectl-test only) =="
case "$UNAME" in
  MINGW*|MSYS*|CYGWIN*) DEV='\\.\PhysicalDrive99'; SYSDEV='\\.\PhysicalDrive0'; PART='C:' ;;
  Darwin) DEV=/dev/disk99; SYSDEV=/dev/disk0; PART=/dev/disk0s1 ;;
  *) DEV=/dev/sdzz; SYSDEV=$(lsblk -no PKNAME "$(findmnt -no SOURCE / 2>/dev/null)" 2>/dev/null | head -1); SYSDEV=/dev/${SYSDEV:-sda}; PART=${SYSDEV}1 ;;
esac
facts() { printf '%s\n' whole=1 removable=1 sd_bus=0 bytes=64000000000 holds_os=0 layout_ok=0 "$@" >"$DIR/facts"; }
seam() { TAPECTL_TEST_FACTS="$DIR/facts" "$@"; }
for rule in "whole=0:REFUSE_NOT_WHOLE_DEVICE" "removable=0:REFUSE_NOT_REMOVABLE" "bytes=137438953473:REFUSE_TOO_LARGE" \
            "holds_os=1:REFUSE_SYSTEM_DISK" "mounted=2:/mnt/x:REFUSE_FOREIGN_MOUNT"; do
  id=${rule##*:}; fact=${rule%:*}
  facts "$fact"
  expect 3 "$id refuses verify" -- seam "$TAPECTL_T" verify "$DEV"
  has "$id" "$DIR/err" "$id named"
  expect 3 "$id refuses provision" -- seam "$TAPECTL_T" provision "$DEV" --label x --erase "$DEV"
done
facts removable=0 sd_bus=1
expect 2 "control: SD-class bus passes safety (then the absent disk cannot open)" -- seam "$TAPECTL_T" verify "$DEV"
facts bytes=137438953472
expect 2 "control: exactly 128 GiB passes safety" -- seam "$TAPECTL_T" verify "$DEV"
facts mounted=1:/Volumes/DIGITALTAPE layout_ok=1
expect 2 "control: our own partition 1 mounted passes safety" -- seam "$TAPECTL_T" verify "$DEV"
facts mounted=1:/Volumes/X layout_ok=0
expect 3 "partition 1 on a foreign layout is foreign" -- seam "$TAPECTL_T" verify "$DEV"
facts
expect 3 "provision without --erase" -- seam "$TAPECTL_T" provision "$DEV" --label x
has REFUSE_ERASE_NOT_CONFIRMED "$DIR/err" "REFUSE_ERASE_NOT_CONFIRMED named"
expect 3 "provision with a different --erase" -- seam "$TAPECTL_T" provision "$DEV" --label x --erase "${DEV}0"
expect 2 "control: a matching --erase passes safety" -- seam "$TAPECTL_T" provision "$DEV" --label x --erase "$DEV"
expect 2 "--image-bytes is refused for a device" -- seam "$TAPECTL_T" provision "$DEV" --label x --erase "$DEV" --image-bytes 512
printf 'whole=1\n' >"$DIR/facts"
expect 3 "a truncated facts file refuses" -- seam "$TAPECTL_T" verify "$DEV"

echo "== the shipped binary: this machine's own disks, and no seam =="
facts
expect 3 "shipped tapectl ignores TAPECTL_TEST_FACTS" -- seam "$TAPECTL" verify "$DEV"
expect 3 "system disk $SYSDEV refused (verify)" -- "$TAPECTL" verify "$SYSDEV"
expect 3 "system disk $SYSDEV refused (provision)" -- "$TAPECTL" provision "$SYSDEV" --label x --erase "$SYSDEV"
expect 3 "a partition path $PART refused" -- "$TAPECTL" verify "$PART"
has REFUSE_NOT_WHOLE_DEVICE "$DIR/err" "REFUSE_NOT_WHOLE_DEVICE for a partition"
expect 2 "format refuses a device path" -- "$TAPECTL" format "$SYSDEV" --blocks 6145 --uuid $UUID --epoch 0 --label x --length-s 9

[ "$FAILS" -eq 0 ] && echo "PASS  tapectl WP-14 smoke" || { echo "FAIL  tapectl WP-14 smoke: $FAILS"; exit 1; }
