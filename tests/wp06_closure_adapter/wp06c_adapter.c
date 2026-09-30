/*
 * WP-06 R52 closure-gap product adapter.
 *
 * Software-owned binding for the imported verifier package
 * tests/wp06_closure_r52. Public header only; it does not import the oracle
 * and decides nothing. One invocation runs one gap_plan.json case on a fresh
 * flat device and prints one wp06-r52-observation-v1 JSON object: public
 * calls, every device callback in order, and named raw snapshots.
 *
 * Usage: wp06c_adapter CASE_ID
 */
#include "tape.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BLOCK 512u
#define SLOT_BLOCKS 128u
#define LBA_A0 8u
#define LBA_A1 136u
#define LBA_B0 264u
#define LBA_B1 392u
#define LBA_CHUNK_BASE 2048u
#define CHUNK_BLOCKS 1024u
#define CHUNK_FRAMES 131072u
/* Large enough that each long operation here completes in one call. */
#define BIG_BUDGET (1u << 20)
#define RECORD_FRAMES 10u

/* Independently chosen cartridge identity: ASCII "WP06-R52-closure". */
static const uint8_t k_uuid[16] = {0x57,0x50,0x30,0x36,0x2d,0x52,0x35,0x32,0x2d,0x63,0x6c,0x6f,0x73,0x75,0x72,0x65};

static unsigned char *g_media;
static uint32_t g_block_count;

/* ------------------------------------------------------------------------ */
/* growable text buffer                                                      */
/* ------------------------------------------------------------------------ */

struct buf { char *p; size_t len, cap; };

static void buf_add(struct buf *b, const char *s, size_t n)
{
    if (b->len + n + 1u > b->cap) {
        while (b->len + n + 1u > b->cap) b->cap = b->cap ? b->cap * 2u : 4096u;
        b->p = realloc(b->p, b->cap);
        if (b->p == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    }
    memcpy(b->p + b->len, s, n);
    b->len += n;
    b->p[b->len] = '\0';
}

static void buf_str(struct buf *b, const char *s) { buf_add(b, s, strlen(s)); }

static void buf_hex(struct buf *b, const unsigned char *p, size_t n)
{
    static const char d[] = "0123456789abcdef";
    size_t i;
    char two[2];
    for (i = 0u; i < n; ++i) {
        two[0] = d[p[i] >> 4];
        two[1] = d[p[i] & 15u];
        buf_add(b, two, 2u);
    }
}

/* ------------------------------------------------------------------------ */
/* callback trace and call records                                           */
/* ------------------------------------------------------------------------ */

static struct buf g_events, g_calls, g_snaps;
static const char *g_step = "setup";
static unsigned g_ordinal;

/* `data`, when non-NULL, is the `count` blocks written, emitted as lowercase hex. */
static void log_event(const char *op, bool has_lba, uint32_t lba, uint32_t count, int rc,
                      const unsigned char *data)
{
    char s[200];
    if (has_lba)
        snprintf(s, sizeof s, "%s{\"step\":\"%s\",\"op\":\"%s\",\"lba\":%lu,\"count\":%lu,\"ordinal\":%u,\"result\":%d",
                 g_ordinal ? "," : "", g_step, op, (unsigned long)lba, (unsigned long)count, g_ordinal + 1u, rc);
    else
        snprintf(s, sizeof s, "%s{\"step\":\"%s\",\"op\":\"%s\",\"ordinal\":%u,\"result\":%d",
                 g_ordinal ? "," : "", g_step, op, g_ordinal + 1u, rc);
    ++g_ordinal;
    buf_str(&g_events, s);
    if (data != NULL) {
        buf_str(&g_events, ",\"data\":\"");
        buf_hex(&g_events, data, (size_t)count * BLOCK);
        buf_str(&g_events, "\"");
    }
    buf_str(&g_events, "}");
}

static int cb_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    (void)v;
    if (dst == NULL || count == 0u || (uint64_t)lba + count > g_block_count) {
        log_event("read", true, lba, count, -1, NULL);
        return -1;
    }
    memcpy(dst, g_media + (size_t)lba * BLOCK, (size_t)count * BLOCK);
    log_event("read", true, lba, count, 0, NULL);
    return 0;
}

