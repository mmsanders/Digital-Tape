# Digital Tape

A screenless music player for children. Each cartridge holds one continuous stream
of 44.1 kHz, 16-bit stereo PCM. Side A is the original; Side B is the editable copy.
There are no tracks, titles or browsing. Scrub changes playback rate without filtering.

**Phase 0: DRAFT-8 format/API scope frozen by Michael on 8 September 2026.**
The repo contains provisional engine code, independent tests, and hardware design
and print packets. It is not a finished player or a safety-qualified hardware design.

## Start or resume a lead

1. Fetch main; read [Michael’s issue queue](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Amichael) first.
2. Read [the working agreement](CLAUDE.md) and [current status](docs/STATUS.md).
3. Follow [the onboarding map](docs/START-HERE.md) and
   [issue workflow and role queue](docs/ISSUE-WORKFLOW.md). Historical chat is not required.

| Surface | Authority |
|---|---|
| [Freeze record](docs/PHASE0-FREEZE.md) | Scope, signatures and remaining holds |
| [Product specification](spec/README.md) | PM; revisions/hashes in spec/VERSION.md |
| [Hardware specification](spec/hw/README.md) | Hardware Lead; separately versioned |
| [Work packages](docs/PACKAGES/README.md) | Scope and dependencies |
| [Verification integration](docs/VERIFICATION-INTEGRATION.md) | Provenance, coverage and observed results |
| [Decision log](docs/DECISIONS.md) | Append-only history; later dispositions supersede earlier ones |

One portable C99 engine serves the CLI, GUI and firmware. Hardware source is in
hardware/; the independent mount-test package is in tests/mount_draft8/.

Phase 1 uses individual lead chats with no subworkers. Start with the
[development plan](docs/PHASE1-DEVELOPMENT.md) and [copyable role bootstraps](docs/ROLES/README.md).
