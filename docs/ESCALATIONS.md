# Open escalations

Mirrored from GitHub issues labelled `pm-decision`, because the PM has no GitHub connector and
`raw.githubusercontent.com` serves files, not issues. **This file is the readable copy.** If the
PM can read issues directly, this file is redundant and should be deleted rather than maintained
in parallel — say so and I will.

Each item states a recommendation and what ships by default if nobody answers. None is blocking.

| # | Question | Default in force now |
|---|---|---|
| [2](https://github.com/mmsanders/Digital-Tape/issues/2) | Does the 200 KB static budget include `.rodata`? | RAM only (`.data + .bss`) |
| [3](https://github.com/mmsanders/Digital-Tape/issues/3) | The 512 KiB preroll does not fit the 200 KB engine budget | Caller-provided buffer |
| [4](https://github.com/mmsanders/Digital-Tape/issues/4) | Side B can only grow to 1.50× before the index slot overflows | Refuse the splice; record won't hold down |

---

## #2 — Does the 200 KB static budget include `.rodata`, or is it RAM only?

**Needs answering by:** WP-03, when `spec/engine-api.md` states the budget in bytes.

Guardrail 08 says the engine's *"static budget [is] under 200 KB, asserted in CI"*. It does not
say which sections count.

**A — RAM only (`.data + .bss`).** On the target, `.rodata` lives in flash and `.data`/`.bss`
consume RAM; RAM is the scarce resource, and 200 KB is a plausible RAM figure for an RT1062
leaving room for the preroll and audio buffers.
*Risk:* a large constant table — CRC table, resampling coefficients, a fade curve — sails through
the gate no matter how big it gets.

**B — total static footprint** including `.rodata`. One number, nothing hides, matches the plain
reading.
*Risk:* charges flash against a RAM budget, so it will eventually reject a lookup table that costs
nothing we care about — and the pressure will be to raise the 200 KB number, which weakens the
guardrail more than the table would have.

**C — both, separately budgeted.** RAM ceiling and flash ceiling.
*Risk:* the flash number is a guess until there is a board, and a budget nobody can justify gets
adjusted rather than respected.

**Recommendation: A now, revisited at WP-06.** It protects the resource the guardrail exists to
protect, and the failure mode is visible in review rather than compounding silently the way spent
RAM does. CI prints `.rodata` on every run, so growth is visible before it is a problem. Once
there is a real number to look at, C is likely right.

---

## #3 — The 512 KiB preroll cache does not fit the engine's 200 KB static budget

**Escalation trigger #5** — a guardrail became inconvenient. Shapes `spec/engine-api.md`.

Plan Rev B §04 sizes the preroll at **512 KiB**; §05 says those three seconds *"come out of RAM
while the card comes up underneath"*, which is how guardrail 04 (wake to audio under 100 ms) is
met. Guardrail 08 caps the engine at **200 KB**. This is not a rounding problem — it is 2.5×, and
the preroll alone would exceed the whole budget before a single index slot is loaded.

Checked: 512 KiB ÷ 176,400 B/s = 2.97 s, so size and duration are consistent with each other. It
is the budget they are inconsistent with.

**A — caller-provided buffer.** `tape_mount` takes a pointer and a length; the engine fills and
reads it but does not own it. Firmware allocates from OCRAM or PSRAM. The engine's 200 KB then
covers index slots and working state (two 32 KiB slots + state ≈ 80 KB), which fits comfortably.

**B — raise the engine budget to ~768 KB.**
*Risk:* the budget is the guardrail. Raising it 3.75× the first time it is inconvenient, for a
buffer that is not really engine state, is the failure mode `CLAUDE.md` §1 exists to prevent.

**C — shrink the preroll to ~150 KB (0.85 s).**
*Risk:* trades directly against guardrail 04. SD init is 100–500 ms, so 0.85 s has almost no
margin on a slow mount, and the failure mode is an audible gap — the exact thing the preroll
exists to prevent.

**Recommendation: A.** The only option that costs a parameter rather than a guardrail. It is also
the more correct design independently: preroll size depends on a particular board's SD mount
latency, and guardrail 09 says the engine knows nothing about boards — so the decision belongs
where the knowledge is. Guardrails 04, 08 and 09 all survive intact. The desktop build passes a
static array of the same size, so golden fixtures exercise the identical path, which contract 3
requires anyway.

**Note:** this is now the *second* place where the answer is "the caller supplies it" — the other
is the UUID in charter Defect B. That is a pattern worth naming in `spec/engine-api.md` rather
than two coincidences: **the engine computes, the caller owns anything that needs entropy,
hardware knowledge, or memory beyond its budget.**

---

## #4 — Side B can only grow to 1.50×; what happens when a splice overflows the index slot?

The mechanism is the Software Lead's call. The child-facing behaviour is Michael's —
`FOR-MICHAEL.md` Q-003.

```
index slot                 32 KiB = 32,768 B
  less header (seq, CRC, count)    ~64 B
  at 12 B per {chunk_id, start_offset, length}
                                 = ~2,725 entries
full 90-minute tape              = 1,817 chunks
headroom                           1.50x
```

A 90-minute tape can become ~135 minutes of spliced material, then the slot is full. Guardrail 03
means there is **no screen to explain it**.

This is a *timeline-length* limit, not a storage limit — a 64 GB card is nowhere near full. The
wall is the fixed-size index, which is fixed-size precisely because the commit must be one atomic
block write (guardrail 07). That trade is correct and I am not proposing to change it.

**A — refuse the splice, distinct error, tape untouched.** The commit never happens, so nothing is
at risk.

**B — grow the slot to 64 KiB (3.0× headroom).** 64 KiB more per cartridge on a 64 GB card is
nothing, but it moves the wall rather than removing it, and a 3× longer tape is a stranger object
to hit a wall on. Also raises engine RAM if slots are held resident, which interacts with #3.

**C — coalesce adjacent entries on commit.** Recovers most headroom for typical use.
*Risk:* real work in the commit path — the one path that must stay simple enough to reason about
under crash injection (WP-10). Not worth it in v1.

**Recommendation: A now, with B as a cheap hedge at format time** — slot size is a superblock
field under ADR-008 anyway, so 32 KiB is a default rather than a constant and can be raised later
without a format revision. C stays out of v1: the commit path is where "clever" is a liability.

**Child-facing (Michael's):** record won't hold down, matching the existing "record refuses to
stay down without play" interlock — the only option a seven-year-old could understand without
being told, which is the `CLAUDE.md` §1 tiebreaker.
