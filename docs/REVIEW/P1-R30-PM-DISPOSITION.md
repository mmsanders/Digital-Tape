# P1-R30 PM disposition — corrected R29 packages return to Software

**25 September 2026 UTC.** Input product `main`:
`3b740fa99e5f1bbeca8cc471bdadf05ecda7a555`; independent verifier `main`:
`50c47c1b9087de52f66d831ef2fe00cc02273087`. PM issue
[#233](https://github.com/mmsanders/Digital-Tape/issues/233); Verification issue
[#76](https://github.com/mmsanders/digital-tape-verification/issues/76) and merged
Verification [PR #77](https://github.com/mmsanders/digital-tape-verification/pull/77).
Frozen DRAFT-8 hashes remain those in [`spec/VERSION.md`](../../spec/VERSION.md).
This is a PM routing and evidence-boundary decision. It does not accept product
source, merge a product candidate, or replace independent Verification.

## Decision

Verification completed the requested correction and republication. Return all three
R29 lanes to Software on fresh product branches from current main, with the exact
corrected verifier tree imported before any binding or engine change.

No roadmap rung advances. Product PRs #227, #229 and #230 and their prior evidence
remain held because they predate the corrected package trees. The narrow raw public
observations authenticated from #227 remain recorded at Verification's stated
boundary; its continuity/no-restart and minimum-positive-budget claims are not
accepted. Fresh product evidence is required for every corrected package.

## Authenticated verifier return

Verification PR #77 has already merged. Its source correction and finding are cleanly
separated:

| Item | Exact identity |
|---|---|
| Correction source | commit `7408f0aad4dff2284b2b3f56b39c3ea6e3da2dc7`, tree `85e7689f2bdd07fd0cf37e1dc89170c7a11d3728` |
| Published finding | commit `d257d85054aa2b988697d487ff0d3f443ea41718` |
| Verification merge | `50c47c1b9087de52f66d831ef2fe00cc02273087` |
| Package self-tests | workflow `36107243960`, completed `success` |

The correction changes only the three verifier packages; the following commit adds
only the finding. PM inspected the changed parser, media, oracle, fixture, adapter
contract and negative-control sources. CI supplies the mechanical all-package
self-test result, so PM did not repeat the multi-million-case product campaign.

| Lane | Corrected package tree | Observation schema | Canonical set |
|---|---|---|---|
| R29-C re-spool | `7e98b40c6aceb0a5759bfb1499091a4c9f541927` | `WP10-RESPOOL-OBSERVATION-2` | 4,209,696 cases; `02c52de7a7c51a6ffafe5c9d5afad9c23032b72fc11aaf206bb27a9c9506d3e1` |
| R29-A promote | `e99ba0f2cf3f9e8cdd22199cbd9cc502cc5638a3` | `PROMOTE-OBSERVATION-2` | 44,311 cases; `8732af9434437d0411731b3e4909a2ca9a1278778e5d9c8947642cec7b793442` |
| R29-B format/duplicate | `f76ab23d17beb9212f8ee1d17d3d1875b74abc7d` | `FMTDUP-ID-OBSERVATION-2` | 57,611 cases; `c493e77dff948df48d9c67c51ef4b68f0a61d2e02615b2d08760a594e79dc4e3` |

The canonical membership, order, counts and digests are unchanged. The package trees
changed because their observation contracts and independent parsers changed.

## Why the correction is ready for product binding

The A/B fixtures now use truthful compact geometry: 9 seconds for four chunks and
21 seconds for eight chunks. Both independent media parsers include raw device
capacity and enforce phase-0 capacity plus ordered version, state and geometry
admission before index selection. Red controls reject the former 60-second/4-or-8-
chunk defect, stored/derived disagreement and short media.

All three long-operation contracts now require the minimum positive budget of one,
retain cumulative chronological chunk-region write LBAs, require exact trace-prefix
continuity and reject a repeated copied LBA. Adapter operation labels remain allowed
only as non-causal metadata. Constant-label repeated-copy negative controls go red.
Where raw writes cannot distinguish a restart, the verifier makes no private engine
identity claim.

Promote's stored-position family now expressly models caller-owned storage. It
preserves the caller table through nonterminal calls and clears it only after the
caller observes terminal `TAPE_OK && !more_work`, matching ADR-156 without inventing
an engine API.

These corrections close the publication defects identified in R29 arbitration. They
do not prove that the current product implementation passes; that is Software's next
test-first task and Verification's later independent disposition.

## Prior product evidence boundary

Verification authenticated PR #227 head
`75b36a90cb72e3fa076e62baec1440f48afaf1b6`, tree
`efe5165bab8af07d4e919a0cd20637892b4d2cf6`, its 4,209,696-case aggregate and
retained functional evidence. The retained raw results support only the six named
clean/headroom terminal outcomes, two zero-needed no-I/O outcomes, the recorded
in-progress and Faulted matrix results, zero-budget no-work behavior, ordinary
post-BUSY progress, own-device failure outcomes, ring drain, underrun and abort.

They do not support continuity/no-restart or budget 1. The old adapter used constant
`R1`/`R2`/`R4` labels and a global callback counter, and every small-budget call used
1024. Therefore #227's old aggregate green does not carry to the corrected R29-C
tree. PR #229/#230 evidence likewise predates the corrected R29-B/A trees and receives
no credit.

## Software route and stop

Software receives one bounded issue covering three separately identifiable branches
and PRs, in priority order R29-C, R29-A, R29-B. Each branch starts from the product
main named in that issue and obeys Structural Rule 1: exact verifier import commit
first, mechanical adapter/CI binding next, then any engine fix exposed by the unchanged
package. Software may carry forward useful engine changes from held candidates only
after the corrected import and without carrying forward old evidence as acceptance.

Each returned PR must retain first-failure evidence, cite exact product and verifier
identities, and remain unmerged for blind independent Verification. The prior three
PRs remain held/superseded; closing or relabeling them does not create acceptance.

No Hardware, Surge, Michael or Verification issue is warranted this round. WP-11
goldens remain red. The promote consumer/release hold and every hardware, card,
physical-work, fabrication, charging, safety, wallet and regulatory hold remain in
force.
