# Hardware Lead — review packets

Newest round at the top. Do not edit a previous round; supersede it.

---

## Round 2 — 2 Sep 2026, on PM Decisions 001

Eleven items. Six are answerable yes/no; two are notifications that need nothing.
**Nothing here is blocking** — every item names what ships if nobody answers.

### 1. WP-18's acceptance criteria assume the bench can prove the copy time. It cannot.

**What it is.** The Teensy 4.1 has one 4-bit SDIO port. A second card hangs off SPI at roughly
10–20 MB/s, so a bench copy of a 90-minute cartridge takes 60–95 s however good the cards are.
WP-18 ("dual card, hot-swap detect, copy with LED row") currently reads as though the bench
demonstrates the 30-second criterion.

**Why it matters.** A criterion a platform physically cannot meet does not get missed — it gets
quietly relaxed, and then nobody is sure what the bench was supposed to prove.

**Recommendation.** Reword WP-18 to own function (hot-swap detect, LED row, copy *correctness*)
and explicitly not throughput. Card characterisation moves to a PC with a rated reader
(ADR-103), which is available the day the cards arrive rather than after WP-17.

**Default:** I proceed as if this is agreed, and mark WP-18's throughput line as out of scope.

### 2. Seven hardware limits are proposed and need transcribing into `spec/acceptance.md`

**What it is.** PM Decisions 001 §3 puts limits in `spec/acceptance.md` (PM-owned, frozen) and
measurements in `spec/hw/`. `spec/hw/thermal-budget.md` §8 carries the proposed set: JEITA
window and taper band, solenoid on-time **and duty** ceilings, touch temperature, the 85 dB
criterion made measurable, and the deep-discharge cutoff. **I have not written them into
`spec/acceptance.md`** — that file is frozen and not mine.

**Why it matters.** T-4 (duty ≤ 0.5% over 10 s) is the criterion the charter was missing; see
item 3. And T-6 turns "85 dB against specified headphones" into something a person with a meter
can check, which PM Decisions 001 §4 makes a witnessed measurement.

**Recommendation.** Transcribe as written, or tell me which numbers you want different.

**Default:** the budget is written against them regardless, so the board gets built to them
whether or not they are recorded upstream. That is the wrong way round and is why this is here.

### 3. The solenoid one-shot, as specified, does not close the hole it was for

**Notification, not a question.** Logged as ADR-104's neighbour, ADR-101. A one-shot bounds
pulse *width*; a firmware retrigger loop at 100 Hz still delivers essentially full coil power
through a correctly functioning one-shot. Adding an RC lockout and a PPTC average-current
backstop costs about fifteen cents and closes it physically.

Flagged because it modifies a charter requirement stated as "not optional". Taking you up on
§8: **I would like independent review on this circuit specifically** — its whole job is to be
correct when firmware is wrong, which is exactly the thing a second reader catches.

### 4. A charge refusal is correct, silent, and indistinguishable from a broken toy

**What it is.** `thermal-budget.md` §4: at 35 °C ambient, playing while charging sits ~0.2 K
under the 45 °C JEITA ceiling. The cutoff fires, correctly, and charging stops. There is no
screen. ADR-102 (suspend charging during a copy) and JEITA tapering remove most of this, but a
hot room still reaches it.

**Why it matters.** Guardrail 03 means the only available explanation is physical.

**Recommendation.** A distinct slow pulse on the existing charge indicator for "too warm to
charge right now". It is an *indicator*, not a control, so I read it as not tripping escalation
trigger #3 — but that is your call, and what it looks like is Michael's.

**Default:** no indicator. The device silently declines to charge and nobody knows why.

### 5. Low-voltage latch-off versus the instant-on guardrail

**What it is.** No hard power-off plus a LiPo plus six months in a drawer ends below 2.5 V. The
PCM cuts off — safe, but the cell is degraded. `thermal-budget.md` §5 puts a hardware load
switch below ~3.2 V, released on charger insert, plus the charger's ship mode for storage
between build and gift.

**Why it matters.** It *looks* like escalation trigger #5. I do not think it is: the device
still wakes instantly from any state a child will put it in, and the latch only engages after
neglect that has already ended battery life.

**Recommendation.** Confirm that reading.

**Default:** I build it. It is a safety and lifespan feature and I would rather be told to
remove it than have to add it in rev B.

### 6. A cleaner statement of the Q-002 risk, from the electrical side

