#!/usr/bin/env python3
"""Verifier-owned deterministic generator for the WP-36 100,000-sequence tranche."""
from __future__ import annotations

import hashlib
import json
from collections import Counter

FORMAT = "WP36-FUZZ-PLAN-1"
RNG_ALGORITHM = "splitmix64-v1"
MASTER_SEED = 0x5730365A5EED2026
SEQUENCE_COUNT = 100_000
MIN_OPS = 8
MAX_OPS = 32
FIXTURE_TOTAL_FRAMES = 128
MASK64 = (1 << 64) - 1
GAMMA = 0x9E3779B97F4A7C15
OPS = ("seek", "tell", "set_rate", "render", "service", "status", "info", "set_side")
RATE_POOL = (0, 65536, -65536, 262144, -262144, 0x7FFFFFFF, -0x80000000)
RENDER_POOL = (1, 2, 8, 32, 64)
SERVICE_POOL = (1, 2, 8, 64, 256, 1024)
SEEK_POOL = (0, 1, 63, 127, 128, 129, 255)

# Filled from this exact generator by Verification and asserted by selftest.
EXPECTED_PLAN_SHA256 = "6a6637336eff798e6c7824af76e3d4f227eefcd9ff35e7850a14fd14a1d22bae"
EXPECTED_TOTAL_OPS = 1997914


def _mix64(z: int) -> int:
    z &= MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


class SplitMix64:
    def __init__(self, seed: int):
        self.state = seed & MASK64

    def next_u64(self) -> int:
        self.state = (self.state + GAMMA) & MASK64
        return _mix64(self.state)

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be positive")
        # Modulo reduction is part of splitmix64-v1 and therefore reproducible.
        return self.next_u64() % n


def sequence_seed(index: int) -> int:
    if index < 0:
        raise ValueError("negative sequence index")
    return _mix64((MASTER_SEED + (index + 1) * GAMMA) & MASK64)


def _signed32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v if v < 0x80000000 else v - 0x100000000


def generate_sequence(index: int) -> dict:
    seed = sequence_seed(index)
    r = SplitMix64(seed)
    mount_side = "A" if r.randbelow(2) == 0 else "B"
    length = MIN_OPS + r.randbelow(MAX_OPS - MIN_OPS + 1)
    ops = []
    for _ in range(length):
        kind = OPS[r.randbelow(len(OPS))]
        if kind == "seek":
            bucket = r.randbelow(len(SEEK_POOL) + 1)
            frame = SEEK_POOL[bucket] if bucket < len(SEEK_POOL) else r.randbelow(512)
            ops.append({"op": "seek", "frame": frame})
        elif kind == "tell":
            ops.append({"op": "tell"})
        elif kind == "set_rate":
            bucket = r.randbelow(len(RATE_POOL) + 1)
            rate = RATE_POOL[bucket] if bucket < len(RATE_POOL) else _signed32(r.next_u64())
            ops.append({"op": "set_rate", "rate": rate})
        elif kind == "render":
            bucket = r.randbelow(len(RENDER_POOL) + 1)
            frames = RENDER_POOL[bucket] if bucket < len(RENDER_POOL) else 1 + r.randbelow(64)
            ops.append({"op": "render", "frames": frames})
        elif kind == "service":
            budget = SERVICE_POOL[r.randbelow(len(SERVICE_POOL))]
            ops.append({"op": "service", "budget": budget})
        elif kind == "status":
            ops.append({"op": "status"})
        elif kind == "info":
            ops.append({"op": "info"})
        elif kind == "set_side":
            ops.append({"op": "set_side", "side": "A" if r.randbelow(2) == 0 else "B"})
        else:
            raise AssertionError(kind)
    return {
        "format": FORMAT,
        "seq_index": index,
        "seq_seed": f"{seed:016x}",
        "mount_side": mount_side,
        "ops": ops,
    }


def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def plan_line(plan: dict) -> str:
    """Canonical tab/semicolon wire line for a product adapter."""
    toks = []
    for op in plan["ops"]:
        kind = op["op"]
        if kind == "seek":
            toks.append(f"seek={op['frame']}")
        elif kind == "tell":
            toks.append("tell")
        elif kind == "set_rate":
            toks.append(f"rate={op['rate']}")
        elif kind == "render":
            toks.append(f"render={op['frames']}")
        elif kind == "service":
            toks.append(f"service={op['budget']}")
        elif kind == "status":
            toks.append("status")
        elif kind == "info":
            toks.append("info")
        elif kind == "set_side":
            toks.append(f"side={op['side']}")
        else:
            raise ValueError(f"unknown op {kind!r}")
    return "\t".join((
        "SEQ",
        str(plan["seq_index"]),
        plan["seq_seed"],
        plan["mount_side"],
        str(len(plan["ops"])),
        ";".join(toks),
    ))


