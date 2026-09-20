# `observation.json` — identity and where the bytes live

The raw product observation for the `2026-09-14-r14` run. It is cited by that run's README, by the
bundle's `manifest.json`, and by the PM dispositions that route the run.

**The bytes are not in the working tree. The SHA-256 is the citation.**

| Item | Value |
|---|---|
| Path when fetched | `product-evidence/output/observation.json` |
| Release asset | [`r14-observation.json`](https://github.com/mmsanders/Digital-Tape/releases/download/evidence-2026-09/r14-observation.json) |
| Release | [`evidence-2026-09`](https://github.com/mmsanders/Digital-Tape/releases/tag/evidence-2026-09) |
| Bytes | `14173808` |
| SHA-256 | `4be2a12ca7c638ce256f6b09c2bda99a09e4fd42b63bad182491d8d084f0c7a8` |
| Original git blob | `c99f4bd922f9709fe767680440e9b3de00fd6242` |
| Recorded in | `observation.json.sha256` (this directory) |

## Getting the bytes back

```sh
tools/fetch-evidence.sh 2026-09-14-r14
```

It downloads the asset, checks it against `observation.json.sha256`, and **refuses to
install anything that does not match**. A mismatch is reported and nothing is written —
an asset that is not the cited evidence never reaches the bundle.

This file sits at the **run root**, outside `product-evidence/`, on purpose: the bundle's
`manifest.json` binds an exact file inventory and `replay.py` fails with
`unbound/missing evidence file` if anything is added inside it. The bundle itself is
byte-for-byte what it always was.

## Why this does not shrink a clone

Removing a blob from HEAD does not remove it from history, and it should not: this
repository's dispositions cite these bytes, and Guardrail 3 forbids rewriting history.
The goal is a working tree an agent can traverse safely, and growth that stops — not
reclaimed bytes. `git clone` is the same size as before.

## Offline replay

`replay.py` reads `output/observation.json` directly, and this bundle **replays green
on the fetched bytes** — verified after the relocation, not assumed:

```sh
tools/fetch-evidence.sh 2026-09-14-r14
python3 tests/playback_complete_draft8/replay.py docs/verification/runs/2026-09-14-r14/product-evidence
# REPLAY PASS docs/verification/runs/2026-09-14-r14/product-evidence
```

CI fetches these bytes before the evidence-integrity check runs, so the relocation is
invisible to it. `.gitignore` covers the fetched path, and the docs hygiene gate skips
ignored files, so having fetched evidence locally never fails a contributor's PR.
