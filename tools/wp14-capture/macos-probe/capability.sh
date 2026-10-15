#!/bin/sh
# capability.sh — does fs_usage report pread's full 64-bit offset and its returned byte
# count on this Mac? (Software #438 capability stop.) Runs a6probe under the same
# fs_usage invocation rehearse-macos.sh uses, against a sparse 4 GiB + 1 MiB file, and
# prints each known call beside the line fs_usage recorded for it. Needs sudo.
set -u
d=${1:-a6-capability}
mkdir -p "$d"
cc -O0 -o "$d/a6probe" "$(dirname "$0")/a6probe.c" || exit 1
f="$d/sparse.img"
rm -f "$f"; mkfile -n 4296015872 "$f" || exit 1
cat /bin/test > "$d/a6gate" && chmod 755 "$d/a6gate"
script -q -F "$d/fsusage.txt" sudo fs_usage -w -f filesys a6probe a6gate > /dev/null 2>&1 &
i=0; while [ $i -lt 300 ]; do i=$((i+1)); "$d/a6gate" -e "$d/GATE-start-$i"; sleep 0.1
    grep -q "GATE-start-" "$d/fsusage.txt" 2>/dev/null && break; done
# offsets: 0, 1 MiB-512, 4 GiB, the 4 GiB+1 MiB image's last sector, 4 GiB+1 MiB-100
# (a 512-byte request that can return only 100), and a high distinct pattern
"$d/a6probe" "$f" 0x0:0x200 0xffe00:0x200 0x100000000:0x200 0x1000ffe00:0x200 \
    0x1000fff9c:0x200 0x0fedcba00:0x200 0x1000ffe00:0x80 > "$d/probe-out.txt"
echo "a6probe $?" >> "$d/probe-out.txt"
i=0; while [ $i -lt 300 ]; do i=$((i+1)); "$d/a6gate" -e "$d/GATE-end-$i"; sleep 0.1
    grep -q "GATE-end-" "$d/fsusage.txt" 2>/dev/null && break; done
sudo pkill -INT -x fs_usage; wait
rm -f "$f" "$d/a6gate" "$d"/GATE-*
{ sw_vers; uname -a; csrutil status; } > "$d/versions.txt" 2>&1
echo "== known calls"; cat "$d/probe-out.txt"
echo "== fs_usage pread lines"; grep -E " pread " "$d/fsusage.txt" | grep a6probe
