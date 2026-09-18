# Print packet WP04-01 — the latching button, and the cartridge clasp

**One page. Print the plate. Bring back the parts and this card filled in.**
Hardware Lead · rev 5, 6 Sep 2026 · WP-04 the transport spike, and WP-24 the cartridge shell

> ## ⚠ Do not print this plate yet — read this first (18 Sep 2026)
>
> **The library print did not come back.** No parts, no results. That attempt is recorded as
> inconclusive: it tells us nothing about any part on this plate, and every question below is
> still open.
>
> **You now own an A1 Mini, and this plate was laid out for the library's machine.** The plate
> is **228 mm** long. If the A1 Mini's bed is 180 × 180 mm, **it does not fit**, and no
> orientation fixes it — it is one merged solid by design.
>
> So this card is **on hold pending a rebuild**, and the rebuild needs two things from you
> first: the machine's **actual build volume**, and PM's approval of how the plate is split
> (splitting it reshuffles the blind letters, which is a change to the experiment, not a
> formatting fix). The options are laid out in
> `hardware/printing/owned-printer-baseline.md` §3.
>
> **Everything below this line still describes what the experiment is for and what to look at.**
> The parts of it about the library — one file format, staff choosing orientation, two prints a
> month, whatever spool is loaded — are now void. You choose the material, the orientation and
> the settings, and you record them on `RESULTS.md`.

---

## What this is

**Two experiments on one plate.** They have nothing to do with each other except the bed they
share — which, now that prints are not rationed by trips to the library, is the one reason they
may not stay on one plate.

**A. Nine little buttons, one long bar, and a frame to hold them.** They are nearly all the
same except for **one hidden dimension** — how deep the little hook on the side of each button
is. That hook catches the bar and holds the button down, the way a cassette player's play
button stays down until you hit stop. **One of the nine is different in another way**: its hook
sits on a longer, thinner springy arm. See question 4.

**B. Four little boxes and four lids.** These are a stand-in for the cartridge shell — the
clasp that holds the two halves together without a screw. The four bases differ in **one hidden
dimension**: how much the lip overlaps.

**Each box has its own lid, and the letters match.** Box `N` goes with lid `N`. Please keep
them in their pairs — the two halves of a pair were printed together and are sized to each
other, and swapping them is the one thing that would make your answers mean nothing.

I have not told you which is which, and the letters are shuffled on purpose. **If you knew
which one was supposed to win, you would find that it did.**

> **Some parts on this plate are deliberately the same as each other.** I have not said which,
> and you should not go looking. If two things feel identical to you, **that is a real answer
> and I want it** — it is how I find out whether the differences I am testing are big enough
> for a hand to notice at all. It is not a mistake in the file.

## Printing it

| | |
|---|---|
| **File** | `plate.stl` (`plate.3mf` is also in the packet and your slicer can open it) |
| **Plate size** | **228 × 119 mm** — ⚠ **larger than a 180 mm bed. See the hold above** |
| **Estimated print time** | about 2 hours |
| Material | **Your choice now, and write it down.** PLA is the conservative case the analysis assumes; PETG is fine and gives more margin |
| Layer height | 0.2 mm unless you have a reason |
| **Supports** | **OFF. This is the one setting that can waste the print — see below** |
| **Orientation** | Flat, as laid out — and **all parts in the same orientation**, which is now yours to guarantee rather than a request to staff |

> ## The settings that matter, in order
>
> **1. SUPPORTS OFF.** Not "on build plate only" — **off**.
>
> **2. All parts in one orientation.** The plate is laid out flat and should print flat. Some
> parts are open boxes; turned on their side or upside down they will need supports.
>
> **3. Record what you actually used** on `RESULTS.md` — material, spool, nozzle, plate, layer
> height, orientation, slicer version. A printed part with no process record is not evidence,
> and that is the whole point of owning the machine instead of borrowing one.

