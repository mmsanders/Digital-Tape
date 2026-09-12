/*
 * vt8_ops_probe.c — mechanical VT8-001 adapter.
 *
 * Contract: tests/ops_draft8/ADAPTER.md (Verification-owned, imported verbatim).
 * This file exists only to (a) drive the frozen PUBLIC API through the two
 * scripted case sequences and (b) expose public-call results and harness-owned
 * block-device observations to the verifier runner. It is NOT a product API, it
 * implements no engine behaviour, and it observes no engine internals: the only
 * engine symbols it references are public functions declared in the real
 * product tape.h.
 *
 * Usage: vt8_ops_probe CASE_ID INPUT.vo08 OUTPUT.vo08
 *
 * Stdout is one VT8-OPS-OBSERVATION-1 object. Every callback is recorded in call
 * order, including unexpected ones and nonzero returns: observations are never
 * filtered to make a verdict pass. The runner owns evidence retention, media
 * archiving and adapter provenance.
 *
 * The public header is supplied mechanically so the same source can be linked
 * against any candidate engine archive:
 *     -DTAPE_PUBLIC_HEADER='"tape.h"' -I<engine>/include
 */

#ifndef TAPE_PUBLIC_HEADER
#define TAPE_PUBLIC_HEADER "tape.h"
#endif
#include TAPE_PUBLIC_HEADER

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

/* This adapter drives a real engine. The verifier's own stand-in reports
   "synthetic"; the runner rejects a mismatch against its --adapter-kind. */
#define ADAPTER_KIND "product"
#define OBS_FORMAT   "VT8-OPS-OBSERVATION-1"

/* --- VO08 envelope, per tests/ops_draft8/oracle.py Media --------------------- */

#define VO_BLOCK        512u
#define VO_SLOT_BYTES   65536u
#define VO_SLOT_BLOCKS  (VO_SLOT_BYTES / VO_BLOCK)   /* 128 */
#define VO_SLOTS        4u
#define VO_HEADER       8u
#define VO_SIZE         (VO_HEADER + 2u * VO_BLOCK + VO_SLOTS * VO_SLOT_BYTES)

#define LBA_PRIMARY     0u
#define LBA_A0          8u
#define LBA_CHUNK_BASE  2048u

#define POISON_BYTE     0xA5u
#define MAX_CHUNKS      64u          /* harness bound; fixtures use 16 */
#define SERVICE_GUARD   4096u        /* finite service guard */
#define SERVICE_BUDGET  8u           /* positive fixed block budget */
#define REC_FRAMES      128u

/* Harness-owned media image. Sparse at chunk granularity: an audio chunk is
   backed only once written, so unmapped audio reads stay deterministic poison. */
struct media {
    uint32_t  blocks;
    unsigned char primary[VO_BLOCK];
    unsigned char mirror[VO_BLOCK];
    unsigned char slots[VO_SLOTS][VO_SLOT_BYTES];
    unsigned char *chunk[MAX_CHUNKS];
};

static struct media g_media;

/* --- result symbols --------------------------------------------------------- */

static const char *result_name(tape_result r)
{
    switch (r) {
    case TAPE_OK:                     return "TAPE_OK";
    case TAPE_ERR_IO:                 return "TAPE_ERR_IO";
    case TAPE_ERR_BAD_MAGIC:          return "TAPE_ERR_BAD_MAGIC";
    case TAPE_ERR_CRC:                return "TAPE_ERR_CRC";
    case TAPE_ERR_VERSION:            return "TAPE_ERR_VERSION";
    case TAPE_ERR_UNSUPPORTED_STATE:  return "TAPE_ERR_UNSUPPORTED_STATE";
    case TAPE_ERR_GEOMETRY:           return "TAPE_ERR_GEOMETRY";
    case TAPE_ERR_INCOMPLETE:         return "TAPE_ERR_INCOMPLETE";
    case TAPE_ERR_INCONSISTENT:       return "TAPE_ERR_INCONSISTENT";
    case TAPE_ERR_NO_VALID_INDEX:     return "TAPE_ERR_NO_VALID_INDEX";
    case TAPE_ERR_READ_ONLY:          return "TAPE_ERR_READ_ONLY";
    case TAPE_ERR_CARTRIDGE_FULL:     return "TAPE_ERR_CARTRIDGE_FULL";
    case TAPE_ERR_INDEX_FULL:         return "TAPE_ERR_INDEX_FULL";
    case TAPE_ERR_DEST_TOO_SMALL:     return "TAPE_ERR_DEST_TOO_SMALL";
    case TAPE_ERR_SEQUENCE_EXHAUSTED: return "TAPE_ERR_SEQUENCE_EXHAUSTED";
    case TAPE_ERR_FAULTED:            return "TAPE_ERR_FAULTED";
    case TAPE_ERR_NOT_MOUNTED:        return "TAPE_ERR_NOT_MOUNTED";
    case TAPE_ERR_BUSY:               return "TAPE_ERR_BUSY";
    case TAPE_ERR_UNDERRUN:           return "TAPE_ERR_UNDERRUN";
    case TAPE_ERR_INVALID_ARG:        return "TAPE_ERR_INVALID_ARG";
    default:                          return "TAPE_ERR_UNKNOWN";
    }
}

