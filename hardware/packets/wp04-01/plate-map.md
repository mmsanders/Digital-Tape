# Plate map — packet WP04-01 (rev 2)

Fits a **162 × 65 mm** bed. Laid out for 180 × 180 mm — a Prusa Mini or Bambu A1 mini.

The letter is **not** related to hook depth; the mapping is in `manifest.json` and
deliberately not on the card.

| Part | X | Y | W | H |
|---|---:|---:|---:|---:|
| test-frame | 12 | 12 | 30 | 26 |
| carrier-X-onside | 46 | 12 | 14 | 23 |
| carrier-W | 64 | 12 | 14 | 12 |
| carrier-B | 82 | 12 | 14 | 11 |
| carrier-R | 100 | 12 | 14 | 11 |
| carrier-D | 118 | 12 | 14 | 11 |
| carrier-T | 136 | 12 | 14 | 11 |
| carrier-K | 12 | 42 | 14 | 11 |
| carrier-M | 30 | 42 | 14 | 11 |
| carrier-H | 48 | 42 | 14 | 11 |
| hook-bar | 66 | 42 | 70 | 5 |

`D` and `H` are the same geometry as one of the lettered variants, placed
apart on the bed. If they do not rank together, bed position is affecting the
parts more than the swept parameter is, and the next sweep needs coarser steps.
