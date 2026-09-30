/*
 * WP-08 R52 two-toolchain playback product adapter.
 *
 * Software-owned binding for the imported verifier package
 * tests/portability_wp08_r52. Public header only; it does not import the
 * oracle and decides nothing. run_product.py compiles this file together with
 * the engine sources under GCC and under Clang with the package's flags, so
 * the engine arithmetic itself is built by each compiler.
 *
 * Per plan row, on a fresh device: build a valid Side-B cartridge whose
 * entries are the row's runs, then tape_mount(B), tape_seek, tape_set_rate,
 * tape_service(7) until more_work is false, one tape_render, tape_tell and
 * tape_status. Every callback is recorded against the call that caused it.
 * One JSON object per row, written to OUTPUT_JSONL.
 */
#include "tape.h"

#include <inttypes.h>
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
#define MAX_FRAMES 12
#define MAX_RUNS 4
#define TOTAL_CHUNKS 10u
/* Run k lives at chunk 2k+1, from this frame: physically scattered, off chunk start. */
#define RUN_START_FRAME 100u
#define SERVICE_BUDGET 7u

struct vector {
    const char *id;
    const char *fixture_sha256;
    uint32_t frame_count;
    int16_t pcm[MAX_FRAMES][2];
    uint32_t run_count;
    uint32_t runs[MAX_RUNS];
    uint64_t seek;
    int32_t rate;
    uint32_t requested;
};

#include "plan_vectors.h"

static const uint8_t k_uuid[16] = {0x57,0x50,0x30,0x38,0x2d,0x52,0x35,0x32,0x2d,0x70,0x6f,0x72,0x74,0x61,0x62,0x6c};

static unsigned char *g_media;
static uint32_t g_block_count;
/* Opened "wb": a text-mode stdout would turn every newline into CRLF on Windows. */
static FILE *g_out;

/* ------------------------------------------------------------------------ */
/* per-call callback lists                                                   */
/* ------------------------------------------------------------------------ */

static char g_ev[65536];
static size_t g_ev_len;

static void ev_reset(void) { g_ev_len = 0u; g_ev[0] = '\0'; }

static void ev_add(const char *op, bool has_lba, uint32_t lba, uint32_t count, int rc)
{
    int n;
    if (has_lba)
        n = snprintf(g_ev + g_ev_len, sizeof g_ev - g_ev_len,
                     "%s{\"count\":%" PRIu32 ",\"lba\":%" PRIu32 ",\"op\":\"%s\",\"rc\":%d}",
                     g_ev_len ? "," : "", count, lba, op, rc);
    else
        n = snprintf(g_ev + g_ev_len, sizeof g_ev - g_ev_len,
                     "%s{\"op\":\"%s\",\"rc\":%d}", g_ev_len ? "," : "", op, rc);
    if (n < 0 || (size_t)n >= sizeof g_ev - g_ev_len) { fprintf(stderr, "event overflow\n"); exit(3); }
    g_ev_len += (size_t)n;
}

static int cb_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    (void)v;
    if (dst == NULL || count == 0u || (uint64_t)lba + count > g_block_count) {
        ev_add("read", true, lba, count, -1);
        return -1;
    }
    memcpy(dst, g_media + (size_t)lba * BLOCK, (size_t)count * BLOCK);
    ev_add("read", true, lba, count, 0);
    return 0;
}

static int cb_write(void *v, uint32_t lba, uint32_t count, const void *src)
{
    (void)v;
    if (src == NULL || count == 0u || (uint64_t)lba + count > g_block_count) {
        ev_add("write", true, lba, count, -1);
        return -1;
    }
    memcpy(g_media + (size_t)lba * BLOCK, src, (size_t)count * BLOCK);
    ev_add("write", true, lba, count, 0);
    return 0;
}

