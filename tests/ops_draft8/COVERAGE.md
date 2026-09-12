# VT8-001 assertion and exclusion matrix

This matrix is the acceptance boundary for this package. “Covered” means the verifier
has an independent assertion and a negative control or otherwise explicit evidence;
it does not imply whole-work-package acceptance.

| Assertion ID | Case | Independent assertion | Normative basis | Control/evidence |
|---|---|---|---|---|
| VT8-A01 | reset | `cartridge_sequence` includes every structurally valid slot; B0 commits at 901 | TapeFS §5.5, §9.2 | original live-only-base mutation |
| VT8-A02 | reset | B0 entries equal live A, `side=1`, B becomes selectable, `free_next==H` | TapeFS §§5.2–5.3, §7, §9.2 | final media/remount evidence |
| VT8-A03 | reset | no chunk or superblock write at stage 0 | TapeFS §7, §9.2; Engine API public reset semantics | reset chunk-write mutation |
| VT8-A04 | reset | B0 commit is entries → flush → header → flush | TapeFS §8, §9.2 | ordered commit validator |
| VT8-A05 | record | allocation begins at derived `free_next==H==3`, never below H | TapeFS §7 | original below-H mutation; whole trace |
| VT8-A06 | record | all accepted chunk writes have a durability barrier before metadata | TapeFS §8 steps 1–3; Engine API §7/§7.1 | new post-flush service-write mutation |
| VT8-A07 | record | B1 commit is exactly entries → flush → header → flush; two commit flushes | TapeFS §8; Engine API §7.1 | P1-R1-V01 reordered-flush control |
| VT8-A08 | record | `tape_feed` and other scripted no-I/O calls issue no callback I/O | Engine API §7; TapeFS §7 | P1-R1-V02 feed-write control |
| VT8-A09 | both | every callback has legal phase/op, zero rc, positive in-range widened batch | Engine API device contract §§3, 6–7 | out-of-range and nonzero-rc controls |
| VT8-A10 | record | B1 is `[(0,0,128),(3,0,128)]` at 701; semantic validity and unique structural sequences | TapeFS §§5.1–5.5, §9.1 | original sequence/overlap mutations |
| VT8-A11 | record | ordinary stage-0 record does not update superblock generation | TapeFS §5, §8–§9.1 | original sb-generation mutation |
| VT8-A12 | both | public-call sequence/results prove the intended API path and remount outcome | Engine API §§5–7 | accepted-count result mutation plus exact call script |
| VT8-A13 | evidence | actual spec bytes authenticate to issued DRAFT-8 hashes | `spec/VERSION.md`; Phase-0 freeze | spec-byte tamper control |
| VT8-A14 | evidence | raw input/final VO08, observations and verdict are hash-bound and replayable without engine | P1-R1-V03 evidence requirement | missing/tampered evidence controls |
| VT8-A15 | evidence | adapter is explicitly synthetic/product with immutable source/build provenance | P1-R1-V03 | manifest/observation identity checks |

## Deliberate exclusions

Not covered here: non-NULL warm start; playback/render golden correctness; overwrite
and overdub; zero-frame commit; stage clearing; reset timing; random/10,000-edit
sequences; promote; re-spool; duplicate; format; long-operation continuation/reentry;
FAULTED quarantine; crash injection/recovery; V7-001 two-interruption closure; target
timing/resources; hardware/media atomicity; or human listening. Reads permitted by the
public semantics are not banned merely because a happy synthetic trace omitted them.

The two cases do not establish full WP-07, WP-10, WP-11, WP-12a, operation/state freeze,
or product-engine acceptance. A synthetic green run proves the verifier package only.