**Notification.** Published write benchmarks put good UHS-I cards at 80–100 MB/s sustained
against a 31.75 MB/s requirement, so 90 minutes looks likely to survive — the measurement in
WP-05 will say. More useful for Michael's actual decision:

| | 90 min (953 MB) | 60 min (635 MB) |
|---|---|---|
| SDR104 | comfortable | comfortable |
| SDR50 | 63% bus utilisation — feasible | comfortable |
| High-speed 4-bit | **impossible** (43 s) | 25.4 s — passes |

**A 60-minute cartridge survives the total loss of UHS-I.** A 90-minute one requires at least
SDR50 to work. That is a sharper framing than "90 minutes needs the hard circuit", and it may be
worth Michael having before he answers.

### 7. The egress gap is unchanged, and it now has a name attached to it

**What it is.** No vendor, distributor or fab domain is reachable (round 1, H-02). The concrete
consequence has arrived: **a distributor aggregator lists the SGTL5000 as `Obsolete`** while
NXP's longevity programme is quoted as assuring supply. I cannot resolve it, because resolving
it means reading `nxp.com` and a stock page. It is the codec in the one-board architecture *and*
on the Teensy Audio Shield in order 1b, so both builds inherit the question.

**Recommendation.** Someone with distributor access spends five minutes on this before WP-26.
It is the cheapest possible time to discover a codec change.

**Default:** every part number in `spec/hw/` and `docs/PACKAGES/WP-05.md` carries `UNVERIFIED`,
and Michael finds out at checkout — which is the wrong place.

### 8. ERC still cannot be automated

**What it is.** Round 1, H-03, unchanged. The only KiCad this environment can install is
7.0.11, whose `kicad-cli` has no `sch erc`; that lands in KiCad 8. The PPA is 403 through the
proxy.

**What I did about it.** `make -C hardware erc` now **fails loudly** with the reason rather than
skipping quietly, so the day a board exists the gap is visible instead of passing green. DRC is
fine on 7.0.11 and is wired the same way.

**Recommendation.** Allowlist the KiCad repo, or bless a setup script that installs KiCad 8+.

**Default:** ERC becomes a claim rather than an artefact at WP-26, and the loud failure is the
best I can do about it from here.

### 9. Captive cards added a firmware path that is in no work package

