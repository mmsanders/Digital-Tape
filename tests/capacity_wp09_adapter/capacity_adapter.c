/*
 * WP-09 R52 positive capacity short-accept product adapter.
 *
 * Software-owned binding for the imported verifier package
 * tests/capacity_wp09_r52. Public header only; it does not import the oracle
 * and decides nothing. One invocation runs one plan row on a fresh device and
 * prints one JSON object of raw observations; run_product.py adds the PCM
 * encoding and fixture digest ADAPTER.md names and hands the lines to replay.py.
 *
 * Usage: capacity_adapter MODE AT TOTAL_CHUNKS PREFILL_FRAMES FINAL_REQUESTED
 *                         SERVICE_BUDGET SAMPLE_L SAMPLE_R
 */
#include "tape.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BLOCK 512u
#define LBA_A0 8u
#define LBA_A1 136u
#define LBA_B0 264u
#define LBA_B1 392u
#define LBA_CHUNK_BASE 2048u
#define CHUNK_BLOCKS 1024u
#define CHUNK_FRAMES 131072u
#define FEED_MAX 4096u
/* Half a play ring per render: a whole ring is never available at once. */
#define RENDER_PIECE (TAPE_PLAY_RING_MIN / TAPE_FRAME_BYTES / 2u)
#define SEED_FRAMES 12u
#define SEED_CHUNK 2u
#define A_HIGH_WATER 2u

/* Independently chosen cartridge identity: ASCII "WP09-R52-capshrt". */
static const uint8_t k_uuid[16] = {0x57,0x50,0x30,0x39,0x2d,0x52,0x35,0x32,0x2d,0x63,0x61,0x70,0x73,0x68,0x72,0x74};

/* ------------------------------------------------------------------------ */
/* flat device                                                               */
/* ------------------------------------------------------------------------ */

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
/* callback trace                                                            */
/* ------------------------------------------------------------------------ */

static struct buf g_events;
static const char *g_step = "setup";
static char g_step_buf[32];
static unsigned g_ordinal;

static void set_step(const char *s)
{
    snprintf(g_step_buf, sizeof g_step_buf, "%s", s);
    g_step = g_step_buf;
}

static void log_event(const char *op, bool has_lba, uint32_t lba, uint32_t count, int rc)
{
    char s[200];
    if (has_lba)
        snprintf(s, sizeof s, "%s{\"step\":\"%s\",\"op\":\"%s\",\"lba\":%lu,\"count\":%lu,\"ordinal\":%u,\"rc\":%d}",
                 g_ordinal ? "," : "", g_step, op, (unsigned long)lba, (unsigned long)count, g_ordinal + 1u, rc);
    else
        snprintf(s, sizeof s, "%s{\"step\":\"%s\",\"op\":\"%s\",\"ordinal\":%u,\"rc\":%d}",
                 g_ordinal ? "," : "", g_step, op, g_ordinal + 1u, rc);
    ++g_ordinal;
    buf_str(&g_events, s);
}

static int cb_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    (void)v;
    if (dst == NULL || count == 0u || (uint64_t)lba + count > g_block_count) {
        log_event("read", true, lba, count, -1);
        return -1;
    }
    memcpy(dst, g_media + (size_t)lba * BLOCK, (size_t)count * BLOCK);
    log_event("read", true, lba, count, 0);
    return 0;
}

static int cb_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    (void)v;
    if (src == NULL || count == 0u || (uint64_t)lba + count > g_block_count) {
        log_event("write", true, lba, count, -1);
        return -1;
    }
    memcpy(g_media + (size_t)lba * BLOCK, src, (size_t)count * BLOCK);
    log_event("write", true, lba, count, 0);
    return 0;
}

static int cb_flush(void *v)
{
    (void)v;
    log_event("flush", false, 0u, 0u, 0);
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

/* ------------------------------------------------------------------------ */
/* raw fixture, written directly to media outside callback accounting        */
/* ------------------------------------------------------------------------ */

static void wr16(unsigned char *p, uint32_t v) { p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8); }

