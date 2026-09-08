# Phase 0 freeze record

**Status: FROZEN — MICHAEL SIGNED THE PHASE 0 SCOPE BELOW ON 8 SEPTEMBER 2026.**
**PM review completed: 8 September 2026.**

Michael requested a freeze-ready repository and delegated PM, Software and Hardware
authority for this push. The working agreement reserves final format-freeze sign-off
to Michael. Michael signed this exact scoped decision in the project conversation:
“Consider it signed by me, and do what you need to do to represent that in main.”
This records his approval; it does not grant independent implementation acceptance.

## Exact candidate and publication

DRAFT-8 was published through #25 at
5e92f4085b40d55ea605267b6ce8e0e2c997053c. All four files compare byte-for-byte with
Michael’s attachments and the verifier’s authenticated copy at
4ee116fa040bb5ce040325e0076365abf8b0f8f9.

| File | SHA-256 |
|---|---|
| spec/tapefs-v1.md | 3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb |
| spec/engine-api.md | 537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1 |
| spec/acceptance.md | 7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7 |

The bundle gate passed, rejected a deliberate one-line content mutation, and passed
after exact restoration. The [independent third-cut review](verification/surge-draft8-third-cut-review.md)
records **zero blockers, zero majors, one documentation question** and explicitly
carries forward on byte-identical issuance.

## Signed decision

| Surface | Phase 0 decision |
|---|---|
| TapeFS §§1–8 | Freeze the byte-level contract at the hashes above |
| Engine API §§2–8 and §12 | Freeze the candidate API/contract surface at these bytes |
| Acceptance criteria | Freeze with the format; this does not mark any criterion passed |
| Operations and state matrix | Remain unfrozen until the actual complete WP-10 run is green |
| Hardware spec/design/measurements | Separately versioned; not frozen or safety-qualified here |
| Implementation | No wholesale #20 merge; uncovered behaviour remains held |

**Michael approved the Phase 0 scope above on 8 September 2026.** V8R3-001 is retained as an
editorial debt: the generic “Then” sentence in TapeFS §4.6 should be scoped to
higher-generation writes. The detailed §9.5/§9.6 exhaustion behaviour is singular;
the independent reviewer graded this non-blocking. Do not change a reviewed hash for
cosmetic cleanup without re-authentication/review.

The historical NOT FROZEN banners remain byte-identical to the reviewed candidate.
This signed record supersedes those banners only for the scope in the table above.
Do not imply the operations/state sections froze or silently edit hashed banners.
Any later change to a frozen contract requires PM disposition, independently reviewed
new bytes, impact/migration analysis and a new integrity manifest.

## Evidence and residual holds

- #27 lands verifier tests before implementation. Ten package checks pass; 289 engine
  observations on the held branch pass after two DRAFT-8 fixes. Independent result
  disposition is pending. See [integration](VERIFICATION-INTEGRATION.md).
- Hardware #18 landed after all hardware CI jobs passed. IR-018-18’s Make fix and
  ADR-128’s date-drift fix are implemented. Independent safety acceptances remain open.
- WP-11 golden CI is still red. No full WP-10, hardware measurement or card-atomicity
  acceptance is claimed. Raw destructive operation outcomes retain their exact spec
  boundaries; a paper freeze does not establish physical media atomicity.
- The original program’s Phase 0 spike/buying tasks are not all accepted. This is
  the narrower format/API freeze gate, not a claim that WP-04/05/34 are complete.

## Signatures

- Independent paper threshold: recorded in the third-cut review, authenticated above.
- PM: recommends the exact scoped freeze; recorded by the temporary acting PM.
- Michael: **signed 8 September 2026**, explicit approval quoted above; Q-001 closed.
- Operations/state and hardware acceptance: **not granted**.

The temporary combined-lead freeze mandate has ended; normal roles in
[CLAUDE.md](../CLAUDE.md) resume. Michael separately authorized review/integration
of Agent Bus and Pages infrastructure, excluding binding particular agent instances.
That bounded follow-on authorization does not extend product or verification authority.
