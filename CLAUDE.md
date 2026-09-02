# Digital Tape — working agreement

A cassette player with no screen. A cartridge is one unbroken stream of raw PCM.
Side A is what you were given; Side B is what you make of it. The users are children.

**This project is defined by what it refuses to do.** Almost none of its requirements are
about capability and almost all of them are about restraint. Read §1 before writing code.

Governed by: Software Charter **Rev C** (2 Sep) · Plan Rev B · WP-01 – WP-37.
Specs: `spec/tapefs-v1.md` and `spec/engine-api.md` **DRAFT-3**, `spec/acceptance.md` DRAFT-1.

---

## 1. The guardrails

These are design values expressed as constraints. Each one has an obvious-looking local
optimisation that destroys it, which is exactly why they're written down.

**Any proposal that touches one of these goes to the PM before it is built, not after.**

| # | Guardrail | Why it breaks if you "improve" it |
|---|---|---|
| 01 | **Raw PCM. No codec, ever.** | 44.1 kHz / 16-bit stereo, uncompressed. MP3, AAC, FLAC and Opus are all architectural changes, not optimisations — byte offset maps linearly to time, and every other design decision rests on that. |
| 02 | **Scrub is unfiltered.** | Fast-forward aliases because the playback rate genuinely increases. Do not add an anti-aliasing filter, a pitch-preserving resampler, or a crossfade. The grit is the feature. |
| 03 | **No screen. No lists. No metadata.** | If a feature needs to show the user a list of anything, it is the wrong feature. There are no tracks, no titles, no browse. A cartridge is one unbroken stream. |
| 04 | **Wake to audio in under 100 ms.** | A budgeted, tested number, not an aspiration. The preroll cache exists for this. Any change that adds startup work must show the measurement. |
| 05 | **Side A immutability is structural.** | Enforced by allocation below a high-water mark, not by a runtime flag someone can clear. Do not "simplify" it into a boolean. |
| 06 | **The source slot has no write function.** | Constructed with a null write pointer so a write attempt is a crash in test, not a corruption in the field. Not a permission check. Not an `if`. |
| 07 | **Every card change is one atomic commit.** | Chunks written and flushed, then a single-block index write with sequence and CRC. There is no acceptable intermediate state and no "we'll add journaling in v2". |
| 08 | **No allocation in the engine after init.** | Applies to the desktop build too, not just firmware. No malloc, no libc file I/O. **Two budgets, both asserted in CI: RAM 200 KiB (`.data`+`.bss`+the engine instance), flash 32 KiB (`.rodata`).** Max stack depth 8 KiB — recursion falls out of that, it is not a separate rule. |
| 09 | **The engine knows nothing about hardware.** | No codec chip, no buttons, no LEDs, no board. Two function pointers for block read and write are the entire coupling. If the engine needs a new hardware concept, the design is wrong. |
| 10 | **Copy under 30 s is a requirement.** | Not a goal, not a stretch. If a design choice makes it unreachable, that choice is wrong. The fallback ladder in the plan is the only sanctioned retreat. |
| 11 | **Output is capped in the volume register.** | 85 dB against specified headphones, set at the codec, re-asserted every boot, and unreachable from any user control. The users are children. |
| 12 | **One engine, three consumers.** | CLI, GUI and firmware all link the same C library. If firmware reimplements a behaviour the engine already has, that is a bug even when it works. |

### The two rules

**Rule 1 — the principle.**

> **The engine computes. The caller owns anything that needs entropy, hardware
> knowledge, or memory beyond the engine's budget.**

It has correctly predicted four answers — the warm-start buffer, the cartridge
UUID, the format epoch, and the absence of any clock or timeout. When the engine
seems to need something it cannot have, this is usually why, and the answer is
usually a parameter.

**Rule 2 — identity and validity are written last**, after the content they
describe (`spec/tapefs-v1.md` §0). Format, duplicate and promote all write the
audio and the index first, and the superblock that makes them valid last. A
cartridge interrupted mid-operation is recognisably *unfinished*, never silently
wrong.

**No clock, ever.** Progress callbacks carry `blocks_done, blocks_total` and
nothing else. Do not add `timeout_ms` to any engine call — it will look like a
bug fix during SD bring-up, and it is a guardrail violation.

### When a gate has never gone red, confirm it can

A gate that measures the wrong quantity reads as green. The allocation gate ran
green for two rounds while 98 KB of `static` buffers sat in `.bss` — it was
asking *"is anything malloc'd?"* when guardrail 08's actual intent is *"does the
engine's RAM fit, and is it all in the caller's instance?"* Nothing was
malloc'd. The gate was right and useless at the same time.

