# Plate map — packet WP04-01

Bed positions, front-left origin. The letter is **not** related to the hook
depth: the mapping is in `manifest.json` and deliberately not on the card.

| Letter | Bed X | Bed Y | Role |
|---|---:|---:|---|
| **D** | 12 | 12 | bed-control |
| **R** | 38 | 12 | variant |
| **T** | 64 | 12 | variant |
| **K** | 12 | 42 | variant |
| **W** | 38 | 42 | variant |
| **B** | 64 | 42 | variant |
| **M** | 12 | 72 | variant |
| **H** | 64 | 72 | bed-control |
| **X** | 90 | 12 | orientation-probe |

Plate extent 190 × 198 mm on a 220 × 220 mm bed — **fits**.

`D` and `H` are the same geometry as one of the lettered variants, placed at
opposite ends of the populated area. If they do not rank together, bed position
is affecting the parts more than the swept parameter is, and the next sweep needs
coarser steps rather than finer ones.
