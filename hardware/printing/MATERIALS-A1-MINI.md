# Filament recommendation for the A1 Mini — what to buy, and what not to

**Owner:** Hardware Lead · **Status:** advice only · **Round:** P1-R23-HW
**Date:** 20 September 2026 · **Answers:** issue #119 Part A

**Nothing here is a purchase authorization.** Michael owns the wallet; this is a
recommendation he can act on, ignore, or hand to someone who knows filament better
than I do. No order has been placed and no cart exists.

---

## 0. Read this before the table: what I could and could not check

Every manufacturer and vendor host is **refused by this environment's egress
gateway**. `wiki.bambulab.com`, `bambulab.com`, `store.bambulab.com`, Polymaker,
Prusa, MatterHackers, NinjaTek, Overture and SainSmart all answer 403 at the
CONNECT, by direct fetch and by the harness fetch tool. The **search index is
reachable**; the pages behind it are not.

So I have not read Bambu's official compatibility page, and I have not read a
single datasheet. That is a real limit on this document and I am not going to
paper over it. Every claim below carries a tier:

| Tier | Means |
|---|---|
| **[REPO]** | Verified in this repository. I can point at the file and line. |
| **[INDEX]** | A search-index summary **attributed to** an official or manufacturer page **I could not open**. Treat as a lead to verify, not as a fact. |
| **[INFER]** | My engineering inference from the above. Mine to be wrong about. |

**No number in this document is a measurement**, and where the deciding fact is
one I could not read, the recommendation is *"do not buy until someone opens the
page"* rather than a guess. The one thing I will not do on a children's product is
invent a material property.

`spec/hw/cartridge-shell.md` SH-2 already records this as an open item — *"every
material property is an estimate because no vendor egress here reaches a filament
datasheet"* **[REPO]**. This round does not close it. It narrows what still needs
opening to about four pages.

---

## 1. The shopping list, if you only read one section

> **CORRECTION, 25 September 2026.** The table below recommended buying a spool of
> PETG. **Michael already owns PETG HF, and PLA Matte, and both nozzles** — he said
> so in the 23 September notes and I had not carried it into this document. The
> recommendation is therefore **buy nothing at all**: every material this project
> currently has a justified use for is already on his shelf. The PETG *reasoning*
> below still stands and is why that spool is the one to reach for; only the
> purchase was wrong. TPU is unchanged — still no part to print in it.

| Priority | Buy | For | Spools |
|---|---|---|---|
| **1 — buy now** | **Nothing.** | — | 0 |
| **2 — already owned, no purchase** | **Bambu PETG HF** | The cartridge shell pair that `S-2` needs, and the dashboard case in `SH-4` | 0 |
| **3 — buy only if WP-25 names a compliant part** | One spool of **TPU 95A**, 1.75 mm | A bumper that does not exist in any current drawing | 1 |
| **Do not buy** | ABS, ASA, nylon/PA, PC, and every CF/GF-filled grade | — | 0 |

**Total: nothing.** That is the whole recommendation. The rest of this document is
why, and what would change it.

### Why "buy nothing now"

