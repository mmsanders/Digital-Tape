#!/usr/bin/env python3
"""Independent deterministic plan and C-header generator for WP-08 R52."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

ONE_RATE = 65536

EXTREMA_UP = ((-32768, 32767), (32767, -32768), (-32767, 32766),
              (32766, -32767), (-1, 1), (1, -1))
EXTREMA_DOWN = tuple(reversed(EXTREMA_UP))
MULTI = (
    (-32768, 32767), (-20001, 19999), (32767, -32768),
    (12345, -23456), (-1, 0), (-30000, 30000), (32760, -32760),
    (-32767, 32766), (22222, -11111),
    (0, -1), (16384, -16384), (32767, -32768),
)


@dataclass(frozen=True)
class Vector:
    id: str
    frames: tuple[tuple[int, int], ...]
    runs: tuple[int, ...]
    seek: int
    rate: int
    requested: int

    def public(self):
        return asdict(self)

    def fixture_sha256(self):
        return hashlib.sha256(json.dumps(
            self.public(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def vectors():
    out = [
        Vector("empty-forward", (), (), 0, ONE_RATE, 3),
        Vector("empty-zero", (), (), 0, 0, 3),
        Vector("one-intmax-forward", ((32767, -32768),), (1,), 0, 0x7FFFFFFF, 4),
        Vector("one-intmin-reverse-end", ((-32768, 32767),), (1,), 1, -0x80000000, 4),
        Vector("one-zero", ((123, -456),), (1,), 0, 0, 4),
        Vector("end-forward", EXTREMA_UP, (2, 1, 3), 6, ONE_RATE, 3),
        Vector("start-reverse", EXTREMA_UP, (2, 1, 3), 0, -ONE_RATE, 3),
        Vector("beyond-intmax-forward", EXTREMA_UP, (2, 1, 3), 99, 0x7FFFFFFF, 3),
        Vector("end-reverse-grid", EXTREMA_UP, (2, 1, 3), 6, -ONE_RATE, 4),
        Vector("reverse-end-acceptance-0-1000-2000",
               ((0, 0), (1000, 1000), (2000, 2000)), (3,), 3, -ONE_RATE, 4),
        Vector("extrema-up-half", EXTREMA_UP, (2, 1, 3), 0, 32768, 8),
        Vector("extrema-down-half", EXTREMA_DOWN, (1, 3, 2), 0, 32768, 8),
        Vector("extrema-up-quarter", EXTREMA_UP, (2, 2, 2), 0, 16384, 8),
        Vector("extrema-down-quarter", EXTREMA_DOWN, (3, 1, 2), 0, 16384, 8),
        Vector("extrema-up-three-quarter", EXTREMA_UP, (1, 2, 3), 0, 49152, 8),
        Vector("extrema-down-three-quarter", EXTREMA_DOWN, (3, 2, 1), 0, 49152, 8),
        Vector("tiny-positive", EXTREMA_UP, (2, 1, 3), 1, 1, 7),
        Vector("tiny-negative-end", EXTREMA_UP, (2, 1, 3), 6, -1, 7),
        Vector("negative-fraction", EXTREMA_DOWN, (2, 3, 1), 5, -32767, 7),
    ]
    for boundary in (3, 7, 9):
        for offset in (-1, 0, 1):
            for rate, direction in ((ONE_RATE, "f"), (-ONE_RATE, "r")):
                out.append(Vector(
                    f"run-{boundary}{offset:+d}-{direction}", MULTI, (3, 4, 2, 3),
                    boundary + offset, rate, 6,
                ))
    out += [
        Vector("multirun-intmax-forward", MULTI, (3, 4, 2, 3), 1, 0x7FFFFFFF, 3),
        Vector("multirun-intmin-reverse", MULTI, (3, 4, 2, 3), 11, -0x80000000, 3),
        Vector("multirun-large-positive-fraction", MULTI, (3, 4, 2, 3), 2, 0x40010000, 4),
        Vector("multirun-large-negative-fraction", MULTI, (3, 4, 2, 3), 10, -0x40010000, 4),
    ]
    assert len(out) == 41 and len({v.id for v in out}) == 41
    assert all(sum(v.runs) == len(v.frames) for v in out)
    return out


def plan_sha256():
    raw = json.dumps([v.public() for v in vectors()], sort_keys=True,
                     separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def write_plan(path):
    path.write_text(json.dumps([v.public() for v in vectors()], indent=2,
                               sort_keys=True) + "\n")


def write_header(path):
    lines = ["/* generated from vectors.py; do not hand-edit */",
             f"#define VECTOR_COUNT {len(vectors())}",
             "static const struct vector VECTORS[VECTOR_COUNT] = {"]
    for v in vectors():
        pcm = ", ".join("{%d, %d}" % frame for frame in v.frames) or "{0, 0}"
        lines += ["  {", f'    .id = "{v.id}",',
                  f'    .fixture_sha256 = "{v.fixture_sha256()}",',
                  f"    .frame_count = {len(v.frames)}u,",
                  f"    .pcm = {{{pcm}}},",
                  f"    .run_count = {len(v.runs)}u, .runs = {{{', '.join(f'{r}u' for r in v.runs) or '0u'}}},",
                  f"    .seek = {v.seek}ull, .rate = {v.rate}, .requested = {v.requested}u",
                  "  },"]
    lines += ["};", ""]
    path.write_text("\n".join(lines))
