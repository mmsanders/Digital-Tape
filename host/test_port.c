/*
 * test_port.c — unit tests for the WP-14 host port's pure parts.
 *
 * The MBR layout and its verify findings, the §5 safety policy, the §2 path
 * forms, the FAT volume of §3.2 (structure; host/smoke_wp14.sh hands the same
 * bytes to the OS's own FAT checker where one exists) and the partition view.
 * Every rule is exercised with a passing case and a failing one, so a test
 * that always passed would show here as a failure.
 */

#include "layout.h"
#include "safety.h"
#include "hport.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int g_fail, g_n;

static void check(int ok, const char *what)
{
    g_n++;
    if (!ok) { g_fail++; printf("  FAIL  %s\n", what); }
}

static uint32_t get32(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
static uint32_t get16(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1] << 8; }

static const uint8_t UUID[16] = {0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,0x19,0x1a,0x1b,0x1c,0x1d,0x1e,0x1f};

/* ------------------------------------------------------------------ MBR */

static void test_mbr(void)
{
    const uint64_t N = 124735488ull;             /* a 64 GB card's sectors */
    uint8_t m[512], x[512];
    unsigned i;

    check(mbr_build(m, UUID, N) == 0, "mbr_build on a 64 GB card");
    check(m[510] == 0x55 && m[511] == 0xAA, "MBR signature");
    check(memcmp(m + 440, UUID, 4) == 0, "disk signature is the first four UUID bytes");
    check(m[446] == 0 && m[447] == 0xFE && m[448] == 0xFF && m[449] == 0xFF, "entry 1 status and CHS start");
    check(m[450] == LAYOUT_P1_TYPE, "entry 1 type");
    check(m[451] == 0xFE && m[452] == 0xFF && m[453] == 0xFF, "entry 1 CHS end");
    check(get32(m + 454) == 2048u && get32(m + 458) == LAYOUT_P1_SECTORS, "entry 1 start 2048, 16 MiB");
    check(m[466] == 0xDA && get32(m + 470) == LAYOUT_P2_START, "entry 2 type 0xDA at 34816");
    check(get32(m + 474) == (uint32_t)(N - LAYOUT_P2_START), "entry 2 runs to the last sector");
    for (i = 478; i < 510; i++) { if (m[i]) { break; } }
    check(i == 510, "entries 3 and 4 zero");
    check(mbr_is_layout(m, N), "a built MBR is the exact layout");
    check(!mbr_is_layout(m, N + 1), "control: the same MBR on a larger target is not");
    check(mbr_build(m, UUID, LAYOUT_P2_START) != 0, "no MBR when partition 2 would be empty");
    check(mbr_build(m, UUID, LAYOUT_P2_START + 0x100000000ull) != 0, "no MBR when partition 2 exceeds 2^32-1 sectors");

    (void)mbr_build(m, UUID, N);
    /* Every byte of entries 1-4 and the signature is part of recognition... */
    for (i = 446; i < 512; i++) {
        memcpy(x, m, 512);
        x[i] ^= 0x01;
        if (mbr_is_layout(x, N)) { printf("  FAIL  byte %u is not checked\n", i); g_fail++; }
    }
    g_n++;
    /* ...and the bootstrap and disk signature are not. */
    memcpy(x, m, 512);
    x[0] = 0xEB; x[440] ^= 0xFF;
    check(mbr_is_layout(x, N), "bootstrap and disk signature are not part of recognition");

    /* ADR-165 (P2V-005) target-kind candidate rule. FILE = regular file,
       DEV = whole device. Any nonzero byte in 446..507 is a candidate for
       both; the signature 55 AA alone only for a device. */
    memset(x, 0, 512);
    memcpy(x, "TAPEFS", 6);
    x[508] = 0x12; x[509] = 0x34; x[510] = 0x56; x[511] = 0x78;
    check(!mbr_is_mbr_shaped(x, 0) && !mbr_is_mbr_shaped(x, 1), "a bare superblock is a candidate for neither target");
    x[507] = 1;
    check(mbr_is_mbr_shaped(x, 0) && mbr_is_mbr_shaped(x, 1), "a nonzero byte at 507: candidate for both");
    x[507] = 0; x[446] = 0x80;
    check(mbr_is_mbr_shaped(x, 0) && mbr_is_mbr_shaped(x, 1), "a nonzero byte at 446: candidate for both");
    x[446] = 0; x[508] = 0xFF;
    check(!mbr_is_mbr_shaped(x, 0) && !mbr_is_mbr_shaped(x, 1), "bytes 508..509 are not part of the rule");
    /* A bare superblock whose CRC-32 ends 55 AA (about 1 in 65 536): */
    x[510] = 0x55; x[511] = 0xAA;
    check(!mbr_is_mbr_shaped(x, 0), "P2V-005: a file whose superblock CRC ends 55 AA stays bare");
    check(mbr_is_mbr_shaped(x, 1), "control: the same LBA 0 on a whole device is a candidate");
    memset(x, 0, 512); x[510] = 0x55; x[511] = 0xAA;
    check(!mbr_is_mbr_shaped(x, 0) && mbr_is_mbr_shaped(x, 1), "empty partition table + 55 AA: file bare, device candidate");
    memcpy(x, m, 512); x[510] = 0x00; x[511] = 0x00;
    check(mbr_is_mbr_shaped(x, 0) && mbr_is_mbr_shaped(x, 1), "a real MBR with a damaged signature is a candidate for both");
    check(mbr_findings(x, N) == MBR_F_LAYOUT, "a damaged signature is MBR_LAYOUT");

    /* verify findings (#384 Q3) */
    check(mbr_findings(m, N) == 0, "no findings on the exact layout");
    memcpy(x, m, 512); x[0] = 1;
    check(mbr_is_layout(x, N) && mbr_findings(x, N) == MBR_F_LAYOUT, "bootstrap byte: still recognised, but MBR_LAYOUT under verify");
    memcpy(x, m, 512); x[444] = 1;
    check(mbr_findings(x, N) == MBR_F_LAYOUT, "byte 444 nonzero: MBR_LAYOUT");
    memcpy(x, m, 512); x[441] ^= 0xFF;
    check(mbr_findings(x, N) == 0, "a different disk signature is not judged");
    memcpy(x, m, 512); x[450] = 0x0C;
    check(mbr_findings(x, N) == MBR_F_TYPE, "entry 1 type -> PARTITION_TYPE only");
    memcpy(x, m, 512); x[466] = 0x83;
    check(mbr_findings(x, N) == MBR_F_TYPE, "entry 2 type -> PARTITION_TYPE only");
    check(mbr_findings(m, N - 1000) == MBR_F_TRUNCATED, "device shorter than entry 2 -> PARTITION_TRUNCATED only");
    check(mbr_findings(m, N + 1000) == MBR_F_LAYOUT, "entry 2 ending before the last sector -> MBR_LAYOUT");
    memcpy(x, m, 512); x[454] = 0x00; x[455] = 0x10;
    check(mbr_findings(x, N) == MBR_F_LAYOUT, "entry 1 start -> MBR_LAYOUT");
    memcpy(x, m, 512); x[478 + 4] = 0x07;
    check(mbr_findings(x, N) == MBR_F_LAYOUT, "a third entry -> MBR_LAYOUT");
    memcpy(x, m, 512); x[466] = 0x83;
    check(mbr_findings(x, N - 1000) == (MBR_F_TYPE | MBR_F_TRUNCATED), "type and truncation together");
}

