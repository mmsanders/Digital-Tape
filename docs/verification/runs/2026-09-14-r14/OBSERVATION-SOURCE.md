# `observation.json` — identity and relocation status

This file sits at the **run root**, deliberately outside `product-evidence/`. That
bundle's `manifest.json` binds an exact file inventory, and `replay.py` fails with
`unbound/missing evidence file` if anything is added inside it. The tamper control is
working as designed, so the pointers live here and the bundle stays byte-for-byte
unchanged.

This records the raw product observation for the `2026-09-14-r14` run, cited by that run's
README, by the bundle's `manifest.json`, and by the PM dispositions that route the run.
**The SHA-256 is the citation.**

| Item | Value |
|---|---|
| Path | `product-evidence/output/observation.json` |
| Bytes | `14173808` |
| SHA-256 | `4be2a12ca7c638ce256f6b09c2bda99a09e4fd42b63bad182491d8d084f0c7a8` |
| Original git blob | `c99f4bd922f9709fe767680440e9b3de00fd6242` |
| Recorded in | `observation.json.sha256` (this directory) |

Verify at any time with `sha256sum -c observation.json.sha256` from this directory.

## Status: still in the working tree; relocation pending

WO-6 (repo hygiene) relocates raw evidence over 1 MiB to a GitHub Release asset, leaving
this file and the `.sha256` in its place. **That move has not happened.** The session
running WO-6 could not create releases — the API returned
`403 Creating, editing, or deleting releases is not permitted for this session type` —
so the bytes stay here and the hash is committed as the citation in the meantime.

When the release exists the asset is `r14-observation.json`, and this section is
replaced by its URL and the fetch-and-verify step. Until then nothing about this bundle
has changed.

## Why the move does not shrink a clone

Removing a blob from HEAD does not remove it from history, and it should not: this
repository's dispositions cite these bytes, and Guardrail 3 forbids rewriting history.
The goal is a working tree an agent can traverse safely, and growth that stops — not
reclaimed bytes.

## Offline replay

`replay.py` reads `output/observation.json` directly, and this bundle **replays green
today**:

```sh
python3 tests/playback_complete_draft8/replay.py docs/verification/runs/2026-09-14-r14/product-evidence
# REPLAY PASS docs/verification/runs/2026-09-14-r14/product-evidence
```

Any relocation must keep that command working: fetch the asset back to
`product-evidence/output/observation.json`, verify it against the `.sha256`, then replay.
A relocation that silently breaks offline replay is not acceptable and is the reason the
bytes have not been moved yet.
