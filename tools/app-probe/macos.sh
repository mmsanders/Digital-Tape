#!/usr/bin/env bash
# APP-1 capability probes on hosted macOS (#444). Runs as the runner user;
# only the steps marked "elevated" use sudo. Fixtures are two 8 GiB sparse raw
# images attached by hdiutil as root and provisioned through tapectl-test with
# injected "is a card" facts. No physical disk is touched.
#   macos.sh TAPECTL_TEST OUTDIR
set -uo pipefail
TT=$1; OUT=$2; mkdir -p "$OUT"
HERE=$(cd "$(dirname "$0")" && pwd)
P="python3 -I $HERE/probe.py"
log() { echo "== $* =="; echo "{\"step\": \"$*\", \"t\": \"$(date -u +%FT%TZ)\"}" >>"$OUT/steps.jsonl"; }

log environment
{ sw_vers; uname -a; id; csrutil status; spctl --status; } 2>&1 | tee "$OUT/env.txt"
$P env | tee "$OUT/env.jsonl"
sudo -n true && echo "sudo -n: passwordless (runner-specific)" | tee -a "$OUT/env.txt"
launchctl print "gui/$(id -u)" >/dev/null 2>&1 && echo "gui session: present" | tee -a "$OUT/env.txt" \
  || echo "gui session: absent" | tee -a "$OUT/env.txt"

attach() { sudo hdiutil attach -nomount -imagekey diskimage-class=CRawDiskImage "$1" | head -1 | awk '{print $1}'; }
detach() { sudo hdiutil detach "$1" -force >/dev/null; }
provision() {   # elevated, test build only: the shipped binary refuses virtual media
  local dev=$1 size
  size=$(sudo "$TT" probe "$dev" | sed -n 's/^bytes=//p')
  printf '%s\n' whole=1 removable=1 sd_bus=0 "bytes=$size" holds_os=0 layout_ok=0 >"$OUT/facts"
  sudo env TAPECTL_TEST_FACTS="$OUT/facts" "$TT" provision "$dev" --label "$2" --erase "$dev" \
    --uuid "$3" --epoch 1760659200
}

log fixtures
mkfile -n 8g "$RUNNER_TEMP/A.raw"; mkfile -n 8g "$RUNNER_TEMP/B.raw"
A=$(attach "$RUNNER_TEMP/A.raw"); provision "$A" probeA aaaaaaaa000000000000000000000001; detach "$A"
B=$(attach "$RUNNER_TEMP/B.raw"); provision "$B" probeB bbbbbbbb000000000000000000000002; detach "$B"
A=$(attach "$RUNNER_TEMP/A.raw"); sudo diskutil mountDisk "$A" >/dev/null 2>&1 || true; sleep 3
echo "A attached as $A"

log "F1 unelevated read facts on $A"
$P read-facts "$A" | tee "$OUT/f1-unelevated.jsonl"
log "F1 shipped probe code unelevated (tapectl-test probe)"
"$TT" probe "$A" 2>&1 | tee "$OUT/f1-tapectl-probe-unelevated.txt"; echo "exit ${PIPESTATUS[0]}" >>"$OUT/f1-tapectl-probe-unelevated.txt"
log "F1 the same probe elevated"
sudo "$TT" probe "$A" 2>&1 | tee "$OUT/f1-tapectl-probe-elevated.txt"
log "F1 elevated read facts (control)"
sudo python3 -I "$HERE/probe.py" read-facts "$A" >"$OUT/f1-elevated.jsonl"; grep -E '"probe": "(open-rdonly|read-lba0)"' "$OUT/f1-elevated.jsonl"

log "F2 elevated one open across the provision/load/verify write pattern"
sudo python3 -I "$HERE/probe.py" one-open "$A" | tee "$OUT/f2-one-open.jsonl"
sudo "$TT" verify "$A" >/dev/null 2>&1; echo "shipped verify exit $? (virtual media: 3 expected)" | tee -a "$OUT/f2-one-open.txt"
sudo env TAPECTL_TEST_FACTS="$OUT/facts" "$TT" verify "$A" 2>&1 | tee -a "$OUT/f2-one-open.txt"

