#!/bin/sh
# selftest.sh — a6check.py must PASS each good capture and FAIL every control.
# Software #425; docs/WP14-NATIVE-CAPTURE.md §3. Not acceptance and not a CI gate.
#
#   tools/wp14-capture/selftest.sh                  fixtures only
#   TAPECTL=path/to/tapectl tools/wp14-capture/selftest.sh
#                                                   plus a live Linux rehearsal:
#                                                   provision a sparse image of the
#                                                   physical card's size, capture
#                                                   `verify` under strace, judge it
#
# The fixtures named synthetic-* only exercise the parser on each format; they
# are not captures. linux-shipped-verify.strace is a real strace capture of the
# released tapectl-linux (sha256 4d8c97a4…785c) verifying a sparse image file.
set -u
here=$(cd "$(dirname "$0")" && pwd)
chk="python3 $here/a6check.py"
fx=$here/fixtures
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cap=62537072640
fails=0

expect() {  # expect RC NAME ARGS...
    want=$1; name=$2; shift 2
    $chk "$@" > "$tmp/out.json" 2>&1
    got=$?
    if [ "$got" = "$want" ]; then
        echo "ok   $name (exit $got)"
    else
        echo "FAIL $name: exit $got, wanted $want"; sed 's/^/     /' "$tmp/out.json"; fails=$((fails + 1))
    fi
}

S="verify --format strace --capacity $cap --target card.img"
st=$fx/linux-shipped-verify.strace
expect 0 "strace: real shipped capture" $S --trace "$st" --pid 885
expect 1 "strace: wrong PID" $S --trace "$st" --pid 886
grep -v 62537072128 "$st" > "$tmp/missing.strace"
expect 1 "strace: mirror read missing" $S --trace "$tmp/missing.strace" --pid 885
sed 's/62537072128)/2397498880)/' "$st" > "$tmp/trunc.strace"          # (cap-512) mod 2^32
expect 1 "strace: 32-bit truncated offset" $S --trace "$tmp/trunc.strace" --pid 885
sed 's/62537072128) = 512/62537072128) = -1 EIO (Input\/output error)/' "$st" > "$tmp/eio.strace"
expect 1 "strace: failed call" $S --trace "$tmp/eio.strace" --pid 885
sed 's/62537072128) = 512/62537072128) = 100/' "$st" > "$tmp/short.strace"
expect 1 "strace: short read" $S --trace "$tmp/short.strace" --pid 885
sed 's/"card.img", O_RDONLY/"card.img", O_RDWR/' "$st" > "$tmp/rw.strace"
expect 1 "strace: write-mode open of target" $S --trace "$tmp/rw.strace" --pid 885
sed 's/"card.img"/"helper.img"/' "$st" > "$tmp/other.strace"
expect 1 "strace: read belongs to another file" $S --trace "$tmp/other.strace" --pid 885
expect 1 "strace: capacity not beyond 4 GiB" verify --format strace --capacity 4294967296 --target card.img --trace "$st" --pid 885
printf 'not a binary' > "$tmp/exe"
expect 1 "strace: executable hash mismatch" $S --trace "$st" --pid 885 --exe "$tmp/exe" \
    --sha256 4d8c97a44f163bcd513c98c0903db6a01418001f169cfd6aa126823f6f7a785c

D="verify --format dtrace --capacity $cap --target /dev/rdisk4"
dt=$fx/synthetic-dtrace.trace
expect 0 "dtrace (synthetic): good" $D --trace "$dt" --pid 4242
expect 1 "dtrace (synthetic): wrong PID" $D --trace "$dt" --pid 4243
sed 's/off=62537072128 len=512 ret=512 errno=0/off=62537072128 len=512 ret=-1 errno=5/' "$dt" > "$tmp/eio.dt"
expect 1 "dtrace (synthetic): failed call" $D --trace "$tmp/eio.dt" --pid 4242
sed 's/off=62537072128/off=2397498880/' "$dt" > "$tmp/trunc.dt"
expect 1 "dtrace (synthetic): 32-bit truncated offset" $D --trace "$tmp/trunc.dt" --pid 4242
sed '1d' "$dt" > "$tmp/nohdr.dt"
expect 2 "dtrace (synthetic): not an a6-macos.d capture" $D --trace "$tmp/nohdr.dt" --pid 4242
expect 1 "dtrace (synthetic): stated exit disagrees with traced exit" $D --trace "$dt" --pid 4242 --exit-code 1
sed '0,/flags=0x1000000/s//flags=0x1000002/' "$dt" > "$tmp/rw.dt"
expect 1 "dtrace (synthetic): write-mode open" $D --trace "$tmp/rw.dt" --pid 4242

