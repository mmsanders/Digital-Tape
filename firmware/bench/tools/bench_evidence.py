#!/usr/bin/env python3
"""BE-1 offline bench-evidence checker (docs/WP17-BE1-INTERFACE.md, BE1-IF/3).

    python firmware/bench/tools/bench_evidence.py --offline BUNDLE --out REPORT.json [--golden DIR]

Reads saved evidence only. It never opens a serial port, USB, block device or
network socket, never imports `serial`, never flashes or provisions, and never
writes, renames or deletes anything in BUNDLE. The only file it writes is --out.

A CONSISTENT result is artifact consistency: the saved bytes agree with the
references, limits and each other. It is not target acceptance, a physical PASS,
a card qualification or a substitute for Michael's witness and Verification's
raw-data audit (BE-1).
"""

import argparse
import hashlib
import json
import os
import re
import struct
import sys

VERSION = "BE1-IF/3"
SESSION_SCHEMA = "digital-tape/be1-session/1"
REPORT_SCHEMA = "digital-tape/be1-report/1"

ENGINE_TREE = "d96b4245e04d74078f8938744b1394c3018516f7"
# This kit version's copy of firmware/bench/platformio.ini and tools/requirements.txt.
TOOLCHAIN = {
    "platformio": "6.1.19",
    "platform": "platformio/teensy@6.0.0",
    "framework": "platformio/framework-arduinoteensy@1.162.0",
    "uploader": "platformio/tool-teensy@1.162.0",
    "compiler": "platformio/toolchain-gccarmnoneeabi-teensy@1.150201.0",
}
F1_CASES = ("play-1x-quiet", "play-1x-fortissimo", "splice", "overdub", "overwrite", "reset-b", "promote")
CRITERIA = ("F1", "F2", "F3", "F4", "F5")
FIRST_SESSION = {"F1", "F2", "F5"}
RAM_BUDGET, RODATA_BUDGET, STACK_BUDGET = 204800, 32768, 8192

RANK = {"CONSISTENT": 0, "NOT_RUN": 1, "MISMATCH": 2, "INVALID": 3}
F1_SCOPE = ("Digest/stream PCM consistency of saved serial bytes only. It does not observe "
            "I2S or analogue output and is not target acceptance.")
F5_SCOPE = ("Transcript, witness-record and manual-verify consistency only. It does not establish "
            "a safe physical removal or card preservation.")

HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})")

# §3: the exact lines the FW-1 firmware prints.
LINES = [(name, re.compile(rx)) for name, rx in (
    ("banner", r"DIGITAL-TAPE BENCH WP-17"),
    ("fatal", r"FATAL instance (\d+) > reserve (\d+)"),
    ("mounted", r"CARD MOUNTED side ([AB]) frames (\d+) label ([ -~]*)"),
    ("refused", r"CARD REFUSED (?:IO|NOT_PROVISIONED|MOUNT -?\d+)"),
    ("unmount", r"UNMOUNT (-?\d+)"),
    ("gone", r"CARD GONE (removed|service failed|refused card)"),
    ("play_failed", r"PLAY FAILED (-?\d+)"),
    ("play", r"PLAY (-?\d+)"),
    ("stop", r"STOP (-?\d+)"),
    ("position", r"POSITION (\d+)"),
    ("end", r"END OF SIDE"),
    ("render_failed", r"RENDER FAILED"),
    ("info", r"INFO state (-?\d+) instance (\d+) reserve (\d+) card_blocks (\d+) p2_base (\d+) "
             r"p2_blocks (\d+) stack_high_water (\d+) underruns (\d+)"),
    ("err", r"ERR (?:usage or no mounted card|side -?\d+|unknown command)"),
    ("pcm", r"PCM"),
    ("underruns", r"UNDERRUNS (\d+)"),
    ("digest", r"SHA256 ([0-9a-f]{64}) FRAMES (\d+) RESULT (-?\d+)"),
)]
VERIFY_LINE = re.compile(r"OK|MBR_LAYOUT|PARTITION_TYPE|PARTITION_TRUNCATED|MOUNT [A-Z_]+|NEEDS_REPAIR|"
                         r"SIDE_B_DEGRADED|READ_ERROR SIDE [AB] FRAME \d+")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def worst(*states):
    return max(states, key=RANK.__getitem__) if states else "CONSISTENT"


