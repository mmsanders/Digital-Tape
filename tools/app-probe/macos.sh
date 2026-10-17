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
# Every step has a hard limit: a blocking native call is an observation, not a hang.
lim() { local t=$1; shift; perl -e 'alarm shift; exec @ARGV or die "exec: $!"' "$t" "$@"; local rc=$?; [ $rc -eq 142 ] && echo "TIMEOUT after ${t}s: $*"; return $rc; }
log() { echo "== $* =="; echo "{\"step\": \"$*\", \"t\": \"$(date -u +%FT%TZ)\"}" >>"$OUT/steps.jsonl"; }

log environment
{ sw_vers; uname -a; id; csrutil status; spctl --status; } 2>&1 | tee "$OUT/env.txt"
$P env | tee "$OUT/env.jsonl"
sudo -n true && echo "sudo -n: passwordless (runner-specific)" | tee -a "$OUT/env.txt"
launchctl print "gui/$(id -u)" >/dev/null 2>&1 && echo "gui session: present" | tee -a "$OUT/env.txt" \
  || echo "gui session: absent" | tee -a "$OUT/env.txt"

attach() { lim 60 sudo hdiutil attach -nomount -imagekey diskimage-class=CRawDiskImage "$1" | head -1 | awk '{print $1}'; }
detach() { lim 60 sudo hdiutil detach "$1" -force >/dev/null; }
provision() {   # elevated, test build only: the shipped binary refuses virtual media
  local dev=$1 size
  size=$(lim 60 sudo "$TT" probe "$dev" | sed -n 's/^bytes=//p')
  printf '%s\n' whole=1 removable=1 sd_bus=0 "bytes=$size" holds_os=0 layout_ok=0 >"$OUT/facts"
  lim 120 sudo env TAPECTL_TEST_FACTS="$OUT/facts" "$TT" provision "$dev" --label "$2" --erase "$dev" \
    --uuid "$3" --epoch 1760659200
}

log fixtures
mkfile -n 8g "$RUNNER_TEMP/A.raw"; mkfile -n 8g "$RUNNER_TEMP/B.raw"
A=$(attach "$RUNNER_TEMP/A.raw"); provision "$A" probeA aaaaaaaa000000000000000000000001; detach "$A"
B=$(attach "$RUNNER_TEMP/B.raw"); provision "$B" probeB bbbbbbbb000000000000000000000002; detach "$B"
A=$(attach "$RUNNER_TEMP/A.raw"); lim 30 sudo diskutil mountDisk "$A" >/dev/null 2>&1 || true; sleep 3
echo "A attached as $A"

log "F1 unelevated read facts on $A"
lim 120 $P read-facts "$A" | tee "$OUT/f1-unelevated.jsonl"
log "F1 shipped probe code unelevated (tapectl-test probe)"
lim 60 "$TT" probe "$A" 2>&1 | tee "$OUT/f1-tapectl-probe-unelevated.txt"; echo "exit ${PIPESTATUS[0]}" >>"$OUT/f1-tapectl-probe-unelevated.txt"
log "F1 the same probe elevated"
lim 60 sudo "$TT" probe "$A" 2>&1 | tee "$OUT/f1-tapectl-probe-elevated.txt"
log "F1 elevated read facts (control)"
lim 120 sudo python3 -I "$HERE/probe.py" read-facts "$A" >"$OUT/f1-elevated.jsonl"; grep -E '"probe": "(open-rdonly|read-lba0)"' "$OUT/f1-elevated.jsonl"

log "F2 elevated one open across the provision/load/verify write pattern"
lim 120 sudo python3 -I "$HERE/probe.py" one-open "$A" | tee "$OUT/f2-one-open.jsonl"
lim 120 sudo "$TT" verify "$A" >/dev/null 2>&1; echo "shipped verify exit $? (virtual media: 3 expected)" | tee -a "$OUT/f2-one-open.txt"
lim 300 sudo env TAPECTL_TEST_FACTS="$OUT/facts" "$TT" verify "$A" 2>&1 | tee -a "$OUT/f2-one-open.txt"

