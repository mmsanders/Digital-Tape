# Measurement record — sustained write, three PNY 64 GB V30 + one onn V10

**Work package:** WP-05 · **Criterion:** A-2 (sustained-write characterization)
**Date measured:** 16 September 2026 · **Measured by:** Michael
**Witnessed by:** n/a — Michael ran these himself; see §2
**Status:** `SUBMITTED FOR AUDIT` — acceptance fields below are deliberately unsigned

> **This record establishes headroom, not a qualified card.** The tool's own header says so:
> *"this is no longer a gate. It is a headroom measurement… This media measurement is not
> end-to-end copy acceptance."* WP-05 A-6 (≥ 1,000 qualifying power cuts per exact SKU and
> revision) has **not** been run, and no rig exists to run it. See §10.

## 1. What this is evidence for

WP-05 A-2, quoted verbatim:

> Sustained-write tool: 80% filled media, ≥1200 MB transfer, worst 64 MB window and raw
> per-window data

and the requirement it serves, from `characterisation/measure_sustained_write.py`:

> At 635 MB the copy needs **21.2 MB/s** sustained write

with a reporting bar of **23.3 MB/s** (10% over the C-60 requirement) and **31.75 MB/s** quoted
as what a C-90 would need.

## 2. Provenance, and the limit on what this record can claim

**Michael ran these measurements on his own hardware and supplied the five JSON files
unmodified.** The Hardware Lead did not witness the session and has no independent view of the
bench. Everything in §4 and §5 is what the tool recorded or what Michael reported; nothing here
is a Hardware Lead observation of physical apparatus.

PM Decisions 006 §5 reserves witnessing to Michael and auditing to the Verification Lead. For a
headroom measurement that is a lighter bar than for a safety limit — but it is why this record
is marked `SUBMITTED FOR AUDIT` rather than complete, and why §10 signs nothing.

## 3. Procedure

