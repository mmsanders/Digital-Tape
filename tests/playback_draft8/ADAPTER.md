# Adapter contract — DRAFT-8 playback tranche

The adapter is mechanical plumbing from the public DRAFT-8 API to this independent package. Do not change assertions, expected bytes, seek targets, rates, call ordering, or tolerances.

The runner invokes `<adapter command> --fixture <raw-VO08-path> --out-dir <directory>`, with a finite timeout. Emit `observation.json`, `forward-1x.pcm`, `seek-boundaries.pcm`, and `reverse-neg1x.pcm`; PCM is interleaved stereo s16le at 44.1 kHz.

`observation.json` schema is `playback-draft8-observation-v1`, binds `fixture_sha256`, declares adapter kind `product` or `synthetic`, and records every public call plus every block callback `{call_index,op,lba,count,rc}` without filtering.

Scripts: forward = mount A frame 0 warm NULL, rate +65536, service to `more_work=false`, render 15, unmount. Seek = mount A, rate +65536, for each `0,1,4,5,6,8,9,10`: seek N, service to false, render 1; unmount. Reverse = mount A, seek 15, rate -65536, service to false, render 15, unmount. All calls return `TAPE_OK`.

Playback is read-only: callbacks may occur only during mount/service, must be successful in-range reads, and no write/flush is permitted. Mount and service reads must both be observed. Seek/rate/render may not perform block I/O.

`_synthetic_adapter.py` is verifier-plumbing only, never product evidence or acceptance.

## Identity, provenance, exit, and retention contract

Every run must declare a nonempty adapter kind, adapter ID, adapter source identity,
adapter build identity, verifier source commit, and verifier source tree. These are
declared provenance strings unless separately authenticated by a hash or external
repository evidence; merely naming a commit does not authenticate it. When
`--adapter-source` names a readable file, the runner additionally records that
file's SHA-256.

Corrected evidence uses schema `playback-draft8-evidence-v2` and assignment
`P1-R4-V`; the prior P1-R2 v1 bundle remains historical evidence for its original
runner and is not silently upgraded.

The observation's adapter kind and ID must exactly match the runner declarations.
Offline replay enforces that same equality, requires the execution record and
`output/adapter-exit.txt` to agree on a successful zero exit, and rejects missing,
nonzero, timed-out, relabeled, or ID-mismatched bundles. Synthetic and product
evidence therefore cannot be changed into one another by editing only the manifest.

The evidence destination may be absent or an existing empty directory. A nonempty
destination is rejected before any write and no existing byte is removed. The
runner never clears an earlier evidence directory. Timeout and nonzero-exit runs
return failure while retaining stdout, stderr, the exit/timeout record, result, and
hash-bound manifest for diagnosis; they are not replay-passable evidence.
