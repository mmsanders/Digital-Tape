#!/usr/bin/env bash
# macOS disk-image helpers for device_e2e.sh (run as root).
#   hdiutil_macos.sh attach RAWFILE   prints /dev/diskN. Volumes are mounted as
#                                     macOS chooses, so a provisioned card's
#                                     partition 1 appears under /Volumes.
#   hdiutil_macos.sh detach /dev/diskN
set -euo pipefail
case "$1" in
  attach) hdiutil attach -imagekey diskimage-class=CRawDiskImage "$2" | head -1 | awk '{print $1}' ;;
  detach) hdiutil detach "$2" -force >/dev/null ;;
esac
