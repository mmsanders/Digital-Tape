# G1 negative control

A copy of host/app with one planted violation per G1 static rule. CI requires
`g1_static.py --root tools/app1a/fixtures/g1-negative --require-rules G1-DEV,G1-FS,G1-CHILD,G1-PAGE,G1-CAP`
to report every rule. Never built; never shipped.