/* --- event trace ------------------------------------------------------------ */

struct event {
    const char *phase;
    const char *op;          /* "read" | "write" | "flush" */
    uint32_t lba, count;
    int rc;
    bool has_extent;         /* flush omits lba/count */
};

#define MAX_EVENTS 262144
static struct event g_events[MAX_EVENTS];
static size_t g_event_count;
static bool   g_event_overflow;

/* Set by the wrapper immediately before each public call; never reported by the
   engine. "init" is deliberately outside the contract's allowed phase set, so
   block I/O during tape_init surfaces as a schema violation instead of being
   quietly attributed to the mount that follows. */
static const char *g_phase = "init";

static void record(const char *op, uint32_t lba, uint32_t count, int rc, bool extent)
{
    if (g_event_count >= MAX_EVENTS) { g_event_overflow = true; return; }
    g_events[g_event_count].phase = g_phase;
    g_events[g_event_count].op = op;
    g_events[g_event_count].lba = lba;
    g_events[g_event_count].count = count;
    g_events[g_event_count].rc = rc;
    g_events[g_event_count].has_extent = extent;
    g_event_count++;
}

/* --- public-call results ---------------------------------------------------- */

/* One ordered entry per public call the script performs, carrying the result
   fields the script depends on. Optional fields are emitted only when set, so
   the object shape matches the contract exactly. */
struct call_rec {
    const char *phase;
    const char *call;
    const char *result;
    const char *side;            /* "A" | "B" | NULL */
    const char *mode;            /* record mode | NULL */
    bool     has_side_b_valid, side_b_valid;
    bool     has_frame;      uint64_t frame;
    bool     has_requested;  uint32_t requested;
    bool     has_accepted;   uint32_t accepted;
    bool     has_budget;     uint32_t budget;
    bool     has_more_work;  bool     more_work;
};

#define MAX_CALLS 8192
static struct call_rec g_calls[MAX_CALLS];
static size_t g_call_count;

static struct call_rec *push_call(const char *phase, const char *call, tape_result r)
{
    struct call_rec *c;
    if (g_call_count >= MAX_CALLS) return NULL;
    c = &g_calls[g_call_count++];
    memset(c, 0, sizeof *c);
    c->phase = phase;
    c->call = call;
    c->result = result_name(r);
    return c;
}

/* --- block resolution ------------------------------------------------------- */

static unsigned char *block_at(uint32_t lba, bool alloc)
{
    if (lba == LBA_PRIMARY) return g_media.primary;
    if (lba == g_media.blocks - 1u) return g_media.mirror;
    if (lba >= LBA_A0 && lba < LBA_A0 + VO_SLOTS * VO_SLOT_BLOCKS) {
        uint32_t off = lba - LBA_A0;
        return g_media.slots[off / VO_SLOT_BLOCKS] + (off % VO_SLOT_BLOCKS) * VO_BLOCK;
    }
    if (lba >= LBA_CHUNK_BASE && lba < g_media.blocks - 1u) {
        uint32_t rel = lba - LBA_CHUNK_BASE;
        uint32_t ci  = rel / 1024u;
        if (ci >= MAX_CHUNKS) return NULL;
        if (g_media.chunk[ci] == NULL) {
            if (!alloc) return NULL;
            g_media.chunk[ci] = malloc(1024u * VO_BLOCK);
            if (g_media.chunk[ci] == NULL) return NULL;
            memset(g_media.chunk[ci], (int)POISON_BYTE, 1024u * VO_BLOCK);
        }
        return g_media.chunk[ci] + (rel % 1024u) * VO_BLOCK;
    }
    return NULL;
}

/* Widened arithmetic, evaluated before any copy. */
static bool in_range(uint32_t lba, uint32_t count)
{
    uint64_t end = (uint64_t)lba + (uint64_t)count;
    return count != 0u && end <= (uint64_t)g_media.blocks;
}

