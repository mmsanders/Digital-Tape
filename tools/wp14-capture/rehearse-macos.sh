#!/bin/sh
# rehearse-macos.sh — WP-14 A6 off-card rehearsal on macOS with fs_usage (Software #438).
#
# Leaves SIP on and changes no security setting. Opens no card or disk device: the only
# target is a fresh local 4 GiB + 1 MiB image file, deleted at the end. Needs an admin
# password once (sudo), because fs_usage reads the kernel trace buffer.
#
#   sh rehearse-macos.sh            (in the folder holding the released tapectl)
#
# Writes one folder a6-rh-mac-<time>/ and one zip of it; send the zip to Verification #146.
# The capture is an observation, not a PASS. Every step's exit status is recorded; a
# failing step stops the script and the folder keeps everything up to that point.
set -u
EXPECT=e7550d8bedbb0c784fd528c387a87cca2bad8d1b411c39217d25377329bb0beb   # tapectl-macos, wp14-tapectl-5e2df5aaf23e
CAP=4296015872
here=$(pwd)
out="$here/a6-rh-mac-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$out" || exit 1
stop() { echo "STOPPED: $*" | tee -a "$out/stopped.txt"; zipup; exit 1; }
zipup() { (cd "$here" && /usr/bin/ditto -c -k --keepParent "$out" "$out.zip" && shasum -a 256 "$out.zip"); }

[ -f tapectl ] || stop "no ./tapectl here"
shasum -a 256 tapectl "$0" > "$out/hashes-before.txt"
got=$(shasum -a 256 tapectl | cut -d' ' -f1)
[ "$got" = "$EXPECT" ] || stop "tapectl is $got, not the released $EXPECT"
chmod +x tapectl 2>/dev/null
xattr -d com.apple.quarantine tapectl 2>/dev/null
{ sw_vers; uname -a; csrutil status; } > "$out/versions.txt" 2>&1
df -k "$here" > "$out/space.txt"
free=$(df -k "$here" | awk 'NR==2 {print $4}')
[ "$free" -gt 4400000 ] || stop "need 4.4 GB free here (the image if not sparse); have ${free} KB"

img="$out/rehearsal.img"
./tapectl provision "$img" --label A6-REHEARSAL --uuid 00112233445566778899aabbccddeeff \
    --epoch 1760000000 --image-bytes $CAP > "$out/provision-out.txt" 2> "$out/provision-err.txt"
echo $? > "$out/provision-exit.txt"
[ "$(cat "$out/provision-exit.txt")" = 0 ] || stop "provision failed"
stat -f '%z' "$img" > "$out/geometry.txt"
{ ls -ls "$img"; du -k "$img"; } > "$out/allocation.txt"

# A gate is a copy of /bin/test under its own name, stat-ing a unique path. Seeing a start
# gate in the trace proves fs_usage was live before tapectl started; an end gate issued
# after tapectl exited proves everything up to that exit had been emitted.
cat /bin/test > "$out/a6gate" && chmod 755 "$out/a6gate"
sudo -v || stop "sudo refused"
# fs_usage on a pty (script) so it line-buffers; filtered to tapectl and the gate.
script -q -F "$out/fsusage.txt" sudo fs_usage -w -f filesys -f exec tapectl a6gate > /dev/null 2>&1 &
gate() {   # gate <tag>: issue gates until one is seen; prints the token seen
    i=0
    while [ $i -lt 300 ]; do
        i=$((i + 1))
        "$out/a6gate" -e "$out/GATE-$1-$i"
        sleep 0.1
        seen=$(grep -o "GATE-$1-[0-9]*" "$out/fsusage.txt" 2>/dev/null | head -1)
        [ -n "$seen" ] && { echo "$seen"; return 0; }
    done
    return 1
}
start=$(gate start) || { sudo pkill -INT -x fs_usage; stop "fs_usage never showed the start gate"; }
echo "start-gate $start" > "$out/gates.txt"
./tapectl verify "$img" > "$out/verify-out.txt" 2> "$out/verify-err.txt" &
tp=$!
wait $tp
rc=$?
echo "pid $tp exit $rc" > "$out/verify-pid.txt"
echo $rc > "$out/verify-exit.txt"
end=$(gate end); endrc=$?
echo "end-gate $end" >> "$out/gates.txt"
sudo pkill -INT -x fs_usage
wait
echo "fs_usage-start-gate $([ -n "$start" ] && echo 0 || echo 1)" > "$out/tracer-exits.txt"
echo "fs_usage-end-gate $endrc" >> "$out/tracer-exits.txt"
rm -f "$img" "$out/a6gate" "$out"/GATE-* 2>/dev/null
shasum -a 256 tapectl "$0" > "$out/hashes-after.txt"

if command -v python3 >/dev/null 2>&1 && [ -f a6check.py ] && python3 -c 1 2>/dev/null; then
    python3 a6check.py --format fs_usage --trace "$out/fsusage.txt" --pid "$tp" --capacity $CAP \
        --geometry "$out/geometry.txt" --target "$img" --exe tapectl --sha256 $EXPECT \
        --stdout "$out/verify-out.txt" --diagnostics "$out/verify-err.txt" \
        --tracer-log "$out/tracer-exits.txt" --gates "$out/gates.txt" --exit-code "$rc" \
        > "$out/a6check.json" 2>&1
    echo "a6check $?" >> "$out/a6check.json"
else
    echo "a6check not run here (no python3 or no a6check.py); Verification runs it" > "$out/a6check-not-run.txt"
fi
zipup
echo "Send that zip to Verification #146. This rehearsal is an observation, not a PASS."
