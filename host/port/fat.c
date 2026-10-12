/*
 * fat.c — partition 1 of §3.2: a FAT volume holding README.TXT.
 *
 * Normative: docs/WP14-CLI-CONTRACT.md §3.2. The FAT type and size come from
 * layout.h (erratum E-1), so the same code builds the E-1 FAT16 volume or the
 * FAT32 alternative. The FAT type is decided by cluster count alone (Microsoft
 * FAT specification §3.5); the build refuses a geometry whose cluster count
 * does not give the type it claims.
 *
 * Deterministic: the bytes depend only on the label, UUID and epoch.
 */

#include "layout.h"

#include <string.h>

#define SEC LAYOUT_SECTOR

#if LAYOUT_FAT_BITS == 16
#define SEC_PER_CLUS   4u          /* 2 KiB clusters (§3.2) */
#define RSVD_SECS      4u
#define ROOT_ENTRIES   512u
#elif LAYOUT_FAT_BITS == 32
#define SEC_PER_CLUS   1u
#define RSVD_SECS      32u
#define ROOT_ENTRIES   0u
#else
#error "LAYOUT_FAT_BITS must be 16 or 32"
#endif

#define NUM_FATS       2u
#define TOTAL_SECS     LAYOUT_P1_SECTORS
#define ROOT_SECS      ((ROOT_ENTRIES * 32u + SEC - 1u) / SEC)

/* FAT size, Microsoft FAT specification §3.5 (the FATSz computation). */
#define TMP1           (TOTAL_SECS - (RSVD_SECS + ROOT_SECS))
#if LAYOUT_FAT_BITS == 32
#define TMP2           (((256u * SEC_PER_CLUS) + NUM_FATS) / 2u)
#else
#define TMP2           ((256u * SEC_PER_CLUS) + NUM_FATS)
#endif
#define FAT_SECS       ((TMP1 + TMP2 - 1u) / TMP2)
#define DATA_START     (RSVD_SECS + NUM_FATS * FAT_SECS + ROOT_SECS)
#define CLUSTERS       ((TOTAL_SECS - DATA_START) / SEC_PER_CLUS)

#if LAYOUT_FAT_BITS == 16 && (CLUSTERS < 4085u || CLUSTERS > 65524u)
#error "partition 1 geometry is not FAT16 by cluster count"
#endif
#if LAYOUT_FAT_BITS == 32 && CLUSTERS < 65525u
#error "partition 1 geometry is not FAT32 by cluster count"
#endif

#define VOLUME_LABEL   "DIGITALTAPE"           /* §3.2, 11 bytes, no padding */

/* Clusters: FAT16 root is fixed, README at 2. FAT32 root at 2, README at 3. */
#if LAYOUT_FAT_BITS == 32
#define ROOT_CLUSTER   2u
#define README_CLUSTER 3u
#else
#define README_CLUSTER 2u
#endif

