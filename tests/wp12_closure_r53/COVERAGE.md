# WP-12 / WP-12a R53 coverage

`coverage-ledger.json` splits every assertion of acceptance §Stream 1 WP-12 and WP-12a into
36 rows. 28 map to accepted exact evidence (R25 #44, R29-C #81, R29-A #86, R29-B #83 and the
combined PR #272 disposition #87). 3 are vacuous under the frozen signatures, 2 are unreachable
under DRAFT-9, and 3 genuine reachable gaps are published here. The 3 rows meet the tranche
minimum; no covered row is re-authored.

| Gap row | Cases | Causal controls |
|---|---|---|
| Completed pass renders bit-identically | RENDER-TWOPASS (V3-003 two-pass), RENDER-DECLINE (pass 2 declined), RENDER-FRAGMENTED (3 entries, mid-chunk start, chunk-crossing entry, non-physical order) | `drop_last_frame`, `ignore_entry_start` |
| Promote continuation flush failure enters FAULTED | F-PROMOTE-FLUSH | `failure_keeps_more_work`, `flush_failure_not_faulted` |
| Faulted row on the instance the continuation quarantined, incl. V5-001 pass-1 header-flush path | F-RESPOOL-WRITE, F-RESPOOL-HEADER-FLUSH, F-PROMOTE-WRITE, F-PROMOTE-FLUSH | `arm_after_header_flush`, `service_touches_media`, `flush_failure_not_faulted` |

Render oracle: expected PCM is walked frame-by-frame from the *pre* Side-B entries over a
coordinate-unique audio pattern. The synthetic emitter renders from its own post-copy chunk store,
so the two are not the same code path. Each case renders the whole side through `tape_render` at
1.0× before re-spool, after it in the same session, and after unmount + fresh mount. All three must
equal the logical timeline with zero render block I/O, `tell == total_frames` and `at_end`. The
post Side-B index must be exactly one entry spanning the timeline.

Fault oracle: every call before the planned failure succeeds with `more_work`. The single
failing callback is on a continuation (call index ≥ 1) and the failing call is the last one,
returning `TAPE_ERR_IO` with `more_work == false`. The 15 columns are then probed in plan order,
`arm`/`feed` first (the V5-001 unsafe path). The 11 `F` cells must return `TAPE_ERR_FAULTED` and
the 4 allowed ones `TAPE_OK`, all with zero block events (`dup` also zero destination events). The
device hash before `unmount` must equal the hash at fault.

Each mutant must kill exactly its declared case set and leave every other case green.

## Not gaps (details in the ledger)

- **PM finding, unreachable:** "audio must not stop" is stated for each of respool, promote and dup.
  Under engine-api §10, respool and promote are `B` from Playing and `set_rate` is `B` in every
  in-progress row, so their retained rate is always 0 and the clause is observable only for dup
  (accepted, R29-B). PM decides whether to scope the clause to dup.
- **Unreachable, not a conflict:** dup own-device write/flush failure. `tape_dup` never writes its
  source (tapefs §9.5; engine-api §7.2).
- **Vacuous:** changed-argument continuation for promote and respool, and re-entrancy for respool.
  None of these signatures has a fixed continuation argument or a progress callback. PM already
  confirmed the respool items in R29-C.

Excluded: Product binding or acceptance, WP-10 crash enumeration (#105), listening/goldens,
hardware. No complete WP-12/WP-12a claim is made until a Product run is independently disposed.
