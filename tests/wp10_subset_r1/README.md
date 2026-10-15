# Q-P2-1 any-subset persistence — Verification #183

Authoring return: **model self-test PASS; current-engine execution BLOCKED on
Product adapter import**. No engine operation has run in this mode. This is not
WP-10 acceptance, a defect finding, media qualification or batching permission.

Inputs: Product `c6ff868086e3333bb7568e60d3a2f4ec60fd3344`; immutable engine tree
`d96b4245e04d74078f8938744b1394c3018516f7`; Verification base
`9587317ac4bca4e8164347f0ec62eeb719245cf7`; live #183/ADR-182; original Q-P2-1(a)
in `findings/P2-R1-WP14-PREFLIGHT-2026-10-05.md`. Product implementation was not
inspected. Public adapter READMEs/interface descriptions were read only to find
the existing campaign route. No old publication is edited.

Run from this directory:

```sh
python3 -B selftest.py
python3 -B audit.py
```

`model.py` retains every attempted 512-byte event since the last successful
barrier, including repeated-LBA versions and error acknowledgements. One
multi-block call creates one event per 512-byte unit, retaining its call number.
`crash_image(order)` selects any subset in any landing order; the last landed
version at each LBA wins. No per-LBA ordering guarantee is assumed. Cross-LBA
permutations commute. Torn bytes are rejected and remain the old separate model.
`remount(order)` creates a fresh device from durable bytes only.

A successful flush persists actual final working state and ends the epoch.
A failed flush does neither. An error write can persist even when its working
effect is absent. If an error's working effects are unknown, reads, further
writes and successful barriers are blocked until the binding supplies the actual
working image with `resolve_working`; failure/cut remains available. This avoids
inventing either zero durability or guaranteed full write completion on error.
Atomic all-or-none effects per unit remain the standing assumption, not a claim
that media was qualified. The model projects the final persistence subset at a
cut (including background persistence before/within a failed flush); it is not a
time-based storage scheduler. A binding must not let its own RAM survive a cut.

For epochs with **0–8 attempted units**, `exhaustive` emits every mask and every
per-LBA last-selected-version class. It omits only cross-LBA permutations and
non-winning orders that produce the same durable image. For 8 distinct LBAs it
emits 256 classes; for 8 writes to one LBA, 1,025 mask/winner classes. Equivalence
to every subset permutation is independently brute-forced through 5 events with
interleaved repeated LBAs. These are model bounds, not engine campaign counts.

For larger epochs the planner refuses the exhaustive label. `sampled` emits
none/all/later-only plus 64 seeded subset/order draws, **67 records per seed**.
Seeds `1`, `183`, `3647685189` (hex `d96b4245`) are demonstrated on 32 events
cycling over 8 LBAs. All **201** actual masks, landing orders and image hashes
are in `sampled-masks.jsonl`; duplicates are retained and are not additional
coverage. The file is model evidence, never a Product trace. A future engine run
must record its own real epoch lengths, seeds, masks and full order, not reuse
these 32-event coordinates on a different trace. Bit 0 (rightmost mask bit) is
the first event of the current epoch; landing-order IDs are absolute device IDs.

The self-test proves `(a,B)` is reached while old flush-required/write-through
modes and every write-through prefix miss it. Controls also cover version loss,
wrong landing order, failed-I/O assumptions, barriers, multi-block splitting,
two interruptions and RAM reuse. Dropped-barrier and early-identity examples
are explicitly toy causal controls, not a substitute TapeFS oracle.

See `ADAPTER.md` for the concrete execution dependency, per-operation route and
required return. Original operation outcomes remain authoritative. In particular,
destructive operations do **not** acquire an “old card unchanged” requirement.