static int dev_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    unsigned char *out = dst;
    uint32_t i;
    (void)ctx;
    if (!in_range(lba, count)) { record("read", lba, count, -1, true); return -1; }
    for (i = 0; i < count; i++) {
        const unsigned char *src = block_at(lba + i, false);
        if (src != NULL) memcpy(out + (size_t)i * VO_BLOCK, src, VO_BLOCK);
        else             memset(out + (size_t)i * VO_BLOCK, (int)POISON_BYTE, VO_BLOCK);
    }
    record("read", lba, count, 0, true);
    return 0;
}

static int dev_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    const unsigned char *in = src;
    uint32_t i;
    (void)ctx;
    if (!in_range(lba, count)) { record("write", lba, count, -1, true); return -1; }
    for (i = 0; i < count; i++) {
        unsigned char *dst = block_at(lba + i, true);
        if (dst == NULL) { record("write", lba, count, -1, true); return -1; }
        memcpy(dst, in + (size_t)i * VO_BLOCK, VO_BLOCK);
    }
    record("write", lba, count, 0, true);
    return 0;
}

static int dev_flush(void *ctx)
{
    (void)ctx;
    record("flush", 0, 0, 0, false);
    return 0;
}

/* --- envelope I/O ----------------------------------------------------------- */

static int media_load(const char *path)
{
    static unsigned char buf[VO_SIZE];
    size_t got;
    FILE *f = fopen(path, "rb");
    if (f == NULL) { fprintf(stderr, "cannot open input %s\n", path); return -1; }
    got = fread(buf, 1u, sizeof buf, f);
    if (got != sizeof buf || fgetc(f) != EOF) {
        fprintf(stderr, "input is not a %u-byte VO08 envelope (%zu bytes)\n",
                (unsigned)VO_SIZE, got);
        fclose(f); return -1;
    }
    fclose(f);
    if (memcmp(buf, "VO08", 4) != 0) { fprintf(stderr, "bad VO08 magic\n"); return -1; }
    memset(&g_media, 0, sizeof g_media);
    g_media.blocks = (uint32_t)buf[4] | ((uint32_t)buf[5] << 8)
                   | ((uint32_t)buf[6] << 16) | ((uint32_t)buf[7] << 24);
    {
        size_t p = VO_HEADER;
        unsigned s;
        memcpy(g_media.primary, buf + p, VO_BLOCK); p += VO_BLOCK;
        memcpy(g_media.mirror,  buf + p, VO_BLOCK); p += VO_BLOCK;
        for (s = 0; s < VO_SLOTS; s++) { memcpy(g_media.slots[s], buf + p, VO_SLOT_BYTES); p += VO_SLOT_BYTES; }
    }
    return 0;
}

static int media_store(const char *path)
{
    static unsigned char buf[VO_SIZE];
    size_t p = VO_HEADER;
    unsigned s;
    FILE *f;
    memcpy(buf, "VO08", 4);
    buf[4] = (unsigned char)(g_media.blocks & 0xFFu);
    buf[5] = (unsigned char)((g_media.blocks >> 8) & 0xFFu);
    buf[6] = (unsigned char)((g_media.blocks >> 16) & 0xFFu);
    buf[7] = (unsigned char)((g_media.blocks >> 24) & 0xFFu);
    memcpy(buf + p, g_media.primary, VO_BLOCK); p += VO_BLOCK;
    memcpy(buf + p, g_media.mirror,  VO_BLOCK); p += VO_BLOCK;
    for (s = 0; s < VO_SLOTS; s++) { memcpy(buf + p, g_media.slots[s], VO_SLOT_BYTES); p += VO_SLOT_BYTES; }
    f = fopen(path, "wb");
    if (f == NULL) { fprintf(stderr, "cannot open output %s\n", path); return -1; }
    if (fwrite(buf, 1u, sizeof buf, f) != sizeof buf) { fclose(f); return -1; }
    if (fclose(f) != 0) return -1;
    return 0;
}

/* --- JSON emission --------------------------------------------------------- */

