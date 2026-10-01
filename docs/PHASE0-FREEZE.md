# Phase 0 freeze record

**Status: FROZEN AT DRAFT-10 — MICHAEL AUTHORIZED V10-001…V10-005 ON 1 OCTOBER 2026
UTC; PM ISSUED THEM THROUGH PRODUCT PR #352.** The DRAFT-9 (V9-001) amendment and the
original scoped DRAFT-8 signature remain recorded below.

Michael requested a freeze-ready repository and delegated PM, Software and Hardware
authority for this push. The working agreement reserves final format-freeze sign-off
to Michael. Michael signed this exact scoped decision in the project conversation:
“Consider it signed by me, and do what you need to do to represent that in main.”
This records his approval; it does not grant independent implementation acceptance.

## Current amendment and publication: DRAFT-10

Michael authorized the exact amendments in the project conversation: “I authorize DRAFT-10 amendments V10-001…V10-005 as in PR #352. Please continue”.
PM accepted that as the reserved freeze-amendment approval. PM issued DRAFT-10 by
merging product PR [#352](https://github.com/mmsanders/Digital-Tape/pull/352) at head
`ec6b9813af60202eed322e14d320cfaa8546484e`. Its exact bytes are:

| File | SHA-256 |
|---|---|
| spec/tapefs-v1.md | 2a6a9f7b6fe1e5f9e3fe068b3c6460a81256276082bb7e336c01dbf1e9c17eba |
| spec/engine-api.md | aa042e41e35b02bf2bb6b3896e59340a947720c27dc5fc52a24d657ccd66b33a |
| spec/acceptance.md | 50aa63bd751fdc6b4636de0eb48253887be19b7ec2841768449217b4e9b9e547 |

**No field, layout or CRC changes.** V10-001 (Verification finding V-R54-03) changes only
what raw `tape_format`/`tape_dup` write to a destination with no structurally valid
superblock: it is blank only if both blocks are entirely zero, and otherwise it is residue,
zeroed before step 2. That edits §4.6 item 5, inside the frozen §§1–8, as a description of
raw format/dup only. V10-002…V10-005 are clarifications that PM rulings had already applied
(WP-06e reachability, `BAD_MAGIC`/`CRC`, the WP-06f re-spool floor and the WP-12a audio clause).

Independent review was Verification #133 on r1 (finding `645d4de`: 528 DRAFT-9
resurrections, 0 under DRAFT-10, over 16.9M two-interruption images on 14 shapes) and
Verification #136 on r2 (finding `cc3ba4a`: an exact crash table over 12.8M states,
READY). r3 applied #136's one non-blocking wording note in its own proposed text, with no
change to any permitted set. Issuance is not implementation or acceptance: V10-001 needs
republished verifier rows, an engine change under Structural Rule 1, and independent
disposition. Under `tapefs` §14, §9 freezes at the first fully green WP-10 run.

## Previous amendment: DRAFT-9

Michael selected the recommended fourth-funnel proposal in the project conversation:
“Let’s take the recommended fourth-funnel proposal if you’re good with it. Proceed to
issue whatever work to make that happen.” PM accepted that direction as the reserved
approval for exact amendment V9-001.

