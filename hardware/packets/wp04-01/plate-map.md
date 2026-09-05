# Plate map — packet WP04-01 (rev 4)

**Two experiments, one plate.** `carrier-*`, `hook-bar` and `test-frame` are the
WP-04 latch sweep. `shell-base-*` and `shell-lid-*` are the WP-24 cartridge clasp
sweep. They share a bed and nothing else.

Fits a **162 × 161 mm** bed. Laid out for 180 × 180 mm — a Prusa Mini or Bambu A1 mini.

The letter is **not** related to hook depth; the mapping is in `manifest.json` and
deliberately not on the card.

| Part | X | Y | W | H |
|---|---:|---:|---:|---:|
| shell-base-G | 12 | 12 | 62 | 28 |
| shell-base-Q | 78 | 12 | 62 | 28 |
| shell-base-A | 12 | 44 | 62 | 28 |
| shell-base-N | 78 | 44 | 62 | 28 |
| shell-lid-1 | 12 | 76 | 62 | 28 |
| shell-lid-2 | 78 | 76 | 62 | 28 |
| test-frame | 12 | 108 | 30 | 26 |
| carrier-W | 46 | 108 | 14 | 12 |
| carrier-B | 64 | 108 | 14 | 11 |
| carrier-R | 82 | 108 | 14 | 11 |
| carrier-D | 100 | 108 | 14 | 11 |
| carrier-T | 118 | 108 | 14 | 11 |
| carrier-K | 136 | 108 | 14 | 11 |
| carrier-M | 12 | 138 | 14 | 11 |
| carrier-H | 30 | 138 | 14 | 11 |
| carrier-Z | 48 | 138 | 14 | 11 |
| hook-bar | 66 | 138 | 70 | 5 |

`D` and `H` are the same geometry as one of the lettered variants, placed
apart on the bed. If they do not rank together, bed position is affecting the
parts more than the swept parameter is, and the next sweep needs coarser steps.
