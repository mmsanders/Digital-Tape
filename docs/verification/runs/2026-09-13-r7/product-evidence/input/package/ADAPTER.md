# P1-R6 public adapter contract

The runner invokes `<adapter> --fixture-dir DIR --out-dir DIR`. DIR contains exact
`long.vo08.gz`, `one.vo08.gz`, `empty.vo08.gz`, and `fixture.json` inputs. The adapter
must use only the frozen public API and emit schema
`playback-complete-draft8-observation-v1`, complete unfiltered callback records, and
the seven PCM files named by `oracle.py`. Callback `call_index` indexes each case's
public-call array. Record every result, requested/rendered count, status/tell/info
output, rate, seek, side, service budget and `more_work` exactly as applicable.

Scrub uses every authenticated WP-08 row. Each row is set-rate, then repeated
service(1024) through `more_work=false`, then 128-frame render requests plus the exact
remainder. Empty/zero/extreme and side-switch scripts are executable in `oracle.py`.
No callback may be filtered; render, seek, rate, status, info, tell and side-switch
perform no media I/O. The pre-service side-switch render must retain result 6
(`TAPE_ERR_UNDERRUN`) and zero frames.

Adapter kind/ID, source/build declarations, finite execution, zero exit, verifier
commit/tree and all evidence bytes are hash-bound. A product adapter must identify as
`product`; `_synthetic_adapter.py` is verifier plumbing only.
