#!/usr/bin/env bash
# macOS disk-image helpers for device_e2e.sh (run as root).
#   hdiutil_macos.sh attach RAWFILE   prints /dev/diskN. Volumes are mounted as
#                                     macOS chooses, so a provisioned card's
#                                     partition 1 appears under /Volumes.
#   hdiutil_macos.sh detach /dev/diskN
set -euo pipefail
case "$1" in
  attach)
    # -nomount: a blank image has no file system, and hdiutil refuses to attach
    # it otherwise. Then let macOS mount whatever it recognises (partition 1 of
    # a provisioned card), as it would on insertion.
    dev=$(hdiutil attach -nomount -imagekey diskimage-class=CRawDiskImage "$2" | head -1 | awk '{print $1}')
    diskutil mountDisk "$dev" >/dev/null 2>&1 || true
    sleep 2
    echo "$dev" ;;
  detach) hdiutil detach "$2" -force >/dev/null ;;
esac