/* --------------------------------------------------------------- safety */

static struct device_facts good(void)
{
    struct device_facts f;
    memset(&f, 0, sizeof f);
    f.whole_device = 1; f.removable = 1; f.bytes = 64000000000ull;
    return f;
}

static void test_safety(void)
{
    struct device_facts f;

    f = good();
    check(safety_policy(&f, 0, 0) == REFUSE_NONE, "a removable whole 64 GB card passes");
    check(safety_policy(&f, 1, 1) == REFUSE_NONE, "provision with a matching --erase passes");
    check(safety_policy(&f, 1, 0) == REFUSE_ERASE_NOT_CONFIRMED, "provision without --erase");

    f = good(); f.whole_device = 0;
    check(safety_policy(&f, 0, 0) == REFUSE_NOT_WHOLE_DEVICE, "not a whole device");
    f = good(); f.removable = 0;
    check(safety_policy(&f, 0, 0) == REFUSE_NOT_REMOVABLE, "fixed disk on no SD bus");
    f = good(); f.removable = 0; f.sd_bus = 1;
    check(safety_policy(&f, 0, 0) == REFUSE_NONE, "control: a non-removable disk on an SD bus passes");
    f = good(); f.bytes = SAFETY_TOO_LARGE + 1u;
    check(safety_policy(&f, 0, 0) == REFUSE_TOO_LARGE, "larger than 128 GiB");
    f = good(); f.bytes = SAFETY_TOO_LARGE;
    check(safety_policy(&f, 0, 0) == REFUSE_NONE, "control: exactly 128 GiB passes");
    f = good(); f.holds_os = 1;
    check(safety_policy(&f, 0, 0) == REFUSE_SYSTEM_DISK, "holds the OS");

    f = good(); f.n_mounted = 1; f.mounted[0].partition = 1; f.layout_ok = 1;
    check(safety_policy(&f, 0, 0) == REFUSE_NONE, "only our own partition 1 mounted passes");
    f.layout_ok = 0;
    check(safety_policy(&f, 0, 0) == REFUSE_FOREIGN_MOUNT, "partition 1 mounted on a card that is not our layout");
    f = good(); f.n_mounted = 1; f.mounted[0].partition = 2; f.layout_ok = 1;
    check(safety_policy(&f, 0, 0) == REFUSE_FOREIGN_MOUNT, "partition 2 mounted");
    f = good(); f.n_mounted = 1; f.mounted[0].partition = 0; f.layout_ok = 1;
    check(safety_policy(&f, 0, 0) == REFUSE_FOREIGN_MOUNT, "a volume of unknown partition mounted");
    f = good(); f.n_mounted = SAFETY_MAX_MOUNTS + 1; f.layout_ok = 1;
    check(safety_policy(&f, 0, 0) == REFUSE_FOREIGN_MOUNT, "too many mounts to list");
    f = good(); f.n_mounted = 2; f.mounted[0].partition = 1; f.mounted[1].partition = 1; f.layout_ok = 1;
    check(safety_policy(&f, 0, 0) == REFUSE_NONE, "control: two mounts of partition 1 pass");

    /* §5 order: the first failing rule is the one reported. */
    f = good(); f.whole_device = 0; f.removable = 0; f.holds_os = 1;
    check(safety_policy(&f, 1, 0) == REFUSE_NOT_WHOLE_DEVICE, "order: not-whole before the rest");
    f = good(); f.removable = 0; f.bytes = ~0ull; f.holds_os = 1;
    check(safety_policy(&f, 1, 0) == REFUSE_NOT_REMOVABLE, "order: not-removable before too-large");
    f = good(); f.bytes = ~0ull; f.holds_os = 1;
    check(safety_policy(&f, 1, 0) == REFUSE_TOO_LARGE, "order: too-large before system disk");
    f = good(); f.holds_os = 1; f.n_mounted = 1;
    check(safety_policy(&f, 1, 0) == REFUSE_SYSTEM_DISK, "order: system disk before mounts");
    f = good(); f.n_mounted = 1;
    check(safety_policy(&f, 1, 0) == REFUSE_FOREIGN_MOUNT, "order: mounts before --erase");

    check(strcmp(refusal_id(REFUSE_TOO_LARGE), "REFUSE_TOO_LARGE") == 0, "refusal ids");
    check(refusal_sentence(REFUSE_SYSTEM_DISK)[0] != '\0', "refusal sentences");
}

