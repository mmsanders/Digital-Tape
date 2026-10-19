#!/usr/bin/env bash
# S2 `tapectl cards` (APP-1A §5) on a real device node: a Linux loop device, a
# macOS hdiutil disk image or a Windows VHD. Software's own observations for
# Verification #208; it judges nothing.
#
# None of these is a memory card, so the SHIPPED tapectl must never list it.
# Policy positives run through tapectl-test with TAPECTL_TEST_CARDS, which
# replaces only the named facts (whole / removable_or_sd / virtual / holds_os)
# of the real enumerated disk; the partition view, mounts and size stay the OS's.
# Every cards run is followed by a check that the device's bytes are unchanged.
#
# Usage: cards_e2e.sh TAPECTL TAPECTL_TEST SCRATCH_DIR HELPER BACKING [SUDO]
#   HELPER attach BACKING / HELPER detach DEVICE, as for device_e2e.sh. SUDO
#   (e.g. "sudo") prefixes the attach/provision/raw steps, so cards itself runs
#   as the invoking, unprivileged user.
set -uo pipefail
TAPECTL=$1; TAPECTL_T=$2; DIR=$3; HELPER=$4; BACKING=$5; SUDO=${6:-}
PY=$(command -v python3 || command -v python)
FAILS=0; FAILED=""
mkdir -p "$DIR"
fail() { echo "  FAIL  $*"; FAILS=$((FAILS + 1)); FAILED="$FAILED
  FAIL  $*"; }
ok()   { echo "  ok    $*"; }
case "$(uname -s)" in
  Darwin) OSB="macOS $(sw_vers -productVersion) build $(sw_vers -buildVersion), $(uname -m)" ;;
  MINGW*|MSYS*|CYGWIN*) OSB=$(powershell -NoProfile -Command "\$o=Get-CimInstance Win32_OperatingSystem; \$o.Caption + ' ' + \$o.Version + ' build ' + \$o.BuildNumber" | tr -d '\r') ;;
  *) . /etc/os-release; OSB="$PRETTY_NAME, kernel $(uname -r), $(uname -m)" ;;
esac
echo "== OS: $OSB; cards runs as $(id -un 2>/dev/null || whoami) =="
sha() { "$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1"; }
echo "tapectl $(sha "$TAPECTL")"; echo "tapectl-test $(sha "$TAPECTL_T")"

