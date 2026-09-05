# FOR MICHAEL

The question queue. Things that need your taste or your hands — nothing else blocks on you.

Newest at the top. When you answer, the Software Lead moves the item to **Answered** with the
outcome, and logs it to `DECISIONS.md` if it was a call rather than a preference.

---

## Open

### Q-008 — How big is a cartridge, and does it have to look like a cassette?

**Needs:** your taste · **Blocks:** nothing — a working number is in use
**Why you and not us:** this is the one shell decision that is genuinely aesthetic

I have designed the clasp — the thing that holds the two halves of the cartridge together
without a screw, that you asked for. It works. But I had to pick an outside size to draw it, and
I picked **86 × 54 × 12 mm** for a reason that is defensible and not yours: 86 × 54 is a credit
card, so it is a shape a child's hand already knows, and 12 mm is about a cassette's thickness.

**The good news is that this is a free choice.** The maths that decides whether the plastic
survives has no length term in it — it depends on the wall section and how far the lip bends,
not on how big the box is. So changing the size moves how *hard* it is to open (bigger is
harder) and changes nothing about whether it lasts. You can pick this on taste and I will not
have to redo anything.

Three things worth knowing before you pick:

- **A real cassette is 100 × 64 × 12 mm.** If "it should feel like a cassette" matters more to
  you than "it should fit a small hand", that is the number, and it costs nothing.
- **Bigger is harder for a child to pull open**, slightly, because there is more lip to peel at
  once. Not by enough to change the safety case.
- **Smaller prints faster**, which matters while you are getting two library prints a month.

**Default if you don't pick:** 86 × 54 × 12 mm.

---

### Q-007 — A correction: a home printer will not give us nylon

**Needs:** nothing from you — this is me telling you something I got wrong
**Blocks:** nothing. It does not change the printer recommendation

You were told (Decisions 005 §3) that buying a printer would let us print the latch in PETG
*and* nylon. **PETG yes. Nylon no.** The A1 line runs PLA, PETG and TPU and explicitly does not
do nylon — it needs a hotter bed and an enclosed chamber, and Bambu does not sell an enclosure
for the A1.

**It changes almost nothing, and here is why.** Nylon is good at one thing we thought we needed:
surviving thousands of flexes. The PM's insight about the cartridge — *you will open it once or
twice in its life, not weekly, because every cartridge after the first is copied by the device
itself* — means the shell does not need that. It is designed for PETG throughout and PETG is
comfortable.

**Where it does still bite: the transport latch.** That one clicks every time somebody presses
play, for years, so it genuinely is a fatigue part. If the plate says the latch is marginal, we
send **that one small part** to a print service in nylon and print everything else at home.
That is a normal split and it costs about the price of a takeaway.

**One thing that is worth a pound of prevention:** TPU. The cartridge design uses a thin rubbery
lip to soak up the variation between prints — it is what stops the clasp from being tight in
one colour and loose in another. **The library cannot print it and the A1 can.** That is a more
concrete argument for the combo than "more materials would be nice".

---

### Q-004 — Your tape will remember where you were, but only in your own player

**Needs:** your taste · **Blocks:** nothing — a default will ship
**Why you and not us:** the mechanism is forced; the feeling it creates is a choice

A real cassette resumes where you left off because the tape is physically sitting at that spot.
The position belongs to the tape.

We can't do that. The left slot is read-only by design — that is the thing protecting your kids'
music — so a cartridge played there has no writable surface to record its position on. The fix
is for the *player* to remember, in its own memory, where each cartridge was.

That works, and it's cheap. But it means the position lives in the player rather than the tape,
and there will be four players in the house. Take your tape to your brother's player and it
resumes wherever *he* left that tape, or at the beginning. Bring it back to yours and it's where
you left it.

Our read is that this is fine and possibly even nice — "my player remembers my tapes" is a rule a
child can hold. But it's a real departure from how a cassette behaves, so it should be your call
rather than a side effect of ours.

**Default if you don't pick:** the player remembers, and it remembers the last 64 cartridges.
Anything older starts from the beginning again.

---

### Q-002 — Is 90 minutes worth the UHS-I risk?

**Needs:** your call · **Blocks:** nothing yet, but it should land before the format freeze
**From:** Plan Rev B §13, ask #02 — restated here because it now touches the format spec

You were already asked this in the plan. Raising it again only because it has become
time-sensitive: a 90-minute tape is 952 MB and needs the board's hardest circuit (1.8 V UHS-I
switching) to hit the 30-second copy. A 60-minute tape is 635 MB and hits 29 s on the safe,
boring interface with no 1.8 V switching at all.

The format spec is being written so this can change without a re-spec — region sizes come from
a number stored on the card at format time, not from a constant. So it is genuinely not
blocking. But it is cheaper to answer before the freeze than after, and it trades a real
engineering risk against twenty minutes of tape.

*No recommendation from here — this is a taste-and-risk trade, not an engineering one.*

---

### Q-003 — What should the device do when a tape can't get any longer?

**Needs:** your taste · **Blocks:** nothing — a default will ship if you'd rather not decide
**Why you and not us:** the mechanism is ours; what a child feels at the wall is yours

Side B's timeline can grow to about 1.5× the original length before its index runs out of room
(a 90-minute tape can become roughly 135 minutes of spliced-up mess). A child splicing
enthusiastically will eventually hit that.

