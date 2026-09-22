#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from oracle import Media,make_cases,synth_observation

cid,inp,out=sys.argv[1:4]
case=next(c for c in make_cases() if c.id==cid)
media=Media.decode(Path(inp).read_bytes())
if media!=case.pre:
    raise SystemExit(3)
Path(out).write_bytes(media.encode())
print(json.dumps(synth_observation(case),sort_keys=True))
