# host/ — Stream 3

**Built now (Phase 1, #366):** `tapectl`, exactly per [the WP-11 CLI contract](../docs/WP11-CLI-CONTRACT.md):
`format`, `load`, `play`, `scrub`, `record`, `reset-b`, `promote`, `respool`, `dump`. `make -C host`
builds `build/host/tapectl`; `make -C host test` runs the WAV unit tests and a format → load → dump
smoke. It composes the public engine API over `engine/port/dev_file.c` and reimplements no engine
behaviour. Everything below this line is the Phase 2 plan (WP-14…16), not yet built.

`tapectl` (format, load, dump, verify, promote) plus a Tauri drag-and-drop GUI over the same
engine through FFI. Also the ingest chain: gapless concatenation and loudness normalisation,
so a folder of mixed-source music becomes one stream with consistent level and no clicks at
the joins.

**Packages:** WP-14, 15, 16
**Depends on:** Stream 1 through the C FFI. **Never reimplements format logic in Rust.**

**Done when** a real microSD formats, round-trips through dump byte-identical, and someone who
is not Michael can load a cartridge unaided.

## Scope frozen at Phase 2 exit

It loads cartridges. It is not a music manager, a tag editor, a library, or a player.

**This is the stream most likely to grow features nobody asked for.** If a proposed feature
would show the user a list of anything, it is the wrong feature (guardrail 03).
