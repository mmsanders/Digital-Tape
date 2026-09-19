# Plate map — packet WP04-01 (rev 6)

**Two plates, two experiments.** `plate-wp04` is the latch sweep:
`carrier-*`, `hook-bar`, `test-frame`. `plate-wp24` is the cartridge clasp
sweep: every `shell-base-*` **with its matching `shell-lid-*` in the same
job**, because a base and its lid are a matched pair and printing them
apart re-introduces the confound the per-base lids removed.

Laid out for a **180 × 180 × 180 mm** nominal
envelope with **5 mm clearance** from every edge and a
**175 mm** height cap. The envelope is the machine's advertised
figure, not a measured usable area — nothing here has been printed.

The letter is **not** related to hook depth; the mapping is in
`manifest.json` and deliberately not on the card.

| Plate | Part | X | Y | W | H |
|---|---|---:|---:|---:|---:|
| plate-wp24 | shell-base-G | 5 | 5 | 62 | 28 |
| plate-wp24 | shell-base-Q | 71 | 5 | 62 | 28 |
| plate-wp24 | shell-base-A | 5 | 37 | 62 | 28 |
| plate-wp24 | shell-base-N | 71 | 37 | 62 | 28 |
| plate-wp24 | shell-lid-A | 5 | 69 | 62 | 28 |
| plate-wp24 | shell-lid-N | 71 | 69 | 62 | 28 |
| plate-wp24 | shell-lid-G | 5 | 101 | 62 | 28 |
| plate-wp24 | shell-lid-Q | 71 | 101 | 62 | 28 |
| plate-wp04 | test-frame | 5 | 5 | 30 | 26 |
| plate-wp04 | carrier-W | 39 | 5 | 14 | 12 |
| plate-wp04 | carrier-B | 57 | 5 | 14 | 11 |
| plate-wp04 | carrier-R | 75 | 5 | 14 | 11 |
| plate-wp04 | carrier-D | 93 | 5 | 14 | 11 |
| plate-wp04 | carrier-T | 111 | 5 | 14 | 11 |
| plate-wp04 | carrier-K | 129 | 5 | 14 | 11 |
| plate-wp04 | carrier-M | 147 | 5 | 14 | 11 |
| plate-wp04 | carrier-H | 5 | 35 | 14 | 11 |
| plate-wp04 | carrier-Z | 23 | 35 | 14 | 11 |
| plate-wp04 | hook-bar | 41 | 35 | 70 | 5 |

`D` and `H` are the same geometry as one of the lettered variants, placed
apart on the bed. If they do not rank together, bed position is affecting the
parts more than the swept parameter is, and the next sweep needs coarser steps.
