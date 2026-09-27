/*
 * WP-09 R44 seeded record-history product adapter.
 *
 * Software-owned binding for the imported verifier package
 * tests/history_wp09_r44. Public header only: it links the engine archive and
 * includes nothing but engine/include. It does not import the oracle and
 * decides nothing. The edit schedule is generated here from the seed and the
 * rules ADAPTER.md names, so the stimulus is independent of the oracle's code;
 * the oracle's own "edit schedule drift" and input-digest checks reject any
 * divergence.
 *
 * One continuous history on one device and one engine instance: format, mount
 * Side B, then for each edit seek, arm, feed, service until no frames are owed,
 * commit. Every 400th edit adds a checkpoint; every 800th unmounts and mounts a
 * fresh instance first. A failing edit is recorded and the history continues;
 * nothing restarts.
 *
 * Usage: wp09_adapter   one JSONL object per edit on stdout
 */
#include "tape.h"

#include <openssl/sha.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BLOCK 512u
#define LBA_B0 264u
#define LBA_B1 392u
#define LBA_CHUNK_BASE 2048u
#define CHUNK_BLOCKS 1024u
#define CHUNK_FRAMES 131072u
#define SEED 0x9E3779B9u
#define EDITS 10000u
#define INTERVAL 400u
#define TOTAL_CHUNKS 12000u   /* > 10,000 fresh allocations with headroom */

static const uint8_t k_uuid[16] = {0x57,0x50,0x30,0x39,0x2d,0x52,0x34,0x34,0x2d,0x68,0x69,0x73,0x74,0x6f,0x72,0x79};

/* ------------------------------------------------------------------------ */
/* sparse device                                                             */
/* ------------------------------------------------------------------------ */

#define MAP_CAP (1u << 18)

struct blk { uint32_t lba; bool used; unsigned char data[BLOCK]; };

struct dev { struct blk *map; uint32_t used, block_count; };

static struct dev g_dev;

static struct blk *map_find(struct dev *d, uint32_t lba, bool create)
{
    uint32_t h = (lba * 2654435761u) & (MAP_CAP - 1u);
    for (;;) {
        struct blk *b = &d->map[h];
        if (!b->used) {
            if (!create) return NULL;
            if (d->used + 1u >= MAP_CAP / 2u) { fprintf(stderr, "device map full\n"); exit(3); }
            b->used = true;
            b->lba = lba;
            memset(b->data, 0, BLOCK);
            d->used++;
            return b;
        }
        if (b->lba == lba) return b;
        h = (h + 1u) & (MAP_CAP - 1u);
    }
}

static void dev_get(struct dev *d, uint32_t lba, unsigned char *out)
{
    struct blk *b = map_find(d, lba, false);
    if (b == NULL) memset(out, 0, BLOCK); else memcpy(out, b->data, BLOCK);
}

static void dev_put(struct dev *d, uint32_t lba, const unsigned char *src)
{
    struct blk *b = map_find(d, lba, false);
    if (b == NULL) {
        uint32_t k;
        for (k = 0u; k < BLOCK && src[k] == 0u; ++k) {}
        if (k == BLOCK) return;          /* absent reads as zero */
        b = map_find(d, lba, true);
    }
    memcpy(b->data, src, BLOCK);
}

/* ------------------------------------------------------------------------ */
/* growable text buffers                                                     */
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

static void buf_reset(struct buf *b) { b->len = 0u; if (b->p) b->p[0] = '\0'; }

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

static struct buf *g_trace;      /* where callbacks go; NULL = not logged */
static const char *g_step = "setup";
static unsigned g_ordinal;
static bool g_trace_first;

