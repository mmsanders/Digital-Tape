#!/bin/sh
# rehearse-linux.sh — off-card mechanics rehearsal of the A6 capture on Linux.
# Software #428; docs/WP14-NATIVE-CAPTURE.md §3. IMAGE MECHANICS ONLY: never physical
# evidence and never a macOS/Windows format check.
#
#   rehearse-linux.sh TAPECTL EXPECTED_SHA256 BYTES OUTDIR
#
# Provisions an image of BYTES in OUTDIR only after checking free space, proves how
# much was really allocated, traces `verify` under strace and keeps every raw file:
# versions, hashes, geometry, allocation, stdout, stderr, exits and the trace.
set -u
[ $# -eq 4 ] || { echo "usage: $0 TAPECTL EXPECTED_SHA256 BYTES OUTDIR" >&2; exit 2; }
exe=$1; want=$2; bytes=$3; out=$4
mkdir -p "$out" || exit 2
cd "$out" || exit 2

got=$(sha256sum "$exe" | cut -c1-64)
echo "$got  $exe" > exe.sha256
[ "$got" = "$want" ] || { echo "STOP: $exe is $got, not $want" >&2; exit 1; }
{ uname -a; strace -V | head -1; python3 --version; } > versions.txt 2>&1

# Space safety: refuse unless the filesystem could hold the image even if not sparse.
avail=$(df -Pk . | awk 'NR==2 {print $4}')
need=$(( bytes / 1024 + 1048576 ))
echo "available_kib $avail needed_kib_if_not_sparse $need" > space.txt
[ "$avail" -ge "$need" ] || { echo "STOP: not enough free space for a non-sparse image" >&2; exit 1; }

"$exe" provision rehearsal.img --label A6-REHEARSAL --uuid 00112233445566778899aabbccddeeff \
    --epoch 1760000000 --image-bytes "$bytes" > provision-out.txt 2> provision-err.txt
echo "provision $?" > provision-exit.txt
stat -c %s rehearsal.img > geometry.txt
echo "apparent_bytes $(stat -c %s rehearsal.img) allocated_bytes $(( $(stat -c %b rehearsal.img) * $(stat -c %B rehearsal.img) ))" > allocation.txt

strace -f -e trace=execve,openat,open,pread64,pwrite64,write,fsync,fdatasync,close \
    -o verify.strace "$exe" verify rehearsal.img > verify-out.txt 2> verify-err.txt
rc=$?
echo "$rc" > verify-exit.txt
echo "strace $rc" > tracer-exits.txt          # strace exits with the traced child's status
: > strace-diagnostics.txt                     # strace -o sends its own messages to stderr
grep -v '^tapectl' verify-err.txt >> strace-diagnostics.txt
pid=$(awk 'NR==1 {print $1}' verify.strace)
echo "$pid" > verify-pid.txt
rm -f rehearsal.img
echo "rehearsal: pid $pid exit $rc; outputs in $out"