# First and last 1 MiB of the device: unchanged by every cards run.
edges() {
  $SUDO "$PY" - "$1" "$SZ" <<'EOF'
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
# run NAME BIN [env...]: cards on stdout/err/exit files; prints the exit.
run() {
  local name=$1 bin=$2; shift 2
  env "$@" "$bin" cards >"$DIR/$name.out" 2>"$DIR/$name.err"; echo $? >"$DIR/$name.rc"
}
listed() { grep -F "\"path\":$("$PY" -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$DEV")," "$DIR/$1.out" >/dev/null; }
summary() { "$PY" -c "import json,sys;l=[json.loads(x) for x in open(sys.argv[1])];s=l[-1];assert s['t']=='summary';print(s['$2'])" "$DIR/$1.out"; }
dump() { env "$@" "$TAPECTL_T" discover >"$DIR/discover.$N.json" 2>&1; grep -F "$("$PY" -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$DEV")" "$DIR/discover.$N.json" | sed 's/^/        /'; N=$((N+1)); }
N=0
seam() { printf '%s %s\n' "$DEV" "$*" >"$DIR/seam"; echo "TAPECTL_TEST_CARDS=$DIR/seam"; }

DEV=$($SUDO "$HELPER" attach "$BACKING") || { echo "FAIL  cannot attach $BACKING"; exit 1; }
echo "== attached $BACKING as $DEV =="
SZ=$($SUDO "$TAPECTL_T" probe "$DEV" | sed -n 's/^bytes=//p')
echo "        $SZ bytes"
E0=$(edges "$DEV")

echo "== 1. blank disk: the OS's facts, the shipped refusal, the test-route positive =="
dump
run ship0 "$TAPECTL"
[ "$(cat "$DIR/ship0.rc")" = 0 ] && ok "shipped cards exits 0" || fail "shipped cards exit $(cat "$DIR/ship0.rc"): $(head -c 300 "$DIR/ship0.err")"
listed ship0 && fail "shipped cards lists a virtual disk" || ok "shipped cards does not list $DEV (virtual)"
U0=$(summary ship0 unprobed); O0=$(summary ship0 offered)
echo "        shipped summary: offered=$O0 unprobed=$U0"
run pos "$TAPECTL_T" "$(seam whole=1 removable_or_sd=1 virtual=0)"
listed pos && ok "test route: blank disk with card facts is offered" || fail "test route: blank disk not offered: $(cat "$DIR/pos.out")"
grep -F "\"path\"" "$DIR/pos.out" | sed 's/^/        /'
run unk "$TAPECTL_T" "$(seam whole=1 removable_or_sd=-1 virtual=0)"
! listed unk && [ "$(summary unk unprobed)" = $((U0 + 1)) ] && ok "unknown removable fact: not listed, unprobed +1" \
  || fail "unknown removable fact: $(cat "$DIR/unk.out")"
run os "$TAPECTL_T" "$(seam whole=1 removable_or_sd=1 virtual=0 holds_os=1)"
! listed os && [ "$(summary os unprobed)" = "$U0" ] && ok "OS use: refused, not counted" || fail "OS use: $(cat "$DIR/os.out")"
run notrem "$TAPECTL_T" "$(seam whole=1 removable_or_sd=0 virtual=0)"
! listed notrem && [ "$(summary notrem unprobed)" = "$U0" ] && ok "not removable: refused, not counted" || fail "not removable: $(cat "$DIR/notrem.out")"
[ "$(edges "$DEV")" = "$E0" ] && ok "device bytes unchanged by cards" || fail "device bytes changed"

echo "== 2. exact layout, partition 1 as the OS mounts it =="
printf 'whole=1\nremovable=1\nsd_bus=0\nbytes=%s\nholds_os=0\nlayout_ok=0\n' "$SZ" >"$DIR/facts"
$SUDO env TAPECTL_TEST_FACTS="$DIR/facts" "$TAPECTL_T" provision "$DEV" --label CARDS --length-s 60 --erase "$DEV" >"$DIR/prov.out" 2>"$DIR/prov.err" \
  && ok "tapectl-test provision (exact layout)" || fail "provision: $(cat "$DIR/prov.err")"
$SUDO "$HELPER" detach "$DEV" >/dev/null 2>&1
DEV=$($SUDO "$HELPER" attach "$BACKING") || { echo "FAIL  cannot reattach"; exit 1; }
echo "        reattached as $DEV"
E1=$(edges "$DEV")
dump
run own "$TAPECTL_T" "$(seam whole=1 removable_or_sd=1 virtual=0)"
# view N: "MOUNTED P1TYPE P1HINT" for $DEV in discover dump N (-1 = unknown)
view() { "$PY" -c "import json,sys
for l in open(sys.argv[1]):
  d=json.loads(l)
  if d['path']==sys.argv[2]:
    p1=[p for p in d['parts'] if p['index']==1]
    print(d['n_mounted'], p1[0]['type'] if p1 else -1, repr(p1[0]['hint']) if p1 else 'none')" "$DIR/discover.$1.json" "$DEV"; }
read -r MNT T1 H1 <<<"$(view 1)"
echo "        OS view: $MNT mounted volume(s); partition 1 type $T1 (OS text $H1)"
if [ "$MNT" = 0 ] || [ "$T1" != -1 ]; then
  listed own && ok "test route: provisioned card offered (own-p1 view, $MNT mounted)" || fail "provisioned card not offered: $(cat "$DIR/own.out")"
else
  # APP-1A §5: an unknown OS-view type cannot earn the mounted-p1 exception.
  ! listed own && [ "$(summary own unprobed)" = $((U0 + 1)) ] \
    && ok "OS view names p1's type ($H1), not its byte: mounted card is unprobed, not offered" \
    || fail "unknown p1 type with a mount: $(cat "$DIR/own.out")"
  echo "  UNEXECUTED  own-p1 offered positive on this platform: the OS view gives no type byte for partition 1"
fi
run ship1 "$TAPECTL"
listed ship1 && fail "shipped cards lists the virtual disk" || ok "shipped cards still does not list it"
[ "$(edges "$DEV")" = "$E1" ] && ok "device bytes unchanged by cards" || fail "device bytes changed"

echo "== 3. foreign partition-1 type (0x0B), as the OS sees it after reattach =="
[ "$(uname -s)" = Darwin ] && $SUDO diskutil unmountDisk "$DEV" >/dev/null
$SUDO "$PY" - "$DEV" <<'EOF'
import os, sys
fd = os.open(sys.argv[1], os.O_RDWR | getattr(os, 'O_BINARY', 0))
b = bytearray(os.pread(fd, 512, 0)) if hasattr(os, 'pread') else None
if b is None:
    os.lseek(fd, 0, 0); b = bytearray(os.read(fd, 512))
b[446 + 4] = 0x0B
os.lseek(fd, 0, 0); os.write(fd, bytes(b)); os.fsync(fd); os.close(fd)
EOF
$SUDO "$HELPER" detach "$DEV" >/dev/null 2>&1
DEV=$($SUDO "$HELPER" attach "$BACKING") || { echo "FAIL  cannot reattach"; exit 1; }
E2=$(edges "$DEV")
dump
read -r MNT T1 H1 <<<"$(view 2)"
echo "        OS view: $MNT mounted volume(s); partition 1 type $T1 (OS text $H1)"
run foreign "$TAPECTL_T" "$(seam whole=1 removable_or_sd=1 virtual=0)"
if [ "$MNT" != 0 ] && [ "$MNT" != -1 ] && [ "$T1" = -1 ]; then
  ! listed foreign && [ "$(summary foreign unprobed)" = $((U0 + 1)) ] && ok "mounted, p1 type unknown: unprobed" || fail "foreign/unknown: $(cat "$DIR/foreign.out")"
elif [ "$MNT" = 0 ]; then
  listed foreign && ok "foreign type but nothing mounted: offered (bare-card rule; make refuses it)" || fail "unmounted foreign: $(cat "$DIR/foreign.out")"
elif [ "$MNT" = -1 ]; then
  ! listed foreign && ok "mount facts unknown: not listed" || fail "unknown mounts listed"
else
  ! listed foreign && [ "$(summary foreign unprobed)" = "$(summary ship1 unprobed)" ] \
    && ok "foreign type with a mounted volume: refused, not counted" || fail "foreign mounted: $(cat "$DIR/foreign.out")"
fi
[ "$(edges "$DEV")" = "$E2" ] && ok "device bytes unchanged by cards" || fail "device bytes changed"
$SUDO "$HELPER" detach "$DEV" >/dev/null 2>&1

echo "== 4. report (APP-1A §1) =="
NONCE=0123456789abcdef0123456789abcdef
"$TAPECTL" cards --report "$DIR/r.jsonl" --report-nonce $NONCE >"$DIR/r.out" 2>"$DIR/r.err"; rc=$?
"$PY" - "$DIR/r.jsonl" "$rc" <<'EOF' && ok "report: start, enumerate progress, end; exit $rc" || fail "report shape"
import json, sys
recs = [json.loads(l) for l in open(sys.argv[1], encoding='utf-8')]
assert recs[0]['t'] == 'start' and list(recs[0]) == ['t', 'tool', 'version', 'nonce'] and recs[0]['tool'] == 'tapectl cards'
assert recs[-1] == {'t': 'end', 'exit': int(sys.argv[2])}
prog = [r for r in recs[1:-1]]
assert all(r['t'] == 'progress' and r['step'] == 'enumerate' and list(r) == ['t', 'step', 'done', 'total'] for r in prog)
assert [r['done'] for r in prog] == list(range(1, len(prog) + 1)) and len({r['total'] for r in prog}) <= 1
print('        ' + json.dumps(recs[0]))
EOF
cp "$DIR/r.jsonl" "$DIR/r.before"
"$TAPECTL" cards --report "$DIR/r.jsonl" --report-nonce $NONCE >"$DIR/r2.out" 2>"$DIR/r2.err"; rc=$?
[ $rc = 1 ] && [ ! -s "$DIR/r2.out" ] && cmp -s "$DIR/r.jsonl" "$DIR/r.before" && ok "existing report leaf: exit 1, stderr only, leaf untouched" \
  || fail "existing leaf: exit $rc"
"$TAPECTL" cards --report "$DIR/r3.jsonl" --report-nonce ABC >"$DIR/r3.out" 2>"$DIR/r3.err"; rc=$?
[ $rc = 2 ] && [ ! -e "$DIR/r3.jsonl" ] && ok "invalid nonce: exit 2, no file" || fail "invalid nonce: exit $rc"
"$TAPECTL" cards --report "$DIR/r4.jsonl" --report-nonce $NONCE --bogus x >"$DIR/r4.out" 2>"$DIR/r4.err"; rc=$?
[ $rc = 2 ] && grep -q '"id":"USAGE"' "$DIR/r4.jsonl" && grep -q '{"t":"end","exit":2}' "$DIR/r4.jsonl" \
  && ok "other usage error after a valid report: exit 2, USAGE recorded" || fail "usage after report: exit $rc"
if ln -s "$DIR/nowhere" "$DIR/dangling" 2>/dev/null && [ -L "$DIR/dangling" ]; then
  "$TAPECTL" cards --report "$DIR/dangling" --report-nonce $NONCE >"$DIR/r5.out" 2>"$DIR/r5.err"; rc=$?
  [ $rc = 1 ] && [ ! -e "$DIR/nowhere" ] && ok "dangling symlink leaf: exit 1, not followed" || fail "dangling symlink: exit $rc"
else
  echo "  UNEXECUTED  dangling-symlink leaf (no symlink here)"
fi

echo
if [ "$FAILS" -eq 0 ]; then echo "PASS  cards on $DEV ($OSB)"; else echo "FAIL  $FAILS check(s):$FAILED"; fi
exit "$FAILS"
