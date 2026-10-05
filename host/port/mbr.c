/*
 * mbr.c — the §3.1 MBR: build, exact recognition, and verify findings.
 * Normative: docs/WP14-CLI-CONTRACT.md §2, §3.1, §4.1.
 */

#include "layout.h"

#include <string.h>

#define PT_OFF 446u

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}

static uint32_t get32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void entry(uint8_t *e, uint8_t type, uint32_t start, uint32_t sectors)
{
    e[0] = 0x00;                            /* status: not bootable */
    e[1] = 0xFE; e[2] = 0xFF; e[3] = 0xFF;  /* CHS start: LBA-only marker */
    e[4] = type;
    e[5] = 0xFE; e[6] = 0xFF; e[7] = 0xFF;  /* CHS end */
    put32(e + 8, start);
    put32(e + 12, sectors);
}

static int p2_sectors(uint64_t total_sectors, uint32_t *out)
{
    if (total_sectors <= LAYOUT_P2_START) { return -1; }
    if (total_sectors - LAYOUT_P2_START > 0xFFFFFFFFull) { return -1; }
    *out = (uint32_t)(total_sectors - LAYOUT_P2_START);
    return 0;
}

/* The partition table §3.1 requires: 64 bytes at 446, plus 55 AA. */
static int expected_table(uint8_t table[66], uint64_t total_sectors)
{
    uint32_t n2;
    if (p2_sectors(total_sectors, &n2)) { return -1; }
    memset(table, 0, 66);
    entry(table, (uint8_t)LAYOUT_P1_TYPE, LAYOUT_P1_START, LAYOUT_P1_SECTORS);
    entry(table + 16, (uint8_t)LAYOUT_P2_TYPE, LAYOUT_P2_START, n2);
    table[64] = 0x55;
    table[65] = 0xAA;
    return 0;
}

int mbr_build(uint8_t out[512], const uint8_t uuid[16], uint64_t total_sectors)
{
    memset(out, 0, 512);
    if (expected_table(out + PT_OFF, total_sectors)) { return -1; }
    memcpy(out + 440, uuid, 4);             /* disk signature: first 4 UUID bytes */
    return 0;
}

int mbr_is_layout(const uint8_t lba0[512], uint64_t total_sectors)
{
    uint8_t want[66];
    if (expected_table(want, total_sectors)) { return 0; }
    return memcmp(lba0 + PT_OFF, want, sizeof want) == 0;
}

int mbr_is_mbr_shaped(const uint8_t lba0[512])
{
    unsigned i;
    if (lba0[510] != 0x55 || lba0[511] != 0xAA) { return 0; }
    /* 446..507, not ..509: a superblock's reserved zeros end at 507, and its
       508..511 may be anything, 55 AA included. */
    for (i = PT_OFF; i < 508u; i++) {
        if (lba0[i] != 0) { return 1; }
    }
    return 0;
}

void mbr_entry2(const uint8_t lba0[512], uint32_t *start, uint32_t *sectors)
{
    *start = get32(lba0 + PT_OFF + 16u + 8u);
    *sectors = get32(lba0 + PT_OFF + 16u + 12u);
}

unsigned mbr_findings(const uint8_t lba0[512], uint64_t total_sectors)
{
    uint8_t norm[512];
    uint32_t s2, n2, want_n2;
    unsigned f = 0;

    mbr_entry2(lba0, &s2, &n2);
    if ((uint64_t)s2 + n2 > total_sectors) { f |= MBR_F_TRUNCATED; }
    if (lba0[PT_OFF + 4u] != LAYOUT_P1_TYPE || lba0[PT_OFF + 16u + 4u] != LAYOUT_P2_TYPE) {
        f |= MBR_F_TYPE;
    }
    /* Anything else wrong, once the type bytes and a truncated entry 2's length
       are set to what §3.1 wants, is a layout finding. */
    memcpy(norm, lba0, 512);
    norm[PT_OFF + 4u] = (uint8_t)LAYOUT_P1_TYPE;
    norm[PT_OFF + 16u + 4u] = (uint8_t)LAYOUT_P2_TYPE;
    if ((f & MBR_F_TRUNCATED) && p2_sectors(total_sectors, &want_n2) == 0) {
        put32(norm + PT_OFF + 16u + 12u, want_n2);
    }
    if (!mbr_is_layout(norm, total_sectors)) { f |= MBR_F_LAYOUT; }
    return f;
}
