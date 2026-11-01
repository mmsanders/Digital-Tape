# C1 independent outcome tests (Verification364)

Authority: Product `262466d354dac779b0fda9d712a2d75b73eeec33`, ADR-195,
APP-1/APP-1A, Verification input `5512a2d0d7bd8135f4a10016d9469c612340737a`.
Authored without opening Software624 implementation or private tests. Reading its
public return established the candidate identity, not new expected behavior.

Run `python -B tests/c1_closeout_r1/controls.py` for the method's controls.
`static_check.py ROOT` scans the first-party integrated ingest/app source for raw
device paths, device APIs and device-control operations. Ordinary file I/O remains
allowed. It is a bounded source check, not a whole-program theorem. Review external
dependencies/build scripts and candidate manifests alongside it. No raw device is
opened by any verifier script. Existing G1 `static_controls.py` remains unchanged.

`g3.py --emit` emits the independent bridge test matrix. An adapter must drive the
production bridge/coordinator, capture actual messages/state/child requests, and
pass its returned JSON to `g3.py RESULT.json`. App events use the real bridge action
and a controlled launcher/recheck error at that dependency boundary; never forge a
child report to select an app-origin event. Child-origin cases use real tool exits
and original report bytes on private images/loop/VHD targets in CI, fed through the
production completion path. Include source SHA, raw argv/exit/stdout/stderr/report,
adapter source and bridge entry references. Synthetic selftests are NOT these runs.
No shipping injection flag, native UI gesture or physical device is required in CI.

The matrix complements, rather than replaces, existing parser, report, bridge,
screen, cards and make packages. Use both the unchanged make runner and the C1
supplement when the latter applies. All child messages must also survive changed
stderr wording with unchanged actual exit/report; diagnostics must remain copyable.
Every listed case is required unless a specific contract-based unreachable reason
is independently disposed. No force-failure switch for guarded outcomes.

`C2-CHECKLIST.md` is the human screen/install/real-card half. G1/G3/G4/G5 remain open
until C2 on the cleared exact candidate. G2 is a later, separate unaided session.
