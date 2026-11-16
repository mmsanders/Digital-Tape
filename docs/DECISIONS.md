# Decisions

Newest at the bottom. Record a decision here only when it changes a guardrail, the spec,
the working agreement or something expensive to reverse (CLAUDE.md §4). Never edit an
entry; supersede it with a new one.

**ADR-001 to ADR-209** are in [the closed log](archive/DECISIONS-ADR-001-209.md), with
[a one-line index](archive/DECISIONS-INDEX-ADR-001-209.md). They remain in force unless a
later decision supersedes them. The closed log was moved unchanged; its SHA-256 is
`287fc535acd394f7ca043ac15a4c013737adfa67f82e3d97da6f2df64c31fff9`.

**Format:** `## ADR-NNN — title` / **Date** / **Decision** / **Rationale** / **Cost to reverse**

---

## ADR-210 — Light process outside the engine
**Date:** 2026-11-16 PST
**Status:** ADOPTED on Michael's direction after a whole-project review he commissioned:
"2-8 all sound good, please do them all."

**Decision.**
1. **Two tracks, chosen by path.** The tests-first, independently verified process
   (Structural Rule 1, verifier publications, blind disposition) applies to `engine/`, the
   frozen product spec, the goldens and the imported verifier packages. Everything else
   (firmware, desktop tools, hardware, tooling, CI, docs) is one lead, one session, one PR,
   with the author's own proportionate tests. CLAUDE.md §3 is the rule;
   [ENGINE-CHANGES](ENGINE-CHANGES.md) keeps the full strict procedure.
2. **PM is optional.** Michael gives work to a lead directly, in a session or an issue. PM
   runs only when he asks for planning, a spec revision or arbitration.
3. **Bench evidence is a row in MICHAEL-CHECKS.** The firmware prints its numbers and build
   id; Michael records what he saw and his verdict. No capture bundles, record schemas,
   evidence checkers or build-hash linkage for hands-on criteria. This finishes what
   ADR-208 started.
4. **Plain reports.** No recited hashes, run ids or check counts, and no lists of what a
   result does not authorize.
5. **F3 warm wake is implemented directly**: `sleep`, Play, one `WAKE us <n>` line, and a
   `wake150` control. The F3-IF/1 and F3-IF/2 declarations and their bound packages
   (PR 677, Verification `f3_wake_if1_r1` and `f3_if2_r1`) are not imported or built.
6. **The power-cut test stays, and stays simple.** At least 1,000 qualifying cuts per card
   model and zero torn blocks still decide (ADR-208 §6). It is written as bench firmware
   plus a plain log reader when the parts are on the bench, not bound in advance.
7. **CI and the decision log are pruned** as recorded in the PR that carries this entry.

**Unchanged.** Guardrails 01 to 13. The engine pin and format freeze. The output caps and
their margins. The CLOSED fabrication and charging gate. Purchase approval. One block per
card write until the batching hold is lifted. The desktop tools' disk-safety rules. Every
existing acceptance, disposition and piece of evidence.

**Supersedes** the process parts of ADR-209 ("Pre-parts outcomes": declare, bind, then
implement for firmware and tooling) and the per-round PM issue routing of ADR-158/195 for
light-track work. ADR-209's technical rulings on the power-cut method (CID diagnostic
only, completed-before-old is a run failure, SPI scope) stand as design input.

**Rationale.** By November the project was blocked on a small parts order, not on
software, while each firmware feature cost six to eight agent sessions and a hand relay
between each. The F3 timer, about thirty lines of firmware, had produced two interface
documents and 150 bound test cases and no code. The strict process earns its cost where a
bug silently destroys a recording on every device; that code is finished and frozen. A
bench build that Michael holds in his hands is checked best by Michael.

**Cost to reverse.** Low. The strict procedure is intact in ENGINE-CHANGES.md and its CI
gates were not touched; widening its scope again is an edit to CLAUDE.md §3. The verifier
packages left unimported remain published in the verification repository.
