# Digital Tape

A cassette player with no screen.

A cartridge is one unbroken stream of raw PCM — no tracks, no titles, no browse. Side A is
what you were given and cannot be changed. Side B is what you make of it: dub from a phone,
overdub a voice, splice, copy the whole thing to another cartridge. Fast-forward aliases,
because the playback rate genuinely increases. The grit is the feature.

The users are children.

## Start here

| | |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | **The working agreement.** Twelve guardrails, who owns what, when to escalate. Read before writing code |
| [`docs/STATUS.md`](docs/STATUS.md) | Current state of the project. Updated on every merge to main |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Append-only ADRs — choice, date, rationale, cost to reverse |
| [`docs/FOR-MICHAEL.md`](docs/FOR-MICHAEL.md) | The question queue. Nothing else blocks on him |
| [`spec/`](spec/) | The source of truth. PM-owned, frozen at the Phase 0 gate |

## Layout

```
spec/            frozen format and API definitions — PM-owned
engine/          Stream 1 · portable C99, no OS, no allocation
tests/           Stream 2 · Verification Lead owns this outright
host/            Stream 3 · tapectl CLI + Tauri GUI over engine FFI
firmware/bench/  Stream 4 · Teensy 4.1
firmware/prod/   Stream 5 · i.MX RT1062 custom board
hardware/        KiCad boards, CadQuery mechanical, BOMs
docs/            status, decisions, work packages, questions for Michael
```

One engine, three consumers: the CLI, the GUI and the firmware all link the same C library.

## Status

Phase 0 — format freeze. Nothing is implemented. See [`docs/STATUS.md`](docs/STATUS.md).
