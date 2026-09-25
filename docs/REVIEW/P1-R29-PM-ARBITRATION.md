# P1-R29 PM arbitration — Software returns and held operation lanes

**25 September 2026 UTC.** Input product `main`:
`8276d8f22da34a53f9f52dae8d3bd1acb3c763d9`; independent verifier `main`:
`30b820b9e0c41396ceb9409a389fb73e66acc0fe`. PM issue
[#231](https://github.com/mmsanders/Digital-Tape/issues/231), updated
2026-09-25 06:30:50 UTC. Frozen DRAFT-8 hashes remain those in
[`spec/VERSION.md`](../../spec/VERSION.md). This is a PM routing/spec-reading
decision, **not** independent acceptance, product-code review, or merge authority.

## Exact candidates

| Lane | Product candidate | Disposition |
|---|---|---|
| R29-C re-spool | [PR #227](https://github.com/mmsanders/Digital-Tape/pull/227), head `75b36a90cb72e3fa076e62baec1440f48afaf1b6`, tree `efe5165bab8af07d4e919a0cd20637892b4d2cf6` | Route this head, **not** superseded `8026c860...`, to blind Verification. CI evidence-integrity/repo hygiene green; product engine run `36101173027` has 48 canonical crash shards and aggregate job `107966850924` PASS (4,209,696 cases; `fdf477dc99cf55b54aa5dcfc314fcd607e5d2e3269859d9c16a95d58f410e78b`, artifact `10849219575`). Its sole engine-workflow red is the standing WP-11 missing golden. Software separately reports the budget-1 continuation now finishes in nine calls; the published small-budget verifier case does not cover budget 1. Verification must independently audit the harness-token restart oracle before crediting BUSY/continuity. Hold PR for exact-head disposition or a reported verifier correction. |
| R29-B format/dup | [PR #229](https://github.com/mmsanders/Digital-Tape/pull/229), head `42e3bf63ee79add76e89f058e6d13d7570eba4c4`, tree `0f65921553ab6af3564255c7b6c1cb7277f6bed4` | Blocked at canonical case 0. No engine commit; no later case is established. Hold for verifier-owned republication. |
| R29-A promote | [PR #230](https://github.com/mmsanders/Digital-Tape/pull/230), import-only head `02ce3cdc674c5f026572b5e400ea26f1d0030ff3`, verifier tree `4a74a2a410673e4e251405995d4b5e561ef6aefc` | Blocked before binding, as all seeds are unmountable. Its superseded PR #37 adapter/tree-authentication red is expected; no product behavior was exercised. Hold for verifier-owned republication. |

The R29-C import tree `5637fbd3e89316889b4bbd52d2a72c95e3c278e1`
matches verifier publication `f940acc355d1b2e4eb3ccf4788a14136a030b633`.
The product's evidence-integrity workflow `36101172964` passed. Those mechanical
facts and Software's green run do not supply an independent verdict. PM did not
rerun the multi-million-case suite: the current charter assigns mechanical
authentication to CI, and there is no disputed identity requiring a third run.

## Geometry correction before A/B product work

Frozen TapeFS §2.1 derives `ceil(60 * 44100 / 131072) = 21` chunks.
The A/B verifier fixtures instead encode `nominal_length_s=60` with stored
`total_chunks=4` or `8` and a device sized for that stored count. Section 4.1
phase 2 step 5 requires **equality** to the derived count and a fitting region;
§9.6 rejects invalid format geometry before destination I/O. At #229 case 0
the bytes before/after are unchanged, the product remount reports
`TAPE_ERR_GEOMETRY`, and `media.py` incorrectly predicts `TAPE_OK` (artifact
`10845098069`; reproducer SHA-256
`c03f105c8eec997f2ccb675179846fd5f196b4515c7cb25b2a3519824bfdc7a7`).
Software also reports that a scratch-only one-field label correction to 9 s/4
chunks or 21 s/8 chunks mounts the promote seeds; that is a diagnostic, not an
authorized fixture edit. Verification owns both fixture republications and a
`media.py` equality/geometry check with red negative controls. Preserve the
scenario intent, exact case census and any changed case-set digest as **new**
publication identities; do not patch the imported product copies, weaken
`GEOMETRY_OK`, or start A/B product work on invalid seeds. After republication
PM will issue fresh Software directions for a clean test-first import/binding.

## Rulings

1. **Promote defect timing.** Defer the three reported defects to R29-A after a
   valid verifier-first publication: budget-1 livelock, unenforced §10 BUSY
   cells (including write-bearing recording calls), and full-chunk zero-fill
   rather than exact data-block copy. The mid-promote gap can permit writes
   during partial copy; severity is high even though Software reports no
   firmware promote caller today. `tape_promote` is **not approved for new
   consumer use or release** on current main. No separate untested quick fix,
   no merge of #230, and no acceptance from the old narrow PR #37 tests.
   Verification must independently cover budget 1 and the full in-progress
   row before this hold can lift. If a current caller is found, escalate at once
   rather than rely on this scheduling decision.
2. **Stored positions.** TapeFS §11 and engine-api §5 make `(uuid, side)` position
   storage caller-owned device flash. The public `tape_promote` signature has
   no table, callback, or flash handle for it. Read the §9 terminal-clearing
   obligation as a **caller action on `TAPE_OK && !more_work`**, for full,
   decline, resume and NOTHING-TO-DO paths; do not clear on an incremental
   continuation, error, or `TAPE_ERR_BUSY`. A harness may model a caller-owned
   table and expose its raw before/after values after the caller performs that
   action. Label that as a caller-model observation, **not** an engine-observed
   side effect or independent engine acceptance. The literal attribution to
   `tape_promote` in frozen §9 conflicts with the ownership/API and remains a
   documented spec discrepancy; Verification should flag any family it cannot
   independently bind under that reading. No invented engine API or DRAFT-8
   byte edit is authorized. A future spec-bundle correction requires separate
   PM issuance and review.
3. **`operation_token`.** There is no public engine operation identity. A
   harness-side initiation ordinal may be emitted if its provenance is explicit.
   It is not evidence that the engine preserved an operation: Verification
   judges continuity/restart only from public result, `more_work`, raw callback
   `blocks_done`, device-event counts/traces, arguments and terminal media.
   Re-entry/zero-progress checks must not pass merely because the harness
   reused its own token. This applies to #227's disclosed adapter token and
   the future A/B binding. The published verifier oracles currently compare
   token equality as a restart check (`respool_full_draft8/oracle.py` and the
   R29-A/B oracles); that check is tautological for a caller-generated ordinal.
   Verification must independently determine whether the remaining raw facts
   prove every claimed continuity case; otherwise correct the verifier-owned
   oracle/negative controls and republish before accepting that coverage.
   Such a correction changes the package identity and requires a new product
   binding/run at that publication; the current green count does not carry
   over as if its oracle were unchanged.

WP-07, WP-13 and WP-36 remain the complete accepted packages; WP-10 core is
bounded. WP-11 listening/goldens remain red, and all physical/card, fabrication,
charging, safety, wallet and other product holds remain intact. No A/B or C
package/rung advances from this arbitration. Next owner: independent Verification
for exact-head #227 disposition and separate verifier-owned A/B republication;
PM then assesses the returns and issues a fresh Software task where warranted.
