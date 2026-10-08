# READ-1 coverage and candidate census — 59 cases / 3 meaningful rows

`cases.py` emits the exact ordered executable list and twelve actual Product control
requirements. Every case needs a fresh initialized instance/device. No case is a
padding duplicate; dimensions exercise different issued budgets or boundaries.

| Row | Cases | Assertions and principal controls |
|---|---:|---|
| R1-volume-work | 24 | All five named budgets at 1-frame final hold, 32 KiB transfer edge (8193), and ring wrap/partial tail (40001); full exact C60 at 1024; fragmented E=3/128/4096 short and maximum-E long at budgets 1/1024. Requested payload blocks/callbacks, all per-call counts, exact PCM/final frame/status, finite convergence, V bound, no retained movement and PCM-copy bound. Reread/tiny-transfer/full-rescan/movement/budget controls |
| R2-PCM-invalidation | 33 | ±1x/±0.5x/±12x/INT32_MIN/MAX/stopped across physically discontinuous/shared-chunk mapping and interpolation boundaries; covered/uncovered/beyond-end uint64 seek and reverse escape, same/cross-side invalidation, cold remount changed content, successful overwrite/splice invalidation, failed/partial reads and recovery, non-vacuous FAULTED buffered drain, empty/zero budget/lookahead/wrap; nine ordered warm descriptors and warm-flag clearing on same-side selection. Exact arithmetic/position/flags, render I/O absence, seek and episode V bounds; stale-side/content/warm and lookahead controls |
| R3-idle-seam | 2 | Sixteen repeated already-done service calls both Playing and stopped, no recording/long-op obligation: zero device/mapping/PCM work, <=8 counted internal loop iterations, immediate done. Actual seam nonzero/zero primitives, invented-zero counter rejection, idle-mapping/nine-loop controls, shipping equivalence/absence |

The row counts are verified against the machine census in CI. Failed-read behavior
reports requested/completed/errors separately and does not assert the no-error volume
bound. Fragmented payload/callback ceilings are asserted at their issued budget 1024;
fragmented budget1 still gates exact output, per-call budget, mapping visits, copy and
retained movement. Full C60 requests obey 128-frame service-until-done/render cadence;
there is no enlarged render request, consumer cache or PCM tolerance.

Discontinuous bounds are derived per issued episode: reset before the initiating API,
then E/B/F accumulate until the next discontinuity. Seek also has its per-call bound.
No global forward volume ceiling is applied across arbitrary jumps. Ordinary <=12x
rate fixtures fit the caller ring and must give exact serviced requests through the
frozen endpoint; extreme rates require an exact nonempty serviced prefix when a sample
is due, may underrun beyond coverage, and retain exact endpoint/error distinctions.

The two content edits are bounded invalidation checks using unchanged public calls
and carried write semantics. They are not a new write-persistence campaign. A failed
commit flush establishes real FAULTED and drains previously serviced PCM without I/O,
then reaches underrun; a read failure alone does not establish FAULTED.

## READ-1 evidence and exclusions

Verifier selftests check fixture validity/CRCs, fixed ceilings, literal PCM vectors,
oracle red controls, canonical streaming replay and the actual C counting backend.
Their `actual_Product_runs` is zero. Actual Product cases/controls, counters/sites,
shipping absence/equivalence, Phase1 goldens/regressions/resources and exact-head
disposition are READ-2 work after Software #409's returned candidate.

No hardware deadline, total CPU instruction count, wall-time PASS, write/async/
recording redesign, firmware activation, golden regeneration, WP14 A8 acceptance,
Windows10/physical/card qualification or reserved merge approval is granted here.