/* ------------------------------------------------------------ path forms */

static void test_paths(void)
{
#if defined(_WIN32)
    check(path_is_whole_form("\\\\.\\PhysicalDrive2"), "\\\\.\\PhysicalDrive2 is whole");
    check(path_is_whole_form("\\\\.\\physicaldrive12"), "case-insensitive PhysicalDrive");
    check(!path_is_whole_form("\\\\.\\PhysicalDrive"), "no number is not whole");
    check(!path_is_whole_form("\\\\.\\E:"), "a drive letter is not whole");
    check(!path_is_whole_form("\\\\?\\Volume{0}"), "a volume GUID path is not whole");
    check(path_is_device_form("E:") && path_is_device_form("E:\\") && path_is_device_form("\\\\.\\E:"), "drive letters are device paths");
    check(!path_is_device_form("C:\\cards\\x.img") && !path_is_device_form("x.img"), "image paths are not");
#elif defined(__APPLE__)
    check(path_is_whole_form("/dev/disk4") && path_is_whole_form("/dev/rdisk4"), "diskN and rdiskN are whole");
    check(!path_is_whole_form("/dev/disk4s1") && !path_is_whole_form("/dev/rdisk4s1"), "slices are not");
    check(!path_is_whole_form("/dev/disk") && !path_is_whole_form("/tmp/disk4"), "no number, or not in /dev");
    check(path_is_device_form("/dev/disk4s1") && !path_is_device_form("card.img"), "device-form");
#else
    check(path_is_whole_form("/dev/sdb") && path_is_whole_form("/dev/sdaa") && path_is_whole_form("/dev/mmcblk0"), "sdX and mmcblkN are whole");
    check(!path_is_whole_form("/dev/sdb1") && !path_is_whole_form("/dev/mmcblk0p1"), "partitions are not");
    check(!path_is_whole_form("/dev/loop0") && !path_is_whole_form("/dev/sd") && !path_is_whole_form("/dev/nvme0n1"), "anything else is not (#384 Q2)");
    check(path_is_device_form("/dev/loop0") && !path_is_device_form("card.img"), "device-form");
#endif
}

