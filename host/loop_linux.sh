#!/usr/bin/env bash
# Linux loop helpers for device_e2e.sh (run as root).
#   loop_linux.sh attach BACKING     prints /dev/loopN; mounts partition 1 read-only if present
#   loop_linux.sh detach /dev/loopN  unmounts partition 1, detaches
set -euo pipefail
MNT=${LOOP_P1_MNT:-/tmp/wp14-p1}
case "$1" in
  attach)
    dev=$(losetup -fP --show "$2")
    udevadm settle 2>/dev/null || sleep 1
    if [ -b "${dev}p1" ]; then
      mkdir -p "$MNT"
      mount -t vfat -o ro "${dev}p1" "$MNT" && echo "loop_linux: mounted ${dev}p1 on $MNT" >&2
    fi
    echo "$dev" ;;
  detach)
    umount "$MNT" 2>/dev/null || true
    sync
    losetup -d "$2"
    echo 3 >/proc/sys/vm/drop_caches ;;
esac
