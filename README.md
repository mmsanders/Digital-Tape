# Digital Tape

A screenless music player for children. Each cartridge holds one continuous stream of
44.1 kHz, 16-bit stereo PCM. Side A is the original; Side B is the editable copy. There
are no tracks, titles or browsing. Scrub changes playback rate without filtering.

**Where the project is:**
- Phase 1, the audio engine, is complete.
- Phase 2, the Windows desktop tools that make cartridges from a folder of music, is complete.
- Phase 3, bench firmware on a Teensy 4.1, is under way.

Current state is in [STATUS](docs/STATUS.md). This is not yet a finished player or a
safety-qualified hardware design.

## Start or resume a lead

1. Fetch main and read [Michael's issue queue](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Amichael).
2. Read [the working agreement](CLAUDE.md) and [current status](docs/STATUS.md).
3. Follow [START-HERE](docs/START-HERE.md) and [the issue workflow](docs/ISSUE-WORKFLOW.md).

| Surface | What it holds |
|---|---|
| [Status](docs/STATUS.md) | Current phase, accepted packages, holds |
| [Phase 3 plan](docs/PHASE3-PLAN.md) | Next phase: goal, packages, kickoff decisions |
| [Device design](docs/DEVICE-DESIGN.md) | Current owner design of the player and cartridge |
| [Work packages](docs/PACKAGES/README.md) | Every package and its state |
| [Product specification](spec/README.md) | PM-owned, hash-pinned in spec/VERSION.md |
| [Hardware specification](spec/hw/README.md) | Hardware Lead, separately versioned |
| [Decision log](docs/DECISIONS.md) | Append-only; later decisions supersede earlier ones |

One portable C99 engine serves the CLI (`tapectl`), the desktop app and the firmware.
Independent verifier packages are imported under tests/ and declared in
[tests/IMPORTS.json](tests/IMPORTS.json). Closed phases and round records are in
docs/archive/ and docs/REVIEW/.
