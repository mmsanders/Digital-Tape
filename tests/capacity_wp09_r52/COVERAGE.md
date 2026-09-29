# WP-09 R52 assertion matrix

The 27 rows are the Cartesian product of three modes, three positions, and
three near-capacity shapes.  “Covered” means an assertion over public calls,
raw device callbacks, raw media, or exact remounted PCM.  Synthetic green
evidence proves this verifier, not Product behavior.

| ID | Independent assertion | Normative basis | Targeted red control |
|---|---|---|---|
| C01 | Exactly 27 unique plan rows: overwrite/overdub/splice × start/middle/end × 1/17/4095-frame final prefix | acceptance WP-09; Engine API §11 | case census/order |
| C02 | Final feed is `TAPE_ERR_CARTRIDGE_FULL`, with exact `0 < accepted < requested` | Engine API §7; TapeFS §9.1 | wrong accepted count |
| C03 | Feed reserves without any block callback | Engine API §7 | feed I/O |
| C04 | Accepted prefix remains owed; immediate commit is BUSY; service completes it | Engine API §7–§7.1 | premature commit |
| C05 | Service writes obey each 1/17/64-block budget and end with durable flush | Engine API §6–§7 | lost/corrupt prefix |
| C06 | Allocation touches exactly `[3,total_chunks)`, never below Side A high-water 2 or outside media | TapeFS §6–§7 | illegal allocation |
| C07 | Raw pre-media independently derives `free_next==3`; raw post-media derives capacity exhausted | TapeFS §5–§7 | structural/raw assertions |
| C08 | Commit is entries → flush → one-block header → flush in inactive B1, exactly two flushes | TapeFS §8; Engine API §7.1/invariant 24 | absent final flush |
| C09 | Fresh remount reads both superblocks and both B candidates, selecting sequence 4 | TapeFS §4–§5 | raw winner assertions |
| C10 | Exact raw entry array matches overwrite/overdub/splice edit shape and preserves B0 | TapeFS §8–§9.1 | structural/raw assertions |
| C11 | Exact PCM independently preserves/mixes/inserts seed and accepted prefix, with no invented suffix | TapeFS §9.1; acceptance WP-09 | corrupt prefix; invented suffix |
| C12 | Public post-info reports exact frames/entries and zero free chunks | Engine API §4; TapeFS §7 | public/raw cross-check |
| C13 | Adapter verdict labels are ignored | verifier independence boundary | spoofed label still checks |

## Shape arithmetic

| Shape | Total chunks | Free chunks from `free_next=3` | Prefill | Final request | Accepted | Service budget |
|---|---:|---:|---:|---:|---:|---:|
| one-free-one-left | 4 | 1 | 131071 | 64 | 1 | 1 |
| two-free-seventeen-left | 5 | 2 | 262127 | 64 | 17 | 17 |
| three-free-4095-left | 6 | 3 | 389121 | 4096 | 4095 | 64 |

All prefill calls request at most 4096 frames and are serviced to completion.
The larger final request therefore reaches the physical capacity wall in that
call without assuming an unspecified successful short-accept behavior.

## Exclusions

This tranche does not claim Product evidence until a separately built public
adapter's observations pass replay.  It also excludes source review, firmware
transport/button behavior, crash injection, commit latency, golden WAV human
listening, hardware atomicity, and unrelated WP-06/WP-10/WP-12/WP-36 closure.