def _rate_class(rate: int) -> str:
    if rate == 0:
        return "zero"
    if rate == 0x7FFFFFFF:
        return "int32_max"
    if rate == -0x80000000:
        return "int32_min"
    return "positive" if rate > 0 else "negative"


def _seek_class(frame: int) -> str:
    if frame < FIXTURE_TOTAL_FRAMES:
        return "in_range"
    if frame == FIXTURE_TOTAL_FRAMES:
        return "exact_end"
    return "beyond_end"


def census_and_digest(sequence_count: int = SEQUENCE_COUNT) -> tuple[dict, str]:
    if sequence_count < 0:
        raise ValueError("negative sequence_count")
    op_counts = Counter()
    mount_sides = Counter()
    state_counts = Counter()
    rate_counts = Counter()
    seek_counts = Counter()
    side_targets = Counter()
    render_frames = Counter()
    service_budgets = Counter()
    sequence_features = Counter()
    total_ops = 0
    min_len = None
    max_len = 0
    h = hashlib.sha256()

    for i in range(sequence_count):
        plan = generate_sequence(i)
        line = canonical_json(plan).encode("ascii") + b"\n"
        h.update(line)
        mount_sides[plan["mount_side"]] += 1
        current_side = plan["mount_side"]
        transport_state = "stopped"
        features = set()
        n = len(plan["ops"])
        total_ops += n
        min_len = n if min_len is None else min(min_len, n)
        max_len = max(max_len, n)

        for op in plan["ops"]:
            kind = op["op"]
            op_counts[kind] += 1
            state_counts[transport_state] += 1
            features.add(kind)
            if kind == "set_rate":
                rate = int(op["rate"])
                cls = _rate_class(rate)
                rate_counts[cls] += 1
                features.add("rate_" + cls)
                transport_state = "stopped" if rate == 0 else ("playing_forward" if rate > 0 else "playing_reverse")
            elif kind == "seek":
                seek_counts[_seek_class(int(op["frame"]))] += 1
            elif kind == "set_side":
                target = op["side"]
                side_targets[target] += 1
                if target == current_side:
                    sequence_features["same_side_set"] += 1
                else:
                    sequence_features["side_flip"] += 1
                    current_side = target
            elif kind == "render":
                frames = int(op["frames"])
                render_frames[str(frames)] += 1
            elif kind == "service":
                service_budgets[str(op["budget"])] += 1

        for feature in features:
            sequence_features["seq_has_" + feature] += 1

    census = {
        "sequence_count": sequence_count,
        "total_ops": total_ops,
        "min_ops_per_sequence": min_len if min_len is not None else 0,
        "max_ops_per_sequence": max_len,
        "op_counts": dict(sorted(op_counts.items())),
        "mount_sides": dict(sorted(mount_sides.items())),
        "transport_state_exposure": dict(sorted(state_counts.items())),
        "rate_classes": dict(sorted(rate_counts.items())),
        "seek_classes": dict(sorted(seek_counts.items())),
        "set_side_targets": dict(sorted(side_targets.items())),
        "render_frames": dict(sorted(render_frames.items(), key=lambda kv: int(kv[0]))),
        "service_budgets": dict(sorted(service_budgets.items(), key=lambda kv: int(kv[0]))),
        "sequence_features": dict(sorted(sequence_features.items())),
    }
    return census, h.hexdigest()


def validate_generator_census(census: dict) -> list[str]:
    errors = []
    def need(cond: bool, msg: str) -> None:
        if not cond:
            errors.append(msg)

    need(census.get("sequence_count") == SEQUENCE_COUNT, "sequence count is not exactly 100000")
    need(census.get("min_ops_per_sequence") == MIN_OPS, "minimum sequence length not exercised")
    need(census.get("max_ops_per_sequence") == MAX_OPS, "maximum sequence length not exercised")
    ops = census.get("op_counts", {})
    for op in OPS:
        need(int(ops.get(op, 0)) > 0, f"operation {op} not exercised")
    mounts = census.get("mount_sides", {})
    need(int(mounts.get("A", 0)) > 0 and int(mounts.get("B", 0)) > 0, "both mount sides not exercised")
    states = census.get("transport_state_exposure", {})
    for state in ("stopped", "playing_forward", "playing_reverse"):
        need(int(states.get(state, 0)) > 0, f"transport state {state} not exercised")
    rates = census.get("rate_classes", {})
    for cls in ("zero", "positive", "negative", "int32_max", "int32_min"):
        need(int(rates.get(cls, 0)) > 0, f"rate class {cls} not exercised")
    seeks = census.get("seek_classes", {})
    for cls in ("in_range", "exact_end", "beyond_end"):
        need(int(seeks.get(cls, 0)) > 0, f"seek class {cls} not exercised")
    features = census.get("sequence_features", {})
    need(int(features.get("side_flip", 0)) > 0, "side flips not exercised")
    need(int(features.get("same_side_set", 0)) > 0, "same-side set_side not exercised")
    return errors