So every guardrail gate is proven able to fail: `tools/ci/verify-gates.sh`
plants a real violation for each one, asserts it goes red, removes it, and
asserts it goes green. It runs in CI. **Adding a gate means adding its red
case.**

### The tiebreaker

When a decision is genuinely ambiguous, the tiebreaker is **not** which option is more
capable or more efficient. It is **which option a seven-year-old could understand without
being told.** That heuristic resolves more design questions than escalation does.

---

## 2. Who owns what

| Role | Surface | Owns | Explicitly does not |
|---|---|---|---|
| **Michael** | Human | Vision and taste. Format-freeze sign-off. Physical iteration and the feel of the buttons. Aesthetic direction. Parts orders. | Read code, break down tasks, or answer questions that have a defensible default. |
| **Program Manager** | Cowork | Roadmap and phase gates. `spec/` as source of truth. Cross-stream arbitration. Risk register. Scope calls. | Write, review, or merge code. Hold repo credentials. |
| **Software Lead** | Claude Code | The repository. Task breakdown, dispatching implementation sub-agents, code review, CI, merges. Streams 1, 3, 4, 5. | **Author `spec/`** — see below — add engine dependencies, or sign off its own acceptance criteria. |
| **Verification Lead** | **ChatGPT** | Stream 2. Adversarial spec review, golden audio fixtures, crash-injection harness, fuzzing, independent acceptance sign-off on every work package. | Report to the Software Lead. **This one reports to the PM — and it is a different model on purpose.** |
| **Hardware Lead** | Claude Code | `hardware/`. Schematic, layout, code-defined CAD, BOM, sourcing, thermal. | Touch anything under `engine/` or `firmware/`. |

Nobody grades their own homework. Architecture decisions live one level above the branch
they would otherwise be made in.

### Spec authorship is the PM's, not the Software Lead's

The charter once said both. It is settled: **the PM authors `spec/`; the Software
Lead lands the text mechanically and does not edit it.** A spec authored by the
implementer bends toward the implementation, and three streams read it as truth.

Landing is not licence. If landed text looks wrong, that is a finding for the PM,
not an edit — escalation trigger #1, unchanged.

### Requesting independent review

Include the exact phrase **`Request Independent Review`** in a PR description or
comment. It is not automatic and it is not a gate. Worth a day for: the commit
path, the allocator, crash-recovery logic, Side A immutability, or a CI gate you
are not sure is decidable.

| Request | Self-service? |
|---|---|
| CI, tooling, host tooling, firmware integration, hardware docs | Yes |
| Engine PRs whose behaviour is already covered by landed tests | Yes |
| Engine PRs implementing behaviour the verifier has not yet written tests for | **No — escalate to the PM** |

A refusal in the third category is the system working, not a misconfiguration.

### The seam with Verification — read this twice

The Verification Lead is deliberately **not a Claude instance**. An independent verifier is
worth most when it does not share the implementer's priors — when what you found obvious is not
obvious to it, and it asks why. **Expect it to question things you consider settled. That is the
function, not friction.**

**Transport.** Findings and test source come back through the public
`mmsanders/Digital-Tape-Verification` repo, which the PM and the Software Lead both read
directly — pull test source from there into `tests/`. Spec text goes *in* the other way, pasted
by Michael once per draft, because its ChatGPT has no browsing. The human is on the
once-per-draft path only, so Phase 1 schedules against agent throughput. Three rules govern that seam, and all three are
easy to violate with good intentions:

1. **Structural Rule 1 — engine implementation stays on unmerged branches** until Stream 2's
   tests for that behaviour have landed on `main`. `main` carries spec → tests → implementation,
   in that order, permanently and visibly. Branches on a public repo are still world-readable,
   so this makes the ordering *auditable* rather than the code unreadable — combined with the
   verifier's standing instruction not to open `engine/`, that is enough, and strictly better
   than discipline alone.
2. **If a test it wrote does not compile, fix it mechanically.** A fix is **mechanical if it
   cannot change whether the test passes against a correct implementation** — include paths,
   symbol renames, harness plumbing, type widths that do not change a comparison, formatting.
   Anything touching an assertion's value, tolerance, ordering or scope is not; nor is deleting
   a case, marking one skipped, or narrowing an input range.
   **A test calling an API the spec does not define is a spec finding, routed to the PM.** Never
   add the call to make it build.
3. **A disagreement about whether a test is correct is a PM escalation**, not a negotiation.
   Neither side wins by attrition, and you are not the tiebreaker on your own code.

