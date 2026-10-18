# Digital Tape app (WP-15 / APP-1 with annex APP-1A)

One window that will turn folders of music into a cartridge. It runs the bundled
`ingest` and `tapectl` as child processes and never reimplements them (Guardrails 03
and 12). Tauri 2 shell; the page is plain HTML/CSS/JS with no plugins.

**This is slice S4 of #452** — the shell only:

- the four-state window and §2 copy; label box (1–32 UTF-8 bytes, never truncated,
  never pre-filled); folders-only drops with OS-identity de-duplication;
- the background `ingest` check into an app-owned DEST with a fresh report nonce, and
  the APP-1A report reader that turns a usable report ID into a §6 message;
- app-owned job directories with a marker file; only marked directories are deleted;
- children run only when their SHA-256 equals the pin compiled into the build
  (`DT_INGEST_SHA256`, `DT_INGEST_VERSION`); otherwise SPAWN_FAILED.

**Not built:** card discovery (S2, `tapectl cards`) and make (S3, `tapectl make`) wait
for independent feasibility preflight. The card line says so, and Make cartridge is
never enabled. No native permission or elevation exists in this build.

G1: `tools/app1a/g1_static.py` fails on any device name or API, any non-literal
file-system path outside the allowed modules or not derived from that module's own root
(a literal path is judged by its device names), any process launch but the pinned
child, and any page or capability access to files, shells or processes. `#[cfg(test)]`
exempts only the one item it applies to; comments are stripped by a string-aware lexer.
Its controls: `--selftest`, the planted tree `tools/app1a/fixtures/g1-negative`, and
Verification's `tests/wp15_app1a_r1/static_controls.py` on every app Rust file.

The report reader and message choice (`report::read`, `messages::choose`) are run against
Verification's parser package by `examples/parser_adapter.rs` and
`tools/app1a/parser_binding.py` (ingest rows; cards/make rows are S2/S3's).

```
cargo test                    # unit tests; tests/child_binding.rs needs DT_TEST_INGEST(_VERSION)
DT_INGEST_SHA256=… DT_INGEST_VERSION=… cargo build --release
```