There is no screen to explain it. So the options are all physical: refuse the splice with a
distinct sound, refuse it silently, or let the record button simply not hold down — the same
way it already refuses to stay down without play. That last one has the advantage of reusing a
rule the child already knows.

Our default if you don't pick: **record won't hold down**, matching the existing interlock.

---

### Q-001 — Format freeze sign-off (Phase 0 gate)

**Needs:** your sign-off · **Blocks:** Streams 1, 2, 3, 4, 5 — i.e. all of them
**Status:** not ready to put in front of you yet

Once `spec/tapefs-v1.md` exists, you get one look at the cartridge format before it freezes.
This is the one decision where a late change costs real rework: the byte layout is what three
streams implement against, and changing it after firmware exists means reflashing every
cartridge that was ever written.

You will not be asked to read the spec. You will be asked about the handful of choices inside
it that you can feel rather than verify — how long a cartridge holds, what happens when you
yank one mid-record, and whether Side B behaves the way you pictured.

**Update 2 Sep — this moves out again, and that is the right call.** The Verification Lead read
DRAFT-3 and returned **four blocker findings against it**, two of which I confirmed against my
own code. Freezing a format the verifier has already shown to be broken would mean reflashing
every cartridge later to fix something we knew about today.

DRAFT-4 is with the PM. You will get the format for sign-off after that, not before.

---

## Answered

### Q-006 — Library printer
**Answered 2 Sep:** not yet checked; proceed on the default — PLA, 0.2 mm, four-hour
plates, STL + 3MF + bed picture, no G-code. Re-slice if details arrive.

### Q-005 — Spending
**Answered 2 Sep:** every order comes to Michael first, as a checkout-ready cart with
a one-line justification. Running total in STATUS.md. Logged as ADR.

### Q-004 — Resume position
**Answered 2 Sep:** the player remembers, last 64 cartridges, across days; resumes
2 s early. Accepted as a deliberate departure from the tape metaphor. Logged as ADR.

### Q-003 — The wall
**Answered 2 Sep:** record button won't hold down, plus a green/yellow/red record
light showing Side B headroom; red coincides with the button refusing. Logged as ADR.

### Q-002 — Tape length
**Answered 2 Sep:** C-60 is the standard. C-90 and longer permitted by the format
with slower copy. Do nothing that closes off longer lengths. Logged as ADR.

---

### Q-005 — What can I spend, and above what number should I ask first?

**Needs:** your wallet · **Blocks:** nothing — a conservative default is in force
**From:** Hardware Lead

You place the parts orders, so you set the ceiling. I need two numbers before I draft one:

1. A rough budget for hardware across the whole project. The plan carries three board spins,
   and a run of assembled boards is the single biggest line item in this project by a distance.
2. The figure above which I should put an order in front of you *before* proposing it, rather
   than just handing you a prepared cart.

Neither answer blocks me — I would just rather find out now than have you open a cart with a
number on it you weren't expecting.

**The PM has set a default while you think about it** (Decisions 001 §6), so nothing is
blocked: **$150 per order, $600 cumulative, without asking.** Above either, I propose first.
That sits inside the plan's ~$1,590 across roughly eight orders and it covers the card buy
outright. A running total lives in `docs/STATUS-HARDWARE.md`.

**So this is now a confirm-or-change, not a blocker.** The first two carts come to ~$267 of
that $600 — six memory cards and a reader (~$115), and the bench build (~$152). The second is
$2 over the per-order line, which is the sort of thing I would rather you waved through once
than have me ask about every time.

---

**ANSWERED (Decisions 002 §4).** Every order comes to you first as a checkout-ready cart with a one-line justification. Running total in `docs/STATUS-HARDWARE.md`; three carts drafted, ~$400.

---

### Q-006 — What is the library's 3D printer, actually?

**Needs:** your hands and about ten minutes of asking · **Blocks:** WP-04, the critical path
**From:** Hardware Lead

The whole mechanical plan is built on sending you to the library with one plate that answers a
question, instead of one part that produces a data point. To do that I have to hand you a file
that machine will actually accept, and right now I'd be guessing.

Whatever you can find out, in rough order of how much it changes what I send you:

- **What machine is it?** Make and model. A photo of the front of it is a perfect answer.
- **What can you print in?** Most library makerspaces are PLA-only. If PETG or ABS is on the
  menu that matters a lot later — see below.
- **How do they take the job?** Do you hand them a file and they slice it, or do you slice it
  yourself and bring G-code? Is there a machine there you can drive?
- **Is there a time limit per print or per session?** Two hours and four hours are different
  designs on my end.
- **How long from drop-off to part in hand?** If it's same-day, the plan works as written. If
  it's "come back Thursday", I should be designing bigger, less frequent sweeps.

**Why the material question matters more than it sounds.** You'll be ranking how the buttons
*click*, and PLA is a prototyping plastic — it creeps under a spring and it will not feel the
same as whatever the final part is made of. Your ranking is still the right way to find the
answer; I just want to print the top two or three in the real material and have you confirm
the winner still wins, before I commit the enclosure around it.

**My default if you'd rather not chase this:** PLA, 0.2 mm layers, plates that fit in four
hours, and I send you an STL plus a 3MF plus a picture of how it should sit on the bed —
rather than G-code, which only works if I know the machine.

---

**ANSWERED (Decisions 002 §2).** You chose the defaults: PLA, 0.2 mm, four-hour plates, STL + 3MF + a bed picture, no G-code. Packet WP04-01 is built on exactly those and is ready to go. If you learn more about the machine it re-slices in one command.