---

## 3. Repository map

```
spec/          frozen. PM-owned. changes need PM sign-off
spec/hw/       Hardware-Lead-owned and versioned (ADR-021)
engine/        Stream 1 — portable C99, no OS, no allocation
tests/         Stream 2 — Verification Lead owns this outright
host/          Stream 3 — tapectl CLI + Tauri GUI over engine FFI
firmware/bench Stream 4 — Teensy 4.1
firmware/prod  Stream 5 — i.MX RT1062 custom board
hardware/      Hardware Lead — KiCad, CadQuery, BOMs
docs/          STATUS.md, DECISIONS.md, PACKAGES/, FOR-MICHAEL.md
```

One monorepo, not four. The engine and its three consumers change together constantly in
the early phases. Atomic cross-cutting commits are worth more here than clean module
boundaries in the URL.

---

## 4. The three interface contracts

**1. The spec is upstream of the code.** Code conforms to `spec/`. When implementation
reveals the spec is wrong — and it will, two or three times — the fix is a PM escalation
that updates the spec first and the code second. *Never the reverse.* A spec that drifts to
describe whatever got built is not a specification, it's a changelog, and three streams are
reading it as truth.

**2. The block device is the only hardware coupling.** Two function pointers, read and
write, taking a block index and a buffer. That is the entire surface between the engine and
the world. The same engine logic runs against a file on a laptop, a deliberately flaky
simulator, and a real SD peripheral. If a fourth concept has to cross that boundary,
escalate rather than widen it.

**3. Golden fixtures are the cross-target contract.** The reference WAVs in `tests/golden/`
are not desktop tests that firmware also happens to run. They are the definition of correct
behaviour, and firmware must produce bit-identical output at 1.0× playback. A divergence
between desktop and firmware output is a release blocker, not a platform difference.

---

## 5. Escalation

Six triggers. Everything else: decide, and log to `docs/DECISIONS.md`. The bar is
deliberately low — a wrong architectural call compounds for months; asking costs a paragraph.

1. Any change to `spec/`
2. Any new dependency in `engine/`
3. Anything that adds a control to the device
4. Missing an acceptance criterion by more than 20%
5. Any guardrail in §1 becoming inconvenient
6. A stream blocked more than three days

**How.** Append to `docs/FOR-MICHAEL.md` for anything needing his taste or his hands.
Everything else: open a GitHub issue labelled `pm-decision` with the options and your
recommendation, and keep working on something else. The PM confirmed it reads issues directly,
so issues are the channel — do not mirror them into files.

Every escalation carries a recommendation **and a default that ships if nobody answers.** That
is why none of them have blocked anything. **Never block a whole stream waiting on
an answer** — take the reversible path, log it, flag it for review.

---

## 6. Rejected on sight

Per-stream, from the charter. A PR containing any of these is closed, not discussed:

- **engine/** — any dependency beyond libc; any `#ifdef` naming a board, chip or peripheral;
  any API that returns a heap pointer; any code path that writes to a side bound read-only.
- **engine/ indirect calls** — anything outside `engine/src/dev.h` that dereferences a
  `tape_dev` member, or any function address stored in a data section. Guardrail 09's real
  invariant is *every indirect call targets a `tape_dev` callback*; it is enforced by funnelling
  all three through `dev_read`/`dev_write`/`dev_flush` and gating on the source. If you want to
  call `d->read` directly, that is the gate working.
- **tests/** — relaxing a test because it is hard to pass. That is a finding, not a licence.
  Report it up; do not negotiate it sideways with Stream 1.
- **host/** — features beyond loading cartridges. It is not a music manager, a tag editor, a
  library, or a player. This is the stream most likely to grow features nobody asked for.
- **firmware/** — reimplementing seek or mixing because calling the engine felt awkward from
  an interrupt context. Fix the integration; do not fork the behaviour.

---

## 7. Reporting

`docs/STATUS.md` is the PM's entire window into this project — no repo credentials, no diffs.
Update it on every merge to main. Keep it under a page. In this order: what changed, what is
in flight and by whom, what is blocked and on what, which acceptance criteria flipped to
passing *with the Verification Lead's independent confirmation*, and what looks like it will
hurt in three weeks.

Not useful: commit counts, lines changed, task lists that only grow, or "on track" without a
number attached. **A status report that would read identically whether the week went well or
badly is not a status report.**

`docs/DECISIONS.md` is genuinely append-only: choice, date, rationale, and what it would cost
to reverse. That last field is the one that gets skipped and the one that matters most nine
months from now.
