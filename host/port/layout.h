/*
 * layout.h — the card layout tapectl owns: MBR and partition 1.
 *
 * Normative: docs/WP14-CLI-CONTRACT.md §3.1 and §3.2. The engine never sees
 * any of this; it sees partition 2 through a partition view (partview.h).
 *
 * ERRATUM E-1 IS PENDING MICHAEL (#386). The four constants below are the
 * whole of the choice:
 *
 *   E-1 (built, PM-recommended): FAT16, type 0x0E, 16 MiB, P2 at LBA 34 816
 *   Alternative (keep FAT32):    FAT32, type 0x0C, 64 MiB, P2 at LBA 133 120
 *
 * Switching is these four lines; fat.c builds either FAT type from them.
 */

#ifndef HOST_LAYOUT_H
#define HOST_LAYOUT_H

#include <stdint.h>

#define LAYOUT_FAT_BITS       16u        /* 16 (E-1) or 32 (alternative) */
#define LAYOUT_P1_TYPE        0x0Eu      /* 0x0E FAT16 LBA (E-1) or 0x0C FAT32 LBA */
#define LAYOUT_P1_SECTORS     32768u     /* 16 MiB (E-1) or 131072 (64 MiB) */
#define LAYOUT_P2_START       34816u     /* 2048 + P1 sectors: 34816 or 133120 */

#define LAYOUT_P1_START       2048u      /* 1 MiB aligned; unchanged by E-1 */
#define LAYOUT_P2_TYPE        0xDAu
#define LAYOUT_SECTOR         512u

#if LAYOUT_P2_START != LAYOUT_P1_START + LAYOUT_P1_SECTORS
#error "partition 2 must start where partition 1 ends"
#endif

/* §3.1 LBA 0 for a card of `total_sectors`. `uuid` gives the disk signature.
   Returns 0, or -1 if partition 2 would be empty or exceed 2^32-1 sectors. */
int mbr_build(uint8_t out[512], const uint8_t uuid[16], uint64_t total_sectors);

/* §2 exact recognition: 55 AA, entries 1 and 2 match §3.1 field for field for
   a target of `total_sectors`, entries 3 and 4 all zero. Bootstrap and disk
   signature are not part of the test. */
int mbr_is_layout(const uint8_t lba0[512], uint64_t total_sectors);

/* verify only (#384 Q3): LBA 0 has 55 AA and a non-zero byte in 446..507, so
   it is an MBR and not a bare TAPEFS superblock (whose 446..507 are zero). */
int mbr_is_mbr_shaped(const uint8_t lba0[512]);

/* verify findings against §3.1 for an MBR-shaped LBA 0. Bit flags. */
#define MBR_F_LAYOUT     1u    /* MBR_LAYOUT */
#define MBR_F_TYPE       2u    /* PARTITION_TYPE */
#define MBR_F_TRUNCATED  4u    /* PARTITION_TRUNCATED */
unsigned mbr_findings(const uint8_t lba0[512], uint64_t total_sectors);

/* Entry 2's start and sector count, as recorded (no validation). */
void mbr_entry2(const uint8_t lba0[512], uint32_t *start, uint32_t *sectors);

/* Partition 1: the FAT volume of §3.2. Sectors are emitted relative to the
   partition start, in ascending order, through `put`. Only the sectors a FAT
   driver reads are written: boot region, both FATs, the root directory (or the
   FAT32 root cluster) and README.TXT's cluster. `epoch` is u32 seconds since
   1970 UTC for the timestamps. Returns 0, or put's non-zero result. */
typedef int (*fat_put_fn)(void *user, uint32_t sector, const uint8_t data[512]);
int fat_build_p1(fat_put_fn put, void *user, const char *label,
                 const uint8_t uuid[16], uint32_t epoch);

/* The exact README.TXT bytes for `label` (CRLF endings, #384 Q4: the last line
   too). Returns the length, or 0 if it would not fit in `cap`. */
uint32_t fat_readme(char *out, uint32_t cap, const char *label);

#endif /* HOST_LAYOUT_H */
