# DECISIONS

Append-only. Newest at the bottom. Never edit or delete an entry — supersede it with a new one.

Every entry carries four fields. The fourth is the one that gets skipped and the one that
matters most nine months from now.

**Format:** `## ADR-NNN — title` / **Date** / **Decision** / **Rationale** / **Cost to reverse**

**Numbering.** `ADR-0xx` is the shared sequence. **`ADR-1xx` is reserved for Hardware Lead
decisions.** Two leads appending numbers to one append-only file pick the same number and only
find out at merge — which already happened once: the Hardware Lead's first four decisions were
`ADR-010`–`013`, and so are four of the Software Lead's. A separate range removes the class of
problem rather than the instance. This is the reversible path taken under Charter §05; the PM
may collapse it back with one `sed`, and the Verification Lead should claim a range too.

---

## ADR-001 — One monorepo, not four

**Date:** 2026-08-31 · **Decided by:** PM (Software Charter §03)

**Decision.** `github.com/mmsanders/Digital-Tape` holds everything including hardware.

**Rationale.** The engine and its three consumers change together constantly in the early
phases. Separate repos would buy independent versioning nobody needs at the cost of version
skew nobody wants. Atomic cross-cutting commits are worth more than clean module boundaries
in the URL.

**Cost to reverse.** Moderate and rising. Splitting later means untangling shared CI, the FFI
build, and cross-references in `spec/`. Cheap through Phase 1; expensive once firmware and
host both consume the engine in anger.

---

## ADR-002 — Repository is public

**Date:** 2026-08-31 · **Decided by:** PM (Software Charter §03), verified by Software Lead

**Decision.** The repo is public. `docs/STATUS.md` is readable from
`raw.githubusercontent.com` without authentication.

**Rationale.** There is no first-party GitHub connector on the PM's account, so the PM cannot
authenticate into a private repo. Public means live project state at the start of every PM
session — no relaying, no stale summaries, no Michael pasting digests by hand. There is
nothing in a family cassette player worth keeping secret.

**Cost to reverse.** Low technically (flip the setting), but forks and clones taken while
public cannot be recalled. Decide before there is anything sensitive; there is no plan for
there ever to be.

---

## ADR-003 — Verification is a peer role, not a report

**Date:** 2026-08-31 · **Decided by:** PM (Software Charter §01)

**Decision.** The Verification Lead owns `tests/` outright and reports to the PM, not to the
Software Lead.

**Rationale.** The crash-injection harness exists to prove that a child yanking a cartridge
mid-write cannot destroy the music they love. If the agent whose code is under test also
manages the agent writing the tests, that harness will quietly get weaker every time it is
inconvenient.

**Cost to reverse.** Low to reverse, high to undo the consequences. Collapsing the roles saves
one session per cycle and forfeits the one guarantee this project cannot compromise on. The
damage would not be visible until a cartridge is corrupted in the field.

---

## ADR-004 — Code-defined CAD, not GUI CAD

**Date:** 2026-08-31 · **Decided by:** PM (Software Charter §08)

**Decision.** Enclosure, button mechanism and cartridge shell in CadQuery or OpenSCAD; boards
in KiCad. Everything hardware is text and therefore source.

**Rationale.** An agent can iterate, diff, parameterise and regenerate a family of variants
from one changed number. "Print six variants of the latch bar with hook depths from 0.8 to
1.8 mm" is a for-loop, not six modelling sessions — Michael carries one plate to the library
and comes back with the answer instead of one data point. Michael does not model, so a GUI
tool's cost buys nothing.

**Cost to reverse.** High after the first enclosure spin. Parametric intent does not survive
export to a GUI tool; the sweep capability is lost outright.

---

## ADR-005 — CI tooling lives in `tools/`, outside the Charter §03 tree

**Date:** 2026-08-31 · **Decided by:** Software Lead · **Flagged for PM review**

**Decision.** Gate scripts live in `tools/ci/`, with `.github/workflows/ci.yml` as a thin
caller. Charter §03 does not name either directory.

**Rationale.** Charter §09 action 04 requires CI, and it has to live somewhere. Putting the gates in
`tools/ci/` rather than inside the workflow means every gate runs locally exactly as it runs
in CI, so "works on my machine" and "works in CI" are the same claim. Putting them under
`engine/` would have been wrong — the golden-suite gate spans `tests/`, which belongs to the
Verification Lead.

This is the reversible path taken under the "never block a whole stream waiting on an answer"
rule. The PM may rename or relocate it.

