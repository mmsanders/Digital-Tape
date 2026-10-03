# Engine — Stream 1

Portable C99; no allocation, OS, clock or board knowledge. The public contract is
spec/engine-api.md; the current phase state is docs/STATUS.md.
Packages: WP-06/07/08/09/12/13/36. CLI, GUI and firmware share this engine.

**Main holds the full Phase 1 engine.** Every Phase 1 engine package (WP-06/07/08/09/10/
11/12/13/36) is independently accepted for laptop scope; see [STATUS](../docs/STATUS.md) and
[integration status](../docs/VERIFICATION-INTEGRATION.md). Acceptance is per recorded
boundary and makes no target-hardware claim. New behaviour still lands test-first under
Structural Rule 1.

include/ is the public API; src/ is implementation; port/ supplies device shims.
Device coupling is read/write/flush; all engine device access funnels through dev.h.
The port archive may use host file I/O; the engine archive may not.

Build with `make -C engine all`. No engine dependencies beyond permitted libc facilities,
board-specific conditionals, heap-returning APIs or read-only writes. Completion needs
the full spec implementation, independent acceptance, golden/crash suites and resource
gates; compiling the archive proves none of those by itself.
