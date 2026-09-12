# Shopping list — cards for WP-05

**Owner:** Hardware Lead drafts · **Michael approves and orders** · **Updated:** 12 September 2026
**Source of prices:** DigiKey catalogue, 12 September 2026. See `2026-09-12-parts.md` for the
search that produced them.

> **This is a list, not an order.** Nothing is purchased, and no lead can purchase. Every line
> is Michael's to approve, place and pay for.

## Michael's decisions, 12 September 2026

Recorded verbatim in substance, because two of them change standing text:

1. **The "no 64 GB cards" rule was about cost, not capacity.** Michael: *"The 64gb is really
   just about cost, I didn't realize the reality of the situation."* Since the 64 GB V30 part is
   the cheapest V30 card found, **the rule no longer excludes it.**
2. **U3 may be evaluated alongside V30.** Buy both and find out whether the cheaper U3 card
   performs. This is an **evaluation**, not an acceptance that U3 satisfies the V30 requirement.
3. **n = 2 per SKU**, as a unit-to-unit consistency check: *"if they **both** work."*
4. **Revision-drift risk accepted.** Michael: *"I'll just buy like 20 to mitigate them changing
   from under us… I'll accept the risk of them changing the cards later."*
5. **All other cards come off the list.** The six-SKU comparison and every other candidate SKU
   are withdrawn from purchasing for now.

**PM reconciliation needed.** Decisions 1 and 5 conflict with standing text that PM owns:
`CLAUDE.md` §5 (*"No 64 GB cards. Seek cheap 4 GB V30 first"*), `docs/PACKAGES/WP-05.md`
(purchasing boundary and the six-SKU comparison intent) and `docs/FOR-MICHAEL-ORDER-1A.md`.
**Hardware does not edit those**; this file records the decision and flags the conflict.

## The list

### Line 1 — the V30 reference. Firm.

| | |
|---|---|
| **Part** | HTsemi `SDHFSBC064G` |
| **What** | 64 GB microSDXC, Class 10, UHS-I, **U3, V30, A2**, TLC, 0…70 °C |
| **Quantity** | **2** |
| **Price** | **$9.30 each at qty 2 — $18.60 extended** |
| **Availability** | In stock, **DigiKey Marketplace**: ships in ~15 days from HTsemi, separate shipping fee may apply |

This is the V30 comparison arm, and it is exactly purchasable at the quantity wanted.

### Line 2 — the cheap U3 arm. **One decision needed.**

The $5.70 figure is a **quantity-10 price**. DigiKey shows **no qty-1 or qty-2 break** for
`HTF016G3U3`, so two pieces at $5.70 each is not a purchase that exists. Two ways to get the
intent — the cheapest U3 card, n = 2 — and they are not equivalent:

| Option | Part | Capacity | Qty | Unit | **Total** | Temp | Notes |
|---|---|---|---:|---:|---:|---|---|
| **2a — recommended** | `HTF032G3U3` | 32 GB | **2** | $6.80 | **$13.60** | −25…85 °C | **Has a real qty-2 break.** Costs less in total than option 2b, and leaves 8 fewer cards in a drawer |
| 2b — as literally asked | `HTF016G3U3` | 16 GB | **10** | $5.70 | **$57.00** | −25…85 °C | Lowest unit price, but only at qty 10. Buys 8 spares you did not ask for yet |

Both are Class 10, UHS-I, **U3 — no V30 marking**, 3D TLC, marketplace, ~15 day lead.

**Recommendation: option 2a.** It matches "buy 2" exactly, costs $43 less, and the 32 GB part
carries the same U3 mark and the same wide temperature range. Capacity is not a constraint
either way — a C-60 is ~1.27 GB for both sides, so even 16 GB holds about a dozen tapes.

If you would rather have the spares now — you said you would buy ~20 of whichever wins — then
2b is not wasteful, just early. **Your call; I have not picked one.**

### Totals

| Scenario | Total parts cost |
|---|---:|
| Line 1 + option 2a | **$32.20** |
| Line 1 + option 2b | **$75.60** |

Shipping is **not** included and is charged separately by the marketplace seller on both lines.
**Neither total is a quote.** Lead time is ~15 days on every line.

### Removed from the list

Per decision 5, no other card is proposed: not the ATP 4 GB industrial SLC ($167.81), not the
SanDisk Extreme 32 GB, not the amp Inc / Kingston / Swissbit V30 parts, and not the withdrawn
six-card cart in `FOR-MICHAEL-ORDER-1A.md`.

## One gap this list does not close

**A card reader is not on it, and WP-05 needs one.** Criterion A-1 requires a suitable reader in
hand; **A-4 requires establishing that the reader is not the measurement ceiling** — if several
cards return similar top results at the reader's limit, the card-speed conclusion is invalid,
not merely noisy. The bar is meaningful: the sustained-write tool reports against **23.3 MB/s**,
and a C-60 side is 635,040,000 bytes needing 21.168 MB/s of payload alone over 30 seconds.

**I do not know what reader you already have**, so I am not proposing a purchase. If you have a
USB 3.x UHS-I reader, it is very likely sufficient and the answer is free. If the only reader to
hand is USB 2.0, it ceilings at roughly 40 MB/s theoretical and well below that in practice —
close enough to the bar to make every result suspect. **Tell me what you have and I will say
whether it is adequate before you spend anything.**

## What this purchase does and does not enable

**Enables:** the WP-05 A-2 sustained-write characterization on real media — 80 % filled card,
≥ 1200 MB transferred, worst 64 MB window reported with the raw per-window data — using
`hardware/characterisation/measure_sustained_write.py` with exact `--sku`, `--revision`,
`--reader` and `--fill`. Run `make -C hardware atomicity-test` first, as WP-05 directs.

**Does not enable:** any atomicity conclusion. WP-05 A-6 requires **≥ 1,000 qualifying power
cuts per exact SKU and revision**, with a committed plan, a rig, and reviewable firmware and
rail traces — none of which exist. **n = 2 is a consistency check, not a qualification**, and
two cards passing a write test says nothing about torn blocks.

**Also unchanged:** Verification reviews the method before measurements and audits the raw data
afterwards; Michael witnesses; **no lead accepts its own work**; and the fabrication gate stays
CLOSED — none of this touches a board or a cell.
