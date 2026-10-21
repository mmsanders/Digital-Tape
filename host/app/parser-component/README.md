# APP-1A pure parser/message component (Software498)

This standalone build compiles `../src/report.rs` and `../src/messages.rs`
directly. Those are the original S4 production-module paths, restored from
`ecca8c1304ba9511d78791e92ed35fac494f2a27`, then extended under APP-1A §§1–4/7.
It includes no shell, child launcher, device code or Make enablement. A held S4
integration can use these modules at their existing paths without a second parser.

Baseline blobs: report `fd249d696cb86dd7fecc9ddede5e5391ce6663aa`, messages
`69f968eb37a8cee098e7a4831f15215c717d83a1`. Existing ingest interfaces remain.
New pure `choose_make`/`make` and `cards` functions supply the issued copy. Reports
never authorize access. The test binary serializes actual selector variants and
actual rendered messages; it does not read expected fields or import an oracle.

`cargo build --manifest-path host/app/parser-component/Cargo.toml`
followed by `python3 -B tools/app1a/parser_component.py --adapter
host/app/parser-component/target/debug/dtapp-parser-component --out OUT` runs the
unchanged627 APP reports and49 query-matrix report byte strings through the actual
modules. The query rows test only parsing and fallback: their modeled OS/device
fields are not executed or asserted as actual observations. Raw stdin/stdout,
rendered messages, reading details, source/build identities and failures are saved.

All281 ingest rows run because the common parser now dispatches to cards/make
payload validation. This is the justified shared-parser regression, not an audio
or full app campaign. No native, S3, G2 or whole-app acceptance follows. The local
machine has no configured Rust compiler; the normal hosted Rust build is used.
New focused execution is capped at2CPU-hours/512MiB compressed evidence; a single
10-minute hosted job bounds a run to40CPU-minutes on its four-core runner. Actual
build usage is retained with `/usr/bin/time -v`; ordinary required CI is separate.
