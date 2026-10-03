# WP-11 independent frozen reference package, R63

PM #365 / ADR-158 and Verification #143 authorize this initial creation. Product
input is `41d546f4d799dbe8642135cc228ac50de2869b9c`; verifier base is
`ffaad65f2d5e6724e521545fbb9706dec145b163`. The engine implementation was not
inspected. The PM-issued CLI contract, DRAFT-10 engine API §§6–8, and TAPEFS §9.1
define these independent timeline and sample expectations.

`MANIFEST` conforms to Product's runner shape. Each command formats its own
deterministic image and uses only the specified `tapectl` commands. All ten
reference WAVs and four excerpt input WAVs have a canonical 44-byte PCM header,
44.1 kHz, 16-bit stereo, with no metadata and no tolerance. Each is under 1 MiB.
The CLI executable contract fixes its commands; this package uses the existing
host build convention `build/host/tapectl`.

`SOURCES.json` records exact download URLs, original/canonical SHA-256, licence
text and source page revision, conversion tools, commands and exact excerpt
frames. No gain, normalisation, dither or crossfade is applied to the excerpts.
The originals and full canonical WAVs are checksum-verified fixture release
assets at tag `wp11-r63-canonical-v1`. The lossy voice was decoded once; the
canonical WAV, identified by its hash, is the authoritative input. Future decoder
output never replaces it. `canonicalize.py` is an archival reproduction/check,
and refuses conversion bytes with a different hash. Source fetching and release
publication run in GitHub CI because the connector has no release-upload API.
The identified download User-Agent is recorded in SOURCES.json; generic urllib
requests receive HTTP 403 from Wikimedia. Exact URLs and hash checks are retained.

Exact conversion per source, with ffmpeg 6.1.1-3ubuntu5 and Python 3.12.14:

```
ffmpeg -y -v error -i ORIGINAL -map_metadata -1 -ac 2 -ar 44100 -c:a pcm_s16le -fflags +bitexact -flags:a +bitexact -f s16le ROLE.raw
```

`canonicalize.py` then calls `model.write` to pack the canonical 44-byte header
and little-endian raw PCM. Run `python3 tests/golden/canonicalize.py DESTINATION
--download` to fetch, check originals, decode, write and verify the canonical
hashes. Python's version is also recorded in `SOURCES.json`.

`model.py` uses unbounded Python integers and floor division for interpolation,
an independent sample timeline for edits, and explicit saturating addition.
`python3 tests/golden/model.py` only checks the committed references and eight
causal controls. `--initial-create` was used once during this authorized initial
authoring. **Do not regenerate frozen reference bytes without logged PM approval.**
No Product output is used as a reference. Human listening remains Michael's #367
sign-off; Stage 1 is publication, not Product acceptance or listened goldens.

Listening at a modest playback level:

| Reference | Cue |
|---|---|
| play-1x-quiet.wav | Opening 0–4.5 s, low level, stereo intact; no click or offset. |
| play-1x-fortissimo.wav | Ending excerpt 146–150.5 s, 1x, loud orchestral hits. |
| scrub-forward.wav | 0.25x, 0.5x, 1x, 2x, 4x; changes at 0.726, 1.451, 2.177, 2.902 s; source chunk crossing at output 2.965 s. Pitch rises with speed; no wrap click. |
| scrub-reverse-1x.wav | End-to-start at -1x; chunk crossing near output 1.529 s; final original frame zero retained. |
| scrub-reverse-2x.wav | End-to-start at -2x; chunk crossing near 0.764 s; pitched up reverse traversal. |
| splice.wav | Voice begins 2.268 s, song resumes 3.268 s; insertion preserves the song tail. Listen across both joins. |
| overdub.wav | Voice mixed over the maximum-RMS music passage (102–106.5 s); first second mixes voice. Exact positive and negative saturation, clip rather than wrap. |
| overwrite.wav | Voice starts 2.268 s; timeline ends 3.268 s, without the old song tail. |
| reset-b.wav | Edited B reset to original A; exactly the fortissimo input. |
| promote.wav | Edited splice promoted to A; exactly the splice reference, including both joins. |

Overdub has 27 samples clipped to +32767 and 5 to -32768. All retained source
audio is unity gain; users should keep listening volume modest for full-scale
outputs. `SHA256SUMS` binds the package bytes. Product execution is Stage 2.