static void wr32(unsigned char *p, uint32_t v)
{
    p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8);
    p[2] = (unsigned char)(v >> 16); p[3] = (unsigned char)(v >> 24);
}

static void wr64(unsigned char *p, uint64_t v) { wr32(p, (uint32_t)v); wr32(p + 4, (uint32_t)(v >> 32)); }

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

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

/* tapefs §5: header block, entry array from block 1, CRC over header 0..59 + entries. */
static void put_slot(uint32_t lba, uint32_t sequence, unsigned side,
                     const uint32_t (*entries)[3], uint32_t count)
{
    unsigned char *h = blk(lba), *e = blk(lba + 1u);
    uint64_t total = 0u;
    uint32_t i, c;
    memcpy(h, "TAPEIDX\x01", 8);
    wr32(h + 8, sequence);
    h[12] = (unsigned char)side;
    wr32(h + 16, count);
    for (i = 0u; i < count; ++i) {
        wr32(e + 12u * i, entries[i][0]);
        wr32(e + 12u * i + 4u, entries[i][1]);
        wr32(e + 12u * i + 8u, entries[i][2]);
        total += entries[i][2];
    }
    wr64(h + 20, total);
    c = crc32_update(0xFFFFFFFFu, h, 60u);
    c = crc32_update(c, e, (size_t)count * 12u);
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

static void build_fixture(uint32_t total_chunks)
{
    static const uint32_t seed_entry[1][3] = {{SEED_CHUNK, 0u, SEED_FRAMES}};
    unsigned char *sb = blk(0u);
    uint32_t i;

    memcpy(sb, "TAPEFS\0\x01", 8);
    wr16(sb + 8, 1u);                        /* version_major */
    wr16(sb + 10, 0u);                       /* version_minor */
    wr32(sb + 12, 7u);                       /* sb_generation */
    sb[16] = 0u;                             /* state VALID */
    memcpy(sb + 20, k_uuid, 16);
    wr32(sb + 36, 44100u);
    wr16(sb + 40, 2u);
    wr16(sb + 42, 16u);
    wr32(sb + 44, 524288u);
    wr32(sb + 48, nominal_for(total_chunks));
    wr32(sb + 52, total_chunks);
    wr32(sb + 56, A_HIGH_WATER);
    wr32(sb + 60, 65536u);
    wr32(sb + 64, LBA_A0);
    wr32(sb + 68, LBA_A1);
    wr32(sb + 72, LBA_B0);
    wr32(sb + 76, LBA_B1);
    wr32(sb + 80, LBA_CHUNK_BASE);
    wr32(sb + 84, g_block_count - 1u);
    memcpy(sb + 88, "WP09-R52", 8);
    wr32(sb + 120, 1u);                      /* format_epoch */
    wr32(sb + 508, crc32_update(0xFFFFFFFFu, sb, 508u) ^ 0xFFFFFFFFu);
    memcpy(blk(g_block_count - 1u), sb, BLOCK);

    /* Side A must be selectable for any mount (tapefs §4.2 step 1): an empty
       Side-A index. Live B0 at sequence 3 holds the seed run; B1 stays zero. */
    put_slot(LBA_A0, 1u, 0u, NULL, 0u);
    put_slot(LBA_B0, 3u, 1u, seed_entry, 1u);

    for (i = 0u; i < SEED_FRAMES; ++i) {
        unsigned char *f = blk(LBA_CHUNK_BASE + SEED_CHUNK * CHUNK_BLOCKS) + 4u * i;
        wr16(f, (uint32_t)(uint16_t)(int16_t)(100 + (int)i));
        wr16(f + 2, (uint32_t)(uint16_t)(int16_t)(-200 - (int)i));
    }
}

static void raw_slot(struct buf *b, const char *name, uint32_t lba)
{
    const unsigned char *h = blk(lba);
    uint32_t count = rd32(h + 16);
    if (memcmp(h, "TAPEIDX\x01", 8) != 0 || count > 4096u) count = 0u;
    buf_str(b, ",\"");
    buf_str(b, name);
    buf_str(b, "\":{\"header\":\"");
    buf_hex(b, h, BLOCK);
    buf_str(b, "\",\"entries\":\"");
    buf_hex(b, blk(lba + 1u), (size_t)count * 12u);
    buf_str(b, "\"}");
}

static void raw_state(struct buf *b, const char *key)
{
    buf_str(b, ",\"");
    buf_str(b, key);
    buf_str(b, "\":{\"primary\":\"");
    buf_hex(b, blk(0u), BLOCK);
    buf_str(b, "\",\"mirror\":\"");
    buf_hex(b, blk(g_block_count - 1u), BLOCK);
    buf_str(b, "\"");
    raw_slot(b, "B0", LBA_B0);
    raw_slot(b, "B1", LBA_B1);
    buf_str(b, "}");
}

/* ------------------------------------------------------------------------ */
/* instance                                                                  */
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

/* ------------------------------------------------------------------------ */
/* one plan row                                                              */
/* ------------------------------------------------------------------------ */

static unsigned g_service_counter;
static uint32_t g_budget;

/* Service to more_work == false with the row's budget; one record per call. */
static void service_list(struct buf *line)
{
    unsigned guard = 0u;
    bool first = true;
    buf_str(line, ",\"service\":[");
    for (;;) {
        char label[32], s[200];
        bool more = false;
        tape_result r;
        snprintf(label, sizeof label, "service-%04u", g_service_counter++);
        set_step(label);
        r = tape_service(g_t, g_budget, &more);
        snprintf(s, sizeof s, "%s{\"label\":\"%s\",\"budget\":%lu,\"result\":\"%s\",\"more_work\":%s}",
                 first ? "" : ",", label, (unsigned long)g_budget, rname(r), more ? "true" : "false");
        buf_str(line, s);
        first = false;
        if (r != TAPE_OK || !more || ++guard > 1000000u) break;
    }
    buf_str(line, "]");
}

static tape_result info_json(struct buf *line, const char *key)
{
    tape_info info;
    tape_result r;
    char s[300];
    memset(&info, 0, sizeof info);
    r = tape_get_info(g_t, &info);
    snprintf(s, sizeof s, ",\"%s\":{\"result\":\"%s\",\"total_frames\":%llu,\"entry_count\":%lu,"
             "\"total_chunks\":%lu,\"free_chunks\":%lu}",
             key, rname(r), (unsigned long long)info.total_frames, (unsigned long)info.entry_count,
             (unsigned long)info.total_chunks, (unsigned long)info.free_chunks);
    buf_str(line, s);
    return r;
}

static uint32_t arg_u32(const char *s)
{
    char *end;
    unsigned long v = strtoul(s, &end, 10);
    if (*s == '\0' || *end != '\0' || v > 0xFFFFFFFFul) { fprintf(stderr, "bad number %s\n", s); exit(2); }
    return (uint32_t)v;
}

static int16_t arg_s16(const char *s)
{
    char *end;
    long v = strtol(s, &end, 10);
    if (*s == '\0' || *end != '\0' || v < -32768L || v > 32767L) { fprintf(stderr, "bad sample %s\n", s); exit(2); }
    return (int16_t)v;
}

int main(int argc, char **argv)
{
    static int16_t in[2u * FEED_MAX];
    struct buf line = {NULL, 0u, 0u};
    tape_rec_mode mode;
    uint32_t at, total_chunks, prefill, final_requested, fed = 0u, accepted, i;
    unsigned feed_index = 0u, before;
    int16_t sl, sr;
    tape_result r;
    uint64_t pos, total, done = 0u;
    int16_t *pcm;
    unsigned char *le;
    tape_status_t st;
    char s[400];

    if (argc != 9) {
        fprintf(stderr, "usage: %s MODE AT TOTAL_CHUNKS PREFILL_FRAMES FINAL_REQUESTED SERVICE_BUDGET SAMPLE_L SAMPLE_R\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "overwrite") == 0) mode = TAPE_REC_OVERWRITE;
    else if (strcmp(argv[1], "overdub") == 0) mode = TAPE_REC_OVERDUB;
    else if (strcmp(argv[1], "splice") == 0) mode = TAPE_REC_SPLICE;
    else { fprintf(stderr, "bad mode %s\n", argv[1]); return 2; }
    at = arg_u32(argv[2]);
    total_chunks = arg_u32(argv[3]);
    prefill = arg_u32(argv[4]);
    final_requested = arg_u32(argv[5]);
    g_budget = arg_u32(argv[6]);
    sl = arg_s16(argv[7]);
    sr = arg_s16(argv[8]);
    if (final_requested > FEED_MAX || total_chunks < 3u || total_chunks > 64u) { fprintf(stderr, "row out of range\n"); return 2; }
    for (i = 0u; i < FEED_MAX; ++i) { in[2u * i] = sl; in[2u * i + 1u] = sr; }

    g_block_count = LBA_CHUNK_BASE + total_chunks * CHUNK_BLOCKS + 1u;
    g_media = calloc(g_block_count, BLOCK);
    g_mem_len = tape_instance_size();
    g_mem = calloc(1u, g_mem_len);
    g_play = calloc(1u, TAPE_PLAY_RING_MIN);
    g_rec = calloc(1u, TAPE_REC_RING_MIN);
    if (g_media == NULL || g_mem == NULL || g_play == NULL || g_rec == NULL) { fprintf(stderr, "oom\n"); return 3; }

    build_fixture(total_chunks);
    buf_str(&line, "{\"adapter\":\"capacity_adapter\"");
    raw_state(&line, "raw_before");
    buf_str(&line, ",\"calls\":{");

    inst_new();
    set_step("mount");
    r = tape_mount(g_t, TAPE_SIDE_B, 0u, NULL);
    snprintf(s, sizeof s, "\"mount\":{\"result\":\"%s\"}", rname(r));
    buf_str(&line, s);
    set_step("info-before");
    info_json(&line, "info_before");
    set_step("seek");
    r = tape_seek(g_t, at);
    snprintf(s, sizeof s, ",\"seek\":{\"frame\":%lu,\"result\":\"%s\"}", (unsigned long)at, rname(r));
    buf_str(&line, s);
    set_step("arm");
    r = tape_arm(g_t, mode);
    snprintf(s, sizeof s, ",\"arm\":{\"mode\":\"%s\",\"result\":\"%s\"}", argv[1], rname(r));
    buf_str(&line, s);

    buf_str(&line, ",\"feed_steps\":[");
    while (fed < prefill) {
        char label[32];
        uint32_t want = prefill - fed > FEED_MAX ? FEED_MAX : prefill - fed;
        snprintf(label, sizeof label, "feed-%04u", feed_index++);
        set_step(label);
        accepted = 0u;
        before = g_ordinal;
        r = tape_feed(g_t, in, want, &accepted);
        snprintf(s, sizeof s, "%s{\"label\":\"%s\",\"requested\":%lu,\"accepted\":%lu,\"result\":\"%s\",\"events_from_call\":%u",
                 fed ? "," : "", label, (unsigned long)want, (unsigned long)accepted, rname(r), g_ordinal - before);
        buf_str(&line, s);
        service_list(&line);
        buf_str(&line, "}");
        fed += want;
    }

    /* Final feed, then the premature commit before any service of its prefix. */
    set_step("feed-final");
    accepted = 0u;
    before = g_ordinal;
    r = tape_feed(g_t, in, final_requested, &accepted);
    snprintf(s, sizeof s, "%s{\"label\":\"feed-final\",\"requested\":%lu,\"accepted\":%lu,\"result\":\"%s\",\"events_from_call\":%u",
             prefill ? "," : "", (unsigned long)final_requested, (unsigned long)accepted, rname(r), g_ordinal - before);
    buf_str(&line, s);
    {
        struct buf tail = {NULL, 0u, 0u};
        tape_result rc;
        unsigned pc;
        set_step("premature-commit");
        before = g_ordinal;
        rc = tape_commit(g_t);
        pc = g_ordinal - before;
        service_list(&line);
        buf_str(&line, "}]");
        snprintf(s, sizeof s, ",\"premature_commit\":{\"result\":\"%s\",\"events_from_call\":%u}", rname(rc), pc);
        buf_str(&tail, s);
        buf_str(&line, tail.p);
        free(tail.p);
    }

    set_step("status");
    memset(&st, 0, sizeof st);
    r = tape_status(g_t, &st);
    snprintf(s, sizeof s, ",\"status_after_service\":{\"result\":\"%s\",\"frames_owed\":%s}",
             rname(r), st.frames_owed ? "true" : "false");
    buf_str(&line, s);

    set_step("commit");
    r = tape_commit(g_t);
    snprintf(s, sizeof s, ",\"commit\":{\"result\":\"%s\"}", rname(r));
    buf_str(&line, s);
    set_step("unmount");
    r = tape_unmount(g_t, &pos);
    snprintf(s, sizeof s, ",\"unmount\":{\"result\":\"%s\"}", rname(r));
    buf_str(&line, s);

    inst_new();
    set_step("remount");
    r = tape_mount(g_t, TAPE_SIDE_B, 0u, NULL);
    snprintf(s, sizeof s, ",\"remount\":{\"result\":\"%s\"}", rname(r));
    buf_str(&line, s);
    set_step("info-after");
    {
        tape_info info;
        memset(&info, 0, sizeof info);
        (void)tape_get_info(g_t, &info);
        total = info.total_frames;
    }
    info_json(&line, "info_after");

    /* Render the whole remounted timeline at 1x from frame 0. Device reads
       belong to tape_service ("render-service"); tape_render's own callbacks,
       if any, are kept under "render" and counted. */
    pcm = calloc((size_t)total * 2u + 2u, sizeof *pcm);
    le = calloc((size_t)total * 4u + 4u, 1u);
    if (pcm == NULL || le == NULL) { fprintf(stderr, "oom\n"); return 3; }
    {
        tape_result r_render = TAPE_OK, r_seek, r_rate;
        unsigned render_events = 0u, guard = 0u;
        set_step("render-setup");
        r_seek = tape_seek(g_t, 0u);
        r_rate = tape_set_rate(g_t, 65536);
        while (done < total && guard++ < 1000000u) {
            bool more = true;
            unsigned sg = 0u;
            uint32_t want = (uint32_t)((total - done) > RENDER_PIECE ? RENDER_PIECE : (total - done)), got = 0u;
            tape_result rr;
            set_step("render-service");
            while (more && sg++ < 1000000u) {
                more = false;
                if (tape_service(g_t, 64u, &more) != TAPE_OK) break;
            }
            set_step("render");
            before = g_ordinal;
            rr = tape_render(g_t, pcm + 2u * done, want, &got);
            render_events += g_ordinal - before;
            if (rr != TAPE_OK && r_render == TAPE_OK) r_render = rr;
            if (got == 0u) break;
            done += got;
        }
        for (i = 0u; i < (uint32_t)(done * 2u); ++i) {
            uint16_t u = (uint16_t)pcm[i];
            le[2u * i] = (unsigned char)u;
            le[2u * i + 1u] = (unsigned char)(u >> 8);
        }
        snprintf(s, sizeof s, ",\"render\":{\"seek_result\":\"%s\",\"set_rate_result\":\"%s\",\"result\":\"%s\","
                 "\"rendered\":%llu,\"events_from_call\":%u,\"pcm_hex\":\"",
                 rname(r_seek), rname(r_rate), rname(r_render), (unsigned long long)done, render_events);
        buf_str(&line, s);
        buf_hex(&line, le, (size_t)done * 4u);
        buf_str(&line, "\"}");
    }
    buf_str(&line, "}");

    raw_state(&line, "raw_after");
    buf_str(&line, ",\"events\":[");
    buf_add(&line, g_events.p ? g_events.p : "", g_events.len);
    buf_str(&line, "]}\n");
    fwrite(line.p, 1u, line.len, stdout);
    return 0;
}
