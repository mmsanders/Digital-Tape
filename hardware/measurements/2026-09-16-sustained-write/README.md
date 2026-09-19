# Measurement record — sustained write, three PNY 64 GB V30 samples + one onn V10 control

**Work package:** WP-05 · **Criterion:** A-2 (sustained-write characterization)
**Date measured:** 16 September 2026 · **Measured by:** Michael
**Witnessed by:** n/a — Michael ran these himself; see §2
**Status:** `AUDITED — arithmetic only` · Verification P1-R17-V, 18 September 2026
**Schema:** 1 (legacy, summary-only) — acceptance fields in §11 remain unsigned

> **Scope of this record, after independent audit.** Verification independently reproduced
> all 95 recorded window rates and every pass/fail result, and **accepted that arithmetic**.
> It **rejected this packet as complete WP-05 A-2 physical evidence** (P1-R17-V-A01), and PM
> agreed. The reason is structural: these files store *rounded rates*, not the byte counts and
> timestamps those rates came from, so a short write, a wrong transfer size or an unfilled card
> cannot be ruled out after the fact.
>
> What that leaves is narrow and still worth having: **arithmetic over the exact recorded
> vectors of one declared path on one evening.** It is not card qualification, not a card-speed
> measurement, and not end-to-end copy acceptance. Card identity (A-1), attribution (A-4),
> atomicity (A-6) and production copy time remain open, and **C-90 is not reopened.**
>
> **The measurement path has been corrected for the next run** — schema 2 retains the missing
> primitives, and `characterisation/test_sustained_write.py` holds the controls that prove the
> gaps are now caught. §13 describes it. **No rerun is requested yet.**

## 1. What this is evidence for

WP-05 A-2, quoted verbatim from `docs/PACKAGES/WP-05.md` at main `faeaf26`:

> Per candidate SKU/revision, at least one sustained-write run on 80%-filled media: ≥1200 MB
> transfer, worst 64 MB window and raw per-window data. Unfilled repeat/unit/control runs are
> useful screening evidence but do not replace the filled run

and the requirement it serves, from `hardware/characterisation/measure_sustained_write.py`:

> At 635 MB the copy needs **21.2 MB/s** sustained write

with a screening bar of **23.3 MB/s** (10% over the C-60 requirement). The tool also prints a
**31.75 MB/s** C-90 figure; that figure is reported by the tool and is **not** a live requirement
— ADR-018 set the product at C-60 and the P1-R16 disposition does not reopen it.

**How the five runs map onto A-2** (PM disposition, 18 September 2026):

| Role under A-2 | Runs |
|---|---|
| **The conforming filled observation** — one per candidate SKU/revision | `raw/pny3-filled.json` (80% fill) |
| Screening / unit-to-unit evidence | `raw/pny1.json`, `raw/pny2.json`, `raw/pny3.json` |
| Retained negative control | `raw/onn-v10.json` |

The four unfilled runs are **not** A-2 deviations and are not substitutes for a filled run. A-2's
80%-fill condition stands: low logical occupancy in the product does not establish what the flash
translation layer will do after prior writes and garbage collection over the card's service life.

**And the filled run does not complete A-2 either.** Its `filled_to: 0.8` is a record that the
`--fill` flag was passed, not a measurement of occupancy: no capacity or free-space figure was
captured before the fill, after it, or after the run. A-2 asks for a run *on 80%-filled media*,
and a flag does not establish that state. Schema 2 measures it (§13).

## 2. Provenance, and the limit on what this record can claim

**Michael ran these measurements on his own hardware and supplied the five JSON files
unmodified.** The Hardware Lead did not witness the session and has no independent view of the
bench. Everything in §5 onward is what the tool recorded or what Michael reported; nothing here is
a Hardware Lead observation of physical apparatus, and nothing here has been independently
audited.

PM Decisions 006 §5 reserves witnessing to Michael and auditing to the Verification Lead. That is
why this record is marked `SUBMITTED FOR AUDIT` and why §11 signs nothing.

