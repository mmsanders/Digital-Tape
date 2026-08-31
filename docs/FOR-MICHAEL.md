# FOR MICHAEL

The question queue. Things that need your taste or your hands — nothing else blocks on you.

Newest at the top. When you answer, the Software Lead moves the item to **Answered** with the
outcome, and logs it to `DECISIONS.md` if it was a call rather than a preference.

---

## Open

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

*Now unblocked — Plan Rev B arrived 31 Aug. The spec is being written; you will get it for
sign-off once the Verification Lead has had an independent read.*

---

## Answered

*(nothing yet)*
