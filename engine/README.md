# Engine — Stream 1

Portable C99; no allocation, OS, clock or board knowledge. The public contract is
spec/engine-api.md; the current phase state is docs/PHASE0-FREEZE.md.
Packages: WP-06/07/08/09/12/13/36. CLI, GUI and firmware share this engine.

**Main contains only the clean mount/playback slice merged through PR #77.** Its exact
playback observations and 289 mount records have narrow independent dispositions;
that does not accept source/helper design or complete WP-06/WP-08. PR #20 and #64
remain held, including independently uncovered allocator/recording/warm/state
behaviour. See [integration status](../docs/VERIFICATION-INTEGRATION.md) before
extending code.

include/ is the public API; src/ is implementation; port/ supplies device shims.
Device coupling is read/write/flush; all engine device access funnels through dev.h.
The port archive may use host file I/O; the engine archive may not.

Build with `make -C engine all`. No engine dependencies beyond permitted libc facilities,
board-specific conditionals, heap-returning APIs or read-only writes. Completion needs
the full spec implementation, independent acceptance, golden/crash suites and resource
gates; compiling the provisional archive proves none of those by itself.
