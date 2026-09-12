# Phase 1 kickoff — P1-R1 PM disposition

**Issued 12 September 2026 UTC · PM: Astra / ChatGPT Work.**

Michael requested this review and direct publication of lead instructions. Normal
PM authority applies, not the expired combined-lead mandate. No product code is
reviewed, changed or merged here; independent acceptance remains Verification's.

## Decision and exact inputs

**GO for bounded Phase 1 development; no new package acceptance or operations freeze.**

- Product input main: `4c273ce57ce6848762b00b8990b0b29a3dc9f74b`.
- Verification return: `mmsanders/digital-tape-verification` main at
  `689c41909e6bbec499aeb0243008222d7a1c9f64`.
- VT8-001 baseline: verifier `tests/ops_draft8/` at
  `a91138667673fcf19dc9e83c9034322b982b1771`; identical at the return commit.
  Directory Git tree: `c8a43df69a6be8e2c34bf79a1d79933abf48286a`.
- Mount package Git tree in both repositories:
  `4aaa1499429cbdc658065ac336ecab4783d1d730`.
- DRAFT-8 SHA-256 values (unchanged): TapeFS
  `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`;
  Engine API `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`;
  Acceptance `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`.
- PR #20 remains open/draft at `2e0e8a4b7bff42797ac37901196e5ea348b2e392`.
  The dispositioned observations are associated by the run packet with tested
  engine commit `740c97e998c7672d9e98916102be84430993521b`.
  Later-head equivalence is not newly certified by this PM review.

## Assessment of Verification's return

The [independent disposition](../verification/mount-observation-disposition-2026-09-11.md)
is copied verbatim from the return commit's findings directory. Authorship remains
Verification's. PM records its narrow positive disposition: **274/289 before and
289/289 after, with no record-integrity or recomputed-verdict mismatches**.
The prior gzip-access obstacle is resolved; do not ask Michael for the same logs again.

PM reproduced Verification's audit against the exact product input. Log hashes,
fixture identities, order, allowed outcomes and recomputed results agree. This is
reproduction of independent evidence, not a second independent acceptance or a
new engine run. Raw JSONL contains adapter hashes but not engine Git SHAs; the
committed run packet supplies that association. Preserve this provenance limit
and include explicit build/source provenance in future run packets.

The two VT8-001 cases are a useful, spec-grounded next slice: reset-B from degraded
media and one 128-frame end splice use all structurally valid slots for sequence
selection, including a semantically invalid high-sequence slot. Public operations
and callback/media observations avoid inventing allocator or sequence-query APIs.
Published self-tests reproduce: two conforming observations, six rejected mutations;
synthetic runner 2/2. **These are not product-engine results.**

The following are verifier-package findings, not defects alleged against an unseen
implementation or the frozen specification.

| ID | Finding / evidence | Disposition and owner |
|---|---|---|
| P1-R1-V01 | Recording oracle counts two commit flushes and orders entries before header, but accepts both flushes after header. TapeFS §8 requires an intervening flush and final flush. Reproducer below returns no errors. | Verification adds ordered durability assertions/negative controls before operation acceptance. Full crash coverage remains separate. |
| P1-R1-V02 | Allocation writes are filtered to phase service. Adding a feed write to A-owned chunk 0 leaves the oracle green. Engine API §7 forbids feed I/O; TapeFS §7 forbids ordinary B writes below H. | Verification checks whole callback trace, forbidden phases, ranges and results. Old case cannot establish full ownership/no-I/O compliance. |
| P1-R1-V03 | runner.py deletes temporary input/output VO08 envelopes at exit and logs only the final envelope hash. JSONL alone cannot reconstruct bytes used by the oracle. | Verification retains hash-bound raw envelopes and enables offline re-evaluation. Software preserves them externally for baseline diagnostics without changing assertions. |
| P1-R1-D01 | Verifier WP10/WP11/WP12A plan files still label themselves DRAFT-6 and assert old blockers, while current status says DRAFT-8 is testable. | Verification marks plans historical or reconciles active claims to DRAFT-8. Old V6 labels alone do not reopen signed bytes. |
| VR-P1-001 | GitHub main metadata reports protected=false; ruleset 22084355, Branch protection on main, reports enforcement=disabled. | Process major remains open. Software proposes configuration; Michael decides before settings change. No new administrative authority granted. |

### Exact synthetic reproducer for V01/V02

Run from the verification repository at either exact VT8 baseline commit above:

