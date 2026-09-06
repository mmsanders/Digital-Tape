# STATUS — HARDWARE

**Updated:** 2026-09-06 (2nd) · **Phase:** 0 · **Updated by:** Hardware Lead · **Reports to:** PM

The Hardware Lead's window into `hardware/` and `spec/hw/`. Companion to `docs/STATUS.md`,
which stays the Software Lead's. Argument lives in `docs/REVIEW/hardware-lead.md`; this file is
state.

**Scope:** WP-04, WP-05, WP-22–27, WP-29, WP-30, WP-34, WP-37.

> Rewritten on 5 Sep after going three rounds stale. PM Decisions 007 §3 flagged that
> independently — *"I have been reading your work through PRs and the plate itself rather than
> through your status, which works until it does not."* Correct when written; addressed the day
> before, and updated again here.

---

## What changed since last time

**The solenoid circuit was independently reviewed and the response was rejected.** Five findings,
two blockers, all accepted. **The design did not meet the limit** — 0.330 W against 0.25 W once
the electrical corners were included, where my model reported 0.220 W and a 1.14× pass.

**The error was physical, not procedural.** I bounded the *timing* corners on a coil labelled
5.0 W and treated a nominal wattage as a safety maximum. The criterion is average coil *power*
and `P = V²/R`, so rail and winding tolerance are the quantities — a combined **×1.358**, larger
than the whole margin I claimed. Reworked to 3.5 W / 10 ms / 386 ms: **0.183 W, 1.37×**. ADR-121.

**Two claims were sharing one timing corner.** The fault bound and the "real use is never
blocked" proof both used the *fastest* inhibit. At the slow corner the design held the inhibit
**539 ms against a 500 ms period** — it would have met the safety limit partly by dropping the
fastest legitimate press.

**The solenoid gate failed open, and CI never ran it.** `--check` compared the document to the
generator and never evaluated a single inequality; separately, `hardware.yml` **never invoked
`thermal-check` at all**, from the day that workflow was written. Both fixed, with a red case
whose headline is the previous working point. ADR-122.

**That last one generalises.** CLAUDE.md §1 requires every gate to be proven able to go red. It
does not require anyone to check the gate is *reachable* — and a red case in a gate nobody runs
is theatre.

---

**The plate is cleared**The plate is cleared and the two card items are settled, so it can go.** The PM verified the
rev-4 STL against the library machine. Rev 5 settles both items they raised, plus one they did
not have.

**Four lids, one per base.** Rev 4 would have made Michael reuse a mating half across four
variants, confounding wear with test order on a plate whose whole question is retention.

**`D`, `M` and `H` are the same button, deliberately** (ADR-104 bed controls) — and **not
byte-identical, as the review stated.** Each carries a different letter, so as shipped all nine
are distinct meshes. That inverts what the requested gate has to do: comparing solids **runs
green** on the plate that prompted it. The gate now compares the swept parameter and the
mechanism with the label suppressed, and `--mutate` proves the naive version fails three red
cases. ADR-120.

**A third card item, and it is the one that can waste the trip: SUPPORTS OFF.** Each button has
an 8 × 3 mm slot, 14 mm deep, blind at the top and open onto the bed — the thing that makes the
arm springy. Support material in it is unremovable and welds the flexure solid, so every button
would read as identically stiff and *"they all felt the same"* is a legitimate answer on the
card. **The trip would look like it worked and be completely wrong.**

**The clasp is respecified for a material we do not choose** (ADR-119). Closed-position strain
is now **zero, not near-zero**, and proven by a boolean over the closed assembly. The wall went
1.2 → 1.6 mm and the interference 0.30 → 0.18 mm — **lower strain and higher retention at once**,
because thickness enters strain linearly and force cubically. The TPU lip is deleted; anti-rattle
is deferred until the plate says rattle is real.

**The tolerance stopped depending on the filament.** At 0.18 mm nominal a ±0.15 mm band spans
"no engagement" to "past PLA's limit". Halves printed together shrink together, so the governing
figure is ±0.05 mm. That is a manufacturing rule, not a tuned fit.

## In flight

