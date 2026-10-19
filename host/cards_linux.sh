#!/usr/bin/env bash
# S2 `tapectl cards`, Linux-only observations (run as root on a CI runner).
# Software's own; judges nothing.
#   1. syscall trace: the shipped cards opens no /dev node and issues no ioctl;
#      the same check goes red on a one-sector read of the device.
#   2. CARDS_ENUM_UNAVAILABLE from a real failure: /sys hidden by a tmpfs in a
#      private mount namespace, so /sys/block cannot be listed.
#   3. size boundary: a disk of exactly 128 GiB is offered (test route), one
#      sector past it is refused and not counted.
# Usage: cards_linux.sh TAPECTL TAPECTL_TEST SCRATCH_DIR
set -uo pipefail
TAPECTL=$1; TAPECTL_T=$2; DIR=$3
FAILS=0; FAILED=""
mkdir -p "$DIR"
fail() { echo "  FAIL  $*"; FAILS=$((FAILS + 1)); FAILED="$FAILED
  FAIL  $*"; }
ok()   { echo "  ok    $*"; }
NONCE=0123456789abcdef0123456789abcdef

echo "== 1. syscall trace (strace $(strace -V | head -1 | awk '{print $NF}')) =="
dev=$(losetup -f --show "$(truncate -s 64M "$DIR/t.img" && echo "$DIR/t.img")")
devtrace() {   # devtrace TRACE: lines that open a /dev node or issue an ioctl
  # (libc's isatty() on stdio, TCGETS on fd 0-2, is not a device query)
  grep -E 'open(at)?\(.*"/dev/|ioctl\(' "$1" | grep -vE '"/dev/(null|tty|urandom|random)"|ioctl\([012], TCGETS' || true
}
strace -f -qq -e trace=open,openat,ioctl -o "$DIR/cards.trace" "$TAPECTL" cards >"$DIR/cards.out"
n=$(wc -l <"$DIR/cards.trace")
hits=$(devtrace "$DIR/cards.trace")
[ -z "$hits" ] && ok "shipped cards: $n traced open/openat/ioctl calls, none on a /dev node, no ioctl" \
  || fail "shipped cards touched a device: $hits"
strace -f -qq -e trace=open,openat,ioctl -o "$DIR/cards-test.trace" "$TAPECTL_T" cards >/dev/null
[ -z "$(devtrace "$DIR/cards-test.trace")" ] && ok "tapectl-test cards: none either" || fail "tapectl-test cards touched a device"
strace -f -qq -e trace=open,openat,ioctl -o "$DIR/read.trace" head -c 512 "$dev" >/dev/null
[ -n "$(devtrace "$DIR/read.trace")" ] && ok "negative control: the same check sees a one-sector read of $dev" \
  || fail "negative control: the check missed a device open"
devtrace "$DIR/read.trace" | head -3 | sed 's/^/        /'
losetup -d "$dev"

echo "== 2. CARDS_ENUM_UNAVAILABLE: /sys hidden in a private mount namespace =="
unshare -m sh -c "mount -t tmpfs none /sys && exec '$TAPECTL' cards --report '$DIR/enum.jsonl' --report-nonce $NONCE" \
  >"$DIR/enum.out" 2>"$DIR/enum.err"; rc=$?
cat "$DIR/enum.err" | sed 's/^/        /'
[ $rc = 1 ] && [ ! -s "$DIR/enum.out" ] && grep -q '"id":"CARDS_ENUM_UNAVAILABLE","subject":null,"os_error":' "$DIR/enum.jsonl" \
  && tail -1 "$DIR/enum.jsonl" | grep -qx '{"t":"end","exit":1}' \
  && ok "exit 1, no stdout, refusal CARDS_ENUM_UNAVAILABLE with os_error, end exit 1" || fail "enum unavailable: exit $rc, $(cat "$DIR/enum.jsonl")"
sed 's/^/        /' "$DIR/enum.jsonl"

echo "== 3. size boundary: 128 GiB =="
for case in "137438953472 offered" "137438954496 refused"; do
  set -- $case
  truncate -s 0 "$DIR/big.img"; truncate -s "$1" "$DIR/big.img"
  dev=$(losetup -f --show "$DIR/big.img")
  printf '%s whole=1 removable_or_sd=1 virtual=0\n' "$dev" >"$DIR/seam"
  base=$("$TAPECTL" cards | tail -1)
  TAPECTL_TEST_CARDS="$DIR/seam" "$TAPECTL_T" cards >"$DIR/big.out"
  if grep -qF "\"path\":\"$dev\",\"bytes\":$1}" "$DIR/big.out"; then got=offered; else got=refused; fi
  [ "$got" = "$2" ] && [ "$got" = offered -o "$(tail -1 "$DIR/big.out")" = "$base" ] \
    && ok "$1 bytes: $got" || fail "$1 bytes: $got, want $2 ($(tail -1 "$DIR/big.out") vs $base)"
  losetup -d "$dev"
done
rm -f "$DIR/big.img" "$DIR/t.img"
chmod -R a+rX "$DIR"   # the artifact upload runs unprivileged

echo
if [ "$FAILS" -eq 0 ]; then echo "PASS  cards Linux observations"; else echo "FAIL  $FAILS check(s):$FAILED"; fi
exit "$FAILS"