I="verify --format iocap --capacity $cap --target /dev/rdisk4"
io=$fx/synthetic-iocap.jsonl
expect 0 "iocap (synthetic): good" $I --trace "$io" --pid 4242
expect 1 "iocap (synthetic): wrong PID" $I --trace "$io" --pid 1
grep -v iocap_attach "$io" > "$tmp/nopid.jsonl"
expect 2 "iocap (synthetic): no PID record" $I --trace "$tmp/nopid.jsonl" --pid 4242

W="verify --format etw-xml --capacity $cap --disk 1"
ew=$fx/synthetic-etw-disk.xml
ok=$fx/synthetic-etw-verify-stdout.txt
expect 0 "etw (synthetic): good" $W --trace "$ew" --pid 4242 --stdout "$ok" --exit-code 0
expect 1 "etw (synthetic): wrong PID" $W --trace "$ew" --pid 4243 --stdout "$ok" --exit-code 0
expect 1 "etw (synthetic): wrong disk" verify --format etw-xml --capacity $cap --disk 0 --trace "$ew" --pid 4242 --stdout "$ok" --exit-code 0
expect 1 "etw (synthetic): no verify OK for a status-less record" $W --trace "$ew" --pid 4242
printf 'NEEDS_REPAIR\n' > "$tmp/bad.txt"
expect 1 "etw (synthetic): verify not OK" $W --trace "$ew" --pid 4242 --stdout "$tmp/bad.txt" --exit-code 1
sed 's/>tapectl.exe</>powershell.exe</' "$ew" > "$tmp/ps.xml"
expect 1 "etw (synthetic): PID is a helper, not tapectl" $W --trace "$tmp/ps.xml" --pid 4242 --stdout "$ok" --exit-code 0
sed 's/<Data Name="IssuingThreadId">5000</<Data Name="IssuingThreadId">777</' "$ew" > "$tmp/thr.xml"
expect 1 "etw (synthetic): issuing thread not in tapectl" $W --trace "$tmp/thr.xml" --pid 4242 --stdout "$ok" --exit-code 0
printf '<Events/>' > "$tmp/empty.xml"
expect 2 "etw: empty export" $W --trace "$tmp/empty.xml" --pid 4242 --stdout "$ok" --exit-code 0

if [ -n "${TAPECTL:-}" ]; then
    command -v strace >/dev/null || { echo "FAIL live: strace not installed"; exit 1; }
    "$TAPECTL" provision "$tmp/card.img" --label A6-REHEARSAL --uuid 00112233445566778899aabbccddeeff \
        --epoch 1760000000 --image-bytes $cap > /dev/null || { echo "FAIL live: provision"; exit 1; }
    ( cd "$tmp" && strace -f -T -e trace=openat,open,pread64,pwrite64,fsync,fdatasync,close \
        -o live.strace "$TAPECTL" verify card.img > live.out ) ; rc=$?
    pid=$(awk 'NR==1{print $1}' "$tmp/live.strace")
    echo "live: tapectl sha256 $(sha256sum "$TAPECTL" | cut -c1-64) verify exit $rc output $(cat "$tmp/live.out")"
    expect 0 "live strace rehearsal (image, not physical)" $S --trace "$tmp/live.strace" --pid "$pid" --exe "$TAPECTL"
fi

[ "$fails" = 0 ] && echo "selftest: all cases as expected" || echo "selftest: $fails unexpected"
[ "$fails" = 0 ]