static int cb_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    (void)v;
    if (src == NULL || count == 0u || (uint64_t)lba + count > g_block_count) {
        log_event("write", true, lba, count, -1, NULL);
        return -1;
    }
    memcpy(g_media + (size_t)lba * BLOCK, src, (size_t)count * BLOCK);
    /* ADAPTER.md (R53): metadata and mirror writes carry the bytes written. */
    log_event("write", true, lba, count, 0,
              lba < LBA_CHUNK_BASE || lba == g_block_count - 1u ? (const unsigned char *)src : NULL);
    return 0;
}

static int cb_flush(void *v)
{
    (void)v;
    log_event("flush", false, 0u, 0u, 0, NULL);
    return 0;
}

static const char *rname(tape_result r)
{
    switch (r) {
    case TAPE_OK: return "TAPE_OK";
    case TAPE_ERR_IO: return "TAPE_ERR_IO";
    case TAPE_ERR_BAD_MAGIC: return "TAPE_ERR_BAD_MAGIC";
    case TAPE_ERR_CRC: return "TAPE_ERR_CRC";
    case TAPE_ERR_VERSION: return "TAPE_ERR_VERSION";
    case TAPE_ERR_UNSUPPORTED_STATE: return "TAPE_ERR_UNSUPPORTED_STATE";
    case TAPE_ERR_GEOMETRY: return "TAPE_ERR_GEOMETRY";
    case TAPE_ERR_INCOMPLETE: return "TAPE_ERR_INCOMPLETE";
    case TAPE_ERR_INCONSISTENT: return "TAPE_ERR_INCONSISTENT";
    case TAPE_ERR_NO_VALID_INDEX: return "TAPE_ERR_NO_VALID_INDEX";
    case TAPE_ERR_READ_ONLY: return "TAPE_ERR_READ_ONLY";
    case TAPE_ERR_CARTRIDGE_FULL: return "TAPE_ERR_CARTRIDGE_FULL";
    case TAPE_ERR_INDEX_FULL: return "TAPE_ERR_INDEX_FULL";
    case TAPE_ERR_DEST_TOO_SMALL: return "TAPE_ERR_DEST_TOO_SMALL";
    case TAPE_ERR_SEQUENCE_EXHAUSTED: return "TAPE_ERR_SEQUENCE_EXHAUSTED";
    case TAPE_ERR_FAULTED: return "TAPE_ERR_FAULTED";
    case TAPE_ERR_NOT_MOUNTED: return "TAPE_ERR_NOT_MOUNTED";
    case TAPE_ERR_BUSY: return "TAPE_ERR_BUSY";
    case TAPE_ERR_UNDERRUN: return "TAPE_ERR_UNDERRUN";
    case TAPE_ERR_INVALID_ARG: return "TAPE_ERR_INVALID_ARG";
    default: return "TAPE_ERR_UNKNOWN";
    }
}

/* One public call record; `extra` is "" or a leading-comma list of fields. */
static void call(const char *fn, tape_result r, const char *extra)
{
    char s[300];
    snprintf(s, sizeof s, "%s{\"step\":\"%s\",\"fn\":\"%s\",\"result\":\"%s\"%s}",
             g_calls.len ? "," : "", g_step, fn, rname(r), extra);
    buf_str(&g_calls, s);
}

/* ------------------------------------------------------------------------ */
/* raw media, written and read directly, outside callback accounting         */
/* ------------------------------------------------------------------------ */

static void wr16(unsigned char *p, uint32_t v) { p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8); }

static void wr32(unsigned char *p, uint32_t v)
{
    p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8);
    p[2] = (unsigned char)(v >> 16); p[3] = (unsigned char)(v >> 24);
}

static void wr64(unsigned char *p, uint64_t v) { wr32(p, (uint32_t)v); wr32(p + 4, (uint32_t)(v >> 32)); }

