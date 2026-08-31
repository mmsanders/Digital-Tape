# FOR MICHAEL

The question queue. Things that need your taste or your hands — nothing else blocks on you.

Newest at the top. When you answer, the Software Lead moves the item to **Answered** with the
outcome, and logs it to `DECISIONS.md` if it was a call rather than a preference.

---

## Open

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

*Not ready because the spec is blocked on the plan document. See STATUS.md.*

---

## Answered

*(nothing yet)*