## 3. Identity and provenance of the samples

Filled as far as the physical record permits. **Nothing in this table is inferred**; a field that
was not recorded says so, and §12 names the smallest exact request that would close it.

| Field | Value | Source |
|---|---|---|
| Retail identity | PNY, microSD, 64 GB, V30 mark, three samples, ~$13 each, bought on Amazon (`https://a.co/d/0cYsozv6`), free shipping | Michael, reported in chat |
| Manufacturer part number | **not recorded** | — |
| Revision | **not recorded** — the `revision` field is empty in all five files | `raw/*.json` |
| CID | **not recorded** | — |
| Order/invoice identity | **not recorded** (order number, order date, seller of record) | — |
| Sample labels | `pny1`, `pny2`, `pny3` — **operator labels, not part numbers** | `raw/*.json` `sku` field |
| Sample mapping | `pny3` and `pny3-filled` are the **same physical card**; `pny1` and `pny2` are the other two | Michael |
| Control card | onn, V10 mark, capacity **not recorded**, already owned | Michael; `raw/onn-v10.json` |
| Card reader | TRANSCEND TS-RDF5R; firmware **not recorded** | `raw/*.json` `reader` field |
| Host | Windows 11, build 10.0.26200 | `raw/*.json` |
| Target | `E:\`, `filesystem_mode: mounted-filesystem` | `raw/*.json` |
| Host write caching | **not recorded** | — |
| Ambient temperature / humidity | **not recorded** | — |
| Reader temperature | **not instrumented.** Michael reports by hand that it "was getting really hot" | Michael |

WP-05 is explicit that *"Exact SKU, capacity, revision and CID matter; a family name is
insufficient."* On the record as it stands, these results are bound to three physical cards in
Michael's possession — not to a part number anyone could re-order, and not to a revision that
atomicity evidence could later be bound to.

## 4. Procedure

`hardware/characterisation/measure_sustained_write.py` against the mounted filesystem at `E:\`,
1200 MB transfer, 64 MB windows, `os.write()` followed by `os.fsync()` inside each timed window.
Five runs in this order:

| # | File | Card | Fill | `measured_at` (UTC) |
|---|---|---|---|---|
| 1 | `raw/onn-v10.json` | onn V10 control | none | 22:28:32 |
| 2 | `raw/pny1.json` | PNY sample 1 | none | 22:33:50 |
| 3 | `raw/pny2.json` | PNY sample 2 | none | 22:35:26 |
| 4 | `raw/pny3.json` | PNY sample 3 | none | 22:38:41 |
| 5 | `raw/pny3-filled.json` | PNY sample 3, refilled | **80%** | 22:59:03 |

Michael reports the 80% fill took about 20 minutes, which is consistent with the 20-minute gap
between runs 4 and 5. He ran it once rather than three times.

## 5. Raw readings

`raw/*.json`, exactly as the tool emitted them — 19 windows per run, unedited, byte-for-byte as
supplied. No outliers were removed; there are none to remove, and §6's derivation consumes every
window of every run.

## 6. Derivation

`analyse.py` in this directory derives every figure in §7 from `raw/*.json`. It no longer does
the arithmetic itself: it calls `characterisation/audit_sustained_write.py`, the shared auditor,
so this record and any future run are derived by the same audited code. The auditor **recomputes
from the recorded vector and never uses a stored summary field as an input** — it compares each
one and fails on disagreement.

```
run           fill    worst  median    best pair(all)  screen
onn-v10       -       15.34   19.79   25.72     17.76    FAIL
pny1          -       26.18   67.11   68.20     37.84    PASS
pny2          -       25.41   53.69   74.07     35.93    PASS
pny3          -       25.88   65.71   67.11     37.35    PASS
pny3-filled   0.8     27.36   41.30   74.07     38.52    PASS
```

**Two corrections to the previous version of this table**, both from the independent audit:

- **`pairmin` was mislabelled** (P1-R17-V-A03). It said "any adjacent pair" and computed only
  the fixed non-overlapping pairs (0,1), (2,3)…, skipping (1,2), (3,4)…. The column above is now
  every adjacent pair, which is what the words say. For the onn control it moves 18.00776 →
  **17.76235**, and for pny2 36.08881 → **35.93428**. Both values are printed side by side by
  `analyse.py`, and the retained control in `characterisation/test_sustained_write.py` fails if
  the two are ever confused again. **No pass/fail result changes**: the pair rate is a
  descriptive statistic and A-2 is judged on the worst single window.
- **The mean column is gone.** The previous analyser printed the file's *stored* mean without
  checking it; Verification demonstrated that changing pny1's stored mean to `999.0` printed
  `999.00` and still exited 0 (P1-R17-V-A02). The auditor now derives the mean and fails on a
  mismatch, and the column was dropped from the headline table because the median and the worst
  window are what this record is about.

## 7. Results — measured facts only

Against the 23.3 MB/s screening bar, on the worst-64 MB-window criterion the tool applies:

| Run | Role | Worst window | × C-60 requirement (21.2) | × screening bar (23.3) |
|---|---|---:|---:|---:|
| pny3, 80% filled | **conforming filled run** | 27.36 | 1.29 | 1.17 |
| pny1 | screening | 26.18 | 1.23 | 1.12 |
| pny2 | screening | 25.41 | 1.20 | 1.09 |
| pny3 | screening | 25.88 | 1.22 | 1.11 |
| onn V10 | negative control | 15.34 | **0.72** | **0.66** |

Three statements this record does support, each a fact about **this measurement path on this
evening**, not about the cards in isolation:

1. **The conforming filled run cleared the screening bar** at 27.36 MB/s worst window.
2. **The negative control failed**, at 0.72× the C-60 requirement. The measurement therefore
   discriminates adequate from inadequate media rather than passing whatever is put in front of
   it. A check that cannot go red has not established what it detects.
3. **The three PNY samples agree to 3.0%** on the worst window (26.18 / 25.41 / 25.88 MB/s,
   spread 0.77 MB/s) — a unit-to-unit screen across three samples of one retail family, which is
   not statistical qualification of a SKU. *The previous version of this record quoted 1.0% on a
   pair-rate mean. That was a more flattering statistic than the criterion's own, and it is
   withdrawn: the figure above is stated on the worst window, which is what A-2 is judged on.*

On the one sample carrying the fill flag, the result was not degraded: worst window 25.88 →
27.36 on the same physical card. That is a single observation, it does not generalize, **and the
fill itself is unverified** — see §1 and §13.

## 8. Hypotheses — explicitly not established

These are candidate explanations for features of the data. None is tested, none is load-bearing
for anything in §7, and none should be cited as a finding.

**(a) The period-2 alternation may be an artefact of the 64 MB window size.** Every PNY run
alternates roughly 67 / 26 MB/s with period 2, while the derived adjacent-pair rate is steady
(pny1 spans 37.84–38.34 across the whole run). One candidate explanation is the per-window
`fsync` landing on an internal fold boundary, so one window is absorbed and the next pays for it.
**This is untested.** No experiment distinguishing it from ordinary card behaviour has been run,
and no conclusion here depends on it. Testing it would mean re-running at 128 MB and 256 MB
windows on the same cards.

**(b) The measurement path may be limited upstream of the card.** The PNY best windows cluster
within 9.8% (67.11–74.07 MB/s) and two different runs report an identical 74.07 MB/s maximum.
WP-05 A-4 states that *"similar top results at its ceiling invalidate a card-speed conclusion"*;
that condition is met on the face of the data, so **no card-speed conclusion is drawn** (§10).
Whether the limit is the reader, the host, the bus or the driver is **not established** —
identifying it would require measuring the same cards through a different path.

**(c) Thermal drift may be present.** pny2's fast windows decay from 74.07 to 53.69 across the
run while its slow windows hold near 26, and Michael reports the reader was hot to the touch.
No temperature was instrumented, so this is an observation about the numbers and a hand report,
not a measurement, and no cause is established.

Minor and certain: `p05_mb_s` is `null` in all five files because the tool requires ≥20 windows
and 1200 MB at 64 MB gives 19. A 1280 MB transfer would populate it.

## 9. Uncertainty

Instrument accuracy is not characterizable from this record: the timing source is
`time.monotonic()` on a Windows host, the transfer path includes an uncharacterized reader, and
neither host caching state nor ambient conditions were recorded. The spread that *is* visible —
three samples within 1.0% on the pair rate, and a 74.07 MB/s figure repeating exactly across two
runs — is reported in §7 and §8 rather than converted into an error bar, because the dominant
term is a systematic unknown (§8b), not scatter.

What a hostile reader should attack first, and would be right to: every number here is measured
through one reader, on one host, on one evening, by one person, with no independent witness and
no recorded part number.

## 10. Exclusions — open, and not claimable from this record

- **Card qualification.** No card is qualified. Nothing here authorizes an order, a design
  dependency on a specific part, or a claim that this SKU is suitable for the product.
- **Card identity (A-1).** Manufacturer part number, revision and CID are absent (§3). Atomicity
  evidence cannot be bound to a revision that was never recorded.
- **Card speed (A-4).** Not established: the A-4 ceiling condition is met on the face of the data
  (§8b), so this record attributes no speed to the cards themselves.
- **Atomicity (A-6).** Zero of the required ≥1,000 qualifying power cuts have been run, per exact
  SKU and revision. No rig, firmware or rail traces exist.
- **End-to-end copy time (A-3).** This is a PC-side media measurement. Guardrail 10: PC card
  throughput is not proof of production end-to-end time.
- **Complete WP-05 A-2 evidence.** Rejected by independent audit (P1-R17-V-A01) and by the P1-R18
  disposition. The bytes actually written per window, the transfer's real size and the card's
  real occupancy are not recoverable from a schema-1 file. **This is the exclusion that governs
  the rest**: the packet is arithmetic over a recorded vector, nothing more.
- **C-90.** Not reopened, and this record proposes no change to tape duration. The product is
  C-60 by ADR-018.

**What the independent audit did accept**, and it is worth stating precisely: the immutable
identity of all five blobs, the arithmetic over all 95 recorded window rates, the exact vector
minima and pass/fail results, the fact that the control vector goes red, and the path/host/reader
labels as recorded. Method, instruments, conditions and uncertainty were reviewed; the physical
run itself could not be, which is the finding.

## 11. Acceptance

☑ **Arithmetic independently reproduced** — Verification Lead, P1-R17-V, 18 September 2026.
Accepted narrowly: identity, the 95 recorded rates, the minima, the pass/fail results and the
control going red.
☐ **Complete WP-05 A-2 physical evidence — not accepted, and not claimable from this packet.**
☐ *unsigned — PM* (the P1-R18 disposition routes the correction; it accepts no packet)

The Hardware Lead compiled this record and cannot accept it. Michael ran the measurements and
cannot audit them. Both of those are the rule working, not an obstruction.

## 12. Smallest exact request that would close the identity gap

For each of the three PNY cards, and before any atomicity work begins:

1. The **manufacturer part number** printed on the card body or its retail packaging, transcribed
   exactly, including any suffix.
2. The **CID register** read from each card, with the sample label (`pny1` / `pny2` / `pny3`) it
   belongs to. On Linux: `cat /sys/block/mmcblk0/device/cid`.
3. The **Amazon order number and order date**, which fixes seller of record and ship date.

Items 1 and 3 are transcription; item 2 needs a host that exposes the CID, which a USB reader
generally does not. If no such host is available, that is worth recording as a blocker rather
than leaving the field blank — it would mean the revision binding A-6 requires cannot be
established with the equipment currently in hand.

Also useful, and cheap, when the reader question is next touched: the make and model of any
second card reader available, so the same cards can be measured through a different path.

## 13. The corrected measurement path — for the next run, not this one

The five files above are immutable and are **not** migrated, rewritten or upgraded. What changed
is the tool that would produce the next ones. `characterisation/measure_sustained_write.py` is
now **schema 2**, and each addition closes a specific way the old record could have been wrong
without anyone being able to tell:

| Schema 1 | Schema 2 | Closes |
|---|---|---|
| assumed `os.write()` wrote everything it was asked | loops until the window is complete; records requested bytes, returned bytes and the call count | a short write counted as a full window |
| stored a rounded MB/s per window | stores monotonic start, end and duration at full precision per window, plus the byte counts | every figure recomputable; a corrupted summary cannot hide |
| deleted the measurement file | keeps it and records its final size against the bytes written | the transfer being a different size than claimed |
| recorded `filled_to: 0.8` because a flag was passed | measures total/free/used before the fill, after the fill and after the run, and derives occupancy | a fill that did not happen, or did not reach 80% |
| fsync outcome unrecorded | records `fsync_ok` and any error per window | a silent sync failure |
| analyser printed a stored mean it had not checked | `audit_sustained_write.py` derives everything and compares every stored summary, failing on disagreement | P1-R17-V-A02 exactly |
| "any adjacent pair" computed fixed phase-0 pairs | every adjacent pair `(i, i+1)`, with the fixed statistic retained under its real name | P1-R17-V-A03 |

### The repair after independent audit (P1-R19-V01/V02)

Verification audited the schema-2 *method* — not a run, since none exists — and blocked it.
Two things were wrong, and both were the same kind of wrong: **the record summarised what it
should have proven.**

- **V01 — the write-call trace was not retained.** The loop continued correctly after a short
  write, but kept only the aggregate byte count and a call count. An auditor could not show
  that the continuation resumed at the right offset, or that `write_calls` was truthful.
  Removing `write_calls`, setting `short_writes` to 99, removing `offset_bytes` or changing an
  offset to 7 **all passed**.
- **V02 — validation failed open.** Thirteen one-at-a-time mutations passed: missing offsets,
  counts, timing, totals, final size and capacity accounting; a missing `fsync_ok` read as
  success; an invented `target_kind` skipped the final-size branch entirely; and an inserted
  `worst_window_mb_s = 999.0` was ignored rather than rejected.

**What schema 2 now retains.** Every write call, in order, with its sequence number, window,
absolute offset, requested bytes and returned bytes — bound to the record by a SHA-256 over a
canonical serialisation. Each window carries its start and end offset, so contiguity is
provable rather than assumed. The closing `fsync` is recorded **inside the measured span**,
because a flush after the clock stops is time the record does not account for.

**What the auditor now does.** It is a **closed schema**: every required field must be present,
every unknown field is rejected, and a stored summary is rejected outright rather than ignored
— schema 2 holds primitives and derives every figure, so a summary in the file is a
contradiction. The trace is *reconstructed*: contiguous coverage, positive bounded returns,
continuation offsets, per-window totals and call counts, all checked against the windows that
claim them. Capacity accounting is checked arithmetically and for before/after consistency, and
each target kind gets its own final-size branch.

**All fifteen mutations now go red**, each naming the field it broke. Writing the controls also
turned up two defects of my own: an unrelated earlier failure was suppressing the trace audit
entirely, and a missing window field crashed the auditor instead of rejecting the record.

**No schema-2 record exists anywhere**, so there is nothing to migrate — the repair is in
place, and the five schema-1 files are untouched as always.

**Provenance correction.** The prior-head identifier `c0e6a83a474a…` in an earlier assignment
does not exist as a Git object. The authenticated ancestor is
**`c0e6a83ae44c2370288594b75915a214ba25deb7`**, tree `4421e11258690936f02734c176589ff0c3dad826`,
and the five legacy files are byte-identical from it through every head since.

**Retained controls at that round:** `characterisation/test_sustained_write.py`, run by
`make -C hardware card-test`. Eleven controls, each injecting the defect it claims to catch:
short writes (in the tool, against an injected partial writer, and in the record), a stalled
writer, duration and timestamp corruption, window ordering, byte-count and final-size mismatch,
a deleted measurement file, a false occupancy, an unmeasured occupancy, legacy summary tampering
— including the exact `38.79 → 999.0` mutation Verification used — and the adjacent-pair
distinction. Each targeted failure is also required to survive an unrelated failure being
present, so a control cannot pass by firing on everything.

### The second repair after independent audit (P1-R21-V01)

Verification re-audited the method at head `10471f37f432c44d6f5beac59d25b3771e057c38` and
**rejected it again**. The earlier ordered-trace defects were confirmed repaired and all
thirteen prior mutations confirmed rejected — but a new adversarial corpus found the schema
closed only at the top level, and the primitive types not enforced at all. **Thirteen malformed
records were accepted and one crashed the auditor.**

- **The nested objects were open.** Removing `final_fsync.error`, or adding an unknown member
  to `final_fsync`, `fill` or `space_after_measurement`, all passed. A schema closed at the top
  and open one level down is not a closed schema.
- **The types were not enforced.** In Python `True == 1`, so a Boolean `write_trace.seq` or
  window `index` passed as its integer equivalent — defeating the identity typing the trace
  exists to provide. Integral-valued floats passed for byte offsets, byte counts and capacity
  counts; a byte count that arrives as `1.0` has been through a path that does not preserve
  byte identity, which is the one thing the record is for.
- **The closing flush could run backwards.** A `final_fsync` whose end timestamp preceded its
  start was accepted. Containment inside the measured span was checked; ordering was not. A
  reversed interval does not establish that the last durability event was observed in order.
- **A malformed timestamp ended the audit in a traceback.** A string
  `final_fsync.t_start_monotonic_s` raised an uncaught `TypeError`. An audit that dies by
  traceback has reported nothing, and a verifier cannot distinguish that from a tool invoked
  wrongly.
- **The declared metadata was decoration.** A false `window_mb` was accepted while the retained
  windows contradicted it, and `required_mb_s`, `required_c90_mb_s` and `bar_mb_s` were accepted
  at any value — so a record could carry, and move, the bar it is judged against.

**What the auditor now does.** Every nested object is closed with its own required-field set.
Every byte, count, capacity and identity field must be an **exact integer** — not a Boolean,
not an integral float — and must be non-negative. Every timestamp and duration must be a
**finite** number. The closing flush must run forwards and lie inside the measured span, and it
may not report success and an error at once. Types are settled in a single pass **before the
first comparison**, so a malformed record leaves with a problem report the auditor owns rather
than a traceback. `window_mb` is checked against the retained windows — every window but the
last must be exactly that size, and the last may only be shorter — and the three criterion
figures are checked against this module's **own restated** constants, derived from the tape
rather than read back out of the tool. A figure that cannot be measured, such as filesystem
accounting on a raw block device, must be null rather than fabricated.

**All fifteen malformed forms now go red**, each naming the field it is about, and each was
confirmed accepted-or-crashing against the rejected head before being recorded green here. The
retained suite is now **25 controls** over 30 top-level and 35 nested schema-2 fields, and a
coverage registry goes red if any of the fifteen forms loses its control.

**Still not evidence.** No schema-2 record exists, no physical run has occurred, and this repair
promotes no stored result. Closing a method is not qualifying a card.

**No rerun is requested.** The tool is ready and the audit path is exercised against synthetic
fixtures; whether and when to ask Michael for another session is PM's call, and the identity
items in §12 should be collected first since they cost nothing and gate A-6. Independent
Verification owns a fresh method audit of the repaired head before any acquisition.