Michael has one spool of white Bambu PLA Basic and a printer that is mid-test.
Every print the project currently has a justified need for — the held clasp sweep,
the coupon plate in this same round — runs in **that spool**, on that machine,
with no purchase **[REPO: `hardware/packets/a1mini-01/manifest.json`, held PR #92]**.
Buying a second material before the first one has produced a single measured part
would be buying ahead of a question nobody has asked yet.

---

## 2. PLA, and the variants

### Bambu PLA Basic (owned) — sufficient for everything currently justified

**Parts and tests it serves:** the WP-04 latch sweep and the WP-24 clasp sweep on
the held plate; the A1MINI-01 coupon plate in this round; every future geometry,
fit and blind-ranking print.

**Why it is sufficient.** The clasp was **deliberately specified to be
material-indifferent**. ADR-119 puts the closed cartridge at **0.000 % strain** —
the groove is cut deeper than the bead stands proud, so a closed cartridge has no
contact at the bead at all, and there is nothing for any polymer to creep against
**[REPO: `docs/DECISIONS.md` ADR-119]**. Every number in `spec/hw/cartridge-shell.md`
is quoted against PLA **[REPO]**. The material question was engineered out of the
clasp on purpose, and it has stayed out.

**Recommendation: buy no more PLA yet.** Not because one spool is plenty in the
abstract, but because we do not yet know how much of it a real article consumes,
and a second white spool is the easiest thing in the world to buy later.

### PLA variants (PLA Tough / PLA+ / PLA-CF) — recommended against, for now

**PLA-CF and any filled grade needs a hardened steel nozzle**: filaments containing
hard particles (CF, GF) require replacing the nozzle to prevent excessive wear
**[INDEX: attributed to the Bambu wiki]**. That is a consumable purchase, a machine
modification, and a new failure mode, bought to solve a stiffness problem **no
current part has** **[INFER]**.

**PLA Tough / PLA+ are a real possibility I am deliberately not taking yet.** The
honest position: I have not read a datasheet for any of them, so I cannot tell you
what you would be buying over Basic. Ask again when a part fails in Basic.

---

## 3. PETG — the one material I do expect us to need

**The part and the test it serves.** `spec/hw/cartridge-shell.md` **S-2**: *90 days
closed at 23 °C and at 45 °C, then S-1's retention force within 20 %* — recorded as
*"long lead — starts when the first PETG pair exists"* **[REPO: `docs/PACKAGES/WP-24.md`]**.
S-2 is a named, already-accepted criterion that **cannot start until a PETG pair is
printed**. That is the strongest buy case in the project, and it is already written
down; I am not inventing a need.

The second driver is **SH-4**: *a PETG cartridge left on a car dashboard may
deform* **[REPO]**. Note the direction — SH-4 is a concern about PETG, and the
reason it is about PETG rather than PLA is that PETG is the material we expect a
real cartridge to be made of.

**Why PLA Basic is not sufficient here.** Not for stiffness or strength — for
**temperature**. PLA's glass transition is widely given as 55–60 °C against PETG's
80–85 °C, with PLA deforming under load around 50–55 °C **[INDEX]**. A car interior
reaching ~70 °C is the case SH-4 is about **[INDEX]**. If those figures are even
roughly right, a PLA cartridge on a dashboard is a deformation risk and a PETG one
is a margin question — which is exactly the difference S-2's 45 °C arm is written
to detect. **I have not read a datasheet for either number.** They are consistent
across several secondary sources, which is evidence of consensus, not of accuracy.

**Preferred product: Bambu PETG HF, 1.75 mm.** The reasoning is deliberately boring:
it is the grade with a **dedicated profile in the printer's own slicer**, reported as
230 °C first layer / 240 °C after, 70 °C bed, 18 mm³/s **[INDEX]**. On a machine
whose stock profile we are relying on for repeatability, the first-party grade is
the one where "use the stock profile and change nothing" is an instruction that
actually means something **[INFER]**.

**Colour constraint: not white.** The clasp plate is a **blind ranking** and the
existing packet goes to lengths to keep it blind **[REPO: `hardware/packets/wp04-01/CARD.md`]**.
A PETG pair in a visibly different colour from the white PLA parts cannot be
confused with them on a bench. This is a housekeeping constraint, not a material one.

**Plate, process and failure modes.** The textured PEI plate is reported to need no
adhesive for PETG, while a smooth PEI plate is reported to want glue **as a release
layer** — PETG grips smooth PEI hard enough to risk damaging the sheet
**[INDEX]**. Bambu is reported to say to use only their own glue on their plates
**[INDEX]**. Likely failure modes, all [INFER] from the above: stringing, over-strong
first-layer adhesion damaging the plate, and dimensional drift relative to the PLA
coupon result — which is precisely why the coupon plate should be **re-run in PETG**
before a PETG clasp pair is judged, rather than assuming the PLA numbers carry over.

**Drying and storage.** PETG is hygroscopic and wants a dry box or a sealed bag with
desiccant **[INFER — general polymer practice, not read from a datasheet]**. Do not
buy a dryer on my say-so.

**Fallback: Overture PETG or Polymaker PolyLite PETG, 1.75 mm.** Both are
widely-carried generic-profile PETGs. The honest caveat: with a third-party spool
you lose the first-party profile, which was the main reason for the first choice
**[INFER]**.

**Quantity and priority: one spool, after A1MINI-01 comes back.** One spool prints
many cartridge pairs. The reason to wait is not cost — it is that if the coupon
plate shows this machine cannot hold 0.08 mm in PLA, the clasp sweep needs
rethinking before anyone prints it in a second material.

---

## 4. TPU — recommended against buying now, and the reason is a drawing, not a datasheet

**There is no TPU part in any current design.** `tpu-lip.stl` was **deleted**, not
deferred **[REPO: `docs/PACKAGES/WP-24.md`, ADR-119]**. WP-25 lists TPU bumpers as
*"candidates, not mandated solutions"* **[REPO]**, and WP-25's enclosure dependency
WP-23 has no CAD at all **[REPO: `spec/hw/ruggedization.md` RG-2]**.

So the case against buying TPU has nothing to do with whether TPU is good. **There
is nothing to print in it.** A spool bought now sits in a cupboard absorbing water
until a part exists **[INFER]**.

**If a part does appear, here is what the buy looks like.** TPU is reported to be
supported on the A1 series via an **external spool holder only — it is not supported
in the AMS Lite** **[INDEX]**, and Bambu is reported not to support TPU softer than
**85A** **[INDEX]**. Shore hardness is the thing to get right: **95A** is the
recommendation, as the stiffest common TPU and the most forgiving to feed **[INFER,
on [INDEX] reports that the A1 Mini's short filament path is what makes 95A and 90A
achievable]**. A softer 85A would be the wrong first TPU on an open-path machine.

**Preferred product if needed: Bambu TPU 95A HF, 1.75 mm**, for the same
first-party-profile reason as PETG. **Fallback: NinjaTek Cheetah (95A)** — a
long-established semi-flexible with a reputation for feeding well, though on an
[INDEX]-level basis only, and Polymaker PolyFlex TPU95 is the more widely-stocked
equivalent.

**Priority: do not buy. Revisit only when WP-25 or WP-23 names a specific compliant
part with a specific function.** That is a named trigger, not an indefinite maybe.

---

## 5. Screened out: ABS, ASA, nylon/PA, PC, and everything fibre-filled

These are screened against **the A1 Mini's actual process — an open frame with no
heated chamber** — rather than against their bulk properties, because their bulk
properties are exactly what makes them tempting.

| Material | Why not, on this machine |
|---|---|
| **ABS / ASA** | The open frame is reported as the single most common cause of warping specific to this printer, and ABS/ASA are reported to warp on almost any print bigger than a few centimetres without an external enclosure. Bambu is reported **not to officially support ABS on the A1 Mini, for fire-safety reasons** **[INDEX]**. Separately, they emit **styrene** and want ventilation **[INDEX]**. This is a machine that lives in a home with a child in it **[INFER]**. |
| **PC (polycarbonate)** | Higher process temperatures than ABS with the same open-frame warping problem, and no current part needs its properties **[INFER]**. |
| **Nylon / PA** | Strongly hygroscopic; needs active drying to print at all, and absorbs water back out of the air afterwards, changing its properties in service **[INFER]**. ADR-119 already removed the one place nylon was proposed, because its advantage was fatigue life in a flexure that now carries no load **[REPO]**. |
| **CF / GF-filled anything** | Needs a **hardened steel nozzle** **[INDEX]**. A machine modification and a consumable, for stiffness no part has asked for **[INFER]**. |

**The general rule I would apply, and would want challenged:** on an unenclosed
printer, a material's datasheet strength is not available to you unless the part
comes out unwarped, and an enclosure is a purchase and a fire-safety conversation
that belongs to Michael, not to me.

**One exception worth naming honestly:** the reported ABS position is a *fire-safety*
statement attributed to the manufacturer. If that attribution is accurate, it is not
a tuning problem and no enclosure someone builds makes it Bambu-supported. I could
not open the page. **Nobody should treat that as settled on my word.**

---

## 6. What would change this recommendation

1. **Somebody opens four pages.** Bambu's A1 Mini compatible-filament page, their
   PETG HF and TPU 95A pages, and one PETG datasheet. That converts most **[INDEX]**
   rows here into **[REPO]** and could change the product choices outright.
2. **A1MINI-01 comes back.** If this machine cannot hold 0.08 mm, the clasp sweep is
   respecified before any second material is bought.
3. **WP-23 produces enclosure CAD.** That is when the TPU question becomes real, and
   possibly the ABS/enclosure question with it.
4. **A part fails in PLA.** The fastest way to justify a material is to break
   something.

## 7. Escalation to PM — one item

**ADR-119's premise has changed and I am not going to amend it myself.** It reasons
from *"Michael is not buying a printer. The library loads a single spool of whatever
it has... we do not choose the material or the colour"* **[REPO]**.

Michael now owns an A1 Mini. **We do choose the material now.** The decision ADR-119
reached is, I think, still the right one — a clasp that holds zero strain closed is
better engineering than one that depends on a good spool, and it stays better when
you can pick the spool. But an ADR whose stated rationale is no longer true should
be revisited deliberately by PM rather than quietly relied on, and a material
recommendation is not my licence to rewrite the decision it sits under.

**No guardrail, spec or ADR is changed by this document.**
