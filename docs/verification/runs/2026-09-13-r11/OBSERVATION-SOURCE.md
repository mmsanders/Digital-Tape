# `observation.json` — identity and relocation status

This file sits at the **run root**, deliberately outside `product-evidence/`. That
bundle's `manifest.json` binds an exact file inventory, and `replay.py` fails with
`unbound/missing evidence file` if anything is added inside it. The tamper control is
working as designed, so the pointers live here and the bundle stays byte-for-byte
unchanged.

This records the raw product observation for the `2026-09-13-r11` run, cited by that run's
README, by the bundle's `manifest.json`, and by the PM dispositions that route the run.
**The SHA-256 is the citation.**

| Item | Value |
|---|---|
| Path | `product-evidence/output/observation.json` |
| Bytes | `9289887` |
| SHA-256 | `24a35a3cd5a8364d1909f0ee3e0a90d196b4c1afdedfb3bf9d38d34c775e7ce4` |
| Original git blob | `cd7cd5c34a7e00bf543a6b9a4abaa23ba0deff52` |
| Recorded in | `observation.json.sha256` (this directory) |

Verify at any time with `sha256sum -c observation.json.sha256` from this directory.

## Status: still in the working tree; relocation pending

WO-6 (repo hygiene) relocates raw evidence over 1 MiB to a GitHub Release asset, leaving
this file and the `.sha256` in its place. **That move has not happened.** The session
running WO-6 could not create releases — the API returned
`403 Creating, editing, or deleting releases is not permitted for this session type` —
so the bytes stay here and the hash is committed as the citation in the meantime.

When the release exists the asset is `r11-observation.json`, and this section is
replaced by its URL and the fetch-and-verify step. Until then nothing about this bundle
has changed.

## Why the move does not shrink a clone

Removing a blob from HEAD does not remove it from history, and it should not: this
repository's dispositions cite these bytes, and Guardrail 3 forbids rewriting history.
The goal is a working tree an agent can traverse safely, and growth that stops — not
reclaimed bytes.

## Offline replay

`replay.py` reads `output/observation.json` directly.

**This bundle does not replay green against the current package, and that is correct.**
It is the superseded P1-R12 cadence evidence: it used the once-per-row scrub service
schedule the corrected package now rejects by name (`P1-R13-V01`), so the current
`replay.py` returns `REPLAY FAIL: assignment` rather than silently accepting it. That
failure is **pre-existing on main** and was reproduced there before this change; it is a
control working, not a regression. The r14 README records that this run is historical and
must not be read as current.

The bytes are still cited evidence and are retained unchanged.
