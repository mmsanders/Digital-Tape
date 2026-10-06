# Supplemental spec erratum E-1 — partition 1

**Authority:** Michael, 5 October 2026 Pacific time: “Re: Erratum E-1, I accept the default.”
PM ADR-164 / Product #384 and intake #391. Independent paper input: Verification main
`6837102116ed94f80b8a6454713ffb1e7c076427`, findings/P2-R1-WP14-PREFLIGHT-2026-10-05.md.

This is a narrow normative overlay to DRAFT-10 `spec/tapefs-v1.md` §3, whose base SHA-256 is
`2a6a9f7b6fe1e5f9e3fe068b3c6460a81256276082bb7e336c01dbf1e9c17eba`.
The base bundle and all historical evidence copies stay byte-identical. For new whole-card
provisioning, the replacement row below takes precedence over the base row. This does not
revise TAPEFS partition bytes, engine operations, state/crash tables or previous dispositions.
The supplemental integrity manifest is `docs/SPEC-ERRATA.manifest.json`.

| Field | DRAFT-10 §3 | E-1 replacement |
|---|---|---|
| Partition 1 type | 0x0C FAT32 | **0x0E FAT16 LBA** |
| Partition 1 size | 16 MiB | **16 MiB (32768 sectors)** |
| FAT cluster size | unspecified | **2 KiB (4 sectors)** |
| Contents | README.TXT, optional label art | unchanged in format; WP-14 contains README.TXT only |

WP-14 starts partition 1 at LBA 2048 and partition 2 at LBA 34816. Both remain unchanged.
8167 clusters with 1 reserved sector, two 32-sector FATs and 512 root entries is one conforming
example, not an imposed FAT sizing algorithm. Correct alternate FAT16 geometries are allowed.

**Impact/migration:** firmware never reads partition 1; engine sees only partition 2. No engine,
API, CRC, mirror offset or firmware change. Previously produced nonconforming FAT32/16 MiB
whole cards are not silently upgraded or accepted as E-1. Reprovisioning requires the user's
explicit destructive confirmation and reload of audio; bare Phase 1 images need no migration.
No existing physical card is asserted to contain either layout. Actual Windows 10/macOS readability
of the produced FAT16 card remains witnessed acceptance work, not paper compatibility.

**Independent exact-byte confirmation:** Verification #146 confirms this replacement table,
impact statement and manifest as part of its already-assigned Stage 1 package preflight, before
Software imports the completed package. Any disagreement returns to PM. This confirmation is
bundled with package authoring, not a separate paper-review or pass-through round. Michael's
approval is recorded now; no candidate integration or package acceptance precedes that confirmation.
