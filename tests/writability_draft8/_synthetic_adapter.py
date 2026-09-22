#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from oracle import Media,make_cases,synth_observation

cid,inp,out=sys.argv[1:4]
case=next(c for c in make_cases() if c.id==cid)
if Media.decode(Path(inp).read_bytes())!=case.pre:
    raise SystemExit(3)
post,obs=synth_observation(case)
Path(out).write_bytes(post.encode())
print(json.dumps(obs,sort_keys=True))