static void emit_json(void)
{
    size_t i;
    printf("{\"format\":\"%s\",\"adapter_kind\":\"%s\",\"calls\":[", OBS_FORMAT, ADAPTER_KIND);
    for (i = 0; i < g_call_count; i++) {
        const struct call_rec *c = &g_calls[i];
        if (i != 0) printf(",");
        printf("{\"phase\":\"%s\",\"call\":\"%s\",\"result\":\"%s\"", c->phase, c->call, c->result);
        if (c->side != NULL)        printf(",\"side\":\"%s\"", c->side);
        if (c->mode != NULL)        printf(",\"mode\":\"%s\"", c->mode);
        if (c->has_side_b_valid)    printf(",\"side_b_valid\":%s", c->side_b_valid ? "true" : "false");
        if (c->has_frame)           printf(",\"frame\":%llu", (unsigned long long)c->frame);
        if (c->has_requested)       printf(",\"requested\":%lu", (unsigned long)c->requested);
        if (c->has_accepted)        printf(",\"accepted\":%lu", (unsigned long)c->accepted);
        if (c->has_budget)          printf(",\"block_budget\":%lu", (unsigned long)c->budget);
        if (c->has_more_work)       printf(",\"more_work\":%s", c->more_work ? "true" : "false");
        printf("}");
    }
    printf("],\"events\":[");
    for (i = 0; i < g_event_count; i++) {
        const struct event *e = &g_events[i];
        if (i != 0) printf(",");
        if (e->has_extent)
            printf("{\"phase\":\"%s\",\"op\":\"%s\",\"lba\":%lu,\"count\":%lu,\"rc\":%d}",
                   e->phase, e->op, (unsigned long)e->lba, (unsigned long)e->count, e->rc);
        else
            printf("{\"phase\":\"%s\",\"op\":\"%s\",\"rc\":%d}", e->phase, e->op, e->rc);
    }
    printf("],\"event_overflow\":%s,\"service_guard\":%u}\n",
           g_event_overflow ? "true" : "false", SERVICE_GUARD);
}

/* --- caller-owned storage (guardrail 08: the caller owns every buffer) ------ */

static unsigned char g_inst_a[65536];
static unsigned char g_inst_b[65536];
static unsigned char g_play_a[TAPE_PLAY_RING_MIN];
static unsigned char g_rec_a[TAPE_REC_RING_MIN];
static unsigned char g_play_b[TAPE_PLAY_RING_MIN];
static unsigned char g_rec_b[TAPE_REC_RING_MIN];

static tape_dev g_dev;

static void dev_init(void)
{
    g_dev.read = dev_read;
    g_dev.write = dev_write;
    g_dev.flush = dev_flush;
    g_dev.ctx = NULL;
    g_dev.block_count = g_media.blocks;
}

/* tape_instance_size and tape_init are harness setup, not script steps: the
   contract's call sequence starts at tape_mount, so they are not recorded. */
static tape_result open_instance(unsigned char *inst, size_t inst_len,
                                 void *play, void *rec, tape **out)
{
    size_t need = tape_instance_size();
    if (need > inst_len) {
        fprintf(stderr, "instance needs %zu bytes, harness reserved %zu\n", need, inst_len);
        return TAPE_ERR_INVALID_ARG;
    }
    return tape_init(inst, need, &g_dev, play, TAPE_PLAY_RING_MIN, rec, TAPE_REC_RING_MIN, out);
}

/* --- case scripts ---------------------------------------------------------- */

