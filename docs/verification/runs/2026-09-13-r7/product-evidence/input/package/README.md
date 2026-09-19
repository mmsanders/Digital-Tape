# DRAFT-8 complete playback tranche — P1-R6-V

Independent Verification sibling to the preserved P1-R4 package at verifier commit
`7a22cbb4447c40c51b7c8b2282a685ed30a46ba6`, tree
`ff810814dbc8079c6903e6f85ed7ee312abd3076`. It adds the frozen playback boundary,
PM-issued exact scrub, and side-switch families without changing any earlier path.

`generate_fixture.py` reconstructs three VO08 fixtures and both 88,200-frame scrub
candidate PCM files from authenticated product inputs. Run it without `--write` to
reject drift. `selftest.py` runs these ten families, targeted mutations, the retained
P1-R4 controls, saved synthetic evidence, and offline replay. Synthetic results and
candidate PCM are not product execution, listening, WP-11 goldens, or acceptance.

Commands: `python3 generate_fixture.py`; `python3 selftest.py`; and
`python3 replay.py evidence/p1-r6-synthetic` from this directory.
