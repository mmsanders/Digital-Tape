# WP-11 `tapectl` contract (PM-issued, P1-R63)

**Status:** issued 2 Oct 2026 under ADR-158 for Software #366 and Verification #143. Software
builds against it; Verification writes golden `MANIFEST` commands against it, in parallel. A
change to this file after issue is a PM decision recorded here and in both issues.

`tapectl` is host tooling in `host/` (C99, links `engine/` and `engine/port/dev_file.c`). It
**composes the public engine API and reimplements no engine behaviour** (guardrail 12). It loads
cartridges for tests and demos. It is not a player or a library (guardrail 03, `host/README.md`).

## Common rules

- **WAV I/O:** RIFF PCM, 44.1 kHz, 16-bit, stereo only. Any other input is rejected with exit 2,
  never converted. Unknown chunks are skipped on read. Output is a canonical 44-byte header plus data.
- **Image:** the `IMG` argument is a raw block-device file opened through `dev_file`.
- **Exit status:** 0 on success; 1 on an engine result other than `TAPE_OK`, with its name on
  stderr (e.g. `TAPE_ERR_CARTRIDGE_FULL`); 2 on a usage or WAV-format error.
- **Determinism:** the same arguments and input bytes give byte-identical outputs and images. The
  CLI uses no clock, randomness or environment.
- **Render cadence** is the accepted WP-08 cadence (`tests/playback_complete_draft8/ADAPTER.md`).
  Before every render request, call `tape_service(t, 1024, &more)` until `more == false`. Then
  call `tape_render` for at most 128 frames. Repeat.
- **Record cadence:** feed in requests of 1024 frames, with the same service loop before each.
  After the last frame, service until `frames_owed` is zero, then `tape_commit`.
- **Long operations** (`promote`, `respool`) loop with `block_budget` 1024 until
  `more_work == false`.
- Rates are decimal on the command line (e.g. `-1.5`). They are converted to Q16.16 by
  round-half-away-from-zero and passed to `tape_set_rate`.

## Commands

| Command | Engine sequence |
|---|---|
| `tapectl format IMG --blocks N --uuid HEX32 --epoch E --label L --length-s S` | Create or truncate `IMG` to N×512 bytes, then `tape_format` |
| `tapectl load IMG SRC.wav` | Mount, `tape_set_side(B)`, `tape_seek(0)`, arm `OVERWRITE`, feed all of SRC, commit, `tape_promote` to completion. Result: SRC on Side A, and Side B mirroring it |
| `tapectl play IMG --side A\|B --from F --frames N --rate R -o OUT.wav` | Mount, set side, seek F, set rate R, render N frames (fewer only at a boundary, where `tape_render` returns less) |
| `tapectl scrub IMG --side A\|B --from F --schedule R1:N1,R2:N2,… -o OUT.wav` | As `play`, but for each segment `Ri:Ni`: `tape_set_rate(Ri)`, then render Ni frames. Position carries across segments; output is concatenated |
| `tapectl record IMG --at F --mode overwrite\|overdub\|splice IN.wav` | Mount, Side B, seek F, arm mode, feed IN, commit |
| `tapectl reset-b IMG` | `tape_reset_side_b` |
| `tapectl promote IMG` | `tape_promote` to completion |
| `tapectl respool IMG` | `tape_respool` to completion |
| `tapectl dump IMG --side A\|B -o OUT.wav` | `play` from 0 at rate 1.0 to the end of the side |

Mount uses `tape_mount(t, side, 0, NULL)` (cold, no warm buffer). The instance memory is one static
caller-owned block sized by `tape_instance_size()`.

## Out of scope

GUI, ingest and normalisation, real microSD, `dup`, warm start, metadata and labels beyond `format`.
Those belong to WP-14…16 (Phase 2). Adding a command here is a PM change, not a convenience.
