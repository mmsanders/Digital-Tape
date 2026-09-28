/*
 * WP-08 R44 cross-run playback product adapter.
 *
 * Software-owned binding for the imported verifier package
 * tests/crossrun_wp08_r44. Public header only: it links the engine archive and
 * includes nothing but engine/include. It does not import the oracle and
 * decides nothing; it reports public results, every device callback, and raw
 * media bytes read directly from the device outside the engine.
 *
 * Fixture (ADAPTER.md): tape_format a blank device, then write one Side B index
 * with four consecutive runs of 5, 3, 7 and 2 frames at physical chunks 1..4,
 * start_frame 0, and the seeded PCM into those chunks. CRCs are computed here.
 *
 * Usage: wp08_adapter            one JSONL object per case on stdout
 *        wp08_adapter --fixture  the fixture image (every non-zero block) as JSON
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
#define NOMINAL_S 60u
#define SEED 0xA51CE55Du

static const uint32_t k_runs[4] = {5u, 3u, 7u, 2u};
static const uint32_t k_chunks[4] = {1u, 2u, 3u, 4u};
static const uint8_t k_uuid[16] = {0x57,0x50,0x30,0x38,0x2d,0x52,0x34,0x34,0x2d,0x63,0x72,0x6f,0x73,0x73,0x72,0x6e};

/* ------------------------------------------------------------------------ */
/* flat device                                                               */
/* ------------------------------------------------------------------------ */

struct dev {
    unsigned char *img;
    uint32_t block_count;
};

static struct dev g_dev;
static unsigned char *g_fixture;     /* the constructed image, restored per variant */

static uint32_t block_count_for(uint32_t nominal_s)
{
    uint64_t frames = (uint64_t)nominal_s * 44100u;
    uint32_t chunks = (uint32_t)((frames + CHUNK_FRAMES - 1u) / CHUNK_FRAMES);
    return LBA_CHUNK_BASE + chunks * CHUNK_BLOCKS + 1u;
}

/* ------------------------------------------------------------------------ */
/* callback trace                                                            */
/* ------------------------------------------------------------------------ */

static bool g_logging;
static char *g_ev;
static size_t g_ev_len, g_ev_cap;
static unsigned g_ev_n;

static void ev_append(const char *s)
{
    size_t n = strlen(s);
    if (g_ev_len + n + 1u > g_ev_cap) {
        while (g_ev_len + n + 1u > g_ev_cap) g_ev_cap = g_ev_cap ? g_ev_cap * 2u : 4096u;
        g_ev = realloc(g_ev, g_ev_cap);
        if (g_ev == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    }
    memcpy(g_ev + g_ev_len, s, n + 1u);
    g_ev_len += n;
}

static void ev_reset(void) { g_ev_len = 0u; g_ev_n = 0u; if (g_ev) g_ev[0] = '\0'; }

static void log_event(const char *op, bool has_lba, uint32_t lba, uint32_t count, int rc)
{
    char buf[160];
    if (!g_logging) return;
    if (has_lba)
        snprintf(buf, sizeof buf, "%s{\"op\":\"%s\",\"lba\":%u,\"count\":%u,\"rc\":%d}",
                 g_ev_n ? "," : "", op, lba, count, rc);
    else
        snprintf(buf, sizeof buf, "%s{\"op\":\"%s\",\"rc\":%d}", g_ev_n ? "," : "", op, rc);
    ev_append(buf);
    g_ev_n++;
}

static int cb_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct dev *d = (struct dev *)v;
    if (dst == NULL || count == 0u || (uint64_t)lba + count > d->block_count) {
        log_event("read", true, lba, count, -1);
        return -1;
    }
    memcpy(dst, d->img + (size_t)lba * BLOCK, (size_t)count * BLOCK);
    log_event("read", true, lba, count, 0);
    return 0;
}

static int cb_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    struct dev *d = (struct dev *)v;
    if (src == NULL || count == 0u || (uint64_t)lba + count > d->block_count) {
        log_event("write", true, lba, count, -1);
        return -1;
    }
    memcpy(d->img + (size_t)lba * BLOCK, src, (size_t)count * BLOCK);
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

