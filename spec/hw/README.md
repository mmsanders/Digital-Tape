# spec/hw/ — Hardware Lead, versioned not frozen

**Owner: Hardware Lead. No PM gate.** Established by PM Decisions 001 §3.

`spec/` proper is frozen at the Phase 0 gate because three streams implement against it.
These two documents cannot be, because they describe reality and reality keeps changing —
estimates become measurements, and a board revision moves a pin. A rule that made every
thermocouple reading an escalation would be ignored rather than followed, and a spec that
drifts to describe whatever got built is exactly what the freeze exists to prevent.

So the cut is one level finer: **what needs protecting is not the documents, it is their
consumers.**

| File | Consumer | Obligation |
|---|---|---|
| `board-rev-a.md` | `firmware/prod/` | **Notification, not approval.** Any change to a pin, a rail or a timing constraint lands as a PR naming the Software Lead as reviewer, with a `CHANGES` block listing exactly what moved. Firmware acknowledges by merging. The PM does not gate it. |
| `thermal-budget.md` | nothing in code | None. Update freely as measurements replace estimates. |

**Limits live upstream.** Numbers a unit must not exceed — the JEITA window, the solenoid
on-time and duty ceilings, the 85 dB cap, touch temperature — belong in `spec/acceptance.md`,
which is PM-owned and frozen. Measurements live here; the thing they are measured against
does not, so it cannot drift quietly. `thermal-budget.md` §8 carries the proposed set awaiting
PM transcription.