# F3: one held RO descriptor while the medium changes under it.
hold_case() {   # NAME SECONDS ACTION...
  local name=$1 secs=$2; shift 2
  log "F3 $name"
  lim $((secs + 30)) sudo python3 -I "$HERE/probe.py" hold "$A" "$secs" >"$OUT/f3-$name.jsonl" &
  local pid=$!
  sleep 3; "$@"; wait $pid; echo "hold exit $?" >>"$OUT/f3-$name.jsonl.exit"
  cat "$OUT/f3-$name.jsonl"
}
no_change() { :; }
remove_reinsert() {
  echo "{\"event\": \"detach $A\", \"t\": \"$(date -u +%T)\"}" >>"$OUT/f3-events.jsonl"; detach "$A"; sleep 3
  A2=$(attach "$RUNNER_TEMP/A.raw"); echo "{\"event\": \"reattach A as $A2\"}" >>"$OUT/f3-events.jsonl"
  sleep 3; lim 30 sudo python3 -I "$HERE/probe.py" sig "$A2" | tee -a "$OUT/f3-events.jsonl"; A=$A2
}
equal_swap() {
  echo "{\"event\": \"detach $A, attach B\"}" >>"$OUT/f3-events.jsonl"; detach "$A"; sleep 1
  B=$(attach "$RUNNER_TEMP/B.raw"); echo "{\"event\": \"B attached as $B\"}" >>"$OUT/f3-events.jsonl"
  sleep 3; lim 30 sudo python3 -I "$HERE/probe.py" sig "$B" | tee -a "$OUT/f3-events.jsonl"
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

log "G1 runtime observation: fs_usage and eslogger on controls"
# Negative controls: an unelevated attempt (fails EACCES, as an unelevated app's
# would) and an elevated open that succeeds. Positive: an ordinary file open.
g1_round() {   # TRACER-NAME, run with the tracer already started
  python3 -I "$HERE/probe.py" touch "$A" >"$OUT/g1-$1-neg-unelev.jsonl"
  sudo python3 -I "$HERE/probe.py" touch "$A" >"$OUT/g1-$1-neg-root.jsonl"
  python3 -I "$HERE/probe.py" touch "$RUNNER_TEMP/A.raw" >"$OUT/g1-$1-pos.jsonl"
  cat "$OUT"/g1-$1-*.jsonl
}
pid_of() { python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['pid'])" "$1"; }
lim 40 sudo fs_usage -w -f pathname -t 12 >"$OUT/g1-fs_usage.txt" 2>"$OUT/g1-fs_usage.err" &
FSU=$!; sleep 3; g1_round fsu; sleep 2; sudo pkill -INT -x fs_usage 2>/dev/null; wait $FSU; echo "fs_usage exit $?" >>"$OUT/g1-fs_usage.err"
for k in neg-unelev neg-root; do
  python3 -I "$HERE/g1_mac.py" fs_usage "$OUT/g1-fs_usage.txt" "$(pid_of "$OUT/g1-fsu-$k.jsonl")" "$(pid_of "$OUT/g1-fsu-pos.jsonl")" | sed "s/^/$k: /" | tee -a "$OUT/g1-summary.txt"
done
wc -l <"$OUT/g1-fs_usage.txt"; rm -f "$OUT/g1-fs_usage.txt"
lim 30 sudo eslogger open >"$RUNNER_TEMP/g1-eslogger.json" 2>"$OUT/g1-eslogger.err" &
ESP=$!; sleep 4; g1_round esl; sleep 2
sudo pkill -INT -x eslogger 2>/dev/null; wait $ESP; echo "eslogger exit $?" >>"$OUT/g1-eslogger.err"; head -c 400 "$OUT/g1-eslogger.err"
for k in neg-unelev neg-root; do
  python3 -I "$HERE/g1_mac.py" eslogger "$RUNNER_TEMP/g1-eslogger.json" "$(pid_of "$OUT/g1-esl-$k.jsonl")" "$(pid_of "$OUT/g1-esl-pos.jsonl")" | sed "s/^/$k: /" | tee -a "$OUT/g1-summary.txt"
done

log "F3b removal under a held descriptor when detach is refused: stop the disk-image I/O process"
hdiutil info | tee "$OUT/f3b-hdiutil-info.txt" | grep -iE 'process|image-path|/dev/disk' | head -20
lim 40 sudo python3 -I "$HERE/probe.py" hold "$A" 25 >"$OUT/f3b-hold.jsonl" &
HP=$!; sleep 3
lim 30 sudo hdiutil detach "$A" -force; echo "detach -force exit $?" | tee -a "$OUT/f3b-events.txt"
IOP=$(hdiutil info | awk -F: '/process ID/ {gsub(/ /,"",$2); print $2}' | sort -u | head -5)
echo "image process IDs: ${IOP:-none listed}" | tee -a "$OUT/f3b-events.txt"
for p in $IOP; do ps -o pid=,comm= -p "$p"; done | tee -a "$OUT/f3b-events.txt"
for n in diskimagesiod diskimages-helper; do pgrep -lx "$n"; done | tee -a "$OUT/f3b-events.txt"
sudo pkill -9 -x diskimagesiod; sudo pkill -9 -x diskimages-helper; echo "killed image I/O processes at $(date -u +%T)" | tee -a "$OUT/f3b-events.txt"
wait $HP; cat "$OUT/f3b-hold.jsonl"
ls /dev/disk* | tr '\n' ' ' | tee -a "$OUT/f3b-events.txt"; echo

log done
for d in $(hdiutil info | awk '/^\/dev\/disk[0-9]+[ \t]/{print $1}'); do detach "$d" 2>/dev/null || true; done