static void put16(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void put32(uint8_t *p, uint32_t v) { put16(p, v); put16(p + 2, v >> 16); }

static const char *const README_LINES[4] = {
    "This is a Digital Tape cartridge.",
    "Label: ",
    "Please do not format or erase this card on a computer.",
    "Use the Digital Tape app to load music onto it.",
};

uint32_t fat_readme(char *out, uint32_t cap, const char *label)
{
    uint32_t n = 0;
    unsigned i;
    for (i = 0; i < 4u; i++) {
        size_t a = strlen(README_LINES[i]), b = (i == 1u) ? strlen(label) : 0u;
        if (n + a + b + 2u > cap) { return 0; }
        memcpy(out + n, README_LINES[i], a); n += (uint32_t)a;
        if (b) { memcpy(out + n, label, b); n += (uint32_t)b; }
        out[n++] = '\r';
        out[n++] = '\n';
    }
    return n;
}

/* Seconds since 1970 UTC -> FAT date and time, clamped to FAT's 1980..2107. */
static void fat_stamp(uint32_t epoch, uint16_t *date, uint16_t *time)
{
    static const uint32_t FAT_MIN = 315532800u;     /* 1980-01-01T00:00:00Z */
    uint32_t days, secs;
    long z, era, doe, yoe, y, doy, mp, d, m;

    if (epoch < FAT_MIN) { epoch = FAT_MIN; }
    days = epoch / 86400u;
    secs = epoch % 86400u;
    /* civil_from_days (H. Hinnant), days since 1970-01-01. */
    z = (long)days + 719468L;
    era = z / 146097L;
    doe = z - era * 146097L;
    yoe = (doe - doe / 1460L + doe / 36524L - doe / 146096L) / 365L;
    y = yoe + era * 400L;
    doy = doe - (365L * yoe + yoe / 4L - yoe / 100L);
    mp = (5L * doy + 2L) / 153L;
    d = doy - (153L * mp + 2L) / 5L + 1L;
    m = mp < 10L ? mp + 3L : mp - 9L;
    if (m <= 2L) { y++; }
    if (y > 2107L) { y = 2107L; m = 12L; d = 31L; secs = 86399u; }
    *date = (uint16_t)(((y - 1980L) << 9) | (m << 5) | d);
    *time = (uint16_t)(((secs / 3600u) << 11) | (((secs / 60u) % 60u) << 5) | ((secs % 60u) / 2u));
}

static void dirent(uint8_t *e, const char name11[11], uint8_t attr, uint32_t cluster,
                   uint32_t size, uint16_t date, uint16_t time)
{
    memset(e, 0, 32);
    memcpy(e, name11, 11);
    e[11] = attr;
    put16(e + 14, time);          /* creation time */
    put16(e + 16, date);          /* creation date */
    put16(e + 18, date);          /* last access date */
    put16(e + 20, cluster >> 16); /* high word, FAT32 only; zero for FAT16 */
    put16(e + 22, time);          /* write time */
    put16(e + 24, date);          /* write date */
    put16(e + 26, cluster & 0xFFFFu);
    put32(e + 28, size);
}

static void boot_sector(uint8_t *b, const uint8_t uuid[16])
{
    memset(b, 0, SEC);
    b[0] = 0xEB; b[2] = 0x90;
    memcpy(b + 3, "MSDOS5.0", 8);
    put16(b + 11, SEC);
    b[13] = (uint8_t)SEC_PER_CLUS;
    put16(b + 14, RSVD_SECS);
    b[16] = (uint8_t)NUM_FATS;
    put16(b + 17, ROOT_ENTRIES);
    b[21] = 0xF8;                                   /* fixed media */
    put16(b + 24, 63u);                             /* sectors per track */
    put16(b + 26, 255u);                            /* heads */
    put32(b + 28, LAYOUT_P1_START);                 /* hidden sectors */
#if LAYOUT_FAT_BITS == 16
    b[1] = 0x3C;
    put16(b + 19, TOTAL_SECS < 0x10000u ? TOTAL_SECS : 0u);
    put32(b + 32, TOTAL_SECS < 0x10000u ? 0u : TOTAL_SECS);
    put16(b + 22, FAT_SECS);
    b[36] = 0x80;                                   /* drive number */
    b[38] = 0x29;                                   /* extended boot signature */
    memcpy(b + 39, uuid + 4, 4);                    /* volume ID */
    memcpy(b + 43, VOLUME_LABEL, 11);
    memcpy(b + 54, "FAT16   ", 8);
#else
    b[1] = 0x58;
    put32(b + 32, TOTAL_SECS);
    put32(b + 36, FAT_SECS);
    put32(b + 44, ROOT_CLUSTER);
    put16(b + 48, 1u);                              /* FSInfo sector */
    put16(b + 50, 6u);                              /* backup boot sector */
    b[64] = 0x80;
    b[66] = 0x29;
    memcpy(b + 67, uuid + 4, 4);
    memcpy(b + 71, VOLUME_LABEL, 11);
    memcpy(b + 82, "FAT32   ", 8);
#endif
    b[510] = 0x55; b[511] = 0xAA;
}

#if LAYOUT_FAT_BITS == 32
static void fsinfo_sector(uint8_t *b)
{
    memset(b, 0, SEC);
    put32(b + 0, 0x41615252u);
    put32(b + 484, 0x61417272u);
    put32(b + 488, CLUSTERS - 2u);                  /* root and README in use */
    put32(b + 492, README_CLUSTER + 1u);
    put32(b + 508, 0xAA550000u);
}
#endif

int fat_build_p1(fat_put_fn put, void *user, const char *label,
                 const uint8_t uuid[16], uint32_t epoch)
{
    uint8_t s[SEC];
    char readme[SEC_PER_CLUS * SEC];
    uint32_t readme_len = fat_readme(readme, sizeof readme, label);
    uint16_t date, time;
    uint32_t i, f;
    int rc;

    if (readme_len == 0) { return -1; }
    fat_stamp(epoch, &date, &time);

    /* Reserved region. */
    for (i = 0; i < RSVD_SECS; i++) {
        memset(s, 0, SEC);
        if (i == 0u) { boot_sector(s, uuid); }
#if LAYOUT_FAT_BITS == 32
        if (i == 6u) { boot_sector(s, uuid); }
        if (i == 1u || i == 7u) { fsinfo_sector(s); }
#endif
        if ((rc = put(user, i, s)) != 0) { return rc; }
    }

    /* Both FATs, in full: stale bytes in a FAT are allocated clusters. */
    for (f = 0; f < NUM_FATS; f++) {
        for (i = 0; i < FAT_SECS; i++) {
            memset(s, 0, SEC);
            if (i == 0u) {
#if LAYOUT_FAT_BITS == 16
                put16(s + 0, 0xFFF8u);
                put16(s + 2, 0xFFFFu);
                put16(s + 2u * README_CLUSTER, 0xFFFFu);     /* end of chain */
#else
                put32(s + 0, 0x0FFFFFF8u);
                put32(s + 4, 0x0FFFFFFFu);
                put32(s + 4u * ROOT_CLUSTER, 0x0FFFFFFFu);
                put32(s + 4u * README_CLUSTER, 0x0FFFFFFFu);
#endif
            }
            if ((rc = put(user, RSVD_SECS + f * FAT_SECS + i, s)) != 0) { return rc; }
        }
    }

    /* Root directory: the fixed FAT16 region, or the FAT32 root cluster. */
    {
#if LAYOUT_FAT_BITS == 16
        uint32_t first = RSVD_SECS + NUM_FATS * FAT_SECS, count = ROOT_SECS;
#else
        uint32_t first = DATA_START + (ROOT_CLUSTER - 2u) * SEC_PER_CLUS, count = SEC_PER_CLUS;
#endif
        for (i = 0; i < count; i++) {
            memset(s, 0, SEC);
            if (i == 0u) {
                dirent(s, VOLUME_LABEL, 0x08, 0, 0, date, time);
                dirent(s + 32, "README  TXT", 0x20, README_CLUSTER, readme_len, date, time);
            }
            if ((rc = put(user, first + i, s)) != 0) { return rc; }
        }
    }

    /* README.TXT's cluster. */
    for (i = 0; i < SEC_PER_CLUS; i++) {
        uint32_t off = i * SEC;
        memset(s, 0, SEC);
        if (off < readme_len) {
            memcpy(s, readme + off, readme_len - off < SEC ? readme_len - off : SEC);
        }
        if ((rc = put(user, DATA_START + (README_CLUSTER - 2u) * SEC_PER_CLUS + i, s)) != 0) { return rc; }
    }
    return 0;
}
