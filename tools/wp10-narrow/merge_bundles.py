#!/usr/bin/env python3
"""Merge per-tool BUNDLE.json files under ROOT/<sub>/ into one ROOT/BUNDLE.json whose paths
are relative to ROOT, as tests/wp10_narrow_supplement_r1/replay.py reads it.

    python3 -B tools/wp10-narrow/merge_bundles.py ROOT SUB [SUB ...]
"""
import json
import sys
from pathlib import Path

ROW_PATHS = {"duplicate_rows": ("record", "source_before", "source_after", "destination", "source_A_pcm",
                                "source_B_pcm", "dest_A_pcm", "dest_B_pcm"),
             "fault_rows": ("record",), "command_rows": ("record", "original_observation")}


def main():
    root, subs = Path(sys.argv[1]), sys.argv[2:]
    out = {"files": {}, "duplicate_rows": [], "fault_rows": [], "command_rows": [], "parts": {}}
    for sub in subs:
        b = json.loads((root / sub / "BUNDLE.json").read_text())
        out["files"].update({f"{sub}/{k}": v for k, v in b["files"].items()})
        for kind, keys in ROW_PATHS.items():
            for row in b[kind]:
                row = dict(row, **{k: f"{sub}/{row[k]}" for k in keys})
                if "raw_inputs" in row:
                    row["raw_inputs"] = {c: {k: f"{sub}/{v}" for k, v in p.items()} for c, p in row["raw_inputs"].items()}
                out[kind].append(row)
        out["parts"][sub] = {k: v for k, v in b.items() if k not in ("files",) + tuple(ROW_PATHS)}
    (root / "BUNDLE.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print({k: len(out[k]) for k in ROW_PATHS}, len(out["files"]), "files")


if __name__ == "__main__":
    main()
