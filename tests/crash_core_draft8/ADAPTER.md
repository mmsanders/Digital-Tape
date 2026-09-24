# WP-10 core crash product-binding contract

This verifier package owns the fixtures, exhaustive injection manifest, durability
model, raw-media parser and outcome oracle. A later Software round imports the exact
package byte-for-byte under Structural Rule 1 and adds only mechanical product binding.

Software must not change the verifier case set, durability rules, permitted outcomes,
fixture bytes or parser.

## Scope

This package covers only:

1. record commit, in three public record modes: overwrite, overdub, splice;
2. reset Side B, in both ordinary live-B and degraded-B/equal-sequence shapes;
3. §8 stage clearing through `tape_arm`, `tape_reset_side_b` and
   `tape_respool`;
4. V7-001 two-interruption closure for those three stage-clear entry paths.

Full promote, format/duplicate, full re-spool crash enumeration and the other WP-10
families are deliberately outside this package.

## Exact product protocol

The production runner starts one adapter process:

```text
crash_core_product_adapter --fixture-manifest FIXTURES.json
```

The manifest names raw verifier-generated block-device images and their SHA-256s.

The adapter emits:

```json
{
  "format": "WP10-CORE-ADAPTER-1",
  "adapter_kind": "product",
  "caseset_sha256": "6c924fd7bdd54b180084fe58cc50ef49d96fc068b968b8022383685ecf235c96",
  "fixture_sha256": { "...": "..." }
}
```

and flushes stdout.

The runner then streams every verifier-owned case, in order. Production has no case,
durability-mode, torn-length or count override. The adapter returns one
`WP10-CORE-OBSERVATION-1` JSON line per case and finally exits 0 after `done`.

Timeout, EOF, malformed JSON, process death or case identity drift is failure.

## Dual-image fault block device

For each case create distinct:
- **working** bytes — what the running engine observes;
- **durable** bytes — what survives the simulated power cut.

Reads use working bytes.

A successful ordinary write updates working bytes. Under `write_through`, it also
updates durable bytes immediately. Under `flush_required`, a successful write alone
does not change durable bytes.

A successful flush copies all prior working writes to durable bytes.

Every injected crash remount is performed from a fresh engine instance whose device is
initialized **only from durable bytes**. Working bytes are discarded.

### Write-target semantics

The verifier enumerates every target 512-byte block separately.

- `before_write`, landed 0:
  no target byte lands; the target write faults.
- `torn_write`, landed 1…511:
  exactly that prefix of the intended 512-byte block is copied into both working and
  durable media, the rest remains the old durable block, and the write faults.
- `after_write`, landed 512:
  the block write succeeds, then power is cut at the boundary before its following
  flush can make any additional bytes durable. In write-through mode the block is
  already durable; in flush-required mode it is not.
- `at_flush`:
  the preceding write has completed and the flush is reached, but the flush is
  interrupted/fails before it makes new bytes durable. The same two durability modes
  therefore intentionally produce different durable outcomes.

For `after_write`, a C harness may implement the boundary by aborting/long-jumping
at the next flush callback *before applying or recording the flush*. It must not
silently implement this as a 512-byte torn write, because that would incorrectly make
the bytes durable in flush-required mode.

### Torn-write model

All 511 nontrivial prefix lengths are run at **every targeted block write**. This is
the package's exhaustive torn-block model; do not sample or substitute one canonical
tear.

## Raw snapshots

The adapter must expose durable bytes, not an adapter-decoded old/new verdict.

Immediately before the tested transaction and immediately after the injected power
cut, produce `WP10-CORE-SNAPSHOT-1` with verifier-owned `media.compact_snapshot`
semantics:

- exact 512-byte primary superblock;
- exact 512-byte mirror superblock;
- exact first two blocks of A0, A1, B0, B1;
- SHA-256 of every verifier-fixture chunk;
- full raw-image SHA-256.

The first two slot blocks are sufficient because every bounded fixture/post-state here
contains at most two entries. The verifier independently checks CRCs, structural
selection, §5.2 validity, interval disjointness, Side-A high-water bounds, stage
classification and logical selection.

Success evidence may stream these snapshots and discard them after the verifier has
accepted the case. A failing case must retain its exact compact snapshots.

## Clean target baseline

Each distinct scenario/seed must expose a stable `target_baseline`.

For record/reset transactions the target baseline is exactly:

```text
target write 0
target flush 0
target write 1
target flush 1
```

with two one-block writes at the exact verifier-predicted LBAs and exact block SHA-256s.

For stage clearing, the same four target events are the §4.6 update:
partner superblock, flush, candidate superblock, flush.

The runner verifies exact target LBAs and bytes. An implementation with an extra target
write, missing flush, reversed partner/candidate order, or different metadata is
rejected before crash outcomes are considered.

## Record-commit setup and transaction

For each record mode use a fresh `record_commit` fixture and mount Side B.

Before the crash-scoped `tape_commit`:

1. seek to frame 0;
2. arm the exact mode;
3. feed exactly one deterministic zero PCM frame;
4. service until frames owed clear;
5. flush/service completion must have made the newly allocated chunk data durable;
6. capture the `pre_snapshot`.

The pre-commit metadata must still equal the verifier fixture. Only pending chunk 2 is
allowed to differ in chunk hash.

The verifier's exact post-commit metadata is derived from DRAFT-8:

- overwrite: B becomes `{2,0,1}`;
- overdub: B becomes `{2,0,1}, {0,1,131071}`;
- splice: B becomes `{2,0,1}, {0,0,131072}`;
- destination is inactive B1;
- sequence advances from 20 to 21;
- commit writes one entry-array block, flush, one header block, flush.

