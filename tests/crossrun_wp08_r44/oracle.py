"""DRAFT-9 independent multi-run Q16.16 playback property oracle."""
from __future__ import annotations

import hashlib
import json
import struct
import zlib
from dataclasses import dataclass

SEED = 0xA51CE55D
RUN_LENGTHS = (5, 3, 7, 2)  # nonconstant, short final run
ONE = 1 << 32
RATES = (65536, -65536, 32768, -32768, 98304, -98304, 0x7FFFFFFF, -0x80000000)


def need(ok, msg):
    if not ok:
        raise AssertionError(msg)


def pcm(frames):
    return b"".join(struct.pack("<hh", *f) for f in frames)


def fixture():
    x = SEED
    runs = []
    for n in RUN_LENGTHS:
        run = []
        for _ in range(n):
            x ^= (x << 13) & 0xFFFFFFFF
            x ^= x >> 17
            x ^= (x << 5) & 0xFFFFFFFF
            x &= 0xFFFFFFFF
            run.append(((x & 65535) - 32768, ((x >> 16) & 65535) - 32768))
        runs.append(run)
    frames = [f for run in runs for f in run]
    need(len(frames) == 17 and len(set(frames)) == 17, "nonconstant fixture")
    return runs, frames


def raw_fixture(snapshot):
    """Decode the mounted media without trusting adapter logical-frame labels."""
    need(set(snapshot) == {"superblock", "B0", "B1", "chunks"}, "raw fixture fields")
    sb = bytes.fromhex(snapshot["superblock"])
    need(len(sb) == 512 and sb[:8] == b"TAPEFS\0\x01" and
         zlib.crc32(sb[:508]) == struct.unpack_from("<I", sb, 508)[0], "raw superblock/CRC")
    total_chunks = struct.unpack_from("<I", sb, 52)[0]
    valid = []
    for name in ("B0", "B1"):
        image = snapshot[name]
        need(set(image) == {"header", "entries"}, "raw index fields")
        h = bytes.fromhex(image["header"])
        e = bytes.fromhex(image["entries"])
        need(len(h) == 512, "raw index header length")
        if h[:8] != b"TAPEIDX\x01":
            continue
        count = struct.unpack_from("<I", h, 16)[0]
        if count > 4096 or len(e) != count * 12 or zlib.crc32(h[:60] + e) != struct.unpack_from("<I", h, 60)[0]:
            continue
        need(h[12] == 1, "B index side")
        seq = struct.unpack_from("<I", h, 8)[0]
        total = struct.unpack_from("<Q", h, 20)[0]
        entries = [struct.unpack_from("<III", e, 12 * j) for j in range(count)]
        need(total == sum(v[2] for v in entries), "index total frames")
        valid.append((seq, name, entries))
    need(bool(valid), "no raw B index")
    if len(valid) == 2:
        need(valid[0][0] != valid[1][0], "equal-sequence raw B")
    _, _, entries = max(valid)
    need(len(entries) == 4 and [e[2] for e in entries] == list(RUN_LENGTHS), "raw four-run mapping")
    need(all(start == 0 and n > 0 and first < total_chunks for first, start, n in entries),
         "run/chunk geometry")
    need(len({first for first, _, _ in entries}) == 4, "physical run overlap")
    expected_lbas = {str(2048 + first * 1024) for first, _, _ in entries}
    need(isinstance(snapshot["chunks"], dict) and set(snapshot["chunks"]) == expected_lbas,
         "raw chunk block mapping")
    frames = []
    for first, _, n in entries:
        b = bytes.fromhex(snapshot["chunks"][str(2048 + first * 1024)])
        need(len(b) == 512 and 4 * n <= len(b), "raw chunk block length")
        frames.extend(struct.unpack_from("<hh", b, 4 * j) for j in range(n))
    return entries, frames


@dataclass(frozen=True)
class Case:
    id: str
    seek: int
    rate: int
    count: int


def cases():
    out = []
    for boundary in (5, 8, 15):
        for offset in (-1, 0, 1):
            for rate in (65536, -65536):
                out.append(Case(f"boundary-{boundary}{offset:+d}-{'f' if rate > 0 else 'r'}",
                                boundary + offset, rate, 8))
    out += [Case(f"fraction-{j}", start, rate, 11) for j, (start, rate) in enumerate((
        (4, 32768), (7, -32768), (14, 98304), (16, -98304),
        (5, -32768), (8, 98304), (15, -98304), (1, 32768)), 1)]
    out += [Case("end-reverse", 17, -65536, 20), Case("start-reverse", 0, -65536, 3),
            Case("end-forward", 17, 65536, 3), Case("beyond-end", 100, 65536, 3),
            Case("zero-rate", 8, 0, 5), Case("huge-forward", 16, 0x7FFFFFFF, 3),
            Case("huge-reverse", 17, -0x80000000, 3)]
    need(len(out) == 33 and len({c.id for c in out}) == 33, "case census")
    return out


