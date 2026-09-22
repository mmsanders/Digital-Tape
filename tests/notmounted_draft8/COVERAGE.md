# WP-06h not-mounted assertion matrix

| ID | Assertion | Basis | Negative control |
|---|---|---|---|
| NM-A01 | Every §10 ordinary call returns `TAPE_ERR_NOT_MOUNTED` before mount | Engine API §10; WP-06h | one result changed to OK |
| NM-A02 | Every §10 ordinary call returns `TAPE_ERR_NOT_MOUNTED` after a successful mount→unmount | Engine API §10; WP-06h | one result changed to OK |
| NM-A03 | Every target is independently exercised exactly once; no aggregate call sequence can mask another defect | verifier isolation requirement | missing/duplicated probe |
| NM-A04 | After-unmount cases prove setup mount and setup unmount both succeeded before the target call | Engine API §10 row reachability | missing/failed setup |
| NM-A05 | `tape_tell` leaves `*out_frame` at `0x1111111111111111` on refusal in both phases | Engine API §6 / V5-009; WP-06h | sentinel overwritten |
| NM-A06 | `tape_dup` is exercised as the unmounted **source** with a distinct valid destination device | Engine API §10 note on dup source row | target omitted/wrong function |

Callback deltas are preserved as diagnostics but are not an independent WP-06h acceptance gate; the issued criterion specifies return codes plus the `tape_tell` out-parameter rule.

Excluded: `tape_init`, `tape_mount`, `tape_format`, destination-side `tape_dup`, crash/continuation behavior, and product-source acceptance.
