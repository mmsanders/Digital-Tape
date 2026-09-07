# Order 1a — ready to check out

**From:** Hardware Lead · **For:** Michael's approval · **4 Sep 2026**
**Total ~$115.** Nothing here needs a decision from you — approve it and check out.

Every order comes to you first (PM Decisions 002 §4). This is the first one, and it is
the one on the critical path: it answers whether a 60-minute cartridge copies in under
30 seconds, and whether these cards can be trusted not to corrupt a cartridge when a
child yanks it mid-write.

---

## The cart

| # | Item | Qty | ~$ |
|---|---|---:|---:|
| 1 | **SanDisk Extreme Pro microSDXC 64 GB, V30 A2** | 1 | 18 |
| 2 | **SanDisk Extreme microSDXC 64 GB, V30 A2** | 1 | 14 |
| 3 | **Samsung PRO Plus microSDXC 64 GB, V30** | 1 | 13 |
| 4 | **Lexar Professional Silver Plus microSDXC 64 GB, V30** | 1 | 13 |
| 5 | **Kingston Canvas Go! Plus 64 GB, V30** | 1 | 13 |
| 6 | **The cheapest V30 64 GB card you can find, ~$8** | 1 | 8 |
| 7 | **USB 3.2 microSD reader rated ≥ 150 MB/s** | 1 | 15 |
| | Shipping / tax headroom | | ~20 |
| | **Total** | | **~$114** |

**32–64 GB is plenty.** A 60-minute cartridge is 635 MB, so even 32 GB is ten times
what a tape needs. Buy the smallest size each brand sells that is still V30 — bigger
cards cost more and tell us nothing extra.

**V30, not A2.** A2 is about small random reads, which a tape never does — it is one
long sequential stream. V30 is the sustained-write guarantee, and that is the one that
matters. Do not pay extra for A2 if a V30-only version is cheaper.

---

## Two things worth knowing before you approve

**Item 6 is expected to fail, and that is why it is in the cart.** If all six cards
pass, I have not learned that the cards are good — I have learned that my test is too
easy. A card that genuinely struggles proves the measurement has teeth. Please do buy
the cheap one.

**Any brand substitution is fine** as long as it says **V30** on it. The point is to
span different manufacturers' controllers, not these exact five. If a shop has four of
these and one other V30 brand, that is just as good.

---

## What happens to them

Each card gets two measurements, both unattended, both on the same rig in one sitting:

1. **Sustained write** — how much headroom a 60-minute copy actually has. Expect these
   cards to be comfortable; the interesting result would be one that is not.
2. **Media atomicity** — a thousand power cuts in the middle of a write, checking the
   card never leaves a half-written block behind.

The second one matters more than it sounds. **The entire cartridge format assumes a
512-byte write either happens completely or not at all.** Everything protecting a
child's recordings from a yanked cartridge rests on it, it is widely believed, it is
not actually guaranteed by the SD standard, and as far as the PM and I can tell nobody
has ever measured it on these parts. If one card tears, we need to know now rather than
after there are cartridges in the house.

---

## Not in this order

**The bench build (order 1b, ~$152)** — Teensy, audio shield, switches, solenoids. It
is useless until there are printed carriers to put the switches in, so it waits for the
library print.

**The codecs (order 1c)** — cancelled. I thought there was a nine-month lead time; the
PM checked and that was the tray packaging. Mouser has nearly 9 000 of the reel version
on the shelf. We buy those when there is a board to solder them to.

Running total after this order: **~$115** of the project's hardware spend.