static int case_reset_b(void)
{
    tape *t = NULL;
    tape_info info;
    tape_result r;
    struct call_rec *c;
    int failed = 0;

    r = open_instance(g_inst_a, sizeof g_inst_a, g_play_a, g_rec_a, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init: %s\n", result_name(r)); return 1; }

    g_phase = "mount";
    r = tape_mount(t, TAPE_SIDE_A, 0u, NULL);
    c = push_call("mount", "tape_mount", r); if (c) c->side = "A";
    if (r != TAPE_OK) return 1;

    g_phase = "get_info";
    memset(&info, 0, sizeof info);
    r = tape_get_info(t, &info);
    c = push_call("get_info", "tape_get_info", r);
    if (c) { c->has_side_b_valid = true; c->side_b_valid = info.side_b_valid; }
    if (r != TAPE_OK) return 1;
    if (info.side_b_valid) {
        fprintf(stderr, "fixture precondition: expected degraded-B, side_b_valid is true\n");
        failed = 1;
    }

    g_phase = "reset_b";
    r = tape_reset_side_b(t);
    push_call("reset_b", "tape_reset_side_b", r);
    if (r != TAPE_OK) failed = 1;

    g_phase = "unmount";
    r = tape_unmount(t, NULL);
    push_call("unmount", "tape_unmount", r);
    if (r != TAPE_OK) failed = 1;

    g_phase = "remount";
    t = NULL;
    r = open_instance(g_inst_b, sizeof g_inst_b, g_play_b, g_rec_b, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init(2): %s\n", result_name(r)); return 1; }
    r = tape_mount(t, TAPE_SIDE_B, 0u, NULL);
    c = push_call("remount", "tape_mount", r); if (c) c->side = "B";
    if (r != TAPE_OK) failed = 1;

    return failed;
}

static int case_rec_allocseq(void)
{
    tape *t = NULL;
    tape_result r;
    struct call_rec *c;
    int failed = 0;
    static int16_t pcm[REC_FRAMES * 2];
    uint32_t i, accepted = 0u;

    for (i = 0; i < REC_FRAMES; i++) {          /* deterministic; PCM is not an oracle */
        pcm[2u * i]      = (int16_t)(i * 7);
        pcm[2u * i + 1u] = (int16_t)(-(int)(i * 5));
    }

    r = open_instance(g_inst_a, sizeof g_inst_a, g_play_a, g_rec_a, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init: %s\n", result_name(r)); return 1; }

    g_phase = "mount";
    r = tape_mount(t, TAPE_SIDE_B, 0u, NULL);
    c = push_call("mount", "tape_mount", r); if (c) c->side = "B";
    if (r != TAPE_OK) return 1;

    g_phase = "seek";
    r = tape_seek(t, (uint64_t)REC_FRAMES);
    c = push_call("seek", "tape_seek", r);
    if (c) { c->has_frame = true; c->frame = (uint64_t)REC_FRAMES; }
    if (r != TAPE_OK) failed = 1;

    g_phase = "arm";
    r = tape_arm(t, TAPE_REC_SPLICE);
    c = push_call("arm", "tape_arm", r); if (c) c->mode = "TAPE_REC_SPLICE";
    if (r != TAPE_OK) failed = 1;

    g_phase = "feed";
    r = tape_feed(t, pcm, REC_FRAMES, &accepted);
    c = push_call("feed", "tape_feed", r);
    if (c) { c->has_requested = true; c->requested = REC_FRAMES;
             c->has_accepted = true;  c->accepted = accepted; }
    if (r != TAPE_OK || accepted != REC_FRAMES) failed = 1;

    g_phase = "service";
    {
        bool more = true;
        uint32_t iter = 0u;
        while (more) {
            if (iter >= SERVICE_GUARD) {
                fprintf(stderr, "finite service guard tripped after %u calls\n", iter);
                failed = 1;
                break;
            }
            r = tape_service(t, SERVICE_BUDGET, &more);
            iter++;
            c = push_call("service", "tape_service", r);
            if (c) { c->has_budget = true; c->budget = SERVICE_BUDGET;
                     c->has_more_work = true; c->more_work = more; }
            if (r != TAPE_OK) { failed = 1; break; }
        }
    }

    g_phase = "commit";
    r = tape_commit(t);
    push_call("commit", "tape_commit", r);
    if (r != TAPE_OK) failed = 1;

    g_phase = "unmount";
    r = tape_unmount(t, NULL);
    push_call("unmount", "tape_unmount", r);
    if (r != TAPE_OK) failed = 1;

    g_phase = "remount";
    t = NULL;
    r = open_instance(g_inst_b, sizeof g_inst_b, g_play_b, g_rec_b, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init(2): %s\n", result_name(r)); return 1; }
    r = tape_mount(t, TAPE_SIDE_B, 0u, NULL);
    c = push_call("remount", "tape_mount", r); if (c) c->side = "B";
    if (r != TAPE_OK) failed = 1;

    return failed;
}

int main(int argc, char **argv)
{
    int failed;
    if (argc != 4) {
        fprintf(stderr, "usage: %s CASE_ID INPUT.vo08 OUTPUT.vo08\n", argv[0]);
        return 2;
    }
    if (media_load(argv[2]) != 0) return 2;
    dev_init();

    if (strcmp(argv[1], "VT8-001-RB-ALLSLOT") == 0)        failed = case_reset_b();
    else if (strcmp(argv[1], "VT8-001-REC-ALLOCSEQ") == 0) failed = case_rec_allocseq();
    else { fprintf(stderr, "unknown case %s\n", argv[1]); return 2; }

    if (media_store(argv[3]) != 0) failed = 1;
    emit_json();
    if (g_event_overflow) { fprintf(stderr, "event trace overflowed\n"); failed = 1; }
    if (g_call_count >= MAX_CALLS) { fprintf(stderr, "call trace overflowed\n"); failed = 1; }
    return failed ? 1 : 0;
}
