# Intake — where a fact can be true without becoming work

`docs/FOR-MICHAEL.md` and the `michael` label are an **outbound** queue: things PM
needs Michael to do. Nothing was **inbound**. When Michael mentioned a fact mid-week it
entered the next PM disposition directly, as a live requirement, in the round it
arrived, with no scheduling step in between.

What was missing is an *idle state for information*: somewhere a fact can be recorded as
true without becoming work. That is this.

PM is not malfunctioning. Its charter says it owns roadmap, scope and risk, and a
child-safety remark about rough handling is exactly the kind of thing it should not let
slide. The gap is scheduling, not judgment.

## The three tags

Michael prefixes anything he volunteers. Three words, and they cost him nothing per
message.

| Tag | Means | PM does |
|---|---|---|
| `FYI:` | A fact for the record. Changes nothing now. | Records it. **Default disposition: parked**, with a named resume condition. |
| `CONSTRAINT:` | Changes what is permitted, effective now. | Updates holds and package status. **Creates no new work stream.** |
| `REQUEST:` | Do this work now. | The only tag that creates work. PM states in the disposition **which phase's budget it draws from**. |

**An untagged remark is treated as `FYI:`.**

The tag is Michael's, not PM's to reinterpret. If PM believes an `FYI:` needs to become
work, it says so and asks — it does not upgrade the tag on its own reading. Nothing here
restricts what Michael can say or require; it restricts what PM may infer from a remark.

## The worked example this exists because of

At R16 Michael said, in substance, *"I bought an A1 Mini"*. That was an `FYI:`. It was
executed as a `REQUEST:` and became a printer-process transition: revise the packet
around the owned printer, record repeatability, re-audit.

In the same round a ruggedization suggestion became `Guardrail 13` plus a WP-25
expansion — a player-wide requirement gating final enclosure CAD, requiring Hardware to
publish a shock/load-path and failure-mode matrix, then an auditable drop/shake protocol,
then staged trials, with Verification reviewing criteria before any physical test.
**WP-25 is Phase 4.** R16 also recorded that *"Verification is not activated until
Hardware has an auditable packet"* — so the one seat that can produce Phase 1 acceptance
was idled for a round behind Phase 4 groundwork.

Neither decision is reversed by this document. The ruggedization requirement may well be
right for Phase 4. It was simply scheduled into Phase 1.

## How an intake item is filed

One issue per unscheduled input, labeled `intake`, containing exactly three things:

1. **Michael's words, verbatim.** Not PM's summary of them.
2. **PM's classification** — phase, package, blocking or not.
3. **A disposition.**

**The default disposition is `RECORDED — PARKED`, with a named resume condition.**

PM may convert an intake item into work only if:

- it belongs to the **current phase**; or
- Michael **explicitly requests it** (`REQUEST:`).

Recording a fact is not scheduling it. An intake issue that stays parked for months is
the system working, not a backlog failure.

## Dispositions

| Disposition | Meaning |
|---|---|
| `RECORDED — PARKED` | Default. True, recorded, not scheduled. Names the condition that would resume it. |
| `RECORDED — CONSTRAINT APPLIED` | Holds or package status updated. No new work stream. |
| `CONVERTED — <issue>` | Became work. States the phase and whose budget it draws. Requires current phase or an explicit `REQUEST:`. |
| `SUPERSEDED — <item>` | A later input replaced it. |

## What this does not change

Intake is a scheduling queue. It grants no authority and removes none. Independent
acceptance, the signed freeze, purchase approval, physical safety gates and every
product hold are untouched by how an input was filed. A parked item is not a rejected
one, and `CONSTRAINT:` is effective the moment Michael says it, whatever the queue does
afterwards.

See [the PM charter](ROLES/pm.md) for the phase and bottleneck rules that go with this,
and [the issue workflow](ISSUE-WORKFLOW.md) for routing.