static void log_event(const char *op, bool has_lba, uint32_t lba, uint32_t count, int rc)
{
    char s[200];
    if (g_trace == NULL) return;
    if (has_lba)
        snprintf(s, sizeof s, "%s{\"step\":\"%s\",\"op\":\"%s\",\"lba\":%u,\"count\":%u,\"ordinal\":%u,\"rc\":%d}",
                 g_trace_first ? "" : ",", g_step, op, lba, count, ++g_ordinal, rc);
    else
        snprintf(s, sizeof s, "%s{\"step\":\"%s\",\"op\":\"%s\",\"ordinal\":%u,\"rc\":%d}",
                 g_trace_first ? "" : ",", g_step, op, ++g_ordinal, rc);
    buf_str(g_trace, s);
    g_trace_first = false;
}

static void trace_to(struct buf *b)
{
    g_trace = b;
    if (b) buf_reset(b);
    g_trace_first = true;
}

static int cb_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct dev *d = (struct dev *)v;
    uint32_t i;
    if (dst == NULL || count == 0u || (uint64_t)lba + count > d->block_count) {
        log_event("read", true, lba, count, -1);
        return -1;
    }
    for (i = 0u; i < count; ++i) dev_get(d, lba + i, (unsigned char *)dst + (size_t)i * BLOCK);
    log_event("read", true, lba, count, 0);
    return 0;
}

static int cb_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    struct dev *d = (struct dev *)v;
    uint32_t i;
    if (src == NULL || count == 0u || (uint64_t)lba + count > d->block_count) {
        log_event("write", true, lba, count, -1);
        return -1;
    }
    for (i = 0u; i < count; ++i) dev_put(d, lba + i, (const unsigned char *)src + (size_t)i * BLOCK);
    log_event("write", true, lba, count, 0);
    return 0;
}

static int cb_flush(void *v)
{
    (void)v;
    log_event("flush", false, 0u, 0u, 0);
    return 0;
}