**Why supports off matters more than everything else on this card.** Each button has a narrow
slot up the middle of it, about 8 × 3 mm and 14 mm deep, closed at the top and open at the
bottom onto the bed. That slot is not decoration — **it is what makes the little arm springy,
and springiness is the thing this whole plate measures.**

A "supports everywhere" setting fills that slot with support material. Fourteen millimetres
down a 3 mm gap, **you will not get it out**, and while it is in there the arm cannot flex at
all. Every button would then feel identically stiff — and "they all felt the same" is a real
answer on this card, so **the print would look like it worked and would be completely wrong.**

If supports cannot be turned off for some reason, print it anyway and tell me. That is a fact
about the machine I need.

**One thing about the boxes.** They are designed to be safe in either candidate material, but
**I expect one of the four to crack** rather than open. That is deliberate and it
is a useful answer, not a wasted part — tell me which one and I will know my numbers are about
right.

---

## A. The buttons

### Putting it together

1. Push a button into the square hole in the **frame** from the top.
2. Slide the **bar** through the side channel so it sits against the button's hook.
3. Push the button down. The bar should shove aside, then snap back over the hook and hold the
   button down.
4. Pull the bar sideways. The button should pop back up.

The frame has a window in the front so you can see the hook and the bar meet. If a button does
something strange, look through the window before deciding what happened.

### What I need

**Rank your top three by which *click* you like best.** Not which works best, not which is
strongest — which one you would want on the finished thing. Press each one down and let it go,
several times.

You are the instrument here. There is no number to measure and I do not want you to try; your
preference is better data than anything I could ask you to measure with a ruler.

**If they all feel more or less the same, say that instead of picking three.** There is a box
for it. "They were all much of a muchness" tells me my range was too narrow and saves the next
trip. Three rankings I made you invent tells me nothing and costs two weeks.

### What "good" looks like

- Goes down with a definite **click** you can feel through your thumb — not a mush, not a crunch.
- **Stays** down. Does not creep back up on its own.
- Pops up cleanly when the bar moves. Does not need help.
- Does not need a hard shove. A child's index finger.

I expect at least one to be obviously too loose and one obviously too stiff. **That is
deliberate** — if the extremes were not obviously wrong I picked too narrow a range.

---

## B. The boxes

### Putting it together

1. Take a lid and press it onto **the base with the same letter**. It should click shut.
2. To open it: slide a **guitar pick, a spudger, or a butter knife** into the thin slot on the
   long side, and twist. It should pop open along that side and then peel apart.
3. Do all four pairs.

**Keep the pairs together.** Last time I was going to send you two lids for four boxes, and the
PM pointed out that would have meant reusing a lid — so by the fourth box I would be measuring
how worn the lid was rather than how good the box is. You now have one lid per box and that
problem is gone. Just do not mix them up.

### What I need

**Rank the four boxes by which one you would want to be the cartridge.** The feel of the click
shutting, and how it feels to open.

### What "good" looks like

- Shuts with a **click** and stays shut when you shake it.
- **Does not open when you try to pull it apart with your fingers** — that one matters most,
  because a cartridge that a child can pull open is a loose memory card on the floor.
- Opens **easily with the tool** in the slot. Firm, but not a fight.
- No visible gap at the join when it is shut.

### The one that matters more than the ranking

**Try to open each one with your fingernails only, no tool, for a good thirty seconds.** Really
try. If any of them can be opened that way, that is a failure and I need to know — it outranks
every preference on this card.

---

Nothing to arrange, rotate or choose. If the machine wants something this plate does not give
it, that is my mistake and I want to hear about it.

## About how it feels versus how long it lasts

You are answering **how does it feel** only. If you print these in PLA it is a prototyping
plastic — it will not feel quite like the finished part, and it will wear out much sooner. Once
you have picked winners, those shapes get printed in the material that ships and you confirm
they still win. So do not worry about whether these will last. They will not. That is a
different print — and now it is a different afternoon rather than a different month.

---

## Filling in the results

`RESULTS.md` next to this file, or the back of this page. Ten minutes at the kitchen table.
Ticks and letters — please do not write me an essay, and please do not polish it.