DRAFT-9 was issued through product PR
[#247](https://github.com/mmsanders/Digital-Tape/pull/247) at product main
`7910ae3701fbfd94b5ea0558a69a29955da1dd5c`. Its exact current bytes are:

| File | SHA-256 |
|---|---|
| spec/tapefs-v1.md | 3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d |
| spec/engine-api.md | 383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6 |
| spec/acceptance.md | ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d |

V9-001 adds exactly one permitted indirect-call funnel:
`dev_progress` calls the caller-supplied `tape_progress_fn` in `engine/src/dev.h`.
Exactly four named funnels are now permitted; a fifth wrapper, another callback type,
an ambiguous call or any indirect call outside `dev.h` remains forbidden. It changes
no media semantics, exported ABI, callback signature or numeric resource limit.

Verification PR
[#82](https://github.com/mmsanders/digital-tape-verification/pull/82) independently
reviewed the exact candidate and published `tests/embedded_readiness_draft9`, tree
`8e5d0853755e54032b7d5304caf1190a03376393`, on Verification main
`74a2f96d5fa50972f2a20bc391fc6bd363554cb1`. The package keeps all six WP-13 gates
and adds negative controls for the newly bounded funnel; publication is not product
acceptance. Product PR [#249](https://github.com/mmsanders/Digital-Tape/pull/249)
made evidence integrity revision-aware without changing any historical DRAFT-8 copy.

The hashed spec files retain historical **NOT FROZEN** banners because those banners
were inside the independently reviewed candidate bytes. This signed issuance record
supersedes those banners for the exact DRAFT-9 scope above; changing them alone would
create different, unreviewed hashes.

## Original DRAFT-8 signature and publication

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

The DRAFT-8 NOT FROZEN banners remain byte-identical to that reviewed candidate.
The 8 September signed record superseded those banners only for the scope in the
table above; DRAFT-9 now supersedes DRAFT-8 only as stated in V9-001.
Do not imply the operations/state sections froze or silently edit hashed banners.
Any later change to a frozen contract requires PM disposition, Michael's reserved
approval, independently reviewed new bytes, impact/migration analysis and a new
integrity manifest.

## Evidence and residual holds

- Verification #86 independently accepted exact product PR #263 head
  `8a4d2a17138fd89e91f970a2c69c9f8fa0a8d920`: 44,307/44,307 canonical and
  diagnostic cases, 25/25 B6 crafted cases and all six red controls. This is bounded
  R29-A evidence, not complete WP-10/WP-12a acceptance. Software #267 integrated the
  accepted identities unchanged at main `215204b`; this is not a general release claim.
- #27 lands verifier tests before implementation. Ten package checks pass; 289 engine
  observations on the held branch pass after two DRAFT-8 fixes. At signing the
  independent disposition was pending; the 11 September Verification return now
  confirms those 289 assertions only. See [integration](VERIFICATION-INTEGRATION.md).
  This later evidence does not expand the signed scope or accept the full package.
- Hardware #18 landed after all hardware CI jobs passed. IR-018-18’s Make fix and
  ADR-128’s date-drift fix are implemented. Independent safety acceptances remain open.
- WP-11 golden CI is still red. No full WP-10, hardware measurement or card-atomicity
  acceptance is claimed. Raw destructive operation outcomes retain their exact spec
  boundaries; a paper freeze does not establish physical media atomicity.
- Verification #83 independently accepted exact product PR #241 head `74f1173` for
  bounded R29-B (57,611/57,611) and DRAFT-9 WP-13 (all six gates); Software #255
  integrated it at main `867fd4a`. Verification #86 accepted final R29-A PR #263 and
  Software #267 integrated its corrected package tree `197d2f2a` unchanged at main
  `215204b`. This does not grant complete WP-10 or WP-12a acceptance.
- The original program’s Phase 0 spike/buying tasks are not all accepted. This is
  the narrower format/API freeze gate, not a claim that WP-04/05/34 are complete.

## Signatures

- Independent paper threshold: DRAFT-8 third-cut review and DRAFT-9 Verification PR
  #82, authenticated above.
- PM: issued exact DRAFT-9 V9-001 at product main `7910ae3...`.
- Michael: **signed 8 September 2026** and approved V9-001 on **25 September 2026
  Pacific time**, with both explicit approvals quoted above.
- Operations/state and hardware acceptance: **not granted**.

The temporary combined-lead freeze mandate has ended; normal roles in
[CLAUDE.md](../CLAUDE.md) resume. Later infrastructure experiments do not extend
product or verification authority. The current operating format is recorded in
[the Phase 1 plan](PHASE1-DEVELOPMENT.md); the signed scope above is unchanged.