**Cost to reverse.** Trivial now — a `git mv` and one path in the workflow. Rises once the
Hardware Lead adds KiCad ERC/DRC gates alongside these, which the charter anticipates.

---

## ADR-006 — Memory budget counts `.data + .bss`, not `.rodata`

**Date:** 2026-08-31 · **Decided by:** Software Lead · **NEEDS PM CONFIRMATION at WP-03**

**Decision.** The 200 KB static budget in guardrail 08 is enforced against `.data + .bss`.
`.rodata` is reported but not counted.

**Rationale.** On the target, `.rodata` lives in flash and `.data`/`.bss` consume RAM, and RAM
is the scarce resource the guardrail exists to protect. The charter says "static budget under
200 KB" without splitting them, so this is an interpretation, not a reading.

**It may be the wrong one.** If the intent was total static footprint, the gate is currently
too permissive and a large constant table would sail through. `spec/engine-api.md` (WP-03)
must state which, in bytes, per subsystem. Raised as a `pm-decision` issue.

**Cost to reverse.** Trivial today — one line in `tools/ci/audit-memory.sh`. Expensive once
the engine is written against the looser reading, because tightening it later means finding
RAM that was already spent.

---

## ADR-007 — Plan Rev B adopted as the numeric input to WP-02 and WP-03

**Date:** 2026-08-31 · **Decided by:** PM (Plan Rev B), checked by Software Lead

**Decision.** The format and API numbers in Plan Rev B §04 and §05 are the input to
`spec/tapefs-v1.md` and `spec/engine-api.md`. Adopted as given:

| Quantity | Value |
|---|---|
| Audio | 44.1 kHz / 16-bit stereo PCM, 176,400 B/s |
| 90-minute cartridge | 952,560,000 B (~953 MB), 1,817 chunks |
| Chunk | 512 KiB = 2.9722 s |
| Superblock | 4 KiB × 2, both ends of the partition |
| Preroll cache | 512 KiB (~2.97 s) |
| Index slots | 32 KiB × 4 — two double-buffered per side |
| Index entry | `{chunk_id, start_offset, length}`, 12 B |
| Side A store | 952 MB, immutable, below high-water mark |
| Partitioning | MBR: small FAT32 (README + label art) + raw TAPEFS |

**Rationale.** The numbers reconcile exactly and independently. The plan states the Side B map
is "about 22 KB"; 1,817 entries × 12 B = 21,804 B = 21.3 KiB. That arithmetic was not given in
the plan — it confirms the 12-byte entry width rather than assuming it, which is why the entry
layout can be specified byte-exact rather than guessed.

Checked and consistent: byte rate, tape size, chunk duration, chunk count, copy rate
(952.56 MB / 30 s = 31.8 MB/s), preroll duration.

**Two things the plan does not resolve.** Both raised rather than assumed — issues #3 and #4.
Neither blocks WP-02.

**Cost to reverse.** Rises sharply at the format freeze. Before the gate, changing a number is
an edit to one document. After it, it is a reflash of every cartridge ever written. Region
sizes will be parameterised from superblock fields specifically so that tape length can change
without a re-spec — see the open 90-minute question.

---

## ADR-008 — Region sizes are derived from superblock parameters, not hard-coded

**Date:** 2026-08-31 · **Decided by:** Software Lead

**Decision.** `spec/tapefs-v1.md` will state region *offsets and sizes as fields in the
superblock*, computed at format time from a stored tape length, rather than fixing 952 MB and
1,817 chunks as constants in the format.

**Rationale.** Plan §13 ask #02 puts the 90-vs-60-minute question to Michael and it is still
open. 60 minutes changes the Side A store from 952 MB to 635 MB. The plan already lists "format
params" and "region offsets" among the superblock's contents, so this is reading the plan
rather than extending it — but making it explicit means the answer arriving late costs a
format-time constant, not a spec revision and three streams re-reading it.

It also makes the engine's mount path honest: it reads where the regions are instead of
assuming, which is the same code either way.

**Cost to reverse.** Low, and it buys optionality that is expensive to add later. The cost paid
is a handful of extra superblock fields and a mount path that computes instead of assumes —
both of which the engine needs regardless.


---

## ADR-009 — Verification Lead is ChatGPT, with no repository access

**Date:** 2026-08-31 · **Decided by:** PM (Software Charter, revision of 31 Aug)