static uint32_t crc32_update(uint32_t c, const unsigned char *p, size_t n)
{
    size_t i;
    unsigned k;
    for (i = 0u; i < n; ++i) {
        c ^= p[i];
        for (k = 0u; k < 8u; ++k) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return c;
}

static unsigned char *blk(uint32_t lba) { return g_media + (size_t)lba * BLOCK; }

struct run { uint32_t first, start, count; };

/* tapefs §5: header block, entry array from block 1, CRC over header 0..59 + entries. */
static void put_slot(uint32_t lba, uint32_t sequence, unsigned side, const struct run *runs, uint32_t n)
{
    unsigned char *h = blk(lba), *e = blk(lba + 1u);
    uint64_t total = 0u;
    uint32_t i, c;
    memcpy(h, "TAPEIDX\x01", 8);
    wr32(h + 8, sequence);
    h[12] = (unsigned char)side;
    wr32(h + 16, n);
    for (i = 0u; i < n; ++i) {
        wr32(e + 12u * i, runs[i].first);
        wr32(e + 12u * i + 4u, runs[i].start);
        wr32(e + 12u * i + 8u, runs[i].count);
        total += runs[i].count;
    }
    wr64(h + 20, total);
    c = crc32_update(0xFFFFFFFFu, h, 60u);
    c = crc32_update(c, e, (size_t)n * 12u);
    wr32(h + 60, c ^ 0xFFFFFFFFu);
}

/* tapefs §2: the smallest label whose ceiling derives exactly total_chunks. */
static uint32_t nominal_for(uint32_t total_chunks)
{
    uint32_t n = (uint32_t)(((uint64_t)(total_chunks - 1u) * CHUNK_FRAMES) / 44100u) + 1u;
    uint64_t derived = ((uint64_t)n * 44100u + CHUNK_FRAMES - 1u) / CHUNK_FRAMES;
    if (derived != total_chunks) { fprintf(stderr, "no label derives %lu chunks\n", (unsigned long)total_chunks); exit(3); }
    return n;
}

/* A fully populated tapefs §4 superblock, primary and mirror identical. */
static void put_superblock(uint32_t total_chunks, uint32_t high, uint32_t stage, uint32_t staging)
{
    unsigned char *sb = blk(0u);
    memcpy(sb, "TAPEFS\0\x01", 8);
    wr16(sb + 8, 1u);
    wr16(sb + 10, 0u);
    wr32(sb + 12, 10u);                      /* sb_generation */
    sb[16] = 0u;
    memcpy(sb + 20, k_uuid, 16);
    wr32(sb + 36, 44100u);
    wr16(sb + 40, 2u);
    wr16(sb + 42, 16u);
    wr32(sb + 44, 524288u);
    wr32(sb + 48, nominal_for(total_chunks));
    wr32(sb + 52, total_chunks);
    wr32(sb + 56, high);
    wr32(sb + 60, 65536u);
    wr32(sb + 64, LBA_A0);
    wr32(sb + 68, LBA_A1);
    wr32(sb + 72, LBA_B0);
    wr32(sb + 76, LBA_B1);
    wr32(sb + 80, LBA_CHUNK_BASE);
    wr32(sb + 84, g_block_count - 1u);
    memcpy(sb + 88, "WP06-R52", 8);
    wr32(sb + 120, 1u);
    wr32(sb + 124, stage);
    wr32(sb + 128, staging);
    wr32(sb + 508, crc32_update(0xFFFFFFFFu, sb, 508u) ^ 0xFFFFFFFFu);
    memcpy(blk(g_block_count - 1u), sb, BLOCK);
}

/* Distinct non-zero audio in every chunk a fixture references. */
static void fill_chunk(uint32_t chunk)
{
    uint32_t i;
    unsigned char *p = blk(LBA_CHUNK_BASE + chunk * CHUNK_BLOCKS);
    for (i = 0u; i < CHUNK_FRAMES; ++i) {
        wr16(p + 4u * i, (uint32_t)(uint16_t)(int16_t)(int32_t)((chunk + 1u) * 1000u + (i & 255u)));
        wr16(p + 4u * i + 2u, (uint32_t)(uint16_t)(int16_t)(-(int32_t)((chunk + 1u) * 1000u + (i & 255u))));
    }
}

static void media_alloc(uint32_t total_chunks)
{
    g_block_count = LBA_CHUNK_BASE + total_chunks * CHUNK_BLOCKS + 1u;
    g_media = calloc(g_block_count, BLOCK);
    if (g_media == NULL) { fprintf(stderr, "oom\n"); exit(3); }
}

/*
 * The five gap_plan fixtures. Every stage-1 fixture matches tapefs §9.3.3 row 1
 * (live A a single {S,0,N}, live B byte-identical) with S = 2 and H = S + len = 3,
 * unless it is degraded-B, where §4.2 step 2 skips the stage oracle.
 */
static void build_fixture(const char *name)
{
    static const struct run staged[1] = {{2u, 0u, CHUNK_FRAMES}};
    if (strcmp(name, "stage1_row1") == 0 || strcmp(name, "stage1_row1_no_destination") == 0) {
        /* No destination: total_chunks == H, so no run at or above H exists. */
        uint32_t chunks = strcmp(name, "stage1_row1") == 0 ? 8u : 3u;
        media_alloc(chunks);
        put_superblock(chunks, 3u, 1u, 2u);
        put_slot(LBA_A0, 5u, 0u, staged, 1u);
        put_slot(LBA_B0, 6u, 1u, staged, 1u);
        fill_chunk(2u);
    } else if (strcmp(name, "stage1_degraded_absent") == 0) {
        media_alloc(8u);
        put_superblock(8u, 3u, 1u, 2u);
        put_slot(LBA_A0, 5u, 0u, staged, 1u);
        fill_chunk(2u);
    } else if (strcmp(name, "stage1_degraded_divergent") == 0) {
        static const struct run shorter[1] = {{2u, 0u, CHUNK_FRAMES - 1u}};
        media_alloc(8u);
        put_superblock(8u, 3u, 1u, 2u);
        put_slot(LBA_A0, 5u, 0u, staged, 1u);
        put_slot(LBA_B0, 6u, 1u, staged, 1u);
        put_slot(LBA_B1, 6u, 1u, shorter, 1u);
        fill_chunk(2u);
    } else if (strcmp(name, "sideA_live_dense_fragmented_B") == 0) {
        /* ADAPTER.md (R53) floor fixture. Side A is one chunk under H = 2. Live B
           is fragmented (three runs, so promote takes the allocating phase-1 path,
           not adopt-in-place) and densely occupies every chunk in [H, floor):
           it references A's chunk 0, then owns chunks 2 and 3; floor = 4. Its
           timeline is 2 x CHUNK_FRAMES + RECORD_FRAMES frames, so len = 3. */
        static const struct run a[1] = {{0u, 0u, CHUNK_FRAMES}};
        static const struct run b[3] = {{0u, 0u, CHUNK_FRAMES}, {2u, 0u, CHUNK_FRAMES},
                                        {3u, 0u, RECORD_FRAMES}};
        media_alloc(12u);
        put_superblock(12u, 2u, 0u, 0u);
        put_slot(LBA_A0, 5u, 0u, a, 1u);
        put_slot(LBA_B0, 6u, 1u, b, 3u);
        fill_chunk(0u);
        fill_chunk(2u);
        fill_chunk(3u);
    } else {
        fprintf(stderr, "unknown fixture %s\n", name);
        exit(2);
    }
}

static void snapshot(const char *name)
{
    static const struct { const char *key; uint32_t lba; } slots[4] = {
        {"A0", LBA_A0}, {"A1", LBA_A1}, {"B0", LBA_B0}, {"B1", LBA_B1}};
    unsigned i;
    buf_str(&g_snaps, g_snaps.len ? ",\"" : "\"");
    buf_str(&g_snaps, name);
    buf_str(&g_snaps, "\":{\"primary\":\"");
    buf_hex(&g_snaps, blk(0u), BLOCK);
    buf_str(&g_snaps, "\",\"mirror\":\"");
    buf_hex(&g_snaps, blk(g_block_count - 1u), BLOCK);
    for (i = 0u; i < 4u; ++i) {
        buf_str(&g_snaps, "\",\"");
        buf_str(&g_snaps, slots[i].key);
        buf_str(&g_snaps, "\":\"");
        buf_hex(&g_snaps, blk(slots[i].lba), (size_t)SLOT_BLOCKS * BLOCK);
    }
    buf_str(&g_snaps, "\"}");
}

/* ------------------------------------------------------------------------ */
/* instance and public-call helpers                                          */
/* ------------------------------------------------------------------------ */

static unsigned char *g_mem, *g_play, *g_rec;
static size_t g_mem_len;
static tape_dev g_x;
static tape *g_t;

static void inst_new(void)
{
    tape_result r;
    memset(g_mem, 0, g_mem_len);
    memset(g_play, 0, TAPE_PLAY_RING_MIN);
    memset(g_rec, 0, TAPE_REC_RING_MIN);
    g_x.read = cb_read;
    g_x.write = cb_write;
    g_x.flush = cb_flush;
    g_x.ctx = NULL;
    g_x.block_count = g_block_count;
    g_t = NULL;
    r = tape_init(g_mem, g_mem_len, &g_x, g_play, TAPE_PLAY_RING_MIN, g_rec, TAPE_REC_RING_MIN, &g_t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init %s\n", rname(r)); exit(3); }
}

static void do_mount(tape_side side)
{
    tape_result r = tape_mount(g_t, side, 0u, NULL);
    call("tape_mount", r, side == TAPE_SIDE_A ? ",\"side\":\"A\"" : ",\"side\":\"B\"");
}

static void do_info(void)
{
    tape_info info;
    tape_result r;
    memset(&info, 0, sizeof info);
    r = tape_get_info(g_t, &info);
    call("tape_get_info", r, info.side_b_valid ? ",\"side_b_valid\":true" : ",\"side_b_valid\":false");
}

static void do_unmount(void)
{
    uint64_t pos = 0u;
    call("tape_unmount", tape_unmount(g_t, &pos), "");
}

/* ADAPTER.md: drive until more_work == false, every call under one step. */
static void do_long(bool promote)
{
    unsigned guard = 0u;
    for (;;) {
        bool more = false;
        tape_result r = promote ? tape_promote(g_t, BIG_BUDGET, &more, NULL, NULL)
                                : tape_respool(g_t, BIG_BUDGET, &more);
        call(promote ? "tape_promote" : "tape_respool", r, more ? ",\"more_work\":true" : ",\"more_work\":false");
        if (r != TAPE_OK || !more || ++guard > 100000u) break;
    }
}

/* ------------------------------------------------------------------------ */
/* cases                                                                     */
/* ------------------------------------------------------------------------ */

static void run_case(const char *id)
{
    if (strcmp(id, "E-SIDEA-REFUSE") == 0) {
        build_fixture("stage1_row1");
        snapshot("before");
        inst_new();
        g_step = "mount";    do_mount(TAPE_SIDE_A);
        g_step = "exercise"; call("tape_arm", tape_arm(g_t, TAPE_REC_OVERWRITE), "");
        snapshot("after");
    } else if (strcmp(id, "E-RESPOOL-FULL") == 0) {
        build_fixture("stage1_row1_no_destination");
        snapshot("before");
        inst_new();
        g_step = "mount";    do_mount(TAPE_SIDE_B);
        g_step = "exercise"; do_long(false);
        snapshot("after");
    } else if (strcmp(id, "E-RECORD-PROMOTE") == 0) {
        static int16_t in[2u * RECORD_FRAMES];
        uint32_t i, accepted = 0u;
        char s[64];
        bool more = false;
        for (i = 0u; i < RECORD_FRAMES; ++i) { in[2u * i] = (int16_t)(7000 + (int)i); in[2u * i + 1u] = (int16_t)(-7000 - (int)i); }
        build_fixture("stage1_row1");
        snapshot("before");
        inst_new();
        g_step = "mount";   do_mount(TAPE_SIDE_B);
        g_step = "arm";     call("tape_arm", tape_arm(g_t, TAPE_REC_OVERWRITE), "");
        snapshot("after_arm");
        g_step = "record";
        {
            tape_result r = tape_feed(g_t, in, RECORD_FRAMES, &accepted);
            snprintf(s, sizeof s, ",\"accepted\":%lu", (unsigned long)accepted);
            call("tape_feed", r, s);
            r = tape_service(g_t, BIG_BUDGET, &more);
            call("tape_service", r, more ? ",\"more_work\":true" : ",\"more_work\":false");
        }
        g_step = "commit";  call("tape_commit", tape_commit(g_t), "");
        g_step = "promote"; do_long(true);
        snapshot("after_promote");
        g_step = "remount";
        do_unmount();
        inst_new();
        do_mount(TAPE_SIDE_B);
    } else if (strcmp(id, "F-STAGE-DEGRADED-ABSENT") == 0 || strcmp(id, "F-STAGE-DEGRADED-DIVERGENT") == 0) {
        build_fixture(strcmp(id, "F-STAGE-DEGRADED-ABSENT") == 0 ? "stage1_degraded_absent" : "stage1_degraded_divergent");
        snapshot("before");
        inst_new();
        g_step = "mount";   do_mount(TAPE_SIDE_A); do_info();
        g_step = "reset";   call("tape_reset_side_b", tape_reset_side_b(g_t), "");
        snapshot("after_reset");
        g_step = "remount";
        do_unmount();
        inst_new();
        do_mount(TAPE_SIDE_A);
        do_info();
        snapshot("after_remount");
        g_step = "switch";  call("tape_set_side", tape_set_side(g_t, TAPE_SIDE_B), "");
    } else if (strcmp(id, "F-LIVEB-PROMOTE-FLOOR") == 0 || strcmp(id, "F-LIVEB-RESPOOL-FLOOR") == 0) {
        build_fixture("sideA_live_dense_fragmented_B");
        snapshot("before");
        inst_new();
        g_step = "mount";    do_mount(TAPE_SIDE_A);
        g_step = "exercise"; do_long(strcmp(id, "F-LIVEB-PROMOTE-FLOOR") == 0);
    } else {
        fprintf(stderr, "unknown case %s\n", id);
        exit(2);
    }
}

int main(int argc, char **argv)
{
    struct buf out = {NULL, 0u, 0u};
    char s[200];

    if (argc != 2) { fprintf(stderr, "usage: %s CASE_ID\n", argv[0]); return 2; }
    g_mem_len = tape_instance_size();
    g_mem = calloc(1u, g_mem_len);
    g_play = calloc(1u, TAPE_PLAY_RING_MIN);
    g_rec = calloc(1u, TAPE_REC_RING_MIN);
    if (g_mem == NULL || g_play == NULL || g_rec == NULL) { fprintf(stderr, "oom\n"); return 3; }

    run_case(argv[1]);

    snprintf(s, sizeof s, "{\"schema\":\"wp06-r52-observation-v1\",\"case\":\"%s\",\"block_count\":%lu,\"calls\":[",
             argv[1], (unsigned long)g_block_count);
    buf_str(&out, s);
    buf_add(&out, g_calls.p ? g_calls.p : "", g_calls.len);
    buf_str(&out, "],\"events\":[");
    buf_add(&out, g_events.p ? g_events.p : "", g_events.len);
    buf_str(&out, "],\"snapshots\":{");
    buf_add(&out, g_snaps.p ? g_snaps.p : "", g_snaps.len);
    buf_str(&out, "}}\n");
    fwrite(out.p, 1u, out.len, stdout);
    return 0;
}