class Judged:
    """A state plus the reason codes that produced it, in check order."""

    def __init__(self):
        self.state = "CONSISTENT"
        self.reasons = []

    def add(self, state, code):
        self.state = worst(self.state, state)
        if code not in self.reasons:
            self.reasons.append(code)

    def note(self, code):
        if code not in self.reasons:
            self.reasons.append(code)


class Usage(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Usage(message)


# ---- references -------------------------------------------------------------

def wav_payload(raw):
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    i = 12
    while i + 8 <= len(raw):
        cid, n = raw[i:i + 4], struct.unpack_from("<I", raw, i + 4)[0]
        if cid == b"data":
            if i + 8 + n > len(raw):
                raise ValueError("short data chunk")
            return raw[i + 8:i + 8 + n]
        i += 8 + n + (n & 1)
    raise ValueError("no data chunk")


def load_golden(root):
    """WP-11 references, authenticated by SHA256SUMS. Any failure is a usage error."""
    try:
        sums_raw = open(os.path.join(root, "SHA256SUMS"), "rb").read()
        manifest_raw = open(os.path.join(root, "MANIFEST"), "rb").read()
    except OSError as e:
        raise Usage("unreadable --golden: %s" % e)
    sums = {}
    for line in sums_raw.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 2:
            sums[parts[1].lstrip("*")] = parts[0]
    if sums.get("MANIFEST") != sha(manifest_raw):
        raise Usage("--golden MANIFEST does not match its SHA256SUMS")
    refs = {}
    for line in manifest_raw.decode("utf-8").splitlines():
        if not line or line.startswith("#") or line.split()[0] not in F1_CASES:
            continue
        name = line.split()[0]
        last = line.split(" && ")[-1].split()
        opt = lambda flag, default=None: last[last.index(flag) + 1] if flag in last else default
        if "play" in last:
            if opt("--rate") != "1":
                raise Usage("--golden case %s is not a 1x play" % name)
            side, start, frames = opt("--side", "A"), opt("--from", "0"), opt("--frames", "0")
        elif "dump" in last:
            side, start, frames = opt("--side", "A"), "0", "0"
        else:
            raise Usage("--golden case %s has no play or dump step" % name)
        try:
            raw = open(os.path.join(root, "ref", name + ".wav"), "rb").read()
        except OSError as e:
            raise Usage("unreadable --golden reference: %s" % e)
        if sums.get("ref/%s.wav" % name) != sha(raw):
            raise Usage("--golden ref/%s.wav does not match its SHA256SUMS" % name)
        try:
            pcm = wav_payload(raw)
        except ValueError as e:
            raise Usage("--golden ref/%s.wav: %s" % (name, e))
        refs[name] = dict(wav_sha256=sha(raw), pcm=pcm, pcm_sha256=sha(pcm), frames=len(pcm) // 4,
                          side=side, start=start, count=frames)
    if set(refs) != set(F1_CASES):
        raise Usage("--golden MANIFEST lacks F1 cases: %s" % sorted(set(F1_CASES) - set(refs)))
    return dict(refs=refs, sha256sums_sha256=sha(sums_raw), manifest_sha256=sha(manifest_raw))


# ---- transcript grammar -----------------------------------------------------

def parse_transcript(raw):
    """Return (events, error). Events are (kind, match) for lines and
    ("pcm_data", bytes, frames) for a stream region."""
    events, i = [], 0
    while i < len(raw):
        j = raw.find(b"\n", i)
        if j < 0:
            return events, "transcript_truncated"
        line = raw[i:j]
        i = j + 1
        if line.endswith(b"\r"):
            line = line[:-1]
        try:
            text = line.decode("ascii")
        except UnicodeDecodeError:
            return events, "transcript_malformed"
        for kind, rx in LINES:
            m = rx.fullmatch(text)
            if m:
                break
        else:
            return events, "line_unknown"
        events.append((kind, m))
        if kind == "pcm":
            data, frames = bytearray(), 0
            while True:
                if i + 4 > len(raw):
                    return events, "transcript_truncated"
                n = struct.unpack_from("<I", raw, i)[0]
                i += 4
                if n == 0:
                    break
                if i + 4 * n > len(raw):
                    return events, "transcript_truncated"
                data += raw[i:i + 4 * n]
                frames += n
                i += 4 * n
            events.append(("pcm_data", bytes(data), frames))
    return events, None


# ---- manifest schema --------------------------------------------------------

is_str = lambda v: isinstance(v, str)
is_int = lambda v: isinstance(v, int) and not isinstance(v, bool)
opt_str = lambda v: v is None or isinstance(v, str)
hex40 = lambda v: is_str(v) and HEX40.fullmatch(v) is not None
hex64 = lambda v: is_str(v) and HEX64.fullmatch(v) is not None


def check_keys(obj, required, optional, j):
    """Closed-object check. Returns False if obj is not a dict."""
    if not isinstance(obj, dict):
        j.add("INVALID", "field_type")
        return False
    for k in obj:
        if k not in required and k not in optional:
            j.add("INVALID", "field_unknown")
    for k, ok in required.items():
        if k not in obj:
            j.add("INVALID", "field_missing")
        elif not ok(obj[k]):
            j.add("INVALID", "field_type")
    for k, ok in optional.items():
        if k in obj and not ok(obj[k]):
            j.add("INVALID", "field_type")
    return True


def safe_path(p):
    if not is_str(p) or not p or "\\" in p or p.startswith("/") or re.match(r"[A-Za-z]:", p):
        return False
    return all(seg not in ("", ".", "..") for seg in p.split("/"))


COMMON = {"id": is_str, "criterion": lambda v: v in CRITERIA,
          "provenance": lambda v: v in ("actual", "simulated", "not_run"), "sequence": is_int}
COMMON_OPT = {"superseded_by": is_str, "supersede_reason": is_str, "note": is_str}
CARD = {"manufacturer": is_str, "part_number": is_str, "capacity_bytes": is_int, "revision": is_str, "cid": opt_str}
WITNESS = {"name": is_str, "statement": is_str, "present_for": lambda v: isinstance(v, list) and all(map(is_str, v))}
FIELDS = {
    "F1": {"case": is_str, "mode": lambda v: v in ("golden", "stream", "live"), "command": is_str,
           "reference_wav_sha256": hex64, "transcript": is_str},
    "F2": {"size_gate": is_str, "sha256sums": is_str, "transcript": opt_str},
    "F3": {},
    "F4": {},
    "F5": {"transcript": opt_str, "witness": lambda v: v is None or isinstance(v, dict),
           "card_before": lambda v: v is None or isinstance(v, dict),
           "card_after": lambda v: v is None or isinstance(v, dict),
           "verify_command": opt_str, "verify_stdout": opt_str,
           "verify_exit": lambda v: v is None or is_int(v)},
}


# ---- the checker ------------------------------------------------------------

class Checker:
    def __init__(self, bundle, golden):
        self.bundle = bundle
        self.golden = golden
        self.top = Judged()         # manifest, file, candidate and provenance problems
        self.files = []
        self.content = {}           # listed, safe, present path -> bytes
        self.listed = {}            # listed path -> entry state Judged
        self.observations = []
        self.criteria = {}

    # files referenced by observations
    def ref_bytes(self, path, j):
        if not safe_path(path):
            j.add("INVALID", "path_unsafe")
            return None
        if path not in self.listed:
            j.add("INVALID", "file_unlisted")
            return None
        if path not in self.content:
            j.add("INVALID", "file_missing")
            return None
        return self.content[path]

    def run(self):
        mpath = os.path.join(self.bundle, "manifest.json")
        if not os.path.isfile(mpath):
            self.top.add("INVALID", "manifest_missing")
            return self.finish(None)
        raw = open(mpath, "rb").read()
        self.manifest_sha256 = sha(raw)
        try:
            m = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self.top.add("INVALID", "manifest_unreadable")
            return self.finish(None)
        if not isinstance(m, dict):
            self.top.add("INVALID", "manifest_unreadable")
            return self.finish(None)
        self.check_manifest(m)
        return self.finish(m)

    def check_manifest(self, m):
        top = self.top
        if m.get("schema") != SESSION_SCHEMA:
            top.add("INVALID", "schema_unknown")
        check_keys(m, {"schema": is_str, "session": lambda v: isinstance(v, dict),
                       "candidate": lambda v: isinstance(v, dict), "target": lambda v: isinstance(v, dict),
                       "requested": lambda v: isinstance(v, list), "files": lambda v: isinstance(v, list),
                       "observations": lambda v: isinstance(v, list)}, {}, top)
        session = m.get("session") if isinstance(m.get("session"), dict) else {}
        check_keys(session, {"id": is_str, "kind": lambda v: v in ("physical", "simulation"),
                             "timestamp": lambda v: is_str(v) and RFC3339.fullmatch(v) is not None,
                             "operator": is_str, "witness": opt_str,
                             "capture_tool": lambda v: isinstance(v, dict)}, {}, top)
        if isinstance(session.get("capture_tool"), dict):
            check_keys(session["capture_tool"], {"name": is_str, "version": is_str}, {}, top)
        self.kind = session.get("kind")
        if self.kind == "simulation" and session.get("witness") is not None:
            top.add("INVALID", "witness_on_simulation")
        candidate = m.get("candidate") if isinstance(m.get("candidate"), dict) else {}
        check_keys(candidate, {"product_commit": hex40, "engine_tree": hex40, "firmware_hex_sha256": hex64,
                               "toolchain": lambda v: isinstance(v, dict)}, {}, top)
        self.candidate = candidate
        if "engine_tree" in candidate and candidate["engine_tree"] != ENGINE_TREE:
            top.add("MISMATCH", "engine_tree_mismatch")
        if isinstance(candidate.get("toolchain"), dict):
            tc = candidate["toolchain"]
            if check_keys(tc, {k: is_str for k in TOOLCHAIN}, {}, top) and \
                    any(tc.get(k) != v for k, v in TOOLCHAIN.items() if is_str(tc.get(k))):
                top.add("MISMATCH", "toolchain_mismatch")
        if isinstance(m.get("target"), dict):
            check_keys(m["target"], {"board": is_str, "board_revision": opt_str, "audio_board": opt_str}, {}, top)
        requested = m.get("requested")
        if not isinstance(requested, list) or not requested or len(set(map(str, requested))) != len(requested) \
                or any(r not in CRITERIA for r in requested):
            top.add("INVALID", "requested_invalid")
            self.requested = [r for r in requested if r in CRITERIA] if isinstance(requested, list) else []
        else:
            self.requested = list(requested)
        if not FIRST_SESSION <= set(self.requested):
            top.note("requested_missing_first_session")
        self.check_files(m.get("files") if isinstance(m.get("files"), list) else [])
        self.check_observations(m.get("observations") if isinstance(m.get("observations"), list) else [])

    def check_files(self, entries):
        fw = self.candidate.get("firmware_hex_sha256")
        for e in entries:
            j = Judged()
            rec = dict(path=None, sha256=None, declared_sha256=None)
            if check_keys(e, {"path": is_str, "sha256": hex64, "bytes": lambda v: is_int(v) and v >= 0},
                          {"release_asset": is_str}, j):
                path = e.get("path")
                rec.update(path=path, declared_sha256=e.get("sha256"))
                if not safe_path(path) or path in self.listed or path == "manifest.json":
                    j.add("INVALID", "path_unsafe")
                else:
                    self.listed[path] = j
                    full = os.path.join(self.bundle, *path.split("/"))
                    if not os.path.isfile(full):
                        j.add("INVALID", "file_missing")
                    else:
                        data = open(full, "rb").read()
                        self.content[path] = data
                        rec["sha256"] = sha(data)
                        if rec["sha256"] != e.get("sha256"):
                            j.add("MISMATCH", "file_digest_mismatch")
                        if len(data) != e.get("bytes"):
                            j.add("MISMATCH", "file_size_mismatch")
                    if path == "firmware.hex" and hex64(fw) and \
                            (e.get("sha256") != fw or rec["sha256"] not in (None, fw)):
                        j.add("MISMATCH", "candidate_conflict")
            rec.update(state=j.state, reasons=j.reasons)
            self.files.append(rec)
            for code in j.reasons:
                self.top.add(j.state if code in ("path_unsafe", "file_missing", "field_type", "field_unknown",
                                                 "field_missing") else "MISMATCH", code)
        for dirpath, _dirs, names in os.walk(self.bundle):
            for n in names:
                rel = os.path.relpath(os.path.join(dirpath, n), self.bundle).replace(os.sep, "/")
                if rel != "manifest.json" and rel not in self.listed:
                    self.top.add("INVALID", "file_unlisted")
                    self.files.append(dict(path=rel, sha256=None, declared_sha256=None,
                                           state="INVALID", reasons=["file_unlisted"]))

    def check_observations(self, obs):
        top = self.top
        ids, seqs = {}, set()
        valid = []
        for o in obs:
            j = Judged()
            if not isinstance(o, dict):
                top.add("INVALID", "field_type")
                continue
            crit, prov = o.get("criterion"), o.get("provenance")
            if prov == "not_run":
                check_keys(o, dict(COMMON, reason=is_str), {}, j)
            else:
                check_keys(o, COMMON, dict(COMMON_OPT, **FIELDS.get(crit, {})), j)
                for k in FIELDS.get(crit, {}):
                    if k not in o:
                        j.add("INVALID", "field_missing")
            if self.kind == "simulation" and prov == "actual":
                top.add("INVALID", "provenance_conflict")
            if (prov == "simulated" or self.kind == "simulation") and o.get("witness") is not None:
                top.add("INVALID", "witness_on_simulation")
            oid, seq = o.get("id"), o.get("sequence")
            if is_str(oid):
                if oid in ids:
                    top.add("INVALID", "sequence_invalid")
                ids[oid] = o
            if is_int(seq):
                if seq in seqs:
                    top.add("INVALID", "sequence_invalid")
                seqs.add(seq)
            if j.reasons:
                top.add("INVALID", j.reasons[0])
            valid.append((o, j))
        for o, j in valid:
            if "supersede_reason" in o and "superseded_by" not in o:
                top.add("INVALID", "supersede_invalid")
            if "superseded_by" in o:
                t = ids.get(o["superseded_by"])
                if t is None or "supersede_reason" not in o or t is o or t.get("criterion") != o.get("criterion") \
                        or (o.get("criterion") == "F1" and t.get("case") != o.get("case")) \
                        or not (is_int(t.get("sequence")) and is_int(o.get("sequence"))
                                and t["sequence"] > o["sequence"]):
                    top.add("INVALID", "supersede_invalid")
        self.raw_obs = valid

    # ---- per-criterion judgements --------------------------------------------

    def judge_f1(self, o, j):
        refs = self.golden["refs"]
        case, mode = o.get("case"), o.get("mode")
        if case not in F1_CASES:
            j.add("INVALID", "f1_case_unknown")
            ref = None
        else:
            ref = refs[case]
            if o.get("reference_wav_sha256") != ref["wav_sha256"]:
                j.add("MISMATCH", "f1_reference_mismatch")
            if mode == "live":
                want = "live %s %s" % (ref["side"], ref["start"])
            else:
                want = "%s %s %s %s" % (mode, ref["side"], ref["start"], ref["count"])
            if o.get("command") != want:
                j.add("MISMATCH", "f1_command_mismatch")
        raw = self.ref_bytes(o.get("transcript"), j) if is_str(o.get("transcript")) else None
        if raw is None:
            return
        events, err = parse_transcript(raw)
        if err:
            j.add("INVALID", err)
            return
        kinds = [e[0] for e in events]
        digests = [i for i, k in enumerate(kinds) if k == "digest"]
        regions = [i for i, k in enumerate(kinds) if k == "pcm_data"]
        under = [i for i, k in enumerate(kinds) if k == "underruns"]
        if len(digests) != 1 or digests[0] != len(events) - 1 \
                or len(regions) != (1 if mode == "stream" else 0) \
                or len(under) != (1 if mode == "live" else 0) \
                or (mode == "live" and under[0] != len(events) - 2):
            j.add("INVALID", "transcript_malformed")
            return
        dg = events[-1][1]
        digest, frames, result = dg.group(1), int(dg.group(2)), int(dg.group(3))
        if result != 0:
            j.add("MISMATCH", "f1_result_error")
        if ref is None:
            return
        if frames != ref["frames"]:
            j.add("MISMATCH", "f1_frames_mismatch")
        if digest != ref["pcm_sha256"]:
            j.add("MISMATCH", "f1_digest_mismatch")
        if mode == "stream":
            _, data, run_frames = events[regions[0]]
            if data != ref["pcm"]:
                j.add("MISMATCH", "f1_stream_mismatch")
                n = min(len(data), len(ref["pcm"]))
                first = next((k for k in range(n) if data[k] != ref["pcm"][k]), n)
                j.first_difference_frame = first // 4
            if sha(data) != digest or run_frames != frames:
                j.add("MISMATCH", "f1_stream_digest_conflict")
        if mode == "live" and int(events[under[0]][1].group(1)) != 0:
            j.add("MISMATCH", "f1_underruns")

    def judge_f2(self, o, j, workload_max):
        measured = dict(instance=None, reserve=None, stack_high_water=None, ram=None, rodata=None)
        j.measured = measured
        static = None
        gate = self.ref_bytes(o.get("size_gate"), j) if is_str(o.get("size_gate")) else None
        if gate is not None:
            static = self.parse_size_gate(gate, j)
            if static:
                measured.update(ram=static["ram"], rodata=static["rodata"])
        sums = self.ref_bytes(o.get("sha256sums"), j) if is_str(o.get("sha256sums")) else None
        if sums is not None:
            entry = None
            for line in sums.decode("utf-8", "replace").splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1].lstrip("*") == "firmware.hex":
                    entry = parts[0]
            if entry is None:
                j.add("INVALID", "f2_static_malformed")
            elif entry != self.candidate.get("firmware_hex_sha256"):
                j.add("MISMATCH", "candidate_conflict")
        if o.get("transcript") is None:
            j.add("NOT_RUN", "f2_stack_missing")
            return
        if not (is_int(o.get("sequence")) and o["sequence"] > workload_max):
            j.add("INVALID", "f2_stack_before_workload")
        raw = self.ref_bytes(o.get("transcript"), j)
        if raw is None:
            return
        events, err = parse_transcript(raw)
        if err:
            j.add("INVALID", err)
            return
        if any(k == "fatal" for k, *_ in events):
            j.add("MISMATCH", "f2_fatal")
        infos = [e[1] for e in events if e[0] == "info"]
        if not infos:
            j.add("INVALID", "transcript_malformed")
            return
        info = infos[-1]
        instance, reserve, stack = int(info.group(2)), int(info.group(3)), int(info.group(7))
        measured.update(instance=instance, reserve=reserve, stack_high_water=stack)
        if static and reserve != static["instance"]:
            j.add("MISMATCH", "f2_reserve_mismatch")
        if instance > reserve:
            j.add("MISMATCH", "f2_instance_exceeds_reserve")
        if stack <= 0 or stack % 4:
            j.add("INVALID", "f2_stack_invalid")
        elif stack > STACK_BUDGET:
            j.add("MISMATCH", "f2_stack_exceeds")

    @staticmethod
    def parse_size_gate(raw, j):
        try:
            text = raw.decode("ascii")
        except UnicodeDecodeError:
            j.add("INVALID", "f2_static_malformed")
            return None
        pats = {
            "data": r"^\s*engine \.data\s+(\d+)\s*$",
            "bss": r"^\s*engine \.bss\s+(\d+)\s*$",
            "common": r"^\s*engine COMMON\s+(\d+)\s*$",
            "instance": r"^\s*instance\s+(\d+)\s+\(",
            "ram": r"^\s*RAM\s+(\d+) / %d bytes" % RAM_BUDGET,
            "rodata": r"^\s*engine \.rodata\s+(\d+) / %d bytes" % RODATA_BUDGET,
        }
        v = {}
        for k, rx in pats.items():
            found = re.findall(rx, text, re.M)
            if len(found) != 1:
                j.add("INVALID", "f2_static_malformed")
                return None
            v[k] = int(found[0])
        if not re.search(r"^PASS  both budgets\s*$", text, re.M) or re.search(r"^FAIL", text, re.M):
            j.add("MISMATCH", "f2_static_fail")
        if v["ram"] != v["data"] + v["bss"] + v["common"] + v["instance"]:
            j.add("MISMATCH", "f2_ram_sum_mismatch")
        if v["ram"] > RAM_BUDGET or v["rodata"] > RODATA_BUDGET:
            j.add("MISMATCH", "f2_static_fail")
        return v

    def judge_f5(self, o, j):
        # 1-3: transcript, sequence, line values
        if o.get("transcript") is None:
            j.add("NOT_RUN", "f5_transcript_missing")
        else:
            raw = self.ref_bytes(o.get("transcript"), j)
            if raw is not None:
                events, err = parse_transcript(raw)
                if err:
                    j.add("INVALID", err)
                else:
                    self.f5_sequence([e for e in events if e[0] != "pcm_data"], j)
        # 4: witness
        w = o.get("witness")
        if w is None:
            j.add("NOT_RUN", "f5_witness_missing")
        elif check_keys(w, WITNESS, {}, j) and not {"play_stop", "removal", "verify"} <= set(w.get("present_for") or []):
            j.add("NOT_RUN", "f5_witness_missing")
        # 5: card identity
        before, after = o.get("card_before"), o.get("card_after")
        if before is None or after is None:
            j.add("NOT_RUN", "f5_card_identity_missing")
        elif check_keys(before, CARD, {}, j) & check_keys(after, CARD, {}, j):
            if before != after:
                j.add("MISMATCH", "f5_card_identity_changed")
            if before.get("cid") is None and after.get("cid") is None:
                j.note("f5_cid_unknown")
        # 6: manual verify
        vals = [o.get("verify_command"), o.get("verify_stdout"), o.get("verify_exit")]
        if all(v is None for v in vals):
            j.add("NOT_RUN", "f5_verify_missing")
        elif any(v is None for v in vals):
            j.add("INVALID", "field_type")
        else:
            out = self.ref_bytes(o["verify_stdout"], j)
            if out is not None:
                try:
                    text = out.decode("ascii")
                except UnicodeDecodeError:
                    text = None
                lines = text.replace("\r\n", "\n").split("\n") if text is not None else None
                if lines and lines[-1] == "":
                    lines.pop()
                if not lines or any(VERIFY_LINE.fullmatch(x) is None for x in lines):
                    j.add("INVALID", "f5_verify_malformed")
                elif lines != ["OK"] or o["verify_exit"] != 0:
                    j.add("MISMATCH", "f5_verify_findings")

    @staticmethod
    def f5_sequence(lines, j):
        def find(start, pred):
            for i in range(start, len(lines)):
                if pred(i):
                    return i
            return None
        is_ = lambda kind, value=None: lambda i: lines[i][0] == kind and \
            (value is None or lines[i][1].group(1) == value)
        stop_pos = lambda i: lines[i][0] == "stop" and lines[i][1].group(1) == "0" \
            and i + 1 < len(lines) and lines[i + 1][0] == "position"
        at = find(0, lambda i: lines[i][0] == "mounted" and lines[i][1].group(1) == "A")
        positions, plays = [], []
        steps = ["play", "stop", "play", "stop", "play"]
        for step in steps:
            if at is None:
                break
            if step == "play":
                at = find(at + 1, is_("play", "0"))
                if at is not None:
                    plays.append(at)
            else:
                at = find(at + 1, stop_pos)
                if at is not None:
                    positions.append(int(lines[at + 1][1].group(1)))
                    at += 1
        gone = find(at + 1, lambda i: lines[i][0] == "gone" and lines[i][1].group(1) in
                    ("removed", "service failed")) if at is not None else None
        if gone is None:
            j.add("NOT_RUN", "f5_sequence_missing")
        else:
            if not (0 < positions[0] < positions[1]):
                j.add("MISMATCH", "f5_position_not_increasing")
            last_play = max(i for i in range(gone) if lines[i][0] == "play" and lines[i][1].group(1) == "0")
            if any(lines[i][0] in ("stop", "end") for i in range(last_play + 1, gone)):
                j.add("MISMATCH", "f5_removal_not_mid_play")
        if any(k in ("play_failed", "render_failed") for k, _ in lines):
            j.add("MISMATCH", "f5_play_failed")

    # ---- aggregation and report ----------------------------------------------

    def finish(self, m):
        obs_reports, by_crit = [], {c: [] for c in CRITERIA}
        superseded_failures = {c: [] for c in CRITERIA}
        valid = getattr(self, "raw_obs", [])
        workload_max = max([o["sequence"] for o, _ in valid if o.get("criterion") in ("F1", "F5")
                            and o.get("provenance") in ("actual", "simulated") and is_int(o.get("sequence"))],
                           default=-1)
        for o, j in valid:
            crit, prov = o.get("criterion"), o.get("provenance")
            if prov == "not_run":
                j.add("NOT_RUN", "not_run_declared")
            elif not j.reasons:
                if crit == "F1":
                    self.judge_f1(o, j)
                elif crit == "F2":
                    self.judge_f2(o, j, workload_max)
                elif crit == "F5":
                    self.judge_f5(o, j)
            if prov == "simulated":
                j.note("simulated_not_physical")
            sources = {}
            for k in ("transcript", "size_gate", "sha256sums", "verify_stdout"):
                p = o.get(k)
                if is_str(p) and p in self.content:
                    sources[k] = dict(path=p, sha256=sha(self.content[p]))
            rec = dict(id=o.get("id"), criterion=crit, provenance=prov, sequence=o.get("sequence"),
                       state=j.state, reasons=j.reasons, superseded_by=o.get("superseded_by"), sources=sources)
            if crit == "F1":
                rec["case"] = o.get("case")
                rec["mode"] = o.get("mode")
            if hasattr(j, "first_difference_frame"):
                rec["first_difference_frame"] = j.first_difference_frame
            obs_reports.append(rec)
            if crit in CRITERIA:
                if "superseded_by" in o:
                    if j.state in ("INVALID", "MISMATCH"):
                        superseded_failures[crit].append(o.get("id"))
                else:
                    by_crit[crit].append((o, j))

        criteria = {}
        for c in CRITERIA:
            cj = Judged()
            deciders = by_crit[c]
            entry = dict(observations=[o.get("id") for o, _ in deciders],
                         superseded_failures=superseded_failures[c])
            if c in ("F3", "F4"):
                criteria[c] = dict(entry, state="NOT_RUN",
                                   reasons=["f3_method_pending" if c == "F3" else "f4_deferred"])
                continue
            if not deciders:
                cj.add("NOT_RUN", "observation_absent")
            for o, j in deciders:
                cj.state = worst(cj.state, j.state)
                for r in j.reasons:
                    cj.note(r)
            if c == "F1":
                cases = {}
                for name in F1_CASES:
                    states = [j.state for o, j in deciders if o.get("case") == name]
                    if not states:
                        cases[name] = "NOT_RUN"
                        if deciders:
                            cj.add("NOT_RUN", "f1_case_missing")
                    else:
                        cases[name] = worst(*states)
                entry.update(cases=cases, scope=F1_SCOPE)
            if c == "F2":
                last = max(deciders, key=lambda d: d[0].get("sequence") if is_int(d[0].get("sequence")) else -1,
                           default=None)
                entry["measured"] = getattr(last[1], "measured", None) if last else None
                if entry["measured"] is None:
                    entry["measured"] = dict(instance=None, reserve=None, stack_high_water=None, ram=None, rodata=None)
            if c == "F5":
                entry["scope"] = F5_SCOPE
            entry.update(state=cj.state, reasons=cj.reasons)
            entry["decided_by_actual_only"] = bool(deciders) and all(o.get("provenance") == "actual"
                                                                    for o, _ in deciders)
            criteria[c] = entry

        requested = getattr(self, "requested", [])
        overall = self.top.state
        for c in CRITERIA:
            s = criteria[c]["state"]
            if c in requested or s in ("INVALID", "MISMATCH"):
                overall = worst(overall, s)
        for (o, j) in valid:
            if "superseded_by" in o and j.state in ("INVALID", "MISMATCH"):
                overall = worst(overall, j.state)
        physical_run = getattr(self, "kind", None) == "physical" and \
            any(o.get("provenance") == "actual" for o, _ in valid)
        complete = physical_run and set(requested) == FIRST_SESSION and len(requested) == 3 \
            and overall == "CONSISTENT" \
            and all(criteria[c]["state"] == "CONSISTENT" and criteria[c]["decided_by_actual_only"]
                    for c in FIRST_SESSION)
        for c in CRITERIA:
            criteria[c].pop("decided_by_actual_only", None)

        session = m.get("session") if isinstance(m, dict) and isinstance(m.get("session"), dict) else {}
        return dict(
            schema=REPORT_SCHEMA,
            tool=dict(name="bench_evidence.py", version=VERSION, sha256=sha(open(__file__, "rb").read())),
            bundle=dict(path=self.bundle, manifest_sha256=getattr(self, "manifest_sha256", None)),
            golden=dict(sha256sums_sha256=self.golden["sha256sums_sha256"],
                        manifest_sha256=self.golden["manifest_sha256"]),
            candidate=getattr(self, "candidate", None),
            session=dict(id=session.get("id"), kind=session.get("kind")),
            requested=requested,
            overall=overall,
            physical_run=physical_run,
            complete=complete,
            reasons=self.top.reasons,
            files=self.files,
            observations=obs_reports,
            criteria=criteria,
        )


def main(argv=None):
    ap = Parser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--offline", required=True, metavar="BUNDLE")
    ap.add_argument("--out", required=True, metavar="REPORT.json")
    ap.add_argument("--golden", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "..", "..", "..", "tests", "golden"))
    try:
        a = ap.parse_args(argv)
        bundle = os.path.realpath(a.offline)
        out = os.path.realpath(a.out)
        if not os.path.isdir(bundle):
            raise Usage("BUNDLE is not a directory")
        if out == bundle or out.startswith(bundle + os.sep):
            raise Usage("--out must not be inside BUNDLE")
        if not os.path.isdir(os.path.dirname(out)):
            raise Usage("--out directory does not exist")
        golden = load_golden(os.path.realpath(a.golden))
    except Usage as e:
        sys.stderr.write("bench_evidence: usage error: %s\n" % e)
        return 64
    report = Checker(bundle, golden).run()
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print("%s  physical_run=%s complete=%s  %s" % (report["overall"], str(report["physical_run"]).lower(),
                                                    str(report["complete"]).lower(), out))
    return {"INVALID": 2, "MISMATCH": 1}.get(report["overall"], 0)


if __name__ == "__main__":
    sys.exit(main())