/* ------------------------------------------------------------------ FAT */

static uint8_t g_p1[LAYOUT_P1_SECTORS > 40000u ? 1u : LAYOUT_P1_SECTORS][512];
static uint32_t g_last;
static int g_order_ok = 1;

static int put(void *user, uint32_t sector, const uint8_t data[512])
{
    (void)user;
    if (sector >= LAYOUT_P1_SECTORS) { return 1; }
    if (g_last != 0xFFFFFFFFu && sector <= g_last) { g_order_ok = 0; }
    g_last = sector;
    if (LAYOUT_P1_SECTORS <= 40000u) { memcpy(g_p1[sector], data, 512); }
    return 0;
}

static void test_fat(void)
{
    char rd[512];
    const char *want = "This is a Digital Tape cartridge.\r\nLabel: Grieg\r\n"
                       "Please do not format or erase this card on a computer.\r\n"
                       "Use the Digital Tape app to load music onto it.\r\n";
    uint32_t n = fat_readme(rd, sizeof rd, "Grieg");

    check(n == strlen(want) && memcmp(rd, want, n) == 0, "README.TXT bytes, CRLF on every line (#384 Q4)");
    check(fat_readme(rd, 20, "Grieg") == 0, "README refuses a buffer too small");

    g_last = 0xFFFFFFFFu;
    check(fat_build_p1(put, NULL, "Grieg", UUID, 1759622400u) == 0, "fat_build_p1");
    check(g_order_ok, "partition 1 sectors are written in ascending order");
#if LAYOUT_FAT_BITS == 16
    {
        const uint8_t *b = g_p1[0];
        uint32_t rsvd = get16(b + 14), fatsz = get16(b + 22), roots = get16(b + 17), spc = b[13];
        uint32_t tot = get16(b + 19) ? get16(b + 19) : get32(b + 32);
        uint32_t rootsec = rsvd + 2u * fatsz, data = rootsec + (roots * 32u + 511u) / 512u;
        uint32_t clusters = (tot - data) / spc;
        const uint8_t *root = g_p1[rootsec];
        check(b[510] == 0x55 && b[511] == 0xAA && get16(b + 11) == 512u, "boot sector signature, 512-byte sectors");
        check(spc == 4u, "2 KiB clusters (§3.2)");
        check(tot == LAYOUT_P1_SECTORS && get32(b + 28) == LAYOUT_P1_START, "total sectors and hidden sectors");
        check(clusters >= 4085u && clusters <= 65524u, "FAT16 by cluster count");
        check(fatsz * 256u >= clusters + 2u, "the FAT covers every cluster");
        check(memcmp(b + 43, "DIGITALTAPE", 11) == 0 && memcmp(b + 54, "FAT16   ", 8) == 0, "volume label and type string");
        check(memcmp(b + 39, UUID + 4, 4) == 0, "volume ID from the UUID");
        check(get16(g_p1[rsvd]) == 0xFFF8u && get16(g_p1[rsvd] + 4) == 0xFFFFu, "FAT media entry and README end of chain");
        check(memcmp(g_p1[rsvd], g_p1[rsvd + fatsz], 512) == 0, "both FATs identical");
        check(memcmp(root, "DIGITALTAPE", 11) == 0 && root[11] == 0x08, "root: volume label entry");
        check(memcmp(root + 32, "README  TXT", 11) == 0 && root[32 + 11] == 0x20, "root: README.TXT entry");
        check(get16(root + 32 + 26) == 2u && get32(root + 32 + 28) == strlen(want), "README at cluster 2 with its length");
        check(memcmp(g_p1[data], want, strlen(want)) == 0, "README contents in cluster 2");
        /* 2025-10-05T00:00:00Z -> FAT date 2025-10-05, time 00:00:00 */
        check(get16(root + 32 + 24) == (uint32_t)(((2025 - 1980) << 9) | (10 << 5) | 5), "write date from --epoch");
        check(get16(root + 32 + 22) == 0u, "write time from --epoch");
    }
#endif
    {
        /* Epochs before 1980 clamp; determinism: same inputs, same bytes. */
        static uint8_t a[512];
        g_last = 0xFFFFFFFFu;
        check(fat_build_p1(put, NULL, "x", UUID, 0u) == 0, "epoch 0 builds (clamped to 1980)");
        memcpy(a, g_p1[0], 512);
        g_last = 0xFFFFFFFFu;
        (void)fat_build_p1(put, NULL, "x", UUID, 0u);
        check(memcmp(a, g_p1[0], 512) == 0, "deterministic boot sector");
    }
}

