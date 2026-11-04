# Hardware651 correction-1 records binding r1

Michael directly continued the remaining work: per-run setup, loading the rig's
records, and the old-data failure rule. Existing651 is the handoff; V382 stays
closed. No other role, implementation or physical authority is inferred.

Input declaration at577d1776c9b8052f51f9f6eec6b0a33a73d635c8:
ATOMICITY-SCHEMA-R2.md blobbf362578bc5e3bbed4d8118db73450b331311b84,
correction originally declared at2867811; Product authority51d0f8f/WP05/ADR204.
No uncovered implementation was inspected or executed to author expectations.
This is a new package; old27/71-case packages and their evidence remain unchanged.

## Execute

Python3.10+. Each output directory must be new:

```
python -B tests/rig_records_r1/run.py --selftest --out build/rig-records-harness
python -B tests/rig_records_r1/run.py --judge PRODUCT/hardware/characterisation/media_atomicity.py --out build/rig-records-candidate
```

Candidate mode uses the declared `load_manifest(path, evidence_dir)`, its returned
tuple as `judge(..., manifest=...)`, the preserved `qualifies(row)` predicate, and
the declared plan/judge CLI with `--manifest` and `--evidence`. It hashes the exact
provided judge source bytes for manifest identity. Later disposition must also
authenticate the exact Product head and unchanged import-before-implementation.
Do not execute an unimplemented interface and call its absence a candidate result.

## Bound coverage

**133 manifest/evidence cases:** valid synthetic records and byte-distinct whitespace;
exact-byte hash; all13 required controls present/pass/nonempty evidence; changed or
missing bytes for every referenced binary/script/certificate/calibration/skew/control/
photo; strict keys/types/UTF8/object shape/duplicate-key/nonfinite JSON; path traversal/
absolute/drive/backslash refs; judge identity; all measured threshold boundaries,
skew/count boundaries and invalid observations. `load_manifest` must return problems
for bad/missing input without raising. Equal hash-shaped fields are insufficient.

**85 complete-judge cases:** production1000 plus a lawful late NEW miss, normal OLD
mid-busy outcome,999 short/operator override, identity/CID/firmware/switch/SCK/bus/
method/plan/manifest conflicts, missing fields and record-invalid run problems,
manifest absence/problems/repointing, duplicate/missing rows, damage at each of four
neighbours and TORN/CORRUPT on late/ambiguous/no-opening/delayed/chattering misses.
Plan/row identities are resealed together in manifest-agreement controls so a stale
plan digest cannot be the sole reason they fail.

**Old-data failure rule:** OLD strictly before `rail_open-U` fails run integrity,
adds no credit, is listed in completed_write_reverted and is not relabelled TORN or
a media defect. Equality at both±U boundaries is ambiguous, not completion proof.
NEW at a lawful late cut is a miss without a problem. Chatter, incomplete capture,
record invalidity and missing protocol proof cannot supply completed-write proof
merely because a predicate's first-failure reason says before. This is the ADR204
"otherwise qualified" condition; the full judge must apply it consistently.

**Nine additional row predicates:** rail-high true/omitted predicate compatibility,
invalid present marker types, and two/three-edge chatter. The complete judge requires
the rail-high marker even though the predicate permits omission for compatibility.
These were declared partly implemented at input; publication makes no retrospective
tests-first or current-head acceptance claim about that existing code.

**Eleven CLI scenarios:** plan4 creation with identity/hash/canonical digest, auditable
extension with disjoint trials, conflicting identity and999 rejection, a complete
positive run, NaN/±Infinity/duplicate-key raw result rejection, exact-byte manifest
repointing and extension refusal. The canonical plan digest extends the unchanged
revision3 identity/schedule encoding with method and rig_manifest_sha256, as declared.
Also bind the explicit interim rule: method-bearing rows cannot earn credit through
a valid legacy v3 plan with no authenticated manifest. This does not waive v4 success.

## Evidence and qualification boundary

Every byte, CID, instrument, certificate, control pass and witness in these fixtures
is conspicuously **synthetic**. The loader can establish artifact consistency only.
It cannot prove certificate authenticity, actual calibration, which binary ran, a
physical cut or Michael's witness. Model windows/U/delay do not become qualified
electrical limits through a synthetic PASS. In particular, a delayed comparator A
can over-report rollback; raw trace/method review is needed before any media claim.

The harness self-test generates the fixtures, checks declared result contracts and
detects20 result/plan controls. It executes no Product judge/loader/CLI and does not
implement a substitute loader or acceptance judge. CLI scenarios are authored for
later candidate execution; they are not counted as Product runs in self-test CI.
Generated result streams can exceed1MiB; keep them locally and publish only summaries
or release assets with hashes if needed. Never commit raw campaigns into the tree.

The candidate mode reads/writes only synthetic task files through the declared tool
interfaces; it is not an OS sandbox. There is no rig firmware, card/device command,
flashing, energizing or real measurement in this package. All three previously
missing interfaces are now bound. Next owner Hardware651: import unchanged, implement
the per-run/loader/complete-judge/rollback stage, run CI, return its exact head.
Whole-rig, physical/media/safety/purchase and fabrication/charging holds stand.
