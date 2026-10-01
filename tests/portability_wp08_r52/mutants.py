#!/usr/bin/env python3
"""Known-defective reverse models for causal controls and the negative-rate audit."""
from __future__ import annotations

import json

from oracle import ONE, interpolate, model, pcm_hex
from vectors import vectors


def legacy_model(vector, land_and_stop, off_grid_snap):
    frames = vector.frames
    max_pos = len(frames) * ONE
    position = min(vector.seek, len(frames)) * ONE
    step = vector.rate * 65536
    at_start = at_end = False
    emitted = []
    if not frames:
        return emitted, 0, False, True
    if step == 0:
        return emitted, position >> 32, False, False
    if step < 0 and position >= max_pos:
        position = max_pos - 1 if off_grid_snap else (len(frames) - 1) * ONE
    for _ in range(vector.requested):
        if step > 0 and position >= max_pos:
            at_end = True
            break
        if step < 0 and at_start:
            break
        i, fraction = divmod(position, ONE)
        b = frames[i + 1] if i + 1 < len(frames) else frames[i]
        emitted.append(interpolate(frames[i], b, fraction))
        if step > 0:
            at_start = False
            if step >= max_pos - position:
                position, at_end = max_pos, True
            else:
                position += step
        else:
            at_end = False
            if land_and_stop:
                if position <= -step:
                    position, at_start = 0, True
                else:
                    position += step
            elif position == 0:
                at_start = True
            elif position <= -step:
                position = 0
            else:
                position += step
    return emitted, position >> 32, at_start, at_end


MUTANTS = {
    "land-and-stop (d5772c8 §6.2 defect)": dict(land_and_stop=True, off_grid_snap=False),
    "off-grid max_pos-1 snap (d5772c8 §6.3 defect)": dict(land_and_stop=False, off_grid_snap=True),
    "combined d5772c8 behavior": dict(land_and_stop=True, off_grid_snap=True),
}


def record_for(vector, result, template):
    """Rewrite a genuine observation so it reports the given model result."""
    emitted, tell, at_start, at_end = result
    record = json.loads(json.dumps(template))
    record.update(pcm_hex=pcm_hex(emitted), rendered=len(emitted), tell=tell,
                  at_start=at_start, at_end=at_end)
    record["trace"][4]["rendered"] = len(emitted)
    record["trace"][5]["value"] = tell
    record["trace"][6].update(at_start=at_start, at_end=at_end)
    return record


def audit():
    rows = []
    for vector in vectors():
        if vector.rate >= 0:
            continue
        good = model(vector)
        diffs = {name: legacy_model(vector, **cfg) != good for name, cfg in MUTANTS.items()}
        rows.append((vector.id, good, diffs))
    return rows


if __name__ == "__main__":
    names = list(MUTANTS)
    print("negative-rate vector | corrected rendered/tell/at_start/at_end | changed vs " +
          " / ".join(names))
    for vid, (emitted, tell, s, e), diffs in audit():
        print(f"{vid} | {len(emitted)}/{tell}/{s}/{e} | " +
              " / ".join("CHANGED" if diffs[n] else "same" for n in names))
