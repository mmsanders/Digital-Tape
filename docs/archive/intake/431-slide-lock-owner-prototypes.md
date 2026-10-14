Filed at Michael's request ("write this all up in an issue on the repo and label it intake, then it will get filed when the time is right"). Michael ran this as an informal hands-on prototype series in a Claude Code chat, 12–14 Oct 2026, directly with Claude acting in the Hardware Lead's domain. **No `hardware-lead` issue authorised it, and nothing here is acceptance.** The classification and disposition below are only Hardware's suggestion; filing is PM's.

## 1. Michael's words (verbatim)

**The brief (12 Oct):**
> Give me a 3D printable button slide lock test we can use to start prototyping! [...] I'd like stop to pop everything, and the rest of the bar can just be a series of mock buttons with different sizes of latch overhang in a ladder to see what feels best. I'll use springs from pens for each button and the slide lock [...] I'd like each button to have some kind of rail system or slot or something to guide the button up and down. Make sure the catches are oriented the right way on the buttons, and the stop button has no catch at all.

**LADDER-02 results (spoken, transcribed):**
> I put the buttons in starting furthest away from the spring end on the slide latch. Stop, LPF, LPF. I was never able to get the L closest to the stop to latch. The other L that's closer to the spring side does latch, but it doesn't secure it very well. I think probably the P's are the right thickness for this, at least for now. The stop button is way too hard to depress. Maybe we could make the ramp more consistent instead of having like a steepish ramp and then a flat. Maybe we can just make it longer. It's way too hard to press as is. One of the buttons broke on the stem when I was playing with it, so that's worth noting. Maybe we need more infill, or maybe we need to think about that a little bit more. Also, there was an F key that was the very closest to the spring end of the slide lock, and that tab broke off on the slide lock as well. So probably we need to thicken up all of the slide lock tabs in general. I think P is probably about the right button. In terms of the drop test, the F stayed latched in almost every drop orientation, except for if you dropped it on the end that had the slide lock springs, and that popped every time. L and P basically popped if you ever dropped it in any orientation. But that doesn't really necessarily bother me. I think if you drop the player and the buttons pop out and it stops playing music, I think that's fine. I don't think they need to stay down while dropped necessarily. What else? I tried to very carefully remove the lid and it broke the pegs again. So that's not super ideal. I'm wondering if maybe those pegs are not the right tool for the job. Maybe we need something more like the lid insert just on both ends or in a few places. Oh, also, all of this is just brainstorming and taking notes. I don't think we need to do another round on this right now. One more thought is that the keycaps don't necessarily stay aligned very nicely. It makes it look a little tacky to me. They can be, you know, slightly askew. And I think on the real device, that would sort of not be great. So if we could find a way to keep those aligned better or more rigidly, maybe that means a slightly longer stem and a slightly thicker cap, or maybe it means a different shape for pressing the cap onto the stem, or maybe we need a different design there because the stem did break on one of the buttons anyway. Maybe it's too fragile. I'm not quite sure. Anyway, that's my results. Overall, I think happiest with the P button. The stop button is not going to work as designed. It needs to be easier to press. The lid broke on the tabs, but the new thing did seem to work. Oh, I also did have to tape the lid down anyway. So we'll have to workshop that, although this configuration isn't necessarily going to go into the real device anyway. We might have like more like two shells that press together, so that might not be an issue on the real device.

**Earlier remarks:**
> The stop button is fine, it's the slide lock tab that broke off!

> I liked P and not X. X was a no-go.

On the first print, the keys were inserted upside down. That was a card and assembly problem, not the geometry: the catch orientation is correct.

## 2. What was built and measured

All parts were printed on Michael's A1 Mini in Bambu PLA Matte (blue), 0.4 nozzle, 0.20 Standard with **4 wall loops and seam Aligned**, no supports.

**Mechanism.** Seven push-down keys sit over one slide bar that the bar springs hold against a rest stop.
- Each key carries a rigid tooth with its 45° insertion ramp **below** and a flat retention ledge **above**, so the WP-04 root-cause orientation is fixed by construction.
- Stop has a ramp and a vertical dwell face and no ledge. It shifts the bar 2.1 mm.
- Only the catch overhang h was swept; letters were blind until the ranking was done.

**FIT-01 (sizing coupon).**