The crash scope begins at `tape_commit`; chunk writes from service are setup, not
commit injection points. Every post-crash chunk hash must equal the pre-commit durable
chunk hashes. Thus a commit crash may select the old or committed generation but may
not corrupt already-durable user data.

## Reset-B: healthy

Use `reset_healthy` fixture, mount normally, and crash-scope only
`tape_reset_side_b`.

DRAFT-8 requires inactive B1:
- one entry-array block;
- flush;
- block-0 header at sequence 21;
- flush;
- zero chunk-region writes.

The verifier byte-simulates every interruption and accepts only the durable state
implied by that injection/durability mode.

## Reset-B: degraded equal-sequence

Use `reset_degraded_equal`. B0 and B1 are both individually valid at sequence 500
with different entries, so Side-A mount succeeds degraded-B.

Recovery writes B0 directly at sequence 501.

The old B0 entry differs from Side A. Therefore after B0's new entry array becomes
durable but before its new header commits, B0's old CRC no longer matches and B1 may be
the sole valid B slot. That **third** intermediate recovery state is intentional and
must not be called corruption.

Again, target scope is exactly one entry block + flush + one header block + flush, with
zero chunk writes.

Post-crash product remount for this variant is requested on Side A so the original
degraded state is itself a permitted mount result.

## Stage-clear entry paths

Use the verifier stage-1 RESUME-row-1 fixture:

- `promote_stage = 1`;
- `promote_staging_chunk = 2`;
- `a_high_water = 3`;
- live A and B each exactly `{2,0,131072}`;
- both superblocks healthy at generation 10.

The §8 clear must write generation 11, `promote_stage = 0`,
`promote_staging_chunk = 0`, with H unchanged.

Healthy-pair §4.6 order is:
1. mirror partner;
2. flush;
3. primary candidate;
4. flush.

Run that exact update through each path:

### `arm`

Mount B, call `tape_arm(TAPE_REC_OVERWRITE)`. For the clean reachability baseline,
after arm succeeds feed one frame and service until the first chunk write is reached.
The harness stops that post-clear write **before any byte lands**.

### `reset_b`

Call `tape_reset_side_b`. For the clean reachability baseline, after the two
superblock writes/flushes the first B-index write must be reached; stop it before any
byte lands.

### `respool`

Call `tape_respool` with positive budget on the non-empty Side B. After clear, the
first re-spool chunk write must be reached; stop it before any byte lands.

For all three, `target_baseline` must report:
- `post_clear_reached = true`;
- expected next class (`chunk`, `index`, `chunk`);
- `post_clear_write_landed = false`.

The post-clear probe write is **not** an injection point in this tranche.

## V7-001 two-interruption closure

For every stage-clear caller, run four raw stage-1 recovery seeds:

1. current primary only; mirror structurally invalid;
2. current mirror only; primary structurally invalid;
3. current primary generation 10 + stale mirror generation 9;
4. current mirror generation 10 + stale primary generation 9.

The current generation has H=3 and valid live Side A at chunk 2. The stale generation
has H=1, so if it ever becomes the only selected copy, Side A fails
`last < a_high_water` and the cartridge becomes unusable. This is the V7-001 hazard
made concrete.

A normal writable mount would try phase-4 repair before the stage-clear call. To
exercise the permitted unrepaired state:

1. mount the seed;
2. inject a **repair-preservation fault before the repair partner write lands**;
3. require mount result `TAPE_OK`, `needs_repair=true`;
4. verify durable bytes still exactly equal the verifier seed;
5. clear that setup fault and reset the operation trace;
6. invoke the stage-clear path;
7. inject the *second* interruption on its next §4.6 partner block write.

The setup repair fault is not counted as a WP-10 injection point. It is reachability
setup.

For the second partner write enumerate:
- before write (0 landed);
- every torn prefix 1…511;
- after complete write (512 landed);
- both durability modes.

The current generation must remain selectable unless the new generation became
durable. Selection may therefore be generation 10/stage 1 or generation 11/stage 0,
but never stale generation 9 / H=1 and never an unmountable Side A.

## Exact case counts

First-interruption scenarios each contain:

```text
2 durability modes * (2 writes * 513 block outcomes + 2 flush faults)
= 2056 cases
```

There are eight such scenarios:
- record overwrite;
- record overdub;
- record splice;
- reset healthy;
- reset degraded/equal-sequence;
- stage clear via arm;
- stage clear via reset-B;
- stage clear via re-spool.

First-interruption total: **16,448**.

Closure:

```text
3 callers * 4 recovery seeds * 2 durability modes * 513 partner-write outcomes
= 12,312 cases
```

Grand total: **28,760 injection cases**.

Canonical case-set SHA-256:
`6c924fd7bdd54b180084fe58cc50ef49d96fc068b968b8022383685ecf235c96`.

## Failure retention

On first failure retain `failure-reproducer.json` containing:
- exact case index;
- family/variant;
- durability mode;
- write/flush ordinal;
- torn landed-byte count;
- closure seed, where applicable;
- initial fixture digest;
- pre/post compact durable snapshots;
- actual remount result;
- verifier-simulated expected snapshot.

Success retains only compact summary/census, stable baseline hashes, stderr and binding
provenance. Do not retain 28,760 full raw images.

## Provenance required from Software

Retain:
- product commit/tree;
- exact verifier publication/tree;
- adapter source and SHA-256;
- linked binary SHA-256;
- compiler/tool versions and command line;
- summary SHA-256;
- adapter stderr;
- any failure reproducer;
- exact Actions run/job/artifact identities.

A Software green is evidence, never self-acceptance.