`hardware/characterisation/measure_sustained_write.py` against a mounted filesystem (`E:\`),
1200 MB transfer, 64 MB windows, `os.fsync()` after every window. Five runs:

| Run | Card | Fill | File |
|---|---|---|---|
| 1 | onn, V10, capacity unrecorded — a card Michael already had | none | `raw/onn-v10.json` |
| 2 | PNY 64 GB V30, sample 1 | none | `raw/pny1.json` |
| 3 | PNY 64 GB V30, sample 2 | none | `raw/pny2.json` |
| 4 | PNY 64 GB V30, sample 3 | none | `raw/pny3.json` |
| 5 | PNY 64 GB V30, **sample 3 again** | **80%** | `raw/pny3-filled.json` |

**Deviation from A-2 as written:** four of the five runs were **not** filled to 80%. Michael ran
the fill once, on sample 3, and reports it took about 20 minutes. §8 argues this deviation is
defensible for this product and §11 puts the disposition where it belongs.

## 4. Instruments

| Instrument | Identification | Calibration | Notes |
|---|---|---|---|
| Card reader | TRANSCEND TS-RDF5R (from the tool's `reader` field) | n/a | **Michael reports it ran hot.** See §9 |
| Host | Windows 11, build 10.0.26200 | n/a | `filesystem_mode: mounted-filesystem`, target `E:\` |
| Timing | `time.monotonic()` in the tool | host clock | Per-window, write + `fsync` inside the timed region |

**Not recorded, and needed before any atomicity work:** manufacturer part number, revision and
CID for each card; reader firmware; whether host write caching was enabled. WP-05 is explicit —
*"Exact SKU, capacity, revision and CID matter; a family name is insufficient."* The `sku` fields
in the raw files (`pny1`, `pny2`, `pny3`, `onn`) are **operator labels, not part numbers.**

## 5. Conditions

Ambient temperature and humidity were not recorded. Reader temperature was not instrumented;
"ran hot" is a hand observation, not a reading. Each run's UTC timestamp is in its JSON file;
the four PNY runs span 22:33–22:59, so they were taken back to back with a warm reader.

## 6. Raw readings

`raw/*.json`, exactly as the tool emitted them — 19 windows per run, unedited. No outliers were
removed; there are none to remove, and §7's derivation consumes every window.

## 7. Derivation

`analyse.py` in this directory recomputes every figure below from `raw/*.json`. It deliberately
**recomputes each verdict from the per-window data instead of trusting the file's own `verdict`
field**, so an edited or corrupted summary line cannot pass unnoticed. All five agree.

```
run           fill   worst   best   mean  pairmin  verdict
onn-v10       -      15.34  25.72  19.13    18.01     FAIL
pny1          -      26.18  68.20  38.79    37.84     PASS
pny2          -      25.41  74.07  38.46    36.09     PASS
pny3          -      25.88  67.11  38.38    37.35     PASS
pny3-filled   0.8    27.36  74.07  40.59    38.52     PASS
```

## 8. Results

**Against the C-60 requirement the three PNY samples clear the bar on every run**, on the
conservative worst-64 MB-window criterion the tool applies:

| Run | Worst window | × C-60 requirement (21.2) | × reporting bar (23.3) |
|---|---:|---:|---:|
| pny1 | 26.18 | 1.23 | 1.12 |
| pny2 | 25.41 | 1.20 | 1.09 |
| pny3 | 25.88 | 1.22 | 1.11 |
| pny3, 80% filled | 27.36 | 1.29 | 1.17 |
| onn V10 | 15.34 | **0.72** | **0.66** |

**The onn V10 is a genuine negative control and it earned its place.** It fails the requirement
outright at 0.72×, which demonstrates the measurement discriminates adequate media from
inadequate rather than passing whatever is put in front of it. A test that cannot fail has not
established anything; this one can, and did.

**Unit-to-unit consistency is excellent.** The three PNY samples agree to **1.0%** on the 128 MB
pair rate (38.12 / 37.88 / 37.73 MB/s). That is the n≥2 quality check Michael asked for, and it
passes convincingly.

**The 80% fill did not degrade this card — it helped.** Same physical sample, worst window
25.88 → 27.36 (+1.48), pair rate 37.73 → 39.86 (+2.13). The fill condition exists to provoke
garbage-collection stalls; on this SKU it did not provoke one. One SKU, one trial.

## 9. Uncertainty — three things that limit what these numbers mean

**(a) The windows alternate fast/slow with a regularity that is almost certainly an artefact of
the window size.** Every PNY run alternates ~67 / ~26 MB/s with period 2, and the *pair* rate —
each adjacent fast+slow pair, spanning one full cycle — is extraordinarily steady: pny1 ranges
37.84–38.34 across the whole run. A card stalling on garbage collection does not stall on exactly
every second window for nineteen windows. The leading explanation is that the per-window `fsync`
lands on the card's internal fold boundary, so one window is absorbed and the next pays for it.

**This matters because it means the reported worst window may understate the card.** If the
alternation is aliasing, the honest sustained figure is the ~38 MB/s pair rate, not 26 MB/s.
**It does not threaten the C-60 conclusion** — that conclusion uses the pessimistic number and
still passes — but it is load-bearing for C-90 (§11).

**(b) The reader is very likely the ceiling, which is exactly the condition WP-05 A-4 names.**
A-4: *"Establish the reader is not the bottleneck; similar top results at its ceiling invalidate
a card-speed conclusion."* The PNY best windows cluster within 9.8% (67.11–74.07), and **two
different runs sit on the identical maximum, 74.07 MB/s to the last digit.** Different cards
reaching the same number to four significant figures is a shared-path limit, not card behaviour.
Michael's independent observation that the reader ran hot corroborates it.

So **no conclusion about how fast these cards are is available from this data.** What survives is
narrower and still sufficient: a bottleneck upstream of the card cannot make a card look *faster*
than it is, so the measured floor is a floor for the whole path — reader included — and that
floor clears the C-60 requirement. We have measured the path, and the path is good enough.

**(c) Thermal drift is visible in the run that was probably hottest.** pny2's fast windows decay
72.79 → 74.07 → … → 53.69 across the run while its slow windows hold near 26; its pair minimum
(36.09) is the lowest of the three samples. Consistent with a warming reader, not established as
such — nothing was instrumented.

Also minor: `p05_mb_s` is `null` in all five files because the tool needs ≥20 windows and 1200 MB
at 64 MB gives 19. A 1280 MB transfer would populate it.

## 10. What is established, and what is not

**Established (pending independent audit):** three PNY samples and the measurement path together
sustain comfortably more than a C-60 copy needs, with ~20% margin on the most pessimistic
reading and ~80% on the pair-rate reading; the three samples are consistent to 1%; an 80% fill
did not degrade the one sample tested that way; and a V10 card fails the same test.

**Not established, and not claimable from this record:**

- **Card atomicity (A-6).** Zero of the required ≥1,000 qualifying power cuts have been run, per
  exact SKU and revision. No rig, firmware or rail traces exist. `CLAUDE.md` §5: *"Media
  atomicity must be established per exact card SKU/revision before qualification."*
- **Card identity (A-1).** No manufacturer part number, revision or CID is recorded, so these
  results are not yet bound to a part anyone could re-order or re-test.
- **How fast these cards are (A-4).** Invalidated by the ceiling clustering in §9(b).
- **End-to-end copy time (A-3).** This is a PC-side media measurement. Guardrail 10 is explicit
  that PC card throughput is not proof of production end-to-end time.
- **Anything about C-90.** See §11.

**Acceptance:** ☐ *unsigned — Verification Lead* · ☐ *unsigned — PM*

The Hardware Lead compiled this record and cannot accept it. Michael ran the measurements and
cannot audit them. Both of those are the rule working, not an obstruction.

## 11. Two questions this record puts to PM

**(a) Does the A-2 80% fill condition still apply to this product?** ADR-109 set it because *"an
empty card writes to clean blocks; a full one must garbage-collect first, which is when it
stalls."* Michael's argument is that the condition models a state this product never reaches: a
cartridge holds one ~635 MB tape on a 64 GB card, so occupancy stays near 1%. The single filled
trial supports him — it was *faster*, not slower. **Hardware's view: the argument is sound and
the evidence points the same way, but A-2 is a written criterion and relaxing it is PM's call,
not Michael's unilaterally and not mine.** Recommend PM either amend A-2 for low-occupancy media
or record a standing exception. Until then this record stands as a documented deviation.

**(b) C-90 is not supported by this data, and the project already has a bar for it.** ADR-109 set
**≥ 2 SKUs sustaining ≥ 35 MB/s worst-case**; ADR-018 superseded that rule when Michael chose
C-60 directly, so it never fired. Measured against it:

| | worst window | × C-90 requirement (31.75) | × ADR-109 C-90 bar (35.0) |
|---|---:|---:|---:|
| best PNY run | 27.36 | **0.86** | **0.78** |

The worst-window figures do not reach the C-90 *requirement*, let alone its bar. The pair rates
(37.7–39.9) would clear both — but that reading depends on §9(a) being right, and it is measured
through a path that §9(b) shows is itself the limiter. **Reopening C-90 on this evidence would
rest on two unresolved confounds at once.** It is also a product-scope decision reserved to PM
and Michael, not a hardware finding.

**What would settle it,** if PM wants C-90 reconsidered: re-run with 128 MB and 256 MB windows on
the same cards to test the aliasing hypothesis directly, on a reader established not to be the
ceiling — and note that C-90 pulls the bus requirement back up toward SDR104, which ADR-109
records C-60 as having retired. That is a real cost, not just a number.