| Fit | Result |
|---|---|
| Key slide | 0.15 mm/side (0.10 tight, 0.20 rattles; the 0.00 control refused) |
| Cap press fit | 0.05 holds, 0.10 falls out; the 0.00 control went in with force and broke rather than refusing |
| Springs (pen and mechanical-pencil) | Both 14 mm free, about 4 mm solid |
| Spring pegs | Pencil springs grip a Ø3.0 peg, pen springs Ø3.6 |
| Spring OD | Pen fits a Ø5.0 hole, pencil Ø4.5 |
| Lid pegs | In this matte filament, 0.10 falls out where white PLA Basic (A1MINI-01) still held |

**LADDER-01, the blind ladder.**

| h (mm) | Latched |
|---|---|
| 0.3 and 0.5 | 0/10 |
| 0.7 | 6/10 and 1/10 (twin control J/X) |
| 0.9 (L) | 10/10 |
| 1.2 (P) | 10/10 |
| 1.5 (F) | 10/10, "too firm, probably" |

- Ranking: **P > L > F**. "They felt very different."
- The kinematic model predicted that every key from 0.3 mm up would latch. **On this printer about 0.6–0.8 mm of nominal engagement is lost** to corner rounding, key tilt and bar flex.

**LADDER-02 (parts kit).** It had three changes:
- a lid insert into the spring bay with crush ribs (Michael's sketch);
- spring cups on the bar instead of horizontal pins, which printed jagged;
- a thicker Stop tab on the bar.

Results are in Michael's words above.

## 3. Hardware's reading, for whoever picks this up

1. **Catch depth: P (1.2 mm nominal) is the baseline.** L (0.9) depends on its slot on the second print. That points to bar bow or flex as well as print loss.
2. **Stop force is a mechanical-advantage problem.** A 45° ramp with PLA friction (μ about 0.3) needs about 1.9 times the bar-spring force at the finger. A long, even ramp at about 30° needs about 1.1 times, and it fits the 6.2 mm travel. Lighter bar springs help too. Michael's "longer, more consistent ramp" is the right shape: no vertical dwell.
3. **Every bar tab needs thickening, not just Stop's.** The bar prints on its side, so each tab's root is a single layer line. The long, rising rev-3 Stop tab is the pattern, or change the load path or print orientation.
4. **The stem break and the askew caps probably share a cause.** The cap engages only 4 mm of a Ø6 D-neck, so it rocks and levers the neck across its layers. Next: longer engagement, a non-round (rectangular or cross) section, and a stiffer cap. In the product, a one-piece key inserted from inside the shell would remove the joint. More infill is unlikely to help, since the neck is close to solid with 4 walls.
5. **Lid pegs (Ø3, printed upright) broke twice and are the wrong fastener for something that comes off.** The bay insert worked. In the product this becomes a shell-joint question.
6. **Drop:** Michael says popping on a drop is acceptable ("it stops playing music"). That reads on **guardrail 13** ("silently losing the basic playback controls"), so **PM should confirm it** when the latch is chosen. F's one failing direction, dropped on the spring end, is the bar's own inertia carrying it toward its springs.

## 4. Suggested classification and disposition (for PM to confirm)

- **Package:** WP-04 transport spike (Route A, the latch). It feeds WP-22 transport production design and WP-20 button matrix, and touches WP-25 (guardrail 13 drop behaviour).
- **Phase:** hardware is parked through Phase 2 (ADR-160). This was owner-run, informal prototyping and is not blocking.
- **Suggested disposition:** `RECORDED — PARKED`. **Resume condition:** Phase 3 opens or Michael requests WP-04 work. On resume, Hardware starts from §3 and the generator below. Michael: "I don't think we need to do another round on this right now."

## 5. Where the files are, and an open item

**Nothing from this work is committed to the repo.** Michael chose to have the files sent to him in chat. These items exist only in his downloaded `latch-rig.zip` and in the session's temporary scratch space, which will be reclaimed:
- the parametric CadQuery generator (`rig.py`, `kinematics.py`, `build.py`);
- the gate tests and their negative controls (`test_rig.py`);
- the FIT-01, LADDER-01 and LADDER-02 packets: STL and 3MF files, cards, manifests including the blind map, the analyses and Michael's results files.

The gates cover latch retention via motion simulation, five assembled clearance states, overhang and bridge support in print orientation, label-suppressed duplicates, A1 Mini bed fit, the spring stack and lid-insert grip. Each has a negative control that goes red, including the reversed-tooth WP-04 failure.

**Open:** if these should be durable, ask Hardware to commit them under `hardware/` on a branch. That is Michael's call, and probably part of the resume.