static int cb_flush(void *v)
{
    (void)v;
    ev_add("flush", false, 0u, 0u, 0);
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
/* raw fixture                                                               */
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

static void put_slot(uint32_t lba, uint32_t sequence, unsigned side,
                     const uint32_t (*e3)[3], uint32_t n)
{
    unsigned char *h = blk(lba), *e = blk(lba + 1u);
    uint64_t total = 0u;
    uint32_t i, c;
    memcpy(h, "TAPEIDX\x01", 8);
    wr32(h + 8, sequence);
    h[12] = (unsigned char)side;
    wr32(h + 16, n);
    for (i = 0u; i < n; ++i) {
        wr32(e + 12u * i, e3[i][0]);
        wr32(e + 12u * i + 4u, e3[i][1]);
        wr32(e + 12u * i + 8u, e3[i][2]);
        total += e3[i][2];
    }
    wr64(h + 20, total);
    c = crc32_update(0xFFFFFFFFu, h, 60u);
    c = crc32_update(c, e, (size_t)n * 12u);
    wr32(h + 60, c ^ 0xFFFFFFFFu);
}

static uint32_t nominal_for(uint32_t total_chunks)
{
    return (uint32_t)(((uint64_t)(total_chunks - 1u) * CHUNK_FRAMES) / 44100u) + 1u;
}

/* Side A: an empty index at sequence 1, a_high_water 0. Side B: B0 at
   sequence 2, one entry per plan run, run k at chunk 2k+1 from frame 100. */
static void build_fixture(const struct vector *v)
{
    unsigned char *sb;
    uint32_t e3[MAX_RUNS][3];
    uint32_t k, f = 0u;

    g_block_count = LBA_CHUNK_BASE + TOTAL_CHUNKS * CHUNK_BLOCKS + 1u;
    memset(g_media, 0, (size_t)g_block_count * BLOCK);
    sb = blk(0u);
    memcpy(sb, "TAPEFS\0\x01", 8);
    wr16(sb + 8, 1u);
    wr32(sb + 12, 3u);
    memcpy(sb + 20, k_uuid, 16);
    wr32(sb + 36, 44100u);
    wr16(sb + 40, 2u);
    wr16(sb + 42, 16u);
    wr32(sb + 44, 524288u);
    wr32(sb + 48, nominal_for(TOTAL_CHUNKS));
    wr32(sb + 52, TOTAL_CHUNKS);
    wr32(sb + 56, 0u);
    wr32(sb + 60, 65536u);
    wr32(sb + 64, LBA_A0);
    wr32(sb + 68, LBA_A1);
    wr32(sb + 72, LBA_B0);
    wr32(sb + 76, LBA_B1);
    wr32(sb + 80, LBA_CHUNK_BASE);
    wr32(sb + 84, g_block_count - 1u);
    memcpy(sb + 88, "WP08-R52", 8);
    wr32(sb + 120, 1u);
    wr32(sb + 508, crc32_update(0xFFFFFFFFu, sb, 508u) ^ 0xFFFFFFFFu);
    memcpy(blk(g_block_count - 1u), sb, BLOCK);

    put_slot(LBA_A0, 1u, 0u, NULL, 0u);
    for (k = 0u; k < v->run_count; ++k) {
        uint32_t chunk = 2u * k + 1u, i;
        unsigned char *p = blk(LBA_CHUNK_BASE + chunk * CHUNK_BLOCKS) + 4u * RUN_START_FRAME;
        e3[k][0] = chunk;
        e3[k][1] = RUN_START_FRAME;
        e3[k][2] = v->runs[k];
        for (i = 0u; i < v->runs[k]; ++i, ++f) {
            wr16(p + 4u * i, (uint32_t)(uint16_t)v->pcm[f][0]);
            wr16(p + 4u * i + 2u, (uint32_t)(uint16_t)v->pcm[f][1]);
        }
    }
    if (f != v->frame_count) { fprintf(stderr, "%s: runs do not cover frames\n", v->id); exit(3); }
    put_slot(LBA_B0, 2u, 1u, (const uint32_t (*)[3])e3, v->run_count);
}

static void hex(const unsigned char *p, size_t n)
{
    size_t i;
    for (i = 0u; i < n; ++i) fprintf(g_out, "%02x", (unsigned)p[i]);
}

/* ------------------------------------------------------------------------ */
/* one row                                                                   */
/* ------------------------------------------------------------------------ */

static unsigned char *g_mem, *g_play, *g_rec;
static size_t g_mem_len;

static void run(const struct vector *v)
{
    tape_dev x;
    tape *t = NULL;
    tape_result r;
    tape_status_t st;
    int16_t out[2u * MAX_FRAMES + 2u];
    uint32_t rendered = 0u, k;
    uint64_t tell = 0u;
    unsigned guard = 0u;

    build_fixture(v);

    /* Raw identity, read directly from media before the engine runs. */
    fprintf(g_out, "{\"case\":\"%s\",\"fixture_sha256\":\"%s\",\"raw_superblock\":\"", v->id, v->fixture_sha256);
    hex(blk(0u), BLOCK);
    fprintf(g_out, "\",\"raw_B0\":\"");
    hex(blk(LBA_B0), BLOCK);
    hex(blk(LBA_B0 + 1u), (size_t)rd32(blk(LBA_B0) + 16) * 12u);
    fprintf(g_out, "\",\"raw_B1\":\"");
    hex(blk(LBA_B1), BLOCK);
    fprintf(g_out, "\",\"raw_run_pcm\":[");
    for (k = 0u; k < v->run_count; ++k) {
        fprintf(g_out, "%s\"", k ? "," : "");
        hex(blk(LBA_CHUNK_BASE + (2u * k + 1u) * CHUNK_BLOCKS) + 4u * RUN_START_FRAME, (size_t)v->runs[k] * 4u);
        fprintf(g_out, "\"");
    }
    fprintf(g_out, "],\"schema\":\"wp08-portability-r52-v1\",\"trace\":[");

    memset(g_mem, 0, g_mem_len);
    memset(g_play, 0, TAPE_PLAY_RING_MIN);
    memset(g_rec, 0, TAPE_REC_RING_MIN);
    x.read = cb_read;
    x.write = cb_write;
    x.flush = cb_flush;
    x.ctx = NULL;
    x.block_count = g_block_count;
    r = tape_init(g_mem, g_mem_len, &x, g_play, TAPE_PLAY_RING_MIN, g_rec, TAPE_REC_RING_MIN, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init %s\n", rname(r)); exit(3); }

    ev_reset();
    r = tape_mount(t, TAPE_SIDE_B, 0u, NULL);
    fprintf(g_out, "{\"block_events\":[%s],\"fn\":\"tape_mount\",\"result\":\"%s\"},", g_ev, rname(r));

    ev_reset();
    r = tape_seek(t, v->seek);
    fprintf(g_out, "{\"block_events\":[%s],\"fn\":\"tape_seek\",\"frame\":%" PRIu64 ",\"result\":\"%s\"},", g_ev, v->seek, rname(r));

    ev_reset();
    r = tape_set_rate(t, v->rate);
    fprintf(g_out, "{\"block_events\":[%s],\"fn\":\"tape_set_rate\",\"rate_q16_16\":%" PRId32 ",\"result\":\"%s\"},", g_ev, v->rate, rname(r));

    for (;;) {
        bool more = false;
        ev_reset();
        r = tape_service(t, SERVICE_BUDGET, &more);
        fprintf(g_out, "{\"block_events\":[%s],\"budget\":%u,\"fn\":\"tape_service\",\"more_work\":%s,\"result\":\"%s\"},",
               g_ev, SERVICE_BUDGET, more ? "true" : "false", rname(r));
        if (r != TAPE_OK || !more || ++guard > 10000u) break;
    }

    ev_reset();
    r = tape_render(t, out, v->requested, &rendered);
    fprintf(g_out, "{\"block_events\":[%s],\"fn\":\"tape_render\",\"rendered\":%" PRIu32 ",\"requested\":%" PRIu32 ",\"result\":\"%s\"},",
           g_ev, rendered, v->requested, rname(r));
    if (rendered > MAX_FRAMES) { fprintf(stderr, "%s: rendered %u\n", v->id, (unsigned)rendered); exit(3); }

    ev_reset();
    r = tape_tell(t, &tell);
    fprintf(g_out, "{\"fn\":\"tape_tell\",\"value\":%" PRIu64 "},", tell);
    if (r != TAPE_OK || g_ev_len) { fprintf(stderr, "%s: tape_tell %s\n", v->id, rname(r)); exit(3); }

    memset(&st, 0, sizeof st);
    ev_reset();
    r = tape_status(t, &st);
    fprintf(g_out, "{\"at_end\":%s,\"at_start\":%s,\"fn\":\"tape_status\",\"result\":\"%s\"}],",
           st.at_end ? "true" : "false", st.at_start ? "true" : "false", rname(r));
    if (g_ev_len) { fprintf(stderr, "%s: tape_status made callbacks\n", v->id); exit(3); }

    fprintf(g_out, "\"at_end\":%s,\"at_start\":%s,\"pcm_hex\":\"", st.at_end ? "true" : "false", st.at_start ? "true" : "false");
    for (k = 0u; k < rendered; ++k) {
        uint16_t l = (uint16_t)out[2u * k], rr = (uint16_t)out[2u * k + 1u];
        fprintf(g_out, "%02x%02x%02x%02x", (unsigned)(l & 0xffu), (unsigned)(l >> 8), (unsigned)(rr & 0xffu), (unsigned)(rr >> 8));
    }
    fprintf(g_out, "\",\"rendered\":%" PRIu32 ",\"tell\":%" PRIu64 "}\n", rendered, tell);
}

int main(int argc, char **argv)
{
    uint32_t i;
    if (argc != 2) { fprintf(stderr, "usage: %s OUTPUT_JSONL\n", argv[0]); return 2; }
    g_out = fopen(argv[1], "wb");
    if (g_out == NULL) { fprintf(stderr, "cannot open %s\n", argv[1]); return 2; }
    g_media = calloc((size_t)(LBA_CHUNK_BASE + TOTAL_CHUNKS * CHUNK_BLOCKS + 1u), BLOCK);
    g_mem_len = tape_instance_size();
    g_mem = calloc(1u, g_mem_len);
    g_play = calloc(1u, TAPE_PLAY_RING_MIN);
    g_rec = calloc(1u, TAPE_REC_RING_MIN);
    if (g_media == NULL || g_mem == NULL || g_play == NULL || g_rec == NULL) { fprintf(stderr, "oom\n"); return 3; }
    for (i = 0u; i < VECTOR_COUNT; ++i) run(&VECTORS[i]);
    return fclose(g_out) == 0 ? 0 : 3;
}