**Decision.** Stream 2 moves from a Claude Code instance to ChatGPT. Its scope gains adversarial
spec review. It has no repository access: it receives `spec/` as text and returns findings and
test source, which the Software Lead lands and runs. Three seam rules govern the exchange —
recorded verbatim in `CLAUDE.md` §2.

**Rationale (the PM's).** An independent verifier is worth most when it does not share the
implementer's priors. A verifier built on the same model as the implementer will tend to find the
same things obvious, and the things it finds obvious are exactly the things nobody checks.

**Cost to reverse.** Low as a swap, high in what it would quietly undo. Moving Stream 2 back to a
Claude instance would restore repository access and remove the relay described below — a real
convenience — while giving up the shared-priors argument that is the entire reason for the
change. The tell that it has been reversed in spirit rather than by decision would be tests that
stop surprising anyone.

**Consequence not yet resolved.** The charter does not say who carries text across the seam. That
is the highest-frequency interaction in the project and it now has a human-shaped gap in the
middle of it. Raised in `docs/REVIEW/software-lead.md` §3.1.

---

## ADR-101 — Solenoid protection bounds duty cycle, not only pulse width

**Date:** 2026-09-02 · **Decided by:** Hardware Lead (Charter §05 — decide and log)

**Decision.** The solenoid gate carries three hardware protections, not one: a
non-retriggerable one-shot (`74HC221` class) capping on-time at 50 ms, an RC lockout enforcing
a minimum off-time, and a PPTC on the solenoid rail (hold ≈ 100 mA) as an average-current
backstop. Plus a flyback diode per coil and a gate pull-down.

**Rationale.** The Hardware Charter specifies a hardware one-shot and is right that it is not
a firmware responsibility. But a one-shot bounds how long a *single* assertion lasts and says
nothing about how often assertions may occur. Firmware stuck in a retrigger loop at 100 Hz
delivers a 50 ms pulse every 10 ms; the coil sees essentially its full 9 W continuously and the
one-shot fires correctly throughout. **The exact failure the charter describes — a stuck
firmware state cooking a coil built for 30 ms pulses — is reachable through a working
one-shot.** The PPTC closes that hole physically: no sequence of edges can defeat it, because
sustained conduction opens the circuit.

Cost over the charter's single one-shot: about fifteen cents.

**Cost to reverse.** Trivial before layout, expensive after. These are three small parts and a
rail; adding them post-layout means finding board area next to a switching node. Removing them
later is a schematic edit — but doing so re-opens a failure mode whose consequence is a burnt
part inside a sealed enclosure in a child's hands.

---

## ADR-102 — Charging is suspended for the duration of a copy

**Date:** 2026-09-02 · **Decided by:** Hardware Lead

**Decision.** The charger is inhibited while a copy is in progress, via a control line the
charger already has.

**Rationale.** `spec/hw/thermal-budget.md` §3 shows the copy is thermally free — 30 seconds
against a 621-second enclosure time constant raises the bulk temperature about half a kelvin.
The sustained case that governs is playback while charging, and at 35 °C ambient that lands
within 0.2 K of the 45 °C JEITA charge ceiling. Removing the highest-power mode from the
sustained set costs one control line and is imperceptible: nobody notices 30 seconds missing
from a 90-minute charge.

This is the cheapest thermal margin in the design, and it is available only because the copy is
required to be fast — guardrail 10 buys a thermal result as a side effect.

**Cost to reverse.** Near zero. One line in firmware and one net. Worth reversing only if
measurement shows the margin is larger than estimated, which WP-37 will say.

---

## ADR-103 — The bench build validates function, not copy time

**Date:** 2026-09-02 · **Decided by:** Hardware Lead

**Decision.** Card sustained-write characterisation runs on a PC with a rated reader, not on
the Teensy bench build. The bench build owns hot-swap detect, the LED row, the button matrix,
the interlock and the solenoid one-shot — everything in WP-18 and WP-20 except the throughput
number.

**Rationale.** The Teensy 4.1 has one 4-bit SDIO port. A second card hangs off SPI at roughly
10–20 MB/s, so a bench copy of a 90-minute cartridge takes 60–95 s regardless of how good the
cards are. That is a property of the bench platform, not a finding about the design, and a
criterion the platform cannot meet is a criterion that will be quietly relaxed.

Running the characterisation on a PC is also simply better: it is available the day the cards
arrive rather than after WP-17, and it removes our own untested driver from the measurement.

**Cost to reverse.** None — this is a routing decision about where a measurement happens.
The consequence to watch is WP-18's acceptance criteria, which currently read as though the
bench proves the copy time. Raised for the PM in `docs/REVIEW/hardware-lead.md`.

---

## ADR-104 — Print sweeps carry hidden controls and blind labels

**Date:** 2026-09-02 · **Decided by:** Hardware Lead

**Decision.** Every print-run packet embosses labels unrelated to the swept parameter, and
includes duplicate copies of one variant at spread bed positions, ranked blind alongside the
real variants. The mapping lives in the repository, never on the card.

**Rationale.** Two failure modes, both invisible without this. If the labels encode the
parameter, the ranker ranks by expectation rather than by feel — and Michael is the instrument,
so biasing him corrupts the only measurement we have. And a 0.3 mm step in hook depth is within
range of the variation a printer produces across its own bed, so without duplicates a scatter
is indistinguishable from a signal. The duplicates test the print and the ranker with the same
parts and no extra trip.

The counter-intuitive payoff: when the controls scatter, the correct next sweep is **coarser**,
not finer. Without controls the instinct after an inconclusive plate is to refine, which walks
further into the noise and costs another week.

**Cost to reverse.** Zero — it is a convention in `build_packet.py`, about twenty lines.
Abandoning it costs the ability to tell a result from noise, which is the whole reason the
library loop exists.

---

## ADR-105 — The cartridge's microSD is captive

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 001 §2), raised by Hardware Lead (issue #6)

**Decision.** The microSD inside a cartridge is captive. `tapectl` and the GUI reach the card
**through the player over USB-C** — the production board exposes the device itself as the
cartridge. Removing the card is not a workflow the design supports.

Serviceable, **not** tool-free: an adult with a driver may open the shell to replace a failed
card. A curious six-year-old with a fingernail may not. **Where those two requirements fight,
the six-year-old wins.**

**Rationale.** A loose microSD in a child's hands is a lost microSD, and a shell that opens
becomes a container for something else and then a shell with nothing in it. The cartridge exists
so the storage is an object you can hold, label and pass around — it is the object, not a costume
around a memory card. It also settles the shell design in the direction the vision already
points, and removes an ESD path a child can touch.

**Cost to reverse.** High after WP-24. The shell, the sealing, the drop case and the carrier PCB
all follow from it. Reversing also strands the USB-C loading path in firmware and `host/` — which
is the cost this decision *adds*: a device path that is not in any work package today and needs
scoping. That obligation is recorded in `spec/hw/board-rev-a.md` §7.

---

## ADR-106 — `spec/hw/` is versioned, not frozen; limits stay upstream

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 001 §3), raised by Hardware Lead (issue #7)

**Decision.** Two tiers. `spec/` stays PM-owned and frozen at the Phase 0 gate
(`tapefs-v1.md`, `engine-api.md`, `acceptance.md`). **`spec/hw/` is Hardware-Lead-owned and
versioned, with no PM gate** (`board-rev-a.md`, `thermal-budget.md`).

The obligation on `board-rev-a.md` is **notification, not approval**: any change to a pin, a
rail, or a timing constraint lands as a PR naming the Software Lead as reviewer, carrying a
`CHANGES` block listing exactly what moved. Firmware acknowledges by merging.
`thermal-budget.md` has no code consumer and needs no protocol at all.

**But limits move upstream.** The JEITA window, the solenoid on-time and duty ceilings, the
85 dB cap and the touch-temperature limit belong in `spec/acceptance.md`, PM-owned and frozen.
**Measurements live with the Hardware Lead; the numbers a unit must not exceed do not.**

**Rationale.** Both hardware documents are specified to change repeatedly after the freeze —
estimates become measurements, a revision moves a pin. Under a blanket freeze every thermocouple
reading is an escalation, which grinds or, far more likely, gets quietly ignored. That is the
"spec that drifts to describe whatever got built" failure arriving through the front door with
the rule's blessing. The cut is at the *consumer*, not the document: what needed protecting was
firmware's ability to trust a pin map, and notification protects that where a freeze could not.

**Cost to reverse.** Low — a directory move and a paragraph. The thing that would be expensive
to recover is the notification habit, which only works if it is never batched.

---

## ADR-107 — Hardware acceptance sign-off splits three ways by consequence

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 001 §4), raised by Hardware Lead (issue #8)

**Decision.**

- **Criteria and paperwork → Verification Lead.** Its authority extends to reviewing whether a
  hardware acceptance test proves what it claims, **before** the test is run. It does not run the
  test and does not touch hardware.
- **Safety measurements → Michael witnesses.** WP-19's SPL check and WP-37's thermal run.
  Scheduled when he is around, not reported afterward.
- **Everything else → self-reported with data attached.** A chart and a raw log, not "passed".

Standing convention regardless: any result outside the first two categories is marked
**`SELF-REPORTED — no independent confirmation`**. Permanent practice, not a placeholder until
someone is assigned.

**Rationale.** ADR-003 says nobody grades their own homework, but the Verification Lead's scope
is `tests/` — golden fixtures, crash injection, fuzzing — and none of those tools touch a
thermocouple, an SPL meter or a latch counter. The failure mode with a self-designed hardware
test is almost always the **criterion**, not the measurement, which is why review lands before
the run rather than after it. The two witnessed tests are the only ones whose failure can hurt a
child; a second pair of eyes on an SPL meter is the entire mechanism.

**Cost to reverse.** Low to reverse, high to undo. Collapsing it saves a scheduling round and
forfeits the only independent check on the two safety criteria — and the damage would not be
visible until a unit is in a child's hands.

---

## ADR-108 — UHS-I bring-up is split at a testable gate

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 001 §5), raised by Hardware Lead (issue #8)

**Decision.** Hardware Lead owns the bring-up procedure, the test points, the fallback strategy,
and delivering a board that passes an entry gate. Software Lead owns the driver, delay-line
tuning, and the throughput number. The gate:

> On rev A, an **unmodified reference driver** — NXP's SDK USDHC example — completes a 1 GB read
> and a 1 GB write on **each** slot at **SDR50** with **zero CRC retries**.

Fails the gate → hardware, and it is the Hardware Lead's call whether that is layout, power
integrity, or a respin. Passes and throughput still misses → software. Both remain jointly
accountable for the copy-time criterion.

**Rationale.** UHS-I bring-up is the hardest electrical thing on the board and the item most
likely to consume a spin, and it sits exactly between two owners. Without a gate, "is it the
layout or the tuning?" has no answer and both parties can point at the other while the schedule
burns. SDR50 rather than SDR104 because SDR104 depends on delay-line tuning, which is software's
half — **a gate that requires the other party's work to pass is not a gate.** SDR50 is also
sufficient for the requirement: the 90-minute copy needs 63% of a 50 MB/s bus.

**Cost to reverse.** Trivial as text, but it must exist **before fabrication** — written into
`spec/hw/board-rev-a.md` §5 while the board can still be changed to make the gate reachable.
Agreed after the first failure it is no longer a gate, it is an argument.

---

## ADR-109 — Tape length resolves on measurement, not argument

**Date:** 2026-09-02 · **Decided by:** PM (Decisions 001 §1), raised by Hardware Lead (issue #5)

**Decision.** Six candidate microSD SKUs are characterised under fixed conditions — card filled
to ~80%, transfer at least as long as a real copy, **worst-case windowed** write reported rather
than average. Then:

- **≥ 2 SKUs sustain ≥ 35 MB/s worst-case** (10% over the 31.75 MB/s requirement) → **90 minutes
  stands.**
- **Otherwise → 60 minutes becomes the standard tape.** 635 MB at 21.2 MB/s sits inside the V30
  floor with ~40% margin, and drops the bus requirement from SDR104 to SDR50 — retiring the
  highest-risk electrical work on the board as a side effect.

BOM discipline: **exact SKUs with revision, not model families**, recorded in
`spec/hw/board-rev-a.md` with the measured numbers and the date measured.

**Rationale.** On a UHS-I host there is no purchasable specification that guarantees the copy
target: V30's floor is 30 MB/s, below the requirement, and V60/V90 are UHS-II ratings that do
not apply when a card falls back to UHS-I. So the requirement is met by characterised models,
and a rule fixed in advance stops the decision being relitigated once someone has a number they
like. The test conditions each defeat a specific way a card looks faster than it is — an empty
card writes to clean blocks, a short transfer measures the SLC cache, and an average hides the
stall that produces the dropout.

Recording the SKU **and revision** is the whole defence against a silent controller change
inside a part number, which is a real and common failure in SD cards and would otherwise break a
shipped requirement with no change on our side.

**Cost to reverse.** The rule itself is free to change before the cards arrive and expensive
after — its value is precisely that it was fixed before anyone saw a result. Tape length is a
superblock field (`nominal_length_s`, ADR-008), so **the answer does not block the format freeze
or any software**; it changes a format-time constant, not a format.
