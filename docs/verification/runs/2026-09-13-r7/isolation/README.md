# Conflict isolation — Software diagnostic, NOT a verifier artefact

`scratch-oracle.diff` is a diff against a **scratch copy** of the independent
oracle held outside the repository. The package in
`tests/playback_complete_draft8/` is byte-unchanged; the real oracle was run
unmodified and its verdict (`FAIL`, `tape_render.rendered`) is what
`../product-evidence/result.json` records. Nothing here relaxes, replaces or
accepts anything.

Its only purpose is to answer one question PM needs answered: *how much of the
complete package does the product engine satisfy, and is the failure one issue
or twenty?* Three expectations are set aside — the three the return document
raises as findings — and nothing else:

| # | Set aside | Frozen-spec reference |
|---|---|---|
| F-1 | `intmin` expects `tape_render(2) -> rendered 1` and one output frame | §6.2 "land ON frame 0; it is emitted next pass" |
| F-2 | `scrub_reverse` compares against `candidate/scrub-reverse.pcm` | §6.3 V5-005 grid snap to `(total_frames-1) << 32` |
| F-3 | side families expect `tape_render` result `6` | §2 enum: `TAPE_ERR_UNDERRUN` is 18; 6 is `TAPE_ERR_GEOMETRY` |

`result.json` is the scratch run's verdict: **pass**, 1,625 checked calls, and
five byte-exact PCM families (`one_intmax`, `reverse_zero`, `scrub_forward`,
`side_playing`, `side_idle`). Every call order, callback-legality, service
sequence, `tape_tell`/`tape_status`/`tape_get_info` and clamp assertion in the
package holds against the product engine. That is the measurement: the engine
satisfies the tranche except at exactly the three points where the package
disagrees with the frozen contract.

A scratch verdict is not acceptance, not a green gate, and not evidence of
anything except the size of the disagreement.