/* ------------------------------------------------------------------------ */
/* raw helpers (tapefs byte layout, computed here, not by the engine)        */
/* ------------------------------------------------------------------------ */

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void wr32(unsigned char *p, uint32_t v)
{
    p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8);
    p[2] = (unsigned char)(v >> 16); p[3] = (unsigned char)(v >> 24);
}

static void wr64(unsigned char *p, uint64_t v)
{
    wr32(p, (uint32_t)v);
    wr32(p + 4, (uint32_t)(v >> 32));
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

static bool index_valid(const unsigned char *slot, uint32_t *seq)
{
    uint32_t count, c;
    if (memcmp(slot, "TAPEIDX\x01", 8) != 0) return false;
    count = rd32(slot + 16);
    if (count > 4096u) return false;
    c = crc32_update(0xFFFFFFFFu, slot, 60u);
    c = crc32_update(c, slot + BLOCK, (size_t)count * 12u);
    if ((c ^ 0xFFFFFFFFu) != rd32(slot + 60)) return false;
    *seq = rd32(slot + 8);
    return true;
}

/* The seeded frames, in timeline order: xorshift32 from SEED, one step per
   frame, left = low 16 bits − 32768, right = high 16 bits − 32768. */
static void seeded_frames(int16_t out[17][2])
{
    uint32_t x = SEED;
    unsigned i;
    for (i = 0u; i < 17u; ++i) {
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        out[i][0] = (int16_t)((int32_t)(x & 65535u) - 32768);
        out[i][1] = (int16_t)((int32_t)((x >> 16) & 65535u) - 32768);
    }
}

static void build_fixture(void)
{
    static const uint32_t slots[4] = {LBA_A0, LBA_A1, LBA_B0, LBA_B1};
    int16_t frames[17][2];
    unsigned char *slot;
    uint32_t seq, max_seq = 0u, c, target, total = 0u;
    unsigned i, j, f = 0u;
    tape_dev x;
    tape_result r;

    g_dev.block_count = block_count_for(NOMINAL_S);
    g_dev.img = calloc(g_dev.block_count, BLOCK);
    g_fixture = calloc(g_dev.block_count, BLOCK);
    if (g_dev.img == NULL || g_fixture == NULL) { fprintf(stderr, "oom\n"); exit(3); }
    x = dev_of(&g_dev);
    r = tape_format(&x, k_uuid, 1u, "WP08-R44", NOMINAL_S);
    if (r != TAPE_OK) { fprintf(stderr, "format %d\n", (int)r); exit(3); }

    /* The new Side B index goes above every existing sequence, into the B slot
       that is not currently the higher valid one. */
    for (i = 0u; i < 4u; ++i)
        if (index_valid(g_dev.img + (size_t)slots[i] * BLOCK, &seq) && seq > max_seq) max_seq = seq;
    target = LBA_B1;
    if (index_valid(g_dev.img + (size_t)LBA_B1 * BLOCK, &seq)) {
        uint32_t s0;
        if (!index_valid(g_dev.img + (size_t)LBA_B0 * BLOCK, &s0) || s0 < seq) target = LBA_B0;
    }
    slot = g_dev.img + (size_t)target * BLOCK;
    memset(slot, 0, 128u * BLOCK);
    for (i = 0u; i < 4u; ++i) {
        unsigned char *e = slot + BLOCK + 12u * i;
        wr32(e, k_chunks[i]);
        wr32(e + 4, 0u);
        wr32(e + 8, k_runs[i]);
        total += k_runs[i];
    }
    memcpy(slot, "TAPEIDX\x01", 8);
    wr32(slot + 8, max_seq + 1u);
    slot[12] = 1u;
    wr32(slot + 16, 4u);
    wr64(slot + 20, total);
    c = crc32_update(0xFFFFFFFFu, slot, 60u);
    c = crc32_update(c, slot + BLOCK, 4u * 12u);
    wr32(slot + 60, c ^ 0xFFFFFFFFu);

    /* Seeded PCM, little-endian interleaved, from frame 0 of each chunk. */
    seeded_frames(frames);
    for (i = 0u; i < 4u; ++i) {
        unsigned char *p = g_dev.img + (size_t)(LBA_CHUNK_BASE + k_chunks[i] * CHUNK_BLOCKS) * BLOCK;
        for (j = 0u; j < k_runs[i]; ++j, ++f) {
            uint16_t l = (uint16_t)frames[f][0], rr = (uint16_t)frames[f][1];
            p[4u * j] = (unsigned char)l; p[4u * j + 1u] = (unsigned char)(l >> 8);
            p[4u * j + 2u] = (unsigned char)rr; p[4u * j + 3u] = (unsigned char)(rr >> 8);
        }
    }
    memcpy(g_fixture, g_dev.img, (size_t)g_dev.block_count * BLOCK);
}

static void print_hex(const unsigned char *p, size_t n)
{
    static const char d[] = "0123456789abcdef";
    size_t i;
    for (i = 0u; i < n; ++i) { putchar(d[p[i] >> 4]); putchar(d[p[i] & 15u]); }
}

static void print_index_slot(const char *name, uint32_t lba, bool comma)
{
    const unsigned char *h = g_dev.img + (size_t)lba * BLOCK;
    uint32_t count = rd32(h + 16);
    /* The CRC-covered entry bytes as the header declares them; a header with
       no valid magic carries none. */
    if (memcmp(h, "TAPEIDX\x01", 8) != 0 || count > 4096u) count = 0u;
    printf("%s\"%s\":{\"header\":\"", comma ? "," : "", name);
    print_hex(h, BLOCK);
    printf("\",\"entries\":\"");
    print_hex(h + BLOCK, (size_t)count * 12u);
    printf("\"}");
}

/* Raw media read directly from the device buffer, never through the engine. */
static void print_raw_media(void)
{
    const unsigned char *b1 = g_dev.img + (size_t)LBA_B1 * BLOCK;
    const unsigned char *b0 = g_dev.img + (size_t)LBA_B0 * BLOCK;
    uint32_t s0 = 0u, s1 = 0u;
    const unsigned char *live;
    bool v0 = index_valid(b0, &s0), v1 = index_valid(b1, &s1);
    unsigned i;
    live = (v1 && (!v0 || s1 > s0)) ? b1 : b0;
    printf("\"raw_media\":{\"superblock\":\"");
    print_hex(g_dev.img, BLOCK);
    printf("\"");
    print_index_slot("B0", LBA_B0, true);
    print_index_slot("B1", LBA_B1, true);
    printf(",\"chunks\":{");
    /* The first block of every chunk the raw B index names. */
    for (i = 0u; i < rd32(live + 16) && i < 4096u; ++i) {
        uint32_t id = rd32(live + BLOCK + 12u * i);
        uint32_t lba = LBA_CHUNK_BASE + id * CHUNK_BLOCKS;
        if (lba >= g_dev.block_count) continue;
        printf("%s\"%u\":\"", i ? "," : "", lba);
        print_hex(g_dev.img + (size_t)lba * BLOCK, BLOCK);
        printf("\"");
    }
    printf("}}");
}

/* ------------------------------------------------------------------------ */
/* cases                                                                     */
/* ------------------------------------------------------------------------ */

struct wcase { const char *id; uint64_t seek; int32_t rate; uint32_t count; };

static const char *rname(tape_result r)
{
    switch (r) {
    case TAPE_OK: return "TAPE_OK";
    case TAPE_ERR_IO: return "TAPE_ERR_IO";
    case TAPE_ERR_NOT_MOUNTED: return "TAPE_ERR_NOT_MOUNTED";
    case TAPE_ERR_BUSY: return "TAPE_ERR_BUSY";
    case TAPE_ERR_UNDERRUN: return "TAPE_ERR_UNDERRUN";
    case TAPE_ERR_INVALID_ARG: return "TAPE_ERR_INVALID_ARG";
    case TAPE_ERR_FAULTED: return "TAPE_ERR_FAULTED";
    case TAPE_ERR_NO_VALID_INDEX: return "TAPE_ERR_NO_VALID_INDEX";
    case TAPE_ERR_INCONSISTENT: return "TAPE_ERR_INCONSISTENT";
    default: return "TAPE_ERR_OTHER";
    }
}

static unsigned char *g_mem, *g_play, *g_rec;
static size_t g_mem_len;

static void run_variant(const struct wcase *c, const char *label, const uint32_t *sizes,
                        unsigned n_sizes, uint32_t budget, bool comma)
{
    tape_dev x;
    tape *t = NULL;
    tape_result r, rm, rs, rr;
    bool more = true;
    unsigned i, guard = 0u;

    /* A fresh image, instance and mount per variant. */
    memcpy(g_dev.img, g_fixture, (size_t)g_dev.block_count * BLOCK);
    memset(g_mem, 0, g_mem_len);
    x = dev_of(&g_dev);
    r = tape_init(g_mem, g_mem_len, &x, g_play, TAPE_PLAY_RING_MIN, g_rec, TAPE_REC_RING_MIN, &t);
    if (r != TAPE_OK) { fprintf(stderr, "init %s\n", rname(r)); exit(3); }
    rm = tape_mount(t, TAPE_SIDE_B, 0u, NULL);
    rs = tape_seek(t, c->seek);
    rr = tape_set_rate(t, c->rate);

    printf("%s\"%s\":{\"mount_result\":\"%s\",\"seek_result\":\"%s\",\"set_rate_result\":\"%s\","
           "\"render_sizes\":[", comma ? "," : "", label, rname(rm), rname(rs), rname(rr));
    for (i = 0u; i < n_sizes; ++i) printf("%s%u", i ? "," : "", sizes[i]);
    printf("],\"service_budget\":%u,\"services\":[", budget);
    while (more && guard < 100000u) {
        more = false;
        ev_reset();
        g_logging = true;
        r = tape_service(t, budget, &more);
        g_logging = false;
        printf("%s{\"budget\":%u,\"result\":\"%s\",\"more_work\":%s,\"events\":[%s]}",
               guard ? "," : "", budget, rname(r), more ? "true" : "false", g_ev ? g_ev : "");
        if (r != TAPE_OK) break;
        guard++;
    }
    printf("],\"renders\":[");
    for (i = 0u; i < n_sizes; ++i) {
        int16_t out[2u * 64u];
        uint32_t rendered = 0u, k;
        uint64_t tell = 0u;
        tape_status_t st;
        tape_result rt, rst;
        memset(out, 0, sizeof out);
        memset(&st, 0, sizeof st);
        ev_reset();
        g_logging = true;
        r = tape_render(t, out, sizes[i], &rendered);
        g_logging = false;
        rt = tape_tell(t, &tell);
        rst = tape_status(t, &st);
        printf("%s{\"requested\":%u,\"result\":\"%s\",\"rendered\":%u,\"pcm_hex\":\"",
               i ? "," : "", sizes[i], rname(r), rendered);
        for (k = 0u; k < 2u * rendered && k < 2u * 64u; ++k) {
            unsigned char le[2];
            uint16_t s = (uint16_t)out[k];
            le[0] = (unsigned char)s; le[1] = (unsigned char)(s >> 8);
            print_hex(le, 2u);
        }
        printf("\",\"tell\":%llu,\"tell_result\":\"%s\",\"at_start\":%s,\"at_end\":%s,"
               "\"status_result\":\"%s\",\"block_events\":[%s]}",
               (unsigned long long)tell, rname(rt), st.at_start ? "true" : "false",
               st.at_end ? "true" : "false", rname(rst), g_ev ? g_ev : "");
    }
    printf("]}");
    { uint64_t pos; (void)tape_unmount(t, &pos); }
}

static void run_case(const struct wcase *c)
{
    uint32_t whole[1], single[64], uneven[64];
    unsigned i, nu = 0u;
    whole[0] = c->count;
    for (i = 0u; i < c->count; ++i) single[i] = 1u;
    for (i = 0u; i < c->count / 5u; ++i) { uneven[nu++] = 3u; uneven[nu++] = 2u; }
    if (c->count % 5u) uneven[nu++] = c->count % 5u;

    printf("{\"schema\":\"wp08-r44-v1\",\"case\":\"%s\",\"seek\":%llu,\"rate\":%ld,",
           c->id, (unsigned long long)c->seek, (long)c->rate);
    printf("\"variants\":{");
    run_variant(c, "whole", whole, 1u, 256u, false);
    run_variant(c, "single", single, c->count, 1u, true);
    run_variant(c, "uneven", uneven, nu, 7u, true);
    printf("},");
    /* Snapshot after the case: the device as the last variant left it. */
    print_raw_media();
    printf("}\n");
}

static void print_fixture(void)
{
    uint32_t lba;
    bool first = true;
    printf("{\"schema\":\"wp08-r44-product-fixture-1\",\"block_count\":%u,\"nominal_length_s\":%u,"
           "\"runs\":\"four Side B entries {chunk 1..4, start 0, 5/3/7/2 frames}; seed 0x%08X\","
           "\"nonzero_blocks\":{", g_fixture ? g_dev.block_count : 0u, NOMINAL_S, SEED);
    for (lba = 0u; lba < g_dev.block_count; ++lba) {
        const unsigned char *b = g_fixture + (size_t)lba * BLOCK;
        unsigned k;
        for (k = 0u; k < BLOCK && b[k] == 0u; ++k) {}
        if (k == BLOCK) continue;
        printf("%s\"%u\":\"", first ? "" : ",", lba);
        print_hex(b, BLOCK);
        printf("\"");
        first = false;
    }
    printf("}}\n");
}

int main(int argc, char **argv)
{
    static const struct wcase cases[] = {
        {"boundary-5-1-f", 4u, 65536, 8u}, {"boundary-5-1-r", 4u, -65536, 8u},
        {"boundary-5+0-f", 5u, 65536, 8u}, {"boundary-5+0-r", 5u, -65536, 8u},
        {"boundary-5+1-f", 6u, 65536, 8u}, {"boundary-5+1-r", 6u, -65536, 8u},
        {"boundary-8-1-f", 7u, 65536, 8u}, {"boundary-8-1-r", 7u, -65536, 8u},
        {"boundary-8+0-f", 8u, 65536, 8u}, {"boundary-8+0-r", 8u, -65536, 8u},
        {"boundary-8+1-f", 9u, 65536, 8u}, {"boundary-8+1-r", 9u, -65536, 8u},
        {"boundary-15-1-f", 14u, 65536, 8u}, {"boundary-15-1-r", 14u, -65536, 8u},
        {"boundary-15+0-f", 15u, 65536, 8u}, {"boundary-15+0-r", 15u, -65536, 8u},
        {"boundary-15+1-f", 16u, 65536, 8u}, {"boundary-15+1-r", 16u, -65536, 8u},
        {"fraction-1", 4u, 32768, 11u}, {"fraction-2", 7u, -32768, 11u},
        {"fraction-3", 14u, 98304, 11u}, {"fraction-4", 16u, -98304, 11u},
        {"fraction-5", 5u, -32768, 11u}, {"fraction-6", 8u, 98304, 11u},
        {"fraction-7", 15u, -98304, 11u}, {"fraction-8", 1u, 32768, 11u},
        {"end-reverse", 17u, -65536, 20u}, {"start-reverse", 0u, -65536, 3u},
        {"end-forward", 17u, 65536, 3u}, {"beyond-end", 100u, 65536, 3u},
        {"zero-rate", 8u, 0, 5u}, {"huge-forward", 16u, 0x7FFFFFFF, 3u},
        {"huge-reverse", 17u, (int32_t)(-0x7FFFFFFF - 1), 3u},
    };
    unsigned i;

    build_fixture();
    if (argc > 1 && strcmp(argv[1], "--fixture") == 0) { print_fixture(); return 0; }
    g_mem_len = tape_instance_size();
    g_mem = calloc(1u, g_mem_len);
    g_play = calloc(1u, TAPE_PLAY_RING_MIN);
    g_rec = calloc(1u, TAPE_REC_RING_MIN);
    if (g_mem == NULL || g_play == NULL || g_rec == NULL) { fprintf(stderr, "oom\n"); return 3; }
    for (i = 0u; i < sizeof cases / sizeof cases[0]; ++i)
        if (argc < 2 || strcmp(argv[1], cases[i].id) == 0) run_case(&cases[i]);
    return 0;
}
