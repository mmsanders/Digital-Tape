# Plate map — packet WP04-01 (rev 5)

**Two experiments, one plate.** `carrier-*`, `hook-bar` and `test-frame` are the
WP-04 latch sweep. `shell-base-*` and `shell-lid-*` are the WP-24 cartridge clasp
sweep. They share a bed and nothing else.

Fits a **240 × 131 mm** bed. Laid out for 250 × 210 mm — a Prusa Mini or Bambu A1 mini.

The letter is **not** related to hook depth; the mapping is in `manifest.json` and
deliberately not on the card.

| Part | X | Y | W | H |
|---|---:|---:|---:|---:|
| shell-base-G | 12 | 12 | 62 | 28 |
| shell-base-Q | 78 | 12 | 62 | 28 |
| shell-base-A | 144 | 12 | 62 | 28 |
| shell-base-N | 12 | 44 | 62 | 28 |
| shell-lid-A | 78 | 44 | 62 | 28 |
| shell-lid-N | 144 | 44 | 62 | 28 |
| shell-lid-G | 12 | 76 | 62 | 28 |
| shell-lid-Q | 78 | 76 | 62 | 28 |
| test-frame | 144 | 76 | 30 | 26 |
| carrier-W | 178 | 76 | 14 | 12 |
| carrier-B | 196 | 76 | 14 | 11 |
| carrier-R | 214 | 76 | 14 | 11 |
| carrier-D | 12 | 108 | 14 | 11 |
| carrier-T | 30 | 108 | 14 | 11 |
| carrier-K | 48 | 108 | 14 | 11 |
| carrier-M | 66 | 108 | 14 | 11 |
| carrier-H | 84 | 108 | 14 | 11 |
| carrier-Z | 102 | 108 | 14 | 11 |
| hook-bar | 120 | 108 | 70 | 5 |

`D` and `H` are the same geometry as one of the lettered variants, placed
apart on the bed. If they do not rank together, bed position is affecting the
parts more than the swept parameter is, and the next sweep needs coarser steps.
