# Return — P1-R1-HW, Hardware Lead

**Assignment:** [#42](https://github.com/mmsanders/Digital-Tape/issues/42), label `hardware-lead`,
issue updated `2026-09-12T05:27:10Z`
**Input main:** `40507bf44db2f2743abddcc0188674938f4db89e` (the issue cites `d9bc6eb` as its
migration input; current main is one commit later and carries the updated role charter and
`docs/ISSUE-WORKFLOW.md`)
**Returned:** 12 September 2026 · **Next owner:** PM for disposition; Verification for the
audit packet named in §7
**Status:** `EVIDENCE AND GAP REPORT — no acceptance, no purchase, no measurement, no fabrication`

> **Nothing in this return is accepted work.** No acceptance field is signed, no order is
> placed, no physical test was run, and `make -C hardware fabrication-gate` still reads
> **CLOSED** with the same five blockers. Issue closure is not package acceptance.

---

## 1. Vendor and source access, rechecked (assignment item 1)

`docs/FOR-MICHAEL.md` requires leads to recheck their own tools rather than inherit a previous
agent's claim. Rechecked 12 September 2026; **the recorded position has changed in one
direction and held in the other.**

**Reachable:** `www.digikey.com` — full catalogue, parametrics, price breaks, stock.
**Blocked by the egress proxy:** `ti.com`, `mm.digikey.com` (DigiKey's *own* mirrored PDFs),
`rocelec.widen.net`, `nexperia.com`, `onsemi.com`, `diodes.com`, `sandisk.com`,
`westerndigital.com`, `kingston.com`, `sdcard.org`, `amazon.com`, `newegg.com`,
`bhphotovideo.com`, `mouser.com`, `shastalibraries.org`. Web search returns titles and snippets
only.

**The practical shape:** a reputable distributor can now be quoted with a date; **no
manufacturer datasheet and no consumer retail price can be verified from here at all.** That
single fact explains most of what is still open below. Full table:
`hardware/sourcing/2026-09-12-parts.md` §1.

## 2. Cards — the 4 GB V30 requirement (assignment item 1)

**The combination was not found, and I am not substituting for it.** Two independent reasons
point at commercial non-existence rather than a stockout:

1. **The marking.** Every V30 part located was 32 GB or larger; none at 4 GB. Nothing obviously
   *forbids* a 4 GB SDHC card carrying V30, so this is a commercial absence, not a demonstrated
   technical impossibility — and `sdcard.org` is blocked, so that paragraph rests on secondary
   sources, not the SD Association's own text.
2. **What 4 GB is now.** The consumer 4 GB card has left distribution. DigiKey's entire 4 GB
   microSD offering is one industrial SLC part — ATP `AF4GUDI-WACXM`, −40…85 °C, **$167.81 at
   quantity 1**, 3,836 in stock, **no speed-class marking listed**. DigiKey stocks no SanDisk
   microSD at all.

**So "cheap" and "4 GB V30" now fail together**, and minimal capacity has stopped being a proxy
for low cost — the trap `FOR-MICHAEL-ORDER-1A.md` warned about, arriving from the other side.

**A correction to the recorded fallback:** SanDisk `SDSQXAF-032G-GN6MA` appears to be
**superseded by `SDSQXH9-032G-GZ6MA`** (a retailer listing is titled "Replacement for…"). This
is a lead, not a verified fact — the page itself is blocked — but it matters because WP-05 binds
results to exact SKU and revision.

**Four ranked options are in `hardware/sourcing/2026-09-12-parts.md` §2.4.** My recommendation,
for Michael and PM to decide and not for me to act on, is a 32 GB consumer V30 set or a mixed
set, with the exact SKU confirmed from a live page first. **The capacity preference is
Michael's; I will not deviate from it silently.**

**Six-SKU comparison — PM disposition requested.** WP-05 requires PM to disposition any
reduction. I am **not** reducing it: six *4 GB V30* SKUs cannot be assembled because zero were
found. Six remain feasible at 32 GB consumer, and feasible but ~$1,000 at 4 GB industrial.
**Which population the six are drawn from is the PM decision WP-05 reserves**, and it precedes
any order.

## 3. The one-shot — bound, and the gap narrowed (assignment item 2)

**Bound:** TI `CD74HC221E` (16-DIP, bench) and `CD74HC221M96` (16-SOIC, board), both catalogued
**2–6 V**, an envelope that contains the 3.3 V logic rail (`board-rev-a` §1), with dated price
and stock. This replaces "exact orderable variant NOT yet bound" in `spec/hw/thermal-budget.md`
§6.

**Not closed, and the distinction is the whole point.** A distributor's supply-range field is
**not** a timing guarantee. The load-bearing term — the part's **guaranteed minimum/maximum
pulse width at 3.3 V** over the intended R/C and temperature — lives in a datasheet table, and
every host serving it is blocked. So:

- `TIMING_BOUND_VERIFIED` stays `False`; `IC_TOL` = ±14 % stays **ASSUMED**.
- The §6 verdict stays **PROVISIONAL**, and `verdict()` still refuses to return PASS.
- **IR-018-16 remains open**, but its remaining scope is now one specific unread table rather
  than "no vendor access". The H-02 bullet in §6 is corrected to say so.

**A new gate, with a real negative control.** DigiKey lists NXP `74HC221DB112` — an HC part
number — at **4.5–5.5 V**. Whether that is a data error or a real variant, selecting it would
put the one-shot outside its supply range at this rail and nothing in the analysis would have
noticed. `check_criteria()` now fails if the bound part's envelope does not contain `V_LOGIC`;
substituting a 4.5–5.5 V part makes it go red, demonstrated. Per CLAUDE.md §1, a gate that
never goes red has not established what it detects.

**Proposed safe method:** `hardware/measurements/solenoid-timing-method.md`. Its central
property is that it needs **no coil, no cell and no fabricated board** — it is an IC, two
passives, a bench supply and a scope on a breadboard — so **it runs while the fabrication gate
stays CLOSED and does not open it.** It also states plainly what it cannot do: five devices from
one lot is not a process guarantee, so a clean bench result would mean the assumption is *not
contradicted*, not proven, and `TIMING_BOUND_VERIFIED` should stay `False` until a manufacturer
limit is actually read. **That disposition is not the measurer's to make.**

**The pulse length is still a placeholder** (10 ms nominal) pending WP-04's measurement of the
shortest pulse that reliably releases the latch. If it returns above ~10 ms, the feasibility
table sets what the coil must drop to; if the mechanism then needs more energy than the 0.25 W
budget allows, **that is a conflict between a safety limit and a mechanism and goes to the PM**,
not absorbed by widening the limit.

## 4. IR-015 evidence index (assignment item 3)

`hardware/measurements/IR-015-evidence-index.md` indexes all three responses with, for each:
the exact document and revision, the model, the claim, the **load-bearing assumption**, what is
missing before acceptance, proposed instruments and calibration, ambient conditions, the raw
field list, and the uncertainty terms a reviewer must see. **Every acceptance field is left
blank and unsigned.**

The reviewer-facing conclusion is that **the three are not equally ready**: the charger response
is complete in method and blocked only on unread datasheet threshold fractions; the solenoid
response is structurally repaired but rests on the assumed timing corner and a placeholder
pulse; and the transient response is sound in method but **cannot finish before a board
exists**, which is worth stating so its openness is not read as inaction. Two of the three are
blocked on **environment access, not engineering**.

Accepting all three would still not open the fabrication gate — the IR-018-16 gap and the
PROVISIONAL verdict hold it independently.

**Software notification: none required.** No hardware interface changed. `board-rev-a.md` is
untouched at revision 0.5; the one-shot is a board-level component, not a firmware-visible
interface. No `engine/` or `firmware/` file was touched.

## 5. Checks actually run (assignment item 4)

At `40507bf` plus this branch's changes:

| Command | Result |
|---|---|
| `make -C hardware spec-check` | OK — 3 files, content and revision agree (after the deliberate 0.6 bless) |
| `make -C hardware thermal-check` | OK — budget, charger, solenoid all up to date; solenoid prints **VERDICT PROVISIONAL, 1 qualification gap open** |
| `make -C hardware mech-check` | OK — clasp tables up to date |
| `make -C hardware solenoid-test` | OK — 24 checks pass, **and proven able to go red** |
| `make -C hardware atomicity-test` | OK — 43 checks pass, **and proven able to go red** |
| `make -C hardware fabrication-gate-test` | OK — 8 checks + 3 CLI tests, gate **proven able to go red** and able to open on an accepted fixture |
| `make -C hardware fabrication-gate` | **CLOSED, exit 2, 5 blocking items** — unchanged |
| `make -C hardware packet-check`, `shell-test`, `packet-duplicates` | **NOT RUN** — CadQuery absent in this environment. A missing dependency is not a passing test |

The spec manifest gate demonstrated itself in passing: editing §6 and bumping the revision made
`spec-check` fail with *"revision moved 0.5 → 0.6 but the manifest still holds the old hash"*
until `spec-bless` deliberately recorded it. `thermal-budget.md` is now revision **0.6**,
hash `e30982ec982b96dbf34062990d011b454a6c0f7d13b228c527a9323751d78542`.

No packet or CAD file changed in this branch.

## 6. WP04 results card (assignment item 5)

**No results card has been returned.** `hardware/packets/wp04-01/RESULTS.md` is the blank rev-5
template; every field is empty.

Michael reported on 12 September that **the plate is currently being printed and is not yet in
hand.** That is recorded as provenance for the next round, and it is **not** a result: no
material, no orientation, no fit, no ranking and no print outcome is known or inferred. Physical
fit, retention, creep and drop all remain **pending**.

**Rev-5 instructions are preserved unchanged** — four clasp bases each with their own matching
lid, SUPPORTS OFF, one uniform orientation, `plate.stl` as the library deliverable. **The blind
mapping in `manifest.json` stays out of anything Michael is handed**, and nothing in this return
discloses it.

## 7. Packet identified for later Verification audit

The assignment asks for an exact packet. **`hardware/measurements/solenoid-timing-method.md` at
this branch's commit** is the item for Verification's pre-run method review — it is the one
proposed measurement whose criteria must be reviewed *before* it runs, per PM Decisions 001 §4,
and it is self-designed by the party who would run it, which is exactly the failure mode that
rule exists for. `hardware/measurements/IR-015-evidence-index.md` is its supporting index.

**Verification is not asked to accept anything here** — only to review the method before any
session happens, if and when PM and Michael decide it should.

## 8. Blocked, and what would unblock it

| Blocked | On | Unblocked by |
|---|---|---|
| IR-018-16 timing guarantee | Datasheet host egress | One reachable manufacturer host — **or** the proposed bench session, which needs Michael's parts approval and Verification's pre-review |
| Dated retail card prices | Consumer retailer egress | Retailer egress, or Michael checking a live page in a browser |
| Six-SKU sample plan | A decision, not access | **PM disposition** of which population the SKUs are drawn from |
| Capacity deviation from 4 GB | A decision, not access | **Michael**, explicitly. Not mine to make |
| CAD packet checks | CadQuery absent locally | GitHub hardware CI, as before |
| WP04 physical results | The print being in hand | Michael returning the card |
| IR-015-transient closure | A board existing | Later, by construction |

**Two of the seven are environment configuration rather than engineering**, and both are worth
raising before anyone spends money or bench time working around them.

## 9. Holds preserved

Fabrication and charging **CLOSED**. No purchase, no order, no cart, no 64 GB card, no silent
capacity or speed-class substitution. No measurement invented; no estimate reported as a
measurement. No acceptance of my own safety evidence. No frozen spec hash touched — `spec/` at
the Phase 0 freeze is untouched; only `spec/hw/`, which is versioned and not frozen, changed,
with a deliberate revision bump and a CHANGES row. Independent Verification separation intact.
No `engine/` or `firmware/` edit. No subworkers.
