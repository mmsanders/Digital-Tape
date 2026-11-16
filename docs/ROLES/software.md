# Software Lead

Any Claude Code session Michael starts for software work, local or cloud.

**Owns:** `firmware/`, `host/`, `tools/`, `.github/`, and integration of everything into main.

**Light track (almost all work).** Do the task end to end in one session: code, your own
tests, docs, PR. Follow CLAUDE.md §3. For firmware:
- call the engine through `engine/include/tape.h` and never reimplement what it does;
- put logic in portable C that the host harness can run (`firmware/bench/host/`), and keep
  the Teensy glue thin;
- print what Michael needs on serial in one readable line, with the build id;
- say plainly which parts were only compiled and which ran on hardware.

**Strict track (`engine/`, the frozen spec, goldens, imported `tests/` packages).** Do not
start without Michael saying so. Then follow [ENGINE-CHANGES](../ENGINE-CHANGES.md): import
Verification's published tests unchanged in one commit, implement in the next, never edit
an imported tree. A wrong test is a finding to return, not something to fix.

**Before finishing:** CI green or the failure explained; `docs/STATUS.md` updated if the
state changed; tell Michael what to do next.
