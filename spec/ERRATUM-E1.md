# E-1 — README partition filesystem erratum

**Approved by Michael, 5 October 2026 Pacific:** “Re: Erratum E-1, I accept the default.”
**PM issuance:** ADR-164; Product #384. **Scope:** DRAFT-10 `spec/tapefs-v1.md` §3 partition 1 only.

| Field | Frozen text | E-1 replacement |
|---|---|---|
| Partition 1 type / filesystem | 0x0C FAT32 | **0x0E FAT16 (LBA)** |
| Partition 1 size | 16 MiB | **16 MiB, unchanged** |
| FAT allocation unit | unspecified | **2 KiB (4 × 512-byte sectors)** |
| Partition 1 start | host contract LBA 2048 | **LBA 2048, unchanged** |
| Partition 2 start / type | host contract LBA 34816 / 0xDA | **LBA 34816 / 0xDA, unchanged** |

This erratum supersedes only the first row's filesystem/type in §3 and adds the
allocation-unit constraint. README contents and host layout constants are in the
[WP-14 contract](../docs/WP14-CLI-CONTRACT.md). Optional label art remains outside Phase 2.

**Independent paper basis:** Verification main
`6837102116ed94f80b8a6454713ffb1e7c076427`,
[report](https://github.com/mmsanders/digital-tape-verification/blob/6837102116ed94f80b8a6454713ffb1e7c076427/findings/P2-R1-WP14-PREFLIGHT-2026-10-05.md).
16 MiB has fewer sectors than FAT32's minimum data-cluster count. FAT16 with
2 KiB clusters is feasible: the report's example yields 8167 data clusters and
fits two 32-sector FATs and a 512-entry root directory.

**Impact / migration:** the engine sees partition 2 only; its blocks, metadata,
CRC, API and operation semantics do not change. Firmware never reads partition 1.
A provisioned card with the old type is not an E-1 layout; reprovisioning erases
the card and requires the normal explicit device confirmation. Existing bare
TAPEFS images and all historical evidence retain their identities.

**Integrity:** the three historical DRAFT-10 files and their hashes remain
byte-identical. `spec/ERRATA.sha256` authenticates this additive erratum; the
effective host layout is DRAFT-10 plus E-1, not an unlogged edit to frozen bytes.
Verification #146 checks these exact erratum bytes and hash during its existing
Stage 1 preflight before citing E-1 as independently reviewed publication.

Paper feasibility and Michael's approval establish the selected specification.
They do not establish OS readability of the produced card or any WP-05 media
qualification; Windows 10/current macOS card evidence remains WP-14 work.
