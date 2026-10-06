# host/ — Stream 3

**Built (Phase 1, #366):** `tapectl`, exactly per [the WP-11 CLI contract](../docs/WP11-CLI-CONTRACT.md):
`format`, `load`, `play`, `scrub`, `record`, `reset-b`, `promote`, `respool`, `dump`.

**Built (Phase 2 P2-R1, #385, pending Verification):** WP-14, real cards, per
[the WP-14 contract](../docs/WP14-CLI-CONTRACT.md). It adds `provision` and `verify`, and every command
takes a bare image, a provisioned image or a whole removable device.

| Path | What |
|---|---|
| `tapectl.c` | The commands. Composes the public engine API; never parses TAPEFS |
| `target.c` | Target recognition (§2), disk safety before any write-mode open (§5), the partition-2 view |
| `port/hport_*.c` | One port for images and devices: 64-bit offsets, durable flush (`fsync` / `F_FULLFSYNC` / `FlushFileBuffers`), no write coalescing |
| `port/partview.c` | A block range as the engine's `tape_dev`; read-only means a NULL write callback |
| `port/layout.h`, `mbr.c`, `fat.c` | The §3.1 MBR and the §3.2 partition 1. **E-1's four constants live in `layout.h`** |
| `port/safety.c`, `probe_*.c` | §5 as facts (a per-platform probe) and a pure policy |
| `port/facts_test.c` | The `TAPECTL_TEST` facts seam, built only into `tapectl-test` |
| `port/hport.c`, `tseam.h`, `trace_test.c` | The `TAPECTL_TEST` observation seam (`TAPECTL_TEST_TRACE=FILE`: opens, writes, native flush barriers and results, engine bindings, facts and policy, exit) and fault controls (`TAPECTL_TEST_FAULT=noop-flush`, `hidden-flush-error`, `nonnull-binding`, `read-error:LBA`), test build only |

`make -C host` builds `build/host/tapectl` (shipped) and `build/host/tapectl-test` (the same program
plus the facts seam and a `probe DEV` command). `make -C host test` runs:
- the WAV and port unit tests;
- the WP-11 smoke;
- the WP-14 image smoke (`smoke_wp14.sh`);
- the check that the shipped binary has no seam (`test_seam.sh`);
- the observation seam's transport self-check (`trace_selfcheck.sh`).

`device_e2e.sh` is the round trip on a real device node. CI runs it on a Linux loop device, an
`hdiutil` disk image on macOS and a VHD on Windows.

**Using it on a card.**
1. Name the whole card. `tapectl` never picks one.
2. Raw access needs `sudo` on macOS and an Administrator prompt on Windows.
3. A card with any other mounted volume is refused, and factory cards arrive mounted. Eject it first:
   on macOS, `diskutil unmountDisk /dev/diskN`.

```sh
sudo tapectl provision /dev/disk4 --label "Grieg" --erase /dev/disk4
sudo tapectl load /dev/disk4 music.wav
sudo tapectl verify /dev/disk4
```

**WASM keep-possible (ADR-162 D7).**
- Nothing here blocks a later WebAssembly build of engine plus port.
- The engine is untouched C99. The host port is the only platform layer: a browser port would be one
  more `hport_*.c` over memory or OPFS, behind the same `partview`.
- Two things a WASM target would replace rather than port:
  - the disk-safety probe, since a browser has no raw devices;
  - `provision`'s entropy and clock (`port/entropy.c`).

The rest of this file is the Phase 2 plan beyond WP-14.

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
