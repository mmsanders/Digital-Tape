#!/usr/bin/env bash
# Windows VHD helpers for device_e2e.sh (Git Bash, as Administrator).
#   vhd_windows.sh attach FILE.vhd    creates an 8 GiB expandable VHD on first
#                                     use, attaches it, prints \\.\PhysicalDriveN
#   vhd_windows.sh detach \\.\PhysicalDriveN
set -euo pipefail
export MSYS_NO_PATHCONV=1
STATE=${VHD_STATE:-$TEMP/wp14-vhd-path}
script() { local s; s=$(mktemp); printf '%s\n' "$@" >"$s"; diskpart /s "$(cygpath -w "$s")" >"$s.log" 2>&1 || { cat "$s.log" >&2; return 1; }; }
case "$1" in
  attach)
    vhd=$(cygpath -w "$2")
    echo "$vhd" >"$STATE"
    [ -f "$2" ] || script "create vdisk file=\"$vhd\" maximum=8192 type=expandable"
    script "select vdisk file=\"$vhd\"" "attach vdisk"
    n=$(powershell -NoProfile -Command "(Get-DiskImage -ImagePath '$vhd' | Get-Disk).Number" | tr -d '\r')
    printf '\\\\.\\PhysicalDrive%s\n' "$n" ;;
  detach)
    script "select vdisk file=\"$(cat "$STATE")\"" "detach vdisk" ;;
esac
