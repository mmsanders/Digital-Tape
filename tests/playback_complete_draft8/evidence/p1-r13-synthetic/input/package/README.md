# Corrected DRAFT-8 complete playback tranche — P1-R13-V

Independent Verification sibling to the preserved P1-R4 package at verifier commit
`7a22cbb4447c40c51b7c8b2282a685ed30a46ba6`, tree
`ff810814dbc8079c6903e6f85ed7ee312abd3076`. It adds the frozen playback boundary,
PM-issued exact scrub, and side-switch families without changing any earlier path.

`generate_fixture.py` reconstructs three VO08 fixtures and both 88,200-frame scrub
candidate PCM files from authenticated product inputs. P1-R8 corrects exactly three
expectations: reverse `INT32_MIN` emits frame 0, reverse-from-end snaps to the last
frame grid point, and post-side-switch short renders return `TAPE_ERR_UNDERRUN` (18).
P1-R13 additionally enforces the WP-08 completed `tape_service(1024)` sequence before
every scrub render request in all 16 rows and both directions. The service-only cadence
correction leaves fixture and candidate PCM bytes unchanged.
Run the generator without `--write` to reject drift. `selftest.py` runs all ten
families, named P1-R13-V01 forward/reverse and F-1/F-2/F-3 controls, the retained P1-R4 controls, saved synthetic
evidence, and offline replay. Synthetic results and candidate PCM are not product
execution, listening, WP-11 goldens, or acceptance.

Commands: `python3 generate_fixture.py`; `python3 selftest.py`; and
`python3 replay.py evidence/p1-r13-synthetic` from this directory.
