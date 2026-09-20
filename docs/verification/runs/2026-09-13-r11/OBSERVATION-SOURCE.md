# `observation.json` — identity and where the bytes live

The raw product observation for the `2026-09-13-r11` run. It is cited by that run's README, by the
bundle's `manifest.json`, and by the PM dispositions that route the run.

**The bytes are not in the working tree. The SHA-256 is the citation.**

| Item | Value |
|---|---|
| Path when fetched | `product-evidence/output/observation.json` |
| Release asset | [`r11-observation.json`](https://github.com/mmsanders/Digital-Tape/releases/download/evidence-2026-09/r11-observation.json) |
| Release | [`evidence-2026-09`](https://github.com/mmsanders/Digital-Tape/releases/tag/evidence-2026-09) |
| Bytes | `9289887` |
| SHA-256 | `24a35a3cd5a8364d1909f0ee3e0a90d196b4c1afdedfb3bf9d38d34c775e7ce4` |
| Original git blob | `cd7cd5c34a7e00bf543a6b9a4abaa23ba0deff52` |
| Recorded in | `observation.json.sha256` (this directory) |

## Getting the bytes back

```sh
tools/fetch-evidence.sh 2026-09-13-r11
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

`replay.py` reads `output/observation.json` directly.

**This bundle does not replay green against the current package, and that is correct.**
It is the superseded P1-R12 cadence evidence: it used the once-per-row scrub service
schedule the corrected package rejects by name (`P1-R13-V01`), so `replay.py` returns
`REPLAY FAIL: assignment` rather than silently accepting it. That failure predates the
relocation — it was reproduced on `main` beforehand — and is a control working, not a
regression. `tests/IMPORTS.json` declares this bundle `expect: "refuse"`, so a PASS here
would now fail CI.

CI fetches these bytes before the evidence-integrity check runs, so the relocation is
invisible to it. `.gitignore` covers the fetched path, and the docs hygiene gate skips
ignored files, so having fetched evidence locally never fails a contributor's PR.