/* ------------------------------------------------------------ partview */

static void test_partview(void)
{
    struct hport hp;
    struct partview v;
    tape_dev d;
    uint8_t blk[512];
    const char *img = "test_port_partview.img";

    memset(blk, 0xA5, sizeof blk);
    check(hport_create(&hp, img, 64u * 512u) == 0, "hport_create");
    partview_bind(&v, &d, &hp, 10, 20, 1);
    check(d.block_count == 20u && d.write != NULL, "writable view");
    check(d.write(d.ctx, 0, 1, blk) == 0 && d.flush(d.ctx) == 0, "write and durable flush through the view");
    check(d.write(d.ctx, 19, 1, blk) == 0, "last block of the view");
    check(d.write(d.ctx, 20, 1, blk) != 0 && d.read(d.ctx, 19, 2, blk) != 0, "past the view is refused");
    {
        uint8_t back[512];
        check(hport_read(&hp, 10u * 512u, back, 512) == 0 && back[0] == 0xA5, "view LBA 0 is base 10");
        check(hport_read(&hp, 9u * 512u, back, 512) == 0 && back[0] == 0, "nothing below the base was written");
    }
    partview_bind(&v, &d, &hp, 10, 20, 0);
    check(d.write == NULL, "read-only view has a NULL write callback (WP-36 pattern)");
    check(hport_read(&hp, 64u * 512u - 512u, blk, 512) == 0 && hport_read(&hp, 64u * 512u, blk, 512) != 0,
          "reads past the end of the image fail");
    (void)hport_close(&hp);
    check(hport_open(&hp, img, 0, 0) == 0 && hport_write(&hp, 0, blk, 512) != 0, "a read-only open cannot write");
    (void)hport_close(&hp);
    remove(img);
}

int main(void)
{
    test_mbr();
    test_safety();
    test_paths();
    test_fat();
    test_partview();
    printf("test_port: %d/%d %s\n", g_n - g_fail, g_n, g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