| Work | State | Who |
|---|---|---|
| WP-04 packet WP04-01 | **Rev 5, cleared by the PM, card settled.** With Michael to print | Michael |
| WP-24 cartridge shell | **Rev 0.2 — respecified for an unchosen material** (ADR-119) | Hardware Lead |
| WP-05 parts order | Order 1a checkout-ready. Waiting on Michael | Michael |
| WP-34 thermal budget | **Rev 0.3.** Estimates; three IR-015 responses filed, none accepted | Hardware Lead |
| `spec/hw/board-rev-a.md` | Rev 0.5, pin map populated, no pin numbers. Accretes through WP-26 | Hardware Lead |
| WP-26 schematic | Not started. Codec settled, so unblocked | Hardware Lead |

## Blocked, and on what

**The fabrication gate holds.** No board is fabricated and no cell is charged until the three
IR-015 findings are accepted. A response is filed against each; **I do not get to mark my own
responses accepted.** This is the only hard gate on the hardware stream and it is waiting on the
PM or a reviewer, not on work.

**H-02, vendor egress — partially lifted, still binding.** `www.nxp.com`, `www.lcsc.com` and
`www.jlcpcb.com` now resolve; DigiKey and Mouser serve a JS shell or 403 to any non-browser
client. The `www.` prefix is required, and **WebFetch and curl do not share an allowlist**. Net
effect: lifecycle questions are answerable, **stock and price are not**, and no filament
datasheet is reachable — which is why every material property in `cartridge-shell.md` is marked
EST.

**H-03, ERC — unchanged.** Only KiCad 7.0.11 is installable; `kicad-cli sch erc` needs KiCad 8.
`make -C hardware erc` fails loudly rather than skipping, so the gap is visible the day a board
exists. DRC is fine on 7.0.11.

**Not blocked any more:** Q-006 (answered "proceed on the default"; rev 4 is laid out to it) and
the codec (`SGTL5000XNBA3R2`, second source `SGTL5000XNLA3R2`, ADR-115).

## Spending

Per PM Decisions 001 §6 — $150/order, $600 cumulative without asking.

| Order | What | Est. | Status |
|---|---|---:|---|
| 1a | Six card SKUs + rated reader | ~$115 | **Checkout-ready with Michael** |
| 1b | Bench build | ~$152 | Drafted, **$2 over** the per-order limit — needs a nod |
| ~~1c~~ | ~~Codec buy-ahead~~ | — | **Cancelled**, Decisions 003 §2 |
| | **Cumulative committed** | **$0** | Nothing ordered yet |
| | **If 1a and 1b both placed** | **~$267** | of $600 |

## Acceptance criteria flipped to passing

**None, and none can yet.** Nothing has been measured. Every criterion written this cycle is
marked `SELF-REPORTED — no independent confirmation`, which Decisions 001 §4 makes standing
convention rather than a placeholder.

**What did change is what "passing" will require.** Decisions 006 §5: the safety measurements
are witnessed by Michael *and* independently audited by the Verification Lead from method and
raw data. Recorded as ADR-118, with the record format in `hardware/measurements/TEMPLATE.md`.
WP-24's S-4 is written to that standard from the start rather than retrofitted.

## What will hurt in three weeks

- **The solenoid response is open again and the fabrication gate is unchanged.** No board
  fabricated, no cell charged. This is now a *second* response to the same IR-015 finding, and
  I do not accept my own.
- **Two numbers in the solenoid rework are second-hand.** The `R_EXT` range and the ±14 % IC
  spread are the reviewer's datasheet readings; I cannot fetch either datasheet (H-02). They
  need confirming against the exact orderable variant before WP-26, and family variants differ.
- **The pulse length is still a placeholder and the coil now depends on it.** §6 publishes a
  feasibility boundary instead of a point. If WP-04 measures a pulse longer than ~10 ms the coil
  must weaken, and if the mechanism then needs more energy than the budget allows that is a real
  conflict between a safety limit and a mechanism — a PM escalation, not something to absorb.
- **The plate has been ready and unprinted for four days** and is still the critical path.
- **Six plates a month has not been reflected downstream.** The PM's estimate is 2–4 months for
  a working latch instead of 5–10; that moves WP-22 and the package index does not say so.
- **S-2 is a 90-day clock that has not started** and cannot until a printed pair exists.
- **A cartridge left on a car dashboard may deform**, worse in PLA than PETG. WP-25.
- **The review found an error in the engineering, not only in a check.** Rounds 5–10 I recorded
  that the maths always held and only the checks were wrong. That is no longer true, and the
  correction rate on my own numbers is the thing to watch rather than the count of findings.