static tape_dev dev_of(struct dev *d)
{
    tape_dev x;
    x.read = cb_read;
    x.write = cb_write;
    x.flush = cb_flush;
    x.ctx = d;
    x.block_count = d->block_count;
    return x;
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
    g_x = dev_of(&g_dev);
    g_t = NULL;
    r = tape_init(g_mem, g_mem_len, &g_x, g_play, TAPE_PLAY_RING_MIN, g_rec, TAPE_REC_RING_MIN, &g_t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init %s\n", rname(r)); exit(3); }
}

/* ------------------------------------------------------------------------ */
/* the seeded schedule                                                       */
/* ------------------------------------------------------------------------ */

static uint32_t g_rng = SEED;

static uint32_t next_rand(void)
{
    g_rng ^= g_rng << 13;
    g_rng ^= g_rng >> 17;
    g_rng ^= g_rng << 5;
    return g_rng;
}

struct edit {
    unsigned id;
    tape_rec_mode mode;
    const char *mode_name;
    uint64_t at;
    uint32_t count;
    int16_t frames[2u * 7u];
};

static uint64_t g_plan_length;   /* the schedule's own length rule */

static void next_edit(unsigned i, struct edit *e)
{
    static const char *const names[3] = {"overwrite", "overdub", "splice"};
    static const tape_rec_mode modes[3] = {TAPE_REC_OVERWRITE, TAPE_REC_OVERDUB, TAPE_REC_SPLICE};
    uint32_t r = next_rand(), j;
    e->id = i + 1u;
    e->mode = modes[i % 3u];
    e->mode_name = names[i % 3u];
    e->at = (i % 17u == 0u) ? 0u : (i % 19u == 0u) ? g_plan_length : (uint64_t)r % (g_plan_length + 1u);
    e->count = 1u + next_rand() % 7u;
    for (j = 0u; j < e->count; ++j) {
        uint32_t x = next_rand();
        int32_t l = (i % 23u == 0u) ? 32767 : (i % 29u == 0u) ? -32768 : (int32_t)(x & 65535u) - 32768;
        int32_t rr = (i % 31u == 0u) ? -32768 : (i % 37u == 0u) ? 32767 : (int32_t)((x >> 16) & 65535u) - 32768;
        e->frames[2u * j] = (int16_t)l;
        e->frames[2u * j + 1u] = (int16_t)rr;
    }
    if (i % 3u == 0u) g_plan_length = e->at + e->count;
    else if (i % 3u == 2u) g_plan_length += e->count;
    else if (e->at + e->count > g_plan_length) g_plan_length = e->at + e->count;
}

static void sha_hex(const unsigned char *p, size_t n, char out[65])
{
    static const char hx[] = "0123456789abcdef";
    unsigned char dg[SHA256_DIGEST_LENGTH];
    unsigned i;
    SHA256(p, n, dg);
    for (i = 0u; i < SHA256_DIGEST_LENGTH; ++i) {
        out[2u * i] = hx[dg[i] >> 4];
        out[2u * i + 1u] = hx[dg[i] & 15u];
    }
    out[64] = '\0';
}

static void pcm_le(const int16_t *s, size_t samples, unsigned char *out)
{
    size_t k;
    for (k = 0u; k < samples; ++k) {
        uint16_t u = (uint16_t)s[k];
        out[2u * k] = (unsigned char)u;
        out[2u * k + 1u] = (unsigned char)(u >> 8);
    }
}

/* ------------------------------------------------------------------------ */
/* raw reads, outside the engine and its callback accounting                 */
/* ------------------------------------------------------------------------ */

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint32_t crc32_of(const unsigned char *p, size_t n)
{
    uint32_t c = 0xFFFFFFFFu;
    size_t i;
    unsigned k;
    for (i = 0u; i < n; ++i) {
        c ^= p[i];
        for (k = 0u; k < 8u; ++k) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return c ^ 0xFFFFFFFFu;
}

static bool sb_valid(const unsigned char *b)
{
    return memcmp(b, "TAPEFS\0\x01", 8) == 0 && crc32_of(b, 508u) == rd32(b + 508);
}

/* The candidate superblock: the valid copy with the higher sb_generation,
   primary on a tie (tapefs §4.1). */
static void raw_superblock(unsigned char out[BLOCK])
{
    unsigned char p[BLOCK], m[BLOCK];
    bool vp, vm;
    dev_get(&g_dev, 0u, p);
    dev_get(&g_dev, g_dev.block_count - 1u, m);
    vp = sb_valid(p);
    vm = sb_valid(m);
    if (vm && (!vp || rd32(m + 12) > rd32(p + 12))) memcpy(out, m, BLOCK);
    else memcpy(out, p, BLOCK);
}

static void raw_slot(struct buf *b, const char *name, uint32_t lba, bool comma)
{
    unsigned char h[BLOCK], blk[BLOCK];
    uint32_t count, bytes, k;
    dev_get(&g_dev, lba, h);
    count = rd32(h + 16);
    /* A header without the index magic carries no entry bytes. */
    if (memcmp(h, "TAPEIDX\x01", 8) != 0 || count > 4096u) count = 0u;
    bytes = count * 12u;
    buf_str(b, comma ? ",\"" : "\"");
    buf_str(b, name);
    buf_str(b, "\":{\"header\":\"");
    buf_hex(b, h, BLOCK);
    buf_str(b, "\",\"entries\":\"");
    for (k = 0u; bytes > 0u; ++k) {
        uint32_t n = bytes > BLOCK ? BLOCK : bytes;
        dev_get(&g_dev, lba + 1u + k, blk);
        buf_hex(b, blk, n);
        bytes -= n;
    }
    buf_str(b, "\"}");
}

/* ------------------------------------------------------------------------ */
/* history                                                                   */
/* ------------------------------------------------------------------------ */

static struct buf g_events, g_mount_events, g_render_events, g_line;
static int16_t *g_render;         /* whole-timeline render buffer */
static size_t g_render_cap;       /* in frames */

static tape_result worst(tape_result a, tape_result b) { return a != TAPE_OK ? a : b; }

static void checkpoint(unsigned id, struct buf *line)
{
    bool remount = (id % (2u * INTERVAL)) == 0u;
    tape_result r;
    tape_info info;
    uint64_t total = 0u, done = 0u;
    unsigned guard = 0u;
    char digest[65], s[256];
    unsigned char sb[BLOCK];
    tape_result r_mount = TAPE_OK, r_seek, r_rate, r_render = TAPE_OK, r_service = TAPE_OK;

    buf_reset(&g_mount_events);
    if (remount) {
        uint64_t pos;
        g_trace = NULL;
        r = tape_unmount(g_t, &pos);
        if (r != TAPE_OK) fprintf(stderr, "edit %u unmount %s\n", id, rname(r));
        inst_new();
        g_step = "mount";
        g_ordinal = 0u;
        trace_to(&g_mount_events);
        r_mount = tape_mount(g_t, TAPE_SIDE_B, 0u, NULL);
        g_trace = NULL;
    }
    g_trace = NULL;
    r = tape_get_info(g_t, &info);
    if (r == TAPE_OK) total = info.total_frames;
    if (total > g_render_cap) {
        g_render_cap = (size_t)total;
        g_render = realloc(g_render, g_render_cap * 4u + 4u);
        if (g_render == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    }

    /* Render the whole timeline at 1x from frame zero. Service fills the ring
       between renders; only tape_render's callbacks are kept. */
    r_seek = tape_seek(g_t, 0u);
    r_rate = tape_set_rate(g_t, 65536);
    g_step = "render";
    g_ordinal = 0u;
    buf_reset(&g_render_events);
    g_trace_first = true;
    while (done < total && guard++ < 1000000u) {
        bool more = true;
        uint32_t want, got = 0u;
        unsigned sg = 0u;
        g_trace = NULL;
        while (more && sg++ < 100000u) {
            more = false;
            r_service = worst(r_service, tape_service(g_t, 256u, &more));
        }
        want = (uint32_t)((total - done) > 4096u ? 4096u : (total - done));
        g_trace = &g_render_events;
        r_render = worst(r_render, tape_render(g_t, g_render + 2u * done, want, &got));
        g_trace = NULL;
        if (got == 0u) break;
        done += got;
    }
    g_trace = NULL;

    buf_str(line, ",\"checkpoint\":{");
    snprintf(s, sizeof s, "\"id\":%u,\"after_remount\":%s,\"mount_result\":\"%s\",\"seek_result\":\"%s\","
             "\"set_rate_result\":\"%s\",\"service_result\":\"%s\",\"render_result\":\"%s\",\"rendered_frames\":%llu,",
             id, remount ? "true" : "false", rname(r_mount), rname(r_seek), rname(r_rate),
             rname(r_service), rname(r_render), (unsigned long long)done);
    buf_str(line, s);
    {
        unsigned char *le = malloc((size_t)done * 4u + 1u);
        if (le == NULL) { fprintf(stderr, "oom\n"); exit(3); }
        pcm_le(g_render, (size_t)done * 2u, le);
        buf_str(line, "\"render_pcm\":\"");
        buf_hex(line, le, (size_t)done * 4u);
        sha_hex(le, (size_t)done * 4u, digest);
        free(le);
    }
    buf_str(line, "\",\"pcm_sha256\":\"");
    buf_str(line, digest);
    buf_str(line, "\",\"render_block_events\":[");
    buf_str(line, g_render_events.p ? g_render_events.p : "");
    buf_str(line, "],\"raw_superblock\":\"");
    raw_superblock(sb);
    buf_hex(line, sb, BLOCK);
    buf_str(line, "\",\"raw_slots\":{");
    raw_slot(line, "B0", LBA_B0, false);
    raw_slot(line, "B1", LBA_B1, true);
    snprintf(s, sizeof s, "},\"public_info\":{\"result\":\"%s\",\"total_frames\":%llu,\"entry_count\":%u,"
             "\"total_chunks\":%u,\"free_chunks\":%u},\"mount_events\":[",
             rname(r), (unsigned long long)info.total_frames, info.entry_count,
             info.total_chunks, info.free_chunks);
    buf_str(line, s);
    buf_str(line, g_mount_events.p ? g_mount_events.p : "");
    buf_str(line, "]}");
}

static void run_edit(const struct edit *e)
{
    tape_result r_seek, r_arm, r_feed, r_service = TAPE_OK, r_commit;
    uint32_t accepted = 0u;
    unsigned guard = 0u;
    unsigned char le[4u * 7u];
    char digest[65], s[512];
    tape_status_t st;

    g_ordinal = 0u;
    trace_to(&g_events);

    g_step = "seek";
    r_seek = tape_seek(g_t, e->at);
    g_step = "arm";
    r_arm = tape_arm(g_t, e->mode);
    g_step = "feed";
    r_feed = tape_feed(g_t, e->frames, e->count, &accepted);
    g_step = "service";
    for (;;) {
        bool more = false;
        memset(&st, 0, sizeof st);
        g_trace = NULL;
        if (tape_status(g_t, &st) != TAPE_OK || !st.frames_owed || guard++ > 100000u) break;
        g_trace = &g_events;
        r_service = worst(r_service, tape_service(g_t, 256u, &more));
    }
    g_trace = &g_events;
    g_step = "commit";
    r_commit = tape_commit(g_t);
    g_trace = NULL;

    pcm_le(e->frames, 2u * e->count, le);
    sha_hex(le, 4u * e->count, digest);
    buf_reset(&g_line);
    snprintf(s, sizeof s, "{\"schema\":\"wp09-r44-v1\",\"id\":%u,\"mode\":\"%s\",\"at\":%llu,"
             "\"frames\":%u,\"input_sha256\":\"%s\",\"accepted\":%u,"
             "\"calls\":{\"seek\":\"%s\",\"arm\":\"%s\",\"feed\":\"%s\",\"service\":\"%s\",\"commit\":\"%s\"},"
             "\"events\":[",
             e->id, e->mode_name, (unsigned long long)e->at, e->count, digest, accepted,
             rname(r_seek), rname(r_arm), rname(r_feed), rname(r_service), rname(r_commit));
    buf_str(&g_line, s);
    buf_str(&g_line, g_events.p ? g_events.p : "");
    buf_str(&g_line, "]");
    if (e->id % INTERVAL == 0u) checkpoint(e->id, &g_line);
    buf_str(&g_line, "}\n");
    fwrite(g_line.p, 1u, g_line.len, stdout);
}

int main(void)
{
    uint64_t frames = (uint64_t)TOTAL_CHUNKS * CHUNK_FRAMES;
    uint32_t nominal = (uint32_t)((frames + 44099u) / 44100u);
    struct edit e;
    tape_result r;
    unsigned i;

    g_dev.map = calloc(MAP_CAP, sizeof *g_dev.map);
    /* The device holds exactly the chunks the nominal length rounds up to. */
    g_dev.block_count = LBA_CHUNK_BASE
        + (uint32_t)(((uint64_t)nominal * 44100u + CHUNK_FRAMES - 1u) / CHUNK_FRAMES) * CHUNK_BLOCKS + 1u;
    g_mem_len = tape_instance_size();
    g_mem = calloc(1u, g_mem_len);
    g_play = calloc(1u, TAPE_PLAY_RING_MIN);
    g_rec = calloc(1u, TAPE_REC_RING_MIN);
    if (g_dev.map == NULL || g_mem == NULL || g_play == NULL || g_rec == NULL) {
        fprintf(stderr, "oom\n");
        return 3;
    }
    g_x = dev_of(&g_dev);
    r = tape_format(&g_x, k_uuid, 1u, "WP09-R44", nominal);
    if (r != TAPE_OK) { fprintf(stderr, "format %s\n", rname(r)); return 3; }
    inst_new();
    r = tape_mount(g_t, TAPE_SIDE_B, 0u, NULL);
    if (r != TAPE_OK) { fprintf(stderr, "mount %s\n", rname(r)); return 3; }

    for (i = 0u; i < EDITS; ++i) {
        next_edit(i, &e);
        run_edit(&e);
    }
    return 0;
}
