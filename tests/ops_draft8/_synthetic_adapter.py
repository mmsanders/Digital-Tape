#!/usr/bin/env python3
import json,sys
from pathlib import Path
from oracle import Media, make_cases, synth_post
cid,inp,out=sys.argv[1:4]
case=next(c for c in make_cases() if c.id==cid)
# Verify runner supplied exactly the independently generated fixture.
if Media.decode(Path(inp).read_bytes()) != case.pre: raise SystemExit(3)
post,events=synth_post(case); Path(out).write_bytes(post.encode())
print(json.dumps({'events':events}))
