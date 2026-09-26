#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path
from oracle import evaluate

def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--result", type=Path)
    a = p.parse_args(argv)
    evidence = json.loads(a.evidence.read_text(encoding="utf-8"))
    result = evaluate(evidence)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if a.result:
        a.result.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["overall_pass"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