**What it is.** ADR-105 (issue #6, captive) means `tapectl` and the GUI reach the card *through
the player* over USB-C. That requires a firmware device path exposing a mounted cartridge to a
host. **It is not in WP-01…WP-37.** The board half is settled — USB-C carries data, recorded in
`spec/hw/board-rev-a.md` §7 — but the firmware and `host/` halves have no owner and no package.

**Why it matters.** This is the cost the decision added, and I flagged it as a cost when I
raised the issue. It is cheap to scope now and expensive to discover in Phase 4 with the
cartridge shell already drawn around the assumption. Whether it is USB mass storage over the raw
partition or something narrower is the Software Lead's call, not mine.

**Recommendation.** Add a package for it, or fold it into WP-14/WP-15 explicitly.

**Default:** the board carries USB-C data regardless, so hardware proceeds — and the gap surfaces
when someone tries to load a cartridge.

### 10. Two leads picked the same ADR numbers, and would again

**What it is.** My first four decisions logged as `ADR-010`–`013`. So did four of the Software
Lead's, on an unmerged branch. Nobody would have noticed until the merge, in an append-only file
whose entries are referenced by number from a dozen places.

**What I did.** Renumbered mine to **`ADR-101`–`104`** and reserved **`ADR-1xx` for the Hardware
Lead**, with the reasoning in `DECISIONS.md`. Picking `018`+ instead would have fixed this
instance and left the next collision in place.

**Recommendation.** Confirm the range, and give the Verification Lead one too. This is the
reversible path under Charter §05 — one `sed` collapses it if you would rather not.

### 11. The spending total is in `STATUS-HARDWARE.md`, not `STATUS.md`

**Minor, flagging rather than assuming.** Decisions 001 §6 says to keep the running total in
`STATUS.md`. That file is the Software Lead's and I do not write to it, so the total is in
`docs/STATUS-HARDWARE.md` under **Spending**. If you want one number in one place across all
streams, say so and I will ask the Software Lead to mirror it — but two leads writing the same
table is how it goes stale.

---

## Round 1 — 31 Aug 2026

Originally filed as `docs/STATUS-HARDWARE.md` before this directory existed; merged in PR #10.
Moved here verbatim on 2 Sep so the status file could go back to being a status file. All four
`pm-decision` issues it raised (#5–#8) are answered in PM Decisions 001.

## Blocked

Three things, in order of how expensive they are to leave unresolved.

### H-02 — There is no network egress to any vendor, distributor or fab domain

This is the blocker with no workaround available to me. Verified, not assumed:

```
octopart.com:443    403 at CONNECT (policy denial)
www.digikey.com:443 403 at CONNECT
www.nxp.com:443     403 at CONNECT
jlcpcb.com:443      403 at CONNECT
```

`WebFetch` on `nxp.com` returns `EGRESS_BLOCKED`. General web *search* works; fetching the
manufacturer's own page, the datasheet PDF, the errata sheet, the distributor stock page or the
assembler's parts library does not.

`hardware/README.md` lists "web access for datasheets, availability and pricing" as a
prerequisite for standing this role up, and the charter asks for four things that all live
behind it: check every part against the assembler's library before layout, run the errata
checklist per major chip, draft a parts order Michael can check out in thirty minutes, and
maintain a BOM with lead times.

**Concrete example of the cost, found within ten minutes of looking.** A web search reports
the **SGTL5000 listed as `Obsolete` on Octopart**, while NXP's own longevity programme is
quoted as assuring supply. Those two claims cannot both drive a BOM. The SGTL5000 is the codec
in the charter's one-board architecture and it is in the Teensy audio shield in WP-05. I cannot
resolve this, because resolving it means reading `nxp.com/part/SGTL5000XNAA3` and a distributor
stock page, and both are blocked. **If it is genuinely obsolete, that is a schematic-level
change discovered before layout rather than at order time, which is exactly the failure the
charter's "check parts before layout" rule exists to prevent.**

**Ask:** allowlist `nxp.com`, `digikey.com`, `mouser.com`, `octopart.com`, `jlcpcb.com`,
`ti.com`, `analog.com`, `microchip.com`, `datasheets.*` and the SD Association. Failing that,
tell me the sourcing half of the role belongs to a human and I will scope my deliverables to
"specify the part and its requirements, someone else confirms it is buyable."

**What I will do meanwhile:** design to *generic requirements* with named candidate parts and
an explicit `UNVERIFIED — no distributor access` marker on every part number, so nothing
silently reaches an order. Slow, and it means the BOM is not trustworthy until someone with
egress walks it.

### H-03 — No hardware toolchain is installed, and the available KiCad is likely too old

Verified in this container:

```
kicad, kicad-cli, openscad, freecad, prusa-slicer, cura   all MISSING
python3 modules cadquery, build123d, OCP, numpy, trimesh  all MISSING
```

Half of this I can fix and intend to: **PyPI is reachable** (`pip download cadquery` succeeded),
and `archive.ubuntu.com` is reachable, so CadQuery and KiCad can be installed. The problem is
which KiCad:

```
kicad | 7.0.11+dfsg-1build4 | noble/universe    (the only version available)
```

The charter's requirement is "run ERC yourself, run DRC yourself, a clean report is part of the
deliverable." `kicad-cli pcb drc` exists in 7.0. **`kicad-cli sch erc` does not — it lands in
KiCad 8.** So on the distro package, DRC is automatable and ERC is not, and the ERC half of the
deliverable quietly becomes a claim instead of an artefact. The KiCad PPA is 403 through the
proxy, so the 8.x/9.x upgrade path is not currently open either.

**Ask:** either allowlist the KiCad PPA / official repo, or bless a session-start script that
installs KiCad 8+ and CadQuery from a reachable source. This is a one-line environment fix that
otherwise costs a permanent hole in the verification story.

**What I will do meanwhile:** stand up the CadQuery half of `hardware/` (fully unblocked) and
build the KiCad skeleton with the DRC gate wired and the ERC gate wired but marked
`SKIP: kicad-cli sch erc unavailable on KiCad 7`, so it fails loudly the day the toolchain
improves rather than passing silently.

### H-04 — I cannot produce a "sliced-ready plate" without knowing the printer

The packet protocol is the right protocol and I want to run it. But the charter's first bullet —
*"one plate file, sliced-ready; he should not have to arrange anything, choose an orientation, or
decide on supports"* — is not a thing that exists independent of a machine. Slicing binds the
output to a specific printer, nozzle, material profile and slicer. I know none of them, and
"the public library's" is not a machine model.

There is a second-order version of this that matters more than the file format. Library
makerspaces commonly run PLA only, cap print time per session (often 2–4 h), and mediate the
queue through staff with a drop-off/pick-up gap of days. If any of those hold, the charter's
central scheduling assumption — **one print cycle per week, therefore one *answer* per week** —
is optimistic, and the whole packet design should be tuned to a different number.

Queued for Michael as **Q-006** with a stated default so it does not block. See also H-07 on
what PLA does and does not tell us about final feel.

---

## Concerns, in the order they will cost us

Agreement first, because it is short and it matters: **the toolchain decision is right, the
packet protocol is right, "he is the instrument" is right, "rev A is an experiment" is right,
and the hardware one-shot on the solenoid gate is right.** I would not argue any of them.
Everything below is either a gap in those, or a place where a number in the charter does not
survive being checked.

### H-01 — The 30-second copy may be limited by microSD sustained *write*, not by the UHS-I bus

**This is the concern I would want read first.** The charter treats the copy target as an
electrical problem — 1.8 V switching, delay-line tuning, controlled impedance — and hedges rev A
accordingly. That hedging is good and I will build it. But it may be hedging the wrong risk.

The arithmetic:

| | |
|---|---|
| 90-minute cartridge (ADR-007) | 952,560,000 B |
| Copy budget (guardrail 10) | 30 s |
| **Required sustained rate** | **31.75 MB/s — simultaneously read on one slot and *written* on the other** |

The write side is the one nobody has costed. Sequential write on a microSD is much slower than
read and is punctuated by garbage-collection stalls, so worst-case sustained write is the number
that governs, not average.

The only sustained-write *guarantee* the SD Association sells is the Video Speed Class:
**V30 = 30 MB/s minimum sustained write.** That is *below* the 31.75 MB/s the requirement needs,
before any protocol or filesystem overhead. And the classes above it do not rescue us on this
board: **V60 and V90 microSD cards exist, but they are UHS-II parts** — they earn those ratings
over UHS-II's second contact row. On a UHS-I host they fall back to UHS-I and the V-rating no
longer applies.

So: **on a UHS-I host there is no purchasable specification that guarantees the 30-second copy.**
Good premium UHS-I cards do sustain well above 31.75 MB/s in practice — the target is very
likely reachable — but it is reachable *by characterised card models*, not by a spec line. Three
consequences the plan does not currently carry:

1. **The BOM must name exact card SKUs**, and SD manufacturers silently revise controllers
   within a SKU. A requirement met by an unspecified "A2 V30 card" is a requirement that can
   break in the field with no code change.
2. **The fallback ladder may point the wrong way.** `SDR104 → SDR50 → high-speed 4-bit`
   retreats on the *bus*. If the limit is the card's write path, every rung fails and the real
   retreat is a shorter tape.
3. **This changes the framing of Q-002 in `FOR-MICHAEL.md`**, which currently asks Michael to
   trade 90 minutes against *UHS-I risk*. A 60-minute tape needs 21.2 MB/s, comfortably inside
   the V30 floor with room for stalls. The honest question is not "is 90 minutes worth the hard
   circuit" but "is 90 minutes worth a requirement that no card specification guarantees."

**Recommendation:** WP-05 buys 4–6 candidate card models specifically to characterise, and the
bench build measures worst-case sustained write **before the format freeze**, so the number
reaches Michael before he answers Q-002 rather than after. This costs about $80 and two days and
it de-risks the highest-consequence number in the project. Filed as an issue.

Sources: [SD speed classes](https://www.hugdiy.com/blog/a-guide-to-sd-card-speed-class-u1-vs-u3/) ·
[V-class minimums](https://www.kingston.com/en/blog/personal-storage/memory-card-speed-classes) ·
[UHS-II microSD V90 example](https://www.amazon.com/Delkin-Devices-microSDXC-UHS-II-Memory/dp/B07V49PTXN)

### H-05 — The reversible cartridge is a harder part than the enclosure, and it is scheduled like a shell

The charter already calls it "a signal-integrity part, not just a shell", which is right. Going
further, because I think it is the sleeper risk of the mechanical track:

- **The unused contacts are stubs.** "Mirrored edge contacts at both ends" means every data net
  terminates in a second, unused pad set at the far end of the carrier. At SDR104 the clock is
  208 MHz and a card-length unterminated stub on `CLK` and `DAT[0:3]` is a reflector, not a
  cosmetic detail. Two readings of the requirement have very different costs: contacts mirrored
  **end-to-end** (insert either end first) gives a stub the length of the carrier, which I do not
  think survives SDR104; contacts mirrored **top-to-bottom on the same edge** (insert either face
  up, the USB-C solution) gives a stub the length of a via, which does. If the intent is the
  second, this concern mostly evaporates. **Which is it?**
- **ESD protection and signal integrity fight each other here.** Exposed contacts a child touches
  need TVS diodes; TVS capacitance loads a 208 MHz bus. This specific tension is a classic way to
  lose a board spin, and it wants deciding on paper in WP-34/WP-26, not on the bench.
- **Insertion life and plating.** A connector a seven-year-old operates thousands of times wants
  hard gold on the carrier edge. Many low-cost fabs surcharge or refuse it, and ENIG will wear
  through. This is a BOM and vendor question I cannot currently answer (H-02).

**Recommendation:** the cartridge carrier gets its *own* early spike alongside WP-04 rather than
waiting for WP-24 in Phase 4 — a two-layer test carrier, a scope, and an answer about whether
UHS-I survives the connector, before the board that assumes it does gets laid out.

### H-06 — How does a cartridge actually get loaded? It decides the shell.

`host/` is "loading cartridges" via `tapectl` and a GUI over the engine's block-device pointers,
which implies a card reader on a laptop, which implies the microSD comes *out* of the cartridge.
Meanwhile the enclosure guardrails are "sealed", "serviceable screws rather than glue", and
"dropped from waist height by someone who is not sorry", and the tiebreaker is what a
seven-year-old understands without being told.

Those pull in opposite directions and I cannot draw the cartridge shell until it is settled:

- **Captive card** (soldered or under a screwed cover): survives drops, no ESD path, no child
  removing it, and the cartridge is genuinely one object. But then loading must happen through
  the device over USB-C, which is a firmware and `host/` requirement nobody has scoped.
- **Removable card** (push-push socket, accessible): `tapectl` works today with a $9 reader. But
  a push-push socket inside a dropped cartridge ejects, and a card a child can remove is a
  cartridge a child can lose the music out of.

**Recommendation:** captive, with loading over USB-C. It is the answer the tiebreaker gives, and
"the tape is one object" is the whole conceit. It costs a USB mass-storage or custom-protocol
path in firmware, which should be scoped now rather than discovered in Phase 4. Filed as an issue.

### H-07 — 200 cycles is a spike gate, not a life test — and PLA feel is not production feel

Two separate problems with the WP-04 acceptance criterion. I am not asking to weaken it; I am
asking for a second one behind it.

**200 cycles proves the mechanism is not dead on arrival.** It does not bound life. Five buttons,
a child, several years: the real number is tens of thousands of cycles per button. 200 is about
fifteen minutes of Michael's thumb, which is exactly why it is the right *Phase 0* gate — but if
it is the only number, we will discover the latch bar's real life expectancy in Phase 6, in a
house, in a toy someone loves.

**Recommendation:** keep 200 as the WP-04 gate. Add to WP-22 an automated cycling rig — a
solenoid, a MOSFET and a counter, all of which are already in the WP-05 bench order — printed in
the same packet as the mechanism it tests. It runs unattended overnight on Michael's desk and
turns "50,000 cycles" from an aspiration into a Tuesday. Target and material set once we have a
first ranking.

**And the deeper one: he will be ranking the click of a PLA part.** Library PLA is a prototyping
material. The production latch bar will be PETG, ABS, nylon or an insert, because PLA creeps
under sustained spring preload and will relax the very geometry being tuned. Different modulus,
different friction, different snap. **A ranking done in PLA may not transfer**, and we would find
that out after committing the enclosure.

**Recommendation:** print the top two or three variants in the final material before WP-22 locks
the geometry, and treat the PLA ranking as a *bracket-finder* rather than a decision. This is the
one place where the charter's "he is the instrument" protocol has a systematic error in it, and
it is cheap to correct by adding one confirmation trip.

### H-08 — Agreed on the solenoid one-shot, and it must bound duty cycle, not just pulse width

"A hardware one-shot between the MCU and the gate makes that physically impossible for twenty
cents. This is not optional and it is not a firmware responsibility." Completely agreed. This is
the best twenty cents in the design.

One strengthening, because the stated part does not close the whole hole. A one-shot bounds
**pulse width**. It does not bound **duty cycle**. Firmware stuck in a retrigger loop at 100 Hz
still delivers a 30 ms pulse every 10 ms, the coil sees most of its 4 W, and the one-shot fires
happily the whole time. The failure mode the charter describes — a stuck firmware state cooking a
coil designed for 30 ms pulses — is fully reachable through a correctly functioning one-shot.

**Design intent for WP-34/WP-26:** non-retriggerable one-shot, *plus* an RC-enforced minimum
off-time that ignores retriggers inside the recovery window, *plus* an average-current or thermal
backstop on the coil rail. Roughly another fifteen cents. It is my call to make under Charter §05
and I am logging it here rather than escalating, but it changes a stated charter requirement so
the PM should see it.

### H-09 — A sealed case, charging while copying, and a 45 °C cutoff — with no screen to explain it

The bulk case is fine and I agree with the estimate's shape: ~2.2 W in a 110 × 75 × 28 mm
enclosure is roughly 8 K over ambient. Two things that number hides, both of which I own:

**A sealed plastic box couples badly to its own air.** The 8 K figure is case-to-ambient. The
weak link is board-to-air *inside* the sealed volume, where there is no convection to speak of.
Junction temperatures will run meaningfully above what the bulk number suggests, and the budget
must model the internal step rather than the external one. That is a real analysis task, not a
correction to the charter — but it means "the thermal budget permits no vents" is a conclusion
the budget has not actually reached yet, and I would rather reach it than inherit it.

**The JEITA window is the user-visible risk.** WP-37 tests exactly the worst case — an hour of
simultaneous charge and copy. In a 30 °C room, plus a bulk rise, plus a local hot spot near the
charger, an NTC on a cell mounted anywhere near that hot spot can approach the 45 °C cutoff
*during normal use*. The cutoff then fires correctly and the device stops charging.

**And there is no screen to say so.** A child plugs it in overnight, it does not charge, and
nothing anywhere explains why. That is a guardrail-11-shaped problem in a guardrail-03 device: a
correct safety behaviour that is illegible.

**Recommendation:** (a) place the cell and its NTC thermally away from the charger and the
RT1062, with the compartment doing double duty as a thermal break; (b) add "charge refused,
too warm" to whatever the LED language turns out to be — an indicator, not a control, so it does
not trip escalation trigger #3, but the PM should confirm that reading; (c) make WP-37's
hot-soak an ambient sweep to find the room temperature at which normal use trips the cutoff, and
put that number in the budget. If it is 28 °C we have a product problem; if it is 40 °C we do not.

### H-10 — No off switch, a LiPo, and a drawer

"No hard power-off; the MCU sleeps and wakes on a button press" is the right product decision and
I am not arguing it. But a LiPo with no disconnect, in a toy, in a drawer, for six months, plus
sleep current and self-discharge, ends below 2.5 V. The protection PCM cuts off — that is the
safe outcome, not the good one: the cell is then degraded, and a deeply-discharged LiPo is a cell
you do not want charged casually.

**Recommendation:** a hardware low-voltage latch-off (load switch that disconnects the system
below ~3.2 V, released on a charger insert) plus the charger IC's ship mode for storage between
build and gift. Neither is perceptible in normal use — the device still wakes instantly on a
button press from any state a child will ever put it in — so I read this as compatible with the
instant-on guardrail rather than a trade against it. Flagging it because it *looks* like
escalation trigger #5 and I would rather the PM confirm that reading than have me assume it.

### H-11 — `spec/` is frozen and PM-owned, but I am told to own two living documents inside it

A genuine contradiction between the two charters, not a nitpick:

- `spec/README.md`: *"Owner: Program Manager. Frozen at the Phase 0 gate. Any change to a file in
  this directory is escalation trigger #1. No exceptions."*
- Hardware Charter §06: I own `spec/thermal-budget.md`, and *"in Phase 5 the estimates are
  replaced with measurements."*
- Hardware Charter §07: I write `spec/board-rev-a.md`, and *"when the board changes, the document
  changes first."*

Both of my documents are specified to change repeatedly, by me, after the freeze. Under the
current rule every thermocouple reading and every pin move is a PM escalation, which will either
grind or — much more likely — be quietly ignored, which is worse. **This is exactly the "spec
that drifts to describe whatever got built" failure the Software Charter warns about, arriving
through the front door.**

**Recommendation:** `spec/` holds the frozen *interface contracts* (`tapefs-v1.md`,
`engine-api.md`, `acceptance.md`). `thermal-budget.md` and `board-rev-a.md` are named
Hardware-Lead-owned living documents, explicitly exempt from the freeze, with one obligation in
exchange: **any change to a pin, a rail or a timing constraint in `board-rev-a.md` is announced
explicitly to the Software Lead in the same commit**, because a silent pin swap between revisions
is how a week of bring-up gets lost to a problem that is not in the code. That obligation is the
thing the freeze was protecting; the freeze itself is the wrong instrument for it. Filed as an issue.

### H-12 — Nobody grades their own homework, but hardware has no grader

Charter §02 gives the Verification Lead "independent acceptance sign-off on every work package"
and scopes that role to `tests/` — golden fixtures, crash injection, fuzzing. None of those tools
touch a thermocouple, an SPL meter, or a 200-cycle latch count. So for WP-04, WP-25, WP-30 and
WP-37, the person proposing the criterion, running the test and reporting the result is me.

That is precisely the arrangement ADR-003 exists to prevent, and the packages it applies to
include the two safety ones (WP-37 thermal, and the 85 dB cap, which the charter is explicit is a
*system* property verified with a meter and a coupler, not a firmware claim). "No unit reaches a
child before this passes" needs someone other than me to say it passed.

**Second seam, same question.** WP-28 is "firmware port and UHS-I bring-up", owned by Stream 5 —
but UHS-I bring-up is the hardest *electrical* thing on my board, and it is the item most likely
to consume a spin. When SDR104 does not come up, the question "is it the layout or the delay-line
tuning" has no owner. **Recommendation:** I own the hardware-side bring-up procedure, the test
points and the ordered fallback, written into `board-rev-a.md`; firmware owns the tuning; and the
two of us are jointly on the hook for the criterion rather than each pointing at the other.
Filed as an issue covering both seams.

---

## On the packet protocol — agreed, with three refinements

The protocol is the best idea in the charter and I want to run it exactly as written. Three
things I would add, all of them cheap, all of them about not wasting a trip:

**1. Label variants blind.** If variant 6 visibly has the deepest hook, Michael will rank partly
by expectation. Print letters in a randomised order, keep the mapping in the repo and off the
part. Costs nothing, and it is the difference between a preference and a measurement.

**2. Put "they all felt the same" on the card as a box he can tick.** The charter is right that a
too-narrow sweep burns a week — but only if we hear about it. Without an explicit null option he
will rank three anyway, out of helpfulness, and we will spend the next trip refining noise. The
null result is the most informative outcome a bracket sweep has.

**3. Control for bed position.** Six variants across one plate vary by position — first-layer
squish, cooling, draft. On a mechanism where the swept parameter is a 0.2 mm change in hook
depth, that variance can be the same size as the signal. Print the middle variant *twice*, at
opposite corners, as a control. If the two controls do not rank together, the plate is telling us
the print is noisier than the parameter and the sweep needs coarser steps.

---

## Smaller notes, recorded rather than escalated

**Scope reconciliation.** The charter's scope line reads WP-04, 22–27, 29, 30, 34, 37, but
"Start here" ask #04 is **WP-05, parts order #1**, which is not in that list. Separately,
`docs/PACKAGES/README.md` marks WP-05, WP-22 and WP-25 as owner *You* (Michael) and WP-23,
WP-24 as *Either*, while the charter writes all of them as mine to design. I am reading this as:
**I design and prepare, Michael prints, orders and abuses.** I have taken WP-05 as mine to
draft. If that is wrong, correcting it costs one line.

**`spec/` corrections deliberately not made.** `spec/README.md` and `spec/thermal-budget.md`
both still read "no Hardware Lead assigned". Fixing them is escalation trigger #1, so I left
them. Flagging so it reads as discipline rather than an oversight.

**Hardware CI gates.** ADR-005 put gate scripts in `tools/ci/` and noted the cost to reverse
rises once hardware gates land beside them. I intend to follow that layout. One request: a
*separate* workflow for hardware, one that skips cleanly and stays green while `hardware/` is
empty, rather than joining the deliberately-red software pipeline. The Software Lead already
noted that a permanently red pipeline stops being read; a DRC violation arriving against a red
background is that risk realised. Not my ADR to amend, so: flagged, not decided.