def interpolate(a, b, fractional):
    return tuple(a[ch] + ((b[ch] - a[ch]) * fractional // ONE) for ch in (0, 1))


class Transport:
    def __init__(self, frames, seek, rate):
        self.frames = frames
        self.max_pos = len(frames) * ONE
        self.pos = min(seek, len(frames)) * ONE
        self.step = rate * 65536
        self.at_start = False
        self.at_end = False

    def render(self, requested):
        emitted = []
        if not self.frames:
            self.at_end = True
            return emitted
        if self.step == 0:
            return emitted
        if self.step < 0 and self.pos >= self.max_pos:
            self.pos = (len(self.frames) - 1) * ONE
        for _ in range(requested):
            if self.step > 0 and self.pos >= self.max_pos:
                self.at_end = True
                break
            if self.step < 0 and self.at_start:
                break
            i, f = divmod(self.pos, ONE)
            a = self.frames[i]
            b = self.frames[i + 1] if i + 1 < len(self.frames) else a
            emitted.append(interpolate(a, b, f))
            if self.step > 0:
                self.at_start = False
                if self.pos >= self.max_pos or self.step >= self.max_pos - self.pos:
                    self.pos = self.max_pos
                    self.at_end = True
                else:
                    self.pos += self.step
            else:
                self.at_end = False
                s = -self.step
                if self.pos == 0:
                    self.at_start = True
                elif self.pos <= s:
                    self.pos = 0
                else:
                    self.pos -= s
        return emitted


def schedules(count):
    return {"whole": [count], "single": [1] * count,
            "uneven": [3, 2] * (count // 5) + ([count % 5] if count % 5 else [])}


def check(case, obs):
    _, generated = fixture()
    need(obs.get("schema") == "wp08-r44-v1" and obs.get("case") == case.id, "schema/case")
    entries, frames = raw_fixture(obs["raw_media"])
    need(frames == generated, "raw mounted PCM differs from seeded fixture")
    need(obs.get("seek") == case.seek and obs.get("rate") == case.rate, "seek/rate")
    variants = obs.get("variants")
    need(isinstance(variants, dict) and set(variants) == set(schedules(case.count)), "subdivision variants")
    outputs = []
    for label, schedule in schedules(case.count).items():
        v = variants[label]
        need(v.get("render_sizes") == schedule, "render subdivision")
        budget = {"whole": 256, "single": 1, "uneven": 7}[label]
        need(v.get("service_budget") == budget, "service subdivision")
        services = v.get("services")
        need(isinstance(services, list) and bool(services), "missing service calls")
        for service in services:
            events = service.get("events")
            need(isinstance(events, list) and service.get("budget") == budget and
                 service.get("result") == "TAPE_OK", "service public result/trace")
            blocks = 0
            for event in events:
                need(event.get("op") in ("read", "write", "flush"), "unknown callback")
                if event["op"] in ("read", "write"):
                    need(isinstance(event.get("lba"), int) and isinstance(event.get("count"), int)
                         and event["count"] >= 1, "block callback details")
                    blocks += event["count"]
            need(blocks <= budget, "service exceeded block budget in raw callbacks")
        need(services[-1].get("more_work") is False, "service did not complete")
        actual = v.get("renders")
        need(isinstance(actual, list) and len(actual) == len(schedule), "render call count")
        model = Transport(frames, case.seek, case.rate)
        total_pcm = b""
        for j, (request, r) in enumerate(zip(schedule, actual)):
            expected = pcm(model.render(request))
            need(r.get("requested") == request and r.get("result") == "TAPE_OK", "render request/result")
            need(r.get("rendered") == len(expected) // 4 and r.get("pcm_hex") == expected.hex(),
                 f"{label} render {j} exact PCM")
            need(r.get("tell") == model.pos >> 32 and r.get("at_start") is model.at_start
                 and r.get("at_end") is model.at_end, f"{label} render {j} position/endpoint")
            need(r.get("block_events") == [], "render block I/O")
            total_pcm += expected
        outputs.append(total_pcm)
    need(outputs[0] == outputs[1] == outputs[2], "subdivision changed logical output")
    return True


def digest_plan():
    return hashlib.sha256(json.dumps([c.__dict__ for c in cases()], sort_keys=True).encode()).hexdigest()
