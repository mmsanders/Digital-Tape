#!/usr/bin/env python3
"""Independent DRAFT-8 transport extras: tape_set_side + warm-start validation.

No product implementation imports. This package is pre-product verifier work;
it does not claim listened/golden PCM acceptance.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

CF = 131072
SAMPLE_RATE = 44100
NOMINAL_LENGTH_S = 60
CHUNK_BYTES = 524288
BLOCK = 512
BLOCKS_PER_CHUNK = CHUNK_BYTES // BLOCK
SLOT_BYTES = 65536
TAPE_MAX_ENTRIES = 4096
FRAME_BYTES = 4
RATE_1X = 0x00010000
LBA_A0, LBA_A1, LBA_B0, LBA_B1, LBA_CHUNK_BASE = 8, 136, 264, 392, 2048
UUID = bytes(range(16))


@dataclass(frozen=True)
class Media:
    blocks: int
    primary: bytes
    mirror: bytes
    slots: tuple[bytes, bytes, bytes, bytes]

    def encode(self) -> bytes:
        return b"VO08" + struct.pack("<I", self.blocks) + self.primary + self.mirror + b"".join(self.slots)

    @staticmethod
    def decode(data: bytes) -> "Media":
        need = 8 + 2 * BLOCK + 4 * SLOT_BYTES
        if len(data) != need or data[:4] != b"VO08":
            raise ValueError("bad VO08")
        blocks = struct.unpack_from("<I", data, 4)[0]
        p = 8
        primary = data[p : p + BLOCK]
        p += BLOCK
        mirror = data[p : p + BLOCK]
        p += BLOCK
        slots = [data[p + i * SLOT_BYTES : p + (i + 1) * SLOT_BYTES] for i in range(4)]
        return Media(blocks, primary, mirror, tuple(slots))


@dataclass(frozen=True)
class WarmSpec:
    present: bool
    data_present: bool | None
    data_bytes: int | None
    valid_frames: int | None
    start_frame: int | None
    resume_frame: int
    uuid_hex: str | None
    warm_side: str | None
    expect_used: bool


@dataclass(frozen=True)
class Case:
    id: str
    pre: Media
    mount_side: str
    kind: str
    expect: str
    warm: WarmSpec | None = None


def derived_total_chunks() -> int:
    return (NOMINAL_LENGTH_S * SAMPLE_RATE + CF - 1) // CF


def sb(*, high=3) -> bytes:
    chunks = derived_total_chunks()
    blocks = LBA_CHUNK_BASE + chunks * BLOCKS_PER_CHUNK + 1
    b = bytearray(BLOCK)
    b[:8] = b"TAPEFS\0\x01"
    struct.pack_into("<H", b, 8, 1)
    struct.pack_into("<H", b, 10, 0)
    struct.pack_into("<I", b, 12, 7)
    b[20:36] = UUID
    struct.pack_into("<I", b, 36, SAMPLE_RATE)
    struct.pack_into("<H", b, 40, 2)
    struct.pack_into("<H", b, 42, 16)
    struct.pack_into("<I", b, 44, CHUNK_BYTES)
    struct.pack_into("<I", b, 48, NOMINAL_LENGTH_S)
    struct.pack_into("<I", b, 52, chunks)
    struct.pack_into("<I", b, 56, high)
    struct.pack_into("<I", b, 60, SLOT_BYTES)
    struct.pack_into("<I", b, 64, LBA_A0)
    struct.pack_into("<I", b, 68, LBA_A1)
    struct.pack_into("<I", b, 72, LBA_B0)
    struct.pack_into("<I", b, 76, LBA_B1)
    struct.pack_into("<I", b, 80, LBA_CHUNK_BASE)
    struct.pack_into("<I", b, 84, blocks - 1)
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return bytes(b)


def idx(side: int, entries, sequence: int) -> bytes:
    b = bytearray(SLOT_BYTES)
    b[:8] = b"TAPEIDX\x01"
    total = sum(e[2] for e in entries)
    struct.pack_into("<IB3xIQ", b, 8, sequence, side, len(entries), total)
    for i, e in enumerate(entries):
        struct.pack_into("<III", b, 512 + 12 * i, *e)
    struct.pack_into("<I", b, 60, zlib.crc32(b[:60] + b[512 : 512 + 12 * len(entries)]))
    return bytes(b)


def invalid_slot() -> bytes:
    return bytes(SLOT_BYTES)


def healthy() -> Media:
    s = sb()
    chunks = derived_total_chunks()
    blocks = LBA_CHUNK_BASE + chunks * BLOCKS_PER_CHUNK + 1
    # Non-empty A is longer than B so the transition's new-side metadata is observable.
    return Media(
        blocks,
        s,
        s,
        (
            idx(0, [(0, 0, 256)], 10),
            invalid_slot(),
            idx(1, [(0, 0, 64)], 20),
            invalid_slot(),
        ),
    )


def degraded() -> Media:
    s = sb()
    chunks = derived_total_chunks()
    blocks = LBA_CHUNK_BASE + chunks * BLOCKS_PER_CHUNK + 1
    return Media(
        blocks,
        s,
        s,
        (
            idx(0, [(0, 0, 256)], 10),
            invalid_slot(),
            idx(1, [(0, 0, 64)], 500),
            idx(1, [(1, 0, 32)], 500),
        ),
    )


def warm_specs() -> list[tuple[str, WarmSpec]]:
    # For every later predicate, all earlier predicates are deliberately valid.
    # This makes the defect under test observable rather than allowing every
    # case to collapse to the first cold-path condition.
    return [
        ("WARM-NULL", WarmSpec(False, None, None, None, None, 40, None, None, False)),
        ("WARM-DATA-NULL", WarmSpec(True, False, 64, 16, 32, 40, UUID.hex(), "A", False)),
        ("WARM-ZERO-FRAMES", WarmSpec(True, True, 64, 0, 32, 32, UUID.hex(), "A", False)),
        ("WARM-SHORT-BUF", WarmSpec(True, True, 63, 16, 32, 40, UUID.hex(), "A", False)),
        ("WARM-PAST-END", WarmSpec(True, True, 64, 16, 250, 250, UUID.hex(), "A", False)),
        # Mandatory V4-011 checked-64-bit shape. 32-bit start+count would wrap.
        ("WARM-U32-OVERFLOW", WarmSpec(True, True, 64, 16, 0xFFFFFFF8, 250, UUID.hex(), "A", False)),
        ("WARM-RESUME-OUT", WarmSpec(True, True, 64, 16, 32, 48, UUID.hex(), "A", False)),
        ("WARM-UUID", WarmSpec(True, True, 64, 16, 32, 40, ("ff" * 16), "A", False)),
        ("WARM-SIDE", WarmSpec(True, True, 64, 16, 32, 40, UUID.hex(), "B", False)),
        # Metadata-positive anchor. This does not assert PCM identity; it only
        # proves a descriptor satisfying every predicate reaches "use".
        ("WARM-VALID-METADATA", WarmSpec(True, True, 64, 16, 32, 40, UUID.hex(), "A", True)),
    ]


def make_cases() -> list[Case]:
    h = healthy()
    d = degraded()
    cases = [
        Case("SS-PLAYING-A-TO-B", h, "A", "set_side_playing", "TAPE_OK"),
        Case("SS-IDLE-A-TO-B", h, "A", "set_side_idle", "TAPE_OK"),
        Case("SS-SAME-A", h, "A", "set_side_same", "TAPE_OK"),
        Case("SS-DEGRADED-B", d, "A", "set_side_degraded", "TAPE_ERR_NO_VALID_INDEX"),
        Case("SS-DEGRADED-SAME-A", d, "A", "set_side_same_degraded", "TAPE_OK"),
        Case("SS-ARMED-BUSY", h, "B", "set_side_armed", "TAPE_ERR_BUSY"),
    ]
    cases.extend(Case(cid, h, "A", "warm", "TAPE_OK", spec) for cid, spec in warm_specs())
    return cases


def fixture_contract_errors(case: Case) -> list[str]:
    err = []
    if derived_total_chunks() != 21:
        err.append("geometry drift")
    if case.pre.primary != case.pre.mirror:
        err.append("fixture superblocks differ")
    if case.pre.primary[20:36] != UUID:
        err.append("fixture uuid drift")
    if case.kind.startswith("set_side") and case.kind != "set_side_degraded":
        # healthy B total 64 / A total 256 is intentional.
        if case.pre.slots[0][:8] != b"TAPEIDX\x01" or case.pre.slots[2][:8] != b"TAPEIDX\x01":
            err.append("healthy fixture lost live indices")
    if case.kind in ("set_side_degraded", "set_side_same_degraded"):
        if case.pre.slots[2][:8] != b"TAPEIDX\x01" or case.pre.slots[3][:8] != b"TAPEIDX\x01":
            err.append("degraded fixture missing B slots")
        if struct.unpack_from("<I", case.pre.slots[2], 8)[0] != struct.unpack_from("<I", case.pre.slots[3], 8)[0]:
            err.append("degraded fixture sequences differ")
        if case.pre.slots[2] == case.pre.slots[3]:
            err.append("degraded fixture B slots not divergent")
    if case.kind == "warm" and case.warm is None:
        err.append("warm case missing descriptor spec")
    return err


def _writes(events):
    return [e for e in events if e.get("op") == "write"]


def _call(calls, fn, phase=None):
    return [c for c in calls if c.get("fn") == fn and (phase is None or c.get("phase") == phase)]


def _req_no_render_io(events, phase, req):
    req(not any(e.get("phase") == phase for e in events), f"{phase} issued block I/O")


def _check_mount(case, calls, req):
    mounts = _call(calls, "tape_mount")
    req(
        len(mounts) == 1
        and mounts[0].get("result") == "TAPE_OK"
        and mounts[0].get("side") == case.mount_side,
        "mount failed or used wrong side",
    )
    return mounts[0] if mounts else {}


def _check_new_side_state(calls, events, req, *, rate_after_switch: bool):
    tells = _call(calls, "tape_tell", "post-switch-tell")
    req(len(tells) == 1 and tells[0].get("result") == "TAPE_OK" and tells[0].get("frame") == 0,
        "set_side did not reset position to 0")

    stats = _call(calls, "tape_status", "post-switch-status")
    req(
        len(stats) == 1
        and stats[0].get("result") == "TAPE_OK"
        and stats[0].get("at_end") is False
        and stats[0].get("at_start") is False,
        "set_side did not clear endpoint flags",
    )

    infos = _call(calls, "tape_get_info", "post-switch-info")
    req(
        len(infos) == 1
        and infos[0].get("result") == "TAPE_OK"
        and infos[0].get("warm_start_used") is False
        and infos[0].get("total_frames") == 64
        and infos[0].get("entry_count") == 1
        and infos[0].get("entries_free") == TAPE_MAX_ENTRIES - 1
        and infos[0].get("side_b_valid") is True,
        "set_side did not expose new-side metadata/cold-ring state",
    )

    if rate_after_switch:
        rates = _call(calls, "tape_set_rate", "post-switch-rate")
        req(len(rates) == 1 and rates[0].get("result") == "TAPE_OK" and rates[0].get("rate_q16_16") == RATE_1X,
            "idle transition did not set +1.0x after switch")

    cold = _call(calls, "tape_render", "pre-service-render")
    req(
        len(cold) == 1
        and cold[0].get("result") == "TAPE_ERR_UNDERRUN"
        and cold[0].get("requested") == 1
        and cold[0].get("rendered") == 0
        and cold[0].get("events_from_call") == 0,
        "pre-service render did not prove ring invalidation with non-zero rate",
    )
    _req_no_render_io(events, "pre-service-render", req)

    services = _call(calls, "tape_service", "post-switch-service")
    req(
        bool(services)
        and all(x.get("result") == "TAPE_OK" for x in services)
        and services[-1].get("more_work") is False,
        "post-switch service did not complete",
    )

    hot = _call(calls, "tape_render", "post-service-render")
    req(
        len(hot) == 1
        and hot[0].get("result") == "TAPE_OK"
        and hot[0].get("requested") == 1
        and hot[0].get("rendered") == 1
        and hot[0].get("events_from_call") == 0,
        "post-service render failed",
    )
    _req_no_render_io(events, "post-service-render", req)

    after = _call(calls, "tape_tell", "post-service-tell")
    req(
        len(after) == 1 and after[0].get("result") == "TAPE_OK" and after[0].get("frame") == 1,
        "retained/+1.0x rate did not advance exactly one frame",
    )


def _check_warm(case: Case, calls, req):
    spec = case.warm
    assert spec is not None
    mounts = _call(calls, "tape_mount")
    if not mounts:
        req(False, "warm case missing mount")
        return
    m = mounts[0]

    # The adapter must report the descriptor actually supplied. This prevents
    # every negative ID from silently using warm==NULL.
    req(m.get("resume_frame") == spec.resume_frame, "warm resume_frame mismatch")
    req(m.get("warm_present") is spec.present, "warm descriptor presence mismatch")
    if spec.present:
        req(m.get("warm_data_present") is spec.data_present, "warm data pointer shape mismatch")
        req(m.get("warm_data_bytes") == spec.data_bytes, "warm data_bytes mismatch")
        req(m.get("warm_valid_frames") == spec.valid_frames, "warm valid_frames mismatch")
        req(m.get("warm_start_frame") == spec.start_frame, "warm start_frame mismatch")
        req(m.get("warm_uuid_hex") == spec.uuid_hex, "warm uuid argument mismatch")
        req(m.get("warm_side") == spec.warm_side, "warm side argument mismatch")
    else:
        for key in (
            "warm_data_present",
            "warm_data_bytes",
            "warm_valid_frames",
            "warm_start_frame",
            "warm_uuid_hex",
            "warm_side",
        ):
            req(key not in m, "NULL warm case exposed descriptor fields")

    req(m.get("warm_start_used") is spec.expect_used, "mount warm_start_used mismatch")
    infos = _call(calls, "tape_get_info", "info")
    req(
        len(infos) == 1
        and infos[0].get("result") == "TAPE_OK"
        and infos[0].get("warm_start_used") is spec.expect_used,
        "info.warm_start_used mismatch",
    )

    tells = _call(calls, "tape_tell", "tell")
    expected_pos = min(spec.resume_frame, 256)
    req(
        len(tells) == 1
        and tells[0].get("result") == "TAPE_OK"
        and tells[0].get("frame") == expected_pos,
        "warm/cold mount did not land at clamped resume_frame",
    )


def check(case: Case, post: Media, events: list[dict], calls: list[dict]) -> list[str]:
    err = []

    def req(cond, msg):
        if not cond:
            err.append(msg)

    req(post.encode() == case.pre.encode(), "transport extras changed media bytes")
    req(not _writes(events), "transport extras issued a write")

    _check_mount(case, calls, req)

    if case.kind == "warm":
        _check_warm(case, calls, req)

    elif case.kind == "set_side_playing":
        rates = _call(calls, "tape_set_rate", "pre-rate")
        req(len(rates) == 1 and rates[0].get("result") == "TAPE_OK" and rates[0].get("rate_q16_16") == RATE_1X,
            "playing setup did not set +1.0x")
        services = _call(calls, "tape_service", "pre-service")
        req(bool(services) and all(x.get("result") == "TAPE_OK" for x in services) and services[-1].get("more_work") is False,
            "playing setup service did not complete")
        renders = _call(calls, "tape_render", "pre-render-to-end")
        req(
            len(renders) == 1
            and renders[0].get("result") == "TAPE_OK"
            and renders[0].get("requested") == 256
            and renders[0].get("rendered") == 256
            and renders[0].get("events_from_call") == 0,
            "playing setup did not render Side A to its end",
        )
        _req_no_render_io(events, "pre-render-to-end", req)
        pre_stats = _call(calls, "tape_status", "pre-status")
        req(
            len(pre_stats) == 1
            and pre_stats[0].get("result") == "TAPE_OK"
            and pre_stats[0].get("at_end") is True,
            "playing transition did not establish at_end before switch",
        )
        hits = _call(calls, "tape_set_side", "set-side")
        req(len(hits) == 1 and hits[0].get("result") == "TAPE_OK" and hits[0].get("side") == "B",
            "playing set_side A->B failed")
        _check_new_side_state(calls, events, req, rate_after_switch=False)

    elif case.kind == "set_side_idle":
        seeks = _call(calls, "tape_seek", "pre-seek")
        req(len(seeks) == 1 and seeks[0].get("result") == "TAPE_OK" and seeks[0].get("frame") == 10,
            "idle transition setup seek mismatch")
        hits = _call(calls, "tape_set_side", "set-side")
        req(len(hits) == 1 and hits[0].get("result") == "TAPE_OK" and hits[0].get("side") == "B",
            "idle set_side A->B failed")
        _check_new_side_state(calls, events, req, rate_after_switch=True)

    elif case.kind in ("set_side_same", "set_side_same_degraded"):
        seeks = _call(calls, "tape_seek", "pre-seek")
        req(len(seeks) == 1 and seeks[0].get("result") == "TAPE_OK" and seeks[0].get("frame") == 10,
            "same-side setup seek mismatch")
        hits = _call(calls, "tape_set_side", "set-side")
        req(len(hits) == 1 and hits[0].get("result") == "TAPE_OK" and hits[0].get("side") == "A",
            "same-side set_side(A) was not allowed")
        tells = _call(calls, "tape_tell", "post-switch-tell")
        req(len(tells) == 1 and tells[0].get("result") == "TAPE_OK" and tells[0].get("frame") == 0,
            "same-side successful transition did not reset position")
        infos = _call(calls, "tape_get_info", "post-switch-info")
        req(
            len(infos) == 1
            and infos[0].get("total_frames") == 256
            and infos[0].get("entry_count") == 1
            and infos[0].get("entries_free") == TAPE_MAX_ENTRIES - 1,
            "same-side metadata wrong",
        )
        if case.kind == "set_side_same_degraded":
            req(infos[0].get("side_b_valid") is False, "same-side degraded call changed degraded-B state")

    elif case.kind == "set_side_degraded":
        seeks = _call(calls, "tape_seek", "pre-seek")
        req(len(seeks) == 1 and seeks[0].get("result") == "TAPE_OK" and seeks[0].get("frame") == 10,
            "degraded setup seek mismatch")
        pre_info = _call(calls, "tape_get_info", "pre-info")
        req(
            len(pre_info) == 1
            and pre_info[0].get("side_b_valid") is False
            and pre_info[0].get("total_frames") == 256,
            "degraded-B premise not observed",
        )
        hits = _call(calls, "tape_set_side", "set-side")
        req(len(hits) == 1 and hits[0].get("result") == "TAPE_ERR_NO_VALID_INDEX" and hits[0].get("side") == "B",
            "degraded set_side(B) refusal mismatch")
        tells = _call(calls, "tape_tell", "post-refusal-tell")
        req(len(tells) == 1 and tells[0].get("result") == "TAPE_OK" and tells[0].get("frame") == 10,
            "degraded set_side refusal changed position")
        post_info = _call(calls, "tape_get_info", "post-refusal-info")
        req(
            len(post_info) == 1
            and post_info[0].get("side_b_valid") is False
            and post_info[0].get("total_frames") == 256,
            "degraded set_side refusal changed mounted-side state",
        )

    elif case.kind == "set_side_armed":
        seeks = _call(calls, "tape_seek", "pre-seek")
        req(len(seeks) == 1 and seeks[0].get("result") == "TAPE_OK" and seeks[0].get("frame") == 10,
            "armed setup seek mismatch")
        arms = _call(calls, "tape_arm", "arm")
        req(len(arms) == 1 and arms[0].get("result") == "TAPE_OK", "armed fixture failed to arm")
        hits = _call(calls, "tape_set_side", "set-side")
        req(len(hits) == 1 and hits[0].get("result") == "TAPE_ERR_BUSY" and hits[0].get("side") == "A",
            "set_side while armed was not BUSY")
        tells = _call(calls, "tape_tell", "post-refusal-tell")
        req(len(tells) == 1 and tells[0].get("result") == "TAPE_OK" and tells[0].get("frame") == 10,
            "armed BUSY changed position")
        infos = _call(calls, "tape_get_info", "post-refusal-info")
        req(len(infos) == 1 and infos[0].get("total_frames") == 64,
            "armed BUSY changed mounted side")
        aborts = _call(calls, "tape_abort", "abort")
        req(len(aborts) == 1 and aborts[0].get("result") == "TAPE_OK", "armed BUSY abort failed")

    unmounts = _call(calls, "tape_unmount", "unmount")
    req(len(unmounts) == 1 and unmounts[0].get("result") == "TAPE_OK", "terminal unmount failed")
    return err


def _warm_mount_record(case: Case) -> dict:
    spec = case.warm
    assert spec is not None
    m = {
        "phase": "mount",
        "fn": "tape_mount",
        "result": "TAPE_OK",
        "side": case.mount_side,
        "resume_frame": spec.resume_frame,
        "warm_present": spec.present,
        "warm_start_used": spec.expect_used,
    }
    if spec.present:
        m.update(
            {
                "warm_data_present": spec.data_present,
                "warm_data_bytes": spec.data_bytes,
                "warm_valid_frames": spec.valid_frames,
                "warm_start_frame": spec.start_frame,
                "warm_uuid_hex": spec.uuid_hex,
                "warm_side": spec.warm_side,
            }
        )
    return m


def synth_observation(case: Case):
    events = []

    if case.kind == "warm":
        spec = case.warm
        assert spec is not None
        calls = [
            _warm_mount_record(case),
            {
                "phase": "info",
                "fn": "tape_get_info",
                "result": "TAPE_OK",
                "warm_start_used": spec.expect_used,
            },
            {
                "phase": "tell",
                "fn": "tape_tell",
                "result": "TAPE_OK",
                "frame": min(spec.resume_frame, 256),
            },
            {"phase": "unmount", "fn": "tape_unmount", "result": "TAPE_OK"},
        ]
        return case.pre, events, calls

    calls = [
        {
            "phase": "mount",
            "fn": "tape_mount",
            "result": "TAPE_OK",
            "side": case.mount_side,
            "resume_frame": 0,
            "warm_present": False,
            "warm_start_used": False,
        }
    ]

    if case.kind == "set_side_playing":
        calls.extend(
            [
                {"phase": "pre-rate", "fn": "tape_set_rate", "result": "TAPE_OK", "rate_q16_16": RATE_1X},
                {"phase": "pre-service", "fn": "tape_service", "result": "TAPE_OK", "more_work": False},
                {
                    "phase": "pre-render-to-end",
                    "fn": "tape_render",
                    "result": "TAPE_OK",
                    "requested": 256,
                    "rendered": 256,
                    "events_from_call": 0,
                },
                {"phase": "pre-status", "fn": "tape_status", "result": "TAPE_OK", "at_end": True, "at_start": False},
                {"phase": "set-side", "fn": "tape_set_side", "result": "TAPE_OK", "side": "B"},
                {"phase": "post-switch-tell", "fn": "tape_tell", "result": "TAPE_OK", "frame": 0},
                {"phase": "post-switch-status", "fn": "tape_status", "result": "TAPE_OK", "at_end": False, "at_start": False},
                {
                    "phase": "post-switch-info",
                    "fn": "tape_get_info",
                    "result": "TAPE_OK",
                    "warm_start_used": False,
                    "total_frames": 64,
                    "entry_count": 1,
                    "entries_free": TAPE_MAX_ENTRIES - 1,
                    "side_b_valid": True,
                },
                {
                    "phase": "pre-service-render",
                    "fn": "tape_render",
                    "result": "TAPE_ERR_UNDERRUN",
                    "requested": 1,
                    "rendered": 0,
                    "events_from_call": 0,
                },
                {"phase": "post-switch-service", "fn": "tape_service", "result": "TAPE_OK", "more_work": False},
                {
                    "phase": "post-service-render",
                    "fn": "tape_render",
                    "result": "TAPE_OK",
                    "requested": 1,
                    "rendered": 1,
                    "events_from_call": 0,
                },
                {"phase": "post-service-tell", "fn": "tape_tell", "result": "TAPE_OK", "frame": 1},
            ]
        )

    elif case.kind == "set_side_idle":
        calls.extend(
            [
                {"phase": "pre-seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": 10},
                {"phase": "set-side", "fn": "tape_set_side", "result": "TAPE_OK", "side": "B"},
                {"phase": "post-switch-tell", "fn": "tape_tell", "result": "TAPE_OK", "frame": 0},
                {"phase": "post-switch-status", "fn": "tape_status", "result": "TAPE_OK", "at_end": False, "at_start": False},
                {
                    "phase": "post-switch-info",
                    "fn": "tape_get_info",
                    "result": "TAPE_OK",
                    "warm_start_used": False,
                    "total_frames": 64,
                    "entry_count": 1,
                    "entries_free": TAPE_MAX_ENTRIES - 1,
                    "side_b_valid": True,
                },
                {"phase": "post-switch-rate", "fn": "tape_set_rate", "result": "TAPE_OK", "rate_q16_16": RATE_1X},
                {
                    "phase": "pre-service-render",
                    "fn": "tape_render",
                    "result": "TAPE_ERR_UNDERRUN",
                    "requested": 1,
                    "rendered": 0,
                    "events_from_call": 0,
                },
                {"phase": "post-switch-service", "fn": "tape_service", "result": "TAPE_OK", "more_work": False},
                {
                    "phase": "post-service-render",
                    "fn": "tape_render",
                    "result": "TAPE_OK",
                    "requested": 1,
                    "rendered": 1,
                    "events_from_call": 0,
                },
                {"phase": "post-service-tell", "fn": "tape_tell", "result": "TAPE_OK", "frame": 1},
            ]
        )

    elif case.kind in ("set_side_same", "set_side_same_degraded"):
        calls.extend(
            [
                {"phase": "pre-seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": 10},
                {"phase": "set-side", "fn": "tape_set_side", "result": "TAPE_OK", "side": "A"},
                {"phase": "post-switch-tell", "fn": "tape_tell", "result": "TAPE_OK", "frame": 0},
                {
                    "phase": "post-switch-info",
                    "fn": "tape_get_info",
                    "result": "TAPE_OK",
                    "warm_start_used": False,
                    "total_frames": 256,
                    "entry_count": 1,
                    "entries_free": TAPE_MAX_ENTRIES - 1,
                    "side_b_valid": case.kind != "set_side_same_degraded",
                },
            ]
        )

    elif case.kind == "set_side_degraded":
        calls.extend(
            [
                {"phase": "pre-seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": 10},
                {
                    "phase": "pre-info",
                    "fn": "tape_get_info",
                    "result": "TAPE_OK",
                    "side_b_valid": False,
                    "total_frames": 256,
                },
                {"phase": "set-side", "fn": "tape_set_side", "result": "TAPE_ERR_NO_VALID_INDEX", "side": "B"},
                {"phase": "post-refusal-tell", "fn": "tape_tell", "result": "TAPE_OK", "frame": 10},
                {
                    "phase": "post-refusal-info",
                    "fn": "tape_get_info",
                    "result": "TAPE_OK",
                    "side_b_valid": False,
                    "total_frames": 256,
                },
            ]
        )

    elif case.kind == "set_side_armed":
        calls.extend(
            [
                {"phase": "pre-seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": 10},
                {"phase": "arm", "fn": "tape_arm", "result": "TAPE_OK", "mode": "overwrite"},
                {"phase": "set-side", "fn": "tape_set_side", "result": "TAPE_ERR_BUSY", "side": "A"},
                {"phase": "post-refusal-tell", "fn": "tape_tell", "result": "TAPE_OK", "frame": 10},
                {
                    "phase": "post-refusal-info",
                    "fn": "tape_get_info",
                    "result": "TAPE_OK",
                    "total_frames": 64,
                    "side_b_valid": True,
                },
                {"phase": "abort", "fn": "tape_abort", "result": "TAPE_OK"},
            ]
        )

    calls.append({"phase": "unmount", "fn": "tape_unmount", "result": "TAPE_OK"})
    return case.pre, events, calls
