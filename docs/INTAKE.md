# Intake — recording a fact without making it work

`docs/FOR-MICHAEL.md` and the `michael` label are the **outbound** queue: things PM needs
Michael to do. The `intake` label is the **inbound** queue: anything Michael volunteers is
recorded there as true, and becomes work only when the rules below say so.

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

## How an intake item is filed

One issue per unscheduled input, labeled `intake`, containing exactly three things:

1. **Michael's words, verbatim.** Not PM's summary of them.
2. **PM's classification** — phase, package, blocking or not.
3. **A disposition.**

**The default disposition is `RECORDED — PARKED`, with a named resume condition.**

PM may convert an intake item into work only if:

- it belongs to the **current phase**; or
- Michael **explicitly requests it** (`REQUEST:`).

Recording a fact is not scheduling it. A parked intake issue may remain open while its
filing is incomplete, but it does not need to stay in the live queue forever. Once the
durable facts, disposition and named resume condition are copied into the canonical
package/status documentation, PM closes the intake issue as **filed**. Closure means only
that the intake record has been durably filed; it does not reject, supersede or silently
schedule the input.

If a resume condition later becomes true, PM opens a fresh role-labeled work issue with
current scope and exact inputs. Do not reopen the historical intake issue merely to turn a
parked fact into an assignment.

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