```sh
python3 - <<'PY'
import sys
sys.path.insert(0, 'tests/ops_draft8')
from oracle import make_cases, synth_post, check, LBA_CHUNK_BASE
c = make_cases()[1]
p, e = synth_post(c)
bad = e[:2] + [e[2], e[4], e[3], e[5]]
print('commit flushes both after header:', check(c, p, bad))
p, e = synth_post(c)
e.insert(0, {'phase': 'feed', 'op': 'write',
             'lba': LBA_CHUNK_BASE, 'count': 1, 'rc': 0})
print('feed writes A-owned chunk:', check(c, p, e))
PY
```

Both outputs are `[]` (incorrect traces accepted). These are isolated synthetic
observations, not product failures. PM has not changed verifier source or supplied
replacement assertions; Verification independently owns their resolution.

## Work sequence

1. Software imports the exact original VT8 directory test-only, labeled a diagnostic
   baseline with V01–V03 open. No assertion edits or engine changes in that import.
2. In parallel, Verification fixes its package and publishes an immutable return.
   Software builds the public-API adapter and attempts diagnostics on held code.
   Missing operations/ABI obstacles become findings, not permission to implement
   uncovered behavior. This round contains **no product-engine merge authorization**.
3. PM reviews both returns. A later brief authorizes exact revised-test import,
   rerun and any sufficiently covered implementation slice. Verification independently
   dispositions raw results. Two happy-path cases cannot release all of #20.
4. Roadmap priorities after this return: independent playback/golden coverage for
   WP-08/WP-11, broader recording/random edits, WP-10 crash closure and WP-12a/state
   coverage as dependencies permit. These are sequencing intentions, not additional
   work automatically assigned in P1-R1.

Hardware has a separate sourcing/qualification-evidence round, not a prerequisite
to laptop-engine development. Surge is unassigned. Per Michael's clarification,
there is no requirement to assign every lead in every round.

## Checks actually run by PM

Environment: Python 3.12.14, GCC 13.3.0; exact inputs above. Commands are relative
to the respective repository root.

| Repository / command | Result |
|---|---|
| Product: tools/ci/verify-spec-bundle.sh | All three hashes pass |
| Product: make -C tests/mount_draft8 check | 10/10 package checks pass; not an engine mount run |
| Product: tools/ci/build.sh then tools/ci/unit.sh | Build/scaffolding pass: CRC 21, device 37, provisional mount 60 checks; crash scaffolding passes |
| Product: tools/ci/run-golden.sh | Exit 1: missing tests/golden/MANIFEST; unresolved WP-11 |
| Product: make -C hardware fabrication-gate-test | Eight predicate checks plus three CLI regressions pass, including negative controls |
| Product: make -C hardware fabrication-gate | Nonzero/CLOSED, five blockers; no safety acceptance |
| Verifier: python3 procedures/audit_mount_observations.py ../digital-tape | 274/289 before, 289/289 after, zero defects |
| Verifier: make -C tests check | Fault-device, crash-harness and audio-oracle self-tests pass |
| Verifier: python3 tests/ops_draft8/selftest.py | Two conforming observations accepted, six mutations caught |
| Verifier: python3 tests/ops_draft8/runner.py --adapter tests/ops_draft8/_synthetic_adapter.py --log /tmp/pm-vt8-selftest.jsonl | 2/2 synthetic only |
| Verifier: synthetic reproducer above | V01/V02 confirmed |

No new product operation run, held-code review, target timing, audio listening,
CAD qualification or physical measurement was performed. No assertion of all CI
green. Spec, engine, firmware, tests and hardware source remain unchanged by this
PM publication. Documentation/link and exact-copy checks accompany delivery.

## Holds and return boundary

Michael's signed Phase 0 scope and authenticated bytes stand. Operations/state
remain unfrozen until the actual complete green WP-10 run. No full WP-06/WP-07,
WP-08/09/11/12a/13/36 acceptance. Uncovered #20 code stays held. WP-11 acceptance
requires independent bytes and Michael's listening, not product-generated expected
output or a fabricated listening record.

Fabrication and cell charging stay CLOSED: charger, sustained coil-power and
transient-junction acceptance plus exact-part timing qualification remain missing.
Card atomicity is unqualified per exact SKU/revision. No purchases, 64 GB cards,
capacity/speed substitutions, physical actions or protection changes are authorized.
Q-001 is closed; do not request another freeze signature.

PM stops after verified publication of this review, updated status and lead briefs.
Michael resumes selected lead chats; main publication does not wake them. Next PM
round begins on his resumption with exact returns, not historical assignments.
