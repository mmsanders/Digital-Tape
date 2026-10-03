# Digital Tape

A screenless music player for children. Each cartridge holds one continuous stream
of 44.1 kHz, 16-bit stereo PCM. Side A is the original; Side B is the editable copy.
There are no tracks, titles or browsing. Scrub changes playback rate without filtering.

**Phase 1 (audio engine, on a laptop) is complete as of 3 October 2026.** All nine
Phase 1 engine packages are independently accepted for laptop scope, and the golden
suite is green. Phase 2 (desktop tooling) awaits Michael's go. The current spec revision
is recorded in [spec/VERSION.md](spec/VERSION.md); phase state is in [STATUS](docs/STATUS.md).
The repo is not a finished player or a safety-qualified hardware design; hardware is
parked through Phase 2 (see [the roadmap](docs/PACKAGES/README.md)).

## Start or resume a lead

1. Fetch main; read [Michael’s issue queue](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Amichael) first.
2. Read [the working agreement](CLAUDE.md) and [current status](docs/STATUS.md).
3. Follow [the onboarding map](docs/START-HERE.md) and
   [issue workflow and role queue](docs/ISSUE-WORKFLOW.md). Historical chat is not required.

| Surface | Authority |
|---|---|
| [Status](docs/STATUS.md) | Current phase state, accepted packages, holds and risks |
| [Work packages / roadmap](docs/PACKAGES/README.md) | Scope, dependencies, parked work and Phase 2 kickoff items |
| [Product specification](spec/README.md) | PM; revisions/hashes in spec/VERSION.md |
| [Hardware specification](spec/hw/README.md) | Hardware Lead; separately versioned |
| [Freeze record](docs/PHASE0-FREEZE.md) | Phase 0 scoped freeze and its signatures |
| [Verification integration](docs/VERIFICATION-INTEGRATION.md) | Provenance, coverage and observed results |
| [Decision log](docs/DECISIONS.md) | Append-only history; later dispositions supersede earlier ones |

One portable C99 engine serves the CLI (`tapectl`), GUI and firmware. Hardware source is
in hardware/. Independent verifier packages are imported under tests/ and declared in
[tests/IMPORTS.json](tests/IMPORTS.json).

Leads work in individual chats with no subworkers, routed by role-labeled issues. See
[the role bootstraps](docs/ROLES/README.md) and [the issue workflow](docs/ISSUE-WORKFLOW.md).