# F3: one held RO descriptor while the medium changes under it.
hold_case() {   # NAME SECONDS ACTION...
  local name=$1 secs=$2; shift 2
  log "F3 $name"
  sudo python3 -I "$HERE/probe.py" hold "$A" "$secs" >"$OUT/f3-$name.jsonl" &
  local pid=$!
  sleep 3; "$@"; wait $pid
  cat "$OUT/f3-$name.jsonl"
}
no_change() { :; }
remove_reinsert() {
  echo "{\"event\": \"detach $A\", \"t\": \"$(date -u +%T)\"}" >>"$OUT/f3-events.jsonl"; detach "$A"; sleep 3
  A2=$(attach "$RUNNER_TEMP/A.raw"); echo "{\"event\": \"reattach A as $A2\"}" >>"$OUT/f3-events.jsonl"
  sleep 3; sudo python3 -I "$HERE/probe.py" sig "$A2" | tee -a "$OUT/f3-events.jsonl"; A=$A2
}
equal_swap() {
  echo "{\"event\": \"detach $A, attach B\"}" >>"$OUT/f3-events.jsonl"; detach "$A"; sleep 1
  B=$(attach "$RUNNER_TEMP/B.raw"); echo "{\"event\": \"B attached as $B\"}" >>"$OUT/f3-events.jsonl"
  sleep 3; sudo python3 -I "$HERE/probe.py" sig "$B" | tee -a "$OUT/f3-events.jsonl"
}
hold_case no-change 12 no_change
hold_case remove-reinsert 15 remove_reinsert
hold_case equal-size-swap 12 equal_swap
log "F3 what DA reports for A and B (identity fields an app could compare)"
A=$(attach "$RUNNER_TEMP/A.raw") 2>/dev/null || true
for d in $(hdiutil info | awk '/^\/dev\/disk[0-9]+[ \t]/{print $1}'); do
  diskutil info -plist "$d" >"$OUT/f3-info-$(basename "$d").plist" 2>/dev/null || true
done
ls "$OUT"/f3-info-*.plist

log "G1 runtime observation: fs_usage on a control that opens a disk and one that does not"
sudo fs_usage -w -f pathname -t 12 >"$OUT/g1-fs_usage.txt" 2>"$OUT/g1-fs_usage.err" &
FSU=$!; sleep 3
python3 -I "$HERE/probe.py" touch "$A" | tee "$OUT/g1-negative.jsonl"
python3 -I "$HERE/probe.py" touch "$RUNNER_TEMP/A.raw" | tee "$OUT/g1-positive.jsonl"
sleep 2; sudo kill -INT $FSU 2>/dev/null; wait $FSU; echo "fs_usage exit $?" >>"$OUT/g1-fs_usage.err"
NPID=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['pid'])" "$OUT/g1-negative.jsonl")
PPID_=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['pid'])" "$OUT/g1-positive.jsonl")
echo "negative pid $NPID lines naming /dev/:"; grep -E "\.$NPID\b|\b$NPID\$" "$OUT/g1-fs_usage.txt" | grep '/dev/' | head -5 | tee "$OUT/g1-negative-hits.txt"
echo "positive pid $PPID_ lines naming /dev/:"; grep -E "\.$PPID_\b|\b$PPID_\$" "$OUT/g1-fs_usage.txt" | grep '/dev/' | head -5 | tee "$OUT/g1-positive-hits.txt"
echo "positive pid lines naming the image:"; grep -E "\.$PPID_\b" "$OUT/g1-fs_usage.txt" | grep 'A.raw' | head -3
wc -l "$OUT/g1-fs_usage.txt"; head -c 600 "$OUT/g1-fs_usage.err"
log "G1 eslogger availability (ordinary-settings tracer)"
sudo eslogger open >"$OUT/g1-eslogger.json" 2>"$OUT/g1-eslogger.err" &
ESP=$!; sleep 3; python3 -I "$HERE/probe.py" touch "$A" >/dev/null; sleep 2
sudo pkill -INT -x eslogger 2>/dev/null; wait $ESP; echo "eslogger exit $?" >>"$OUT/g1-eslogger.err"
echo "eslogger: $(wc -c <"$OUT/g1-eslogger.json") bytes"; head -c 400 "$OUT/g1-eslogger.err"
grep -c '"/dev/' "$OUT/g1-eslogger.json" 2>/dev/null || true

log done
for d in $(hdiutil info | awk '/^\/dev\/disk[0-9]+[ \t]/{print $1}'); do detach "$d" 2>/dev/null || true; done
