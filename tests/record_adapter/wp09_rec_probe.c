/*
 * wp09_rec_probe.c — mechanical WP-09 record adapter.
 *
 * Contract: tests/record_draft8/ADAPTER.md (Verification-owned, imported
 * verbatim and not modified by this file). This adapter exists only to (a)
 * drive the frozen PUBLIC API through each scripted case and (b) expose
 * public-call results and harness-owned block-device observations to the
 * verifier's own oracles. It is NOT a product API, it implements no engine
 * behaviour, and it observes no engine internals: the only engine symbols it
 * references are public functions declared in the real product tape.h.
 *
 * Usage: wp09_rec_probe CASE_ID INPUT.vo08 OUTPUT.vo08
 *
 * Stdout is one WP09-REC-OBSERVATION-1 object. Every callback is recorded in
 * call order, including unexpected ones and nonzero returns: observations are
 * never filtered to make a verdict pass. Where the contract requires an exact
 * per-call callback count (tape_feed, and the one-frame tail tape_render), it
 * is the difference between the trace length before and after that single call
 * — a counter, not a claim.
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

#define ADAPTER_KIND "product"
#define OBS_FORMAT   "WP09-REC-OBSERVATION-1"

/* --- VO08 envelope, per tests/record_draft8/oracle.py Media ----------------- */

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
#define MAX_CHUNKS      64u          /* harness bound; fixtures derive 21 */
#define SERVICE_GUARD   65536u       /* finite service guard */
#define SERVICE_BUDGET  8u           /* positive fixed block budget */

/*
 * Caller-owned record ring. WP09-OW-MULTICHUNK feeds CHUNK_FRAMES + 64 frames
 * and its oracle requires a SINGLE tape_feed to accept all of them, so the ring
 * the harness supplies has to hold them. Guardrail 08 bounds the ENGINE's RAM,
 * not the caller's buffers (spec §4: the caller owns all storage), so this is a
 * harness number and not an engine one.
 */
#define REC_RING_FRAMES 262144u
#define REC_RING_BYTES  (REC_RING_FRAMES * TAPE_FRAME_BYTES)
#define MAX_FEED_FRAMES (TAPE_CHUNK_FRAMES + 64u)

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

/* Set by the wrapper immediately before each public call. "init" is deliberately
   outside the contract's phase set, so block I/O during tape_init surfaces as a
   schema violation instead of being attributed to the mount that follows. */
static const char *g_phase = "init";

static void record_event(const char *op, uint32_t lba, uint32_t count, int rc, bool extent)
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

struct call_rec {
    const char *phase;
    const char *fn;
    const char *result;
    const char *side;            /* "A" | "B" | NULL */
    const char *mode;            /* "overwrite" | "overdub" | "splice" | NULL */
    bool     has_frame;       uint64_t frame;
    bool     has_requested;   uint32_t requested;
    bool     has_accepted;    uint32_t accepted;
    bool     has_rendered;    uint32_t rendered;
    bool     has_rate;        int32_t  rate;
    bool     has_more_work;   bool     more_work;
    bool     has_evcount;     unsigned long evcount;
};

#define MAX_CALLS 8192
static struct call_rec g_calls[MAX_CALLS];
static size_t g_call_count;

static struct call_rec *push_call(const char *phase, const char *fn, tape_result r)
{
    struct call_rec *c;
    if (g_call_count >= MAX_CALLS) return NULL;
    c = &g_calls[g_call_count++];
    memset(c, 0, sizeof *c);
    c->phase = phase;
    c->fn = fn;
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
        uint32_t ci  = rel / TAPE_CHUNK_BLOCKS;
        if (ci >= MAX_CHUNKS) return NULL;
        if (g_media.chunk[ci] == NULL) {
            if (!alloc) return NULL;
            g_media.chunk[ci] = malloc((size_t)TAPE_CHUNK_BLOCKS * VO_BLOCK);
            if (g_media.chunk[ci] == NULL) return NULL;
            memset(g_media.chunk[ci], (int)POISON_BYTE, (size_t)TAPE_CHUNK_BLOCKS * VO_BLOCK);
        }
        return g_media.chunk[ci] + (rel % TAPE_CHUNK_BLOCKS) * VO_BLOCK;
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
    if (!in_range(lba, count)) { record_event("read", lba, count, -1, true); return -1; }
    for (i = 0; i < count; i++) {
        const unsigned char *src = block_at(lba + i, false);
        if (src != NULL) memcpy(out + (size_t)i * VO_BLOCK, src, VO_BLOCK);
        else             memset(out + (size_t)i * VO_BLOCK, (int)POISON_BYTE, VO_BLOCK);
    }
    record_event("read", lba, count, 0, true);
    return 0;
}

static int dev_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    const unsigned char *in = src;
    uint32_t i;
    (void)ctx;
    if (!in_range(lba, count)) { record_event("write", lba, count, -1, true); return -1; }
    for (i = 0; i < count; i++) {
        unsigned char *dst = block_at(lba + i, true);
        if (dst == NULL) { record_event("write", lba, count, -1, true); return -1; }
        memcpy(dst, in + (size_t)i * VO_BLOCK, VO_BLOCK);
    }
    record_event("write", lba, count, 0, true);
    return 0;
}

static int dev_flush(void *ctx)
{
    (void)ctx;
    record_event("flush", 0, 0, 0, false);
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
        printf("{\"phase\":\"%s\",\"fn\":\"%s\",\"result\":\"%s\"", c->phase, c->fn, c->result);
        if (c->side != NULL)     printf(",\"side\":\"%s\"", c->side);
        if (c->mode != NULL)     printf(",\"mode\":\"%s\"", c->mode);
        if (c->has_frame)        printf(",\"frame\":%llu", (unsigned long long)c->frame);
        if (c->has_requested)    printf(",\"requested\":%lu", (unsigned long)c->requested);
        if (c->has_accepted)     printf(",\"accepted\":%lu", (unsigned long)c->accepted);
        if (c->has_rendered)     printf(",\"rendered\":%lu", (unsigned long)c->rendered);
        if (c->has_rate)         printf(",\"rate_q16_16\":%ld", (long)c->rate);
        if (c->has_more_work)    printf(",\"more_work\":%s", c->more_work ? "true" : "false");
        if (c->has_evcount)      printf(",\"events_from_call\":%lu", c->evcount);
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

/* Guardrail 08 caps the engine's WHOLE RAM budget -- .data + .bss + the
   instance -- at 200 KiB, so a 256 KiB reservation is sufficient for any
   conforming engine by construction and cannot go stale the way a number
   copied from one candidate's tape_instance_size() would. open_instance()
   still checks the real size at run time and fails loudly if that changes. */
#define INSTANCE_BYTES 262144u

static unsigned char g_inst_a[INSTANCE_BYTES];
static unsigned char g_inst_b[INSTANCE_BYTES];
static unsigned char g_play_a[TAPE_PLAY_RING_MIN];
static unsigned char g_play_b[TAPE_PLAY_RING_MIN];
static unsigned char g_rec_a[REC_RING_BYTES];
static unsigned char g_rec_b[REC_RING_BYTES];
static int16_t       g_pcm[MAX_FEED_FRAMES * TAPE_CHANNELS];

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
    return tape_init(inst, need, &g_dev, play, TAPE_PLAY_RING_MIN, rec, REC_RING_BYTES, out);
}

/* --- the case table --------------------------------------------------------- */

enum script { SC_HAPPY, SC_EMPTY, SC_ARM_REFUSE, SC_CART_FULL, SC_ABORT, SC_ARMED_BUSY };

struct case_row {
    const char   *id;
    enum script   script;
    tape_side     side;
    uint64_t      seek;
    tape_rec_mode mode;
    uint32_t      feed;
};

/* Exactly the scripts of tests/record_draft8/{oracle,extra,refusals}.py. The
   seek, mode and feed values are the verifier's, transcribed; nothing here
   chooses them. */
static const struct case_row g_cases[] = {
    { "WP09-OW-MID",         SC_HAPPY,      TAPE_SIDE_B, 128u, TAPE_REC_OVERWRITE, 64u },
    { "WP09-OW-END",         SC_HAPPY,      TAPE_SIDE_B, 256u, TAPE_REC_OVERWRITE, 64u },
    { "WP09-OD-MID",         SC_HAPPY,      TAPE_SIDE_B, 128u, TAPE_REC_OVERDUB,   64u },
    { "WP09-SP-T0",          SC_HAPPY,      TAPE_SIDE_B,   0u, TAPE_REC_SPLICE,    64u },
    { "WP09-SP-MID",         SC_HAPPY,      TAPE_SIDE_B, 128u, TAPE_REC_SPLICE,    64u },
    { "WP09-SP-END",         SC_HAPPY,      TAPE_SIDE_B, 256u, TAPE_REC_SPLICE,    64u },
    { "WP09-OW-MULTICHUNK",  SC_HAPPY,      TAPE_SIDE_B,   0u, TAPE_REC_OVERWRITE, MAX_FEED_FRAMES },
    { "WP09-SP-EMPTY-B",     SC_HAPPY,      TAPE_SIDE_B,   0u, TAPE_REC_SPLICE,    64u },
    { "WP09-SP-BOUNDARY",    SC_HAPPY,      TAPE_SIDE_B, 128u, TAPE_REC_SPLICE,    64u },
    { "WP09-STAGE-CLEAR",    SC_HAPPY,      TAPE_SIDE_B,  64u, TAPE_REC_OVERWRITE, 64u },

    { "WP09-EMPTY-COMMIT",   SC_EMPTY,      TAPE_SIDE_B, 128u, TAPE_REC_OVERWRITE,  0u },
    { "WP09-EMPTY-OW-START", SC_EMPTY,      TAPE_SIDE_B,   0u, TAPE_REC_OVERWRITE,  0u },
    { "WP09-EMPTY-OW-END",   SC_EMPTY,      TAPE_SIDE_B, 256u, TAPE_REC_OVERWRITE,  0u },
    { "WP09-EMPTY-OD-START", SC_EMPTY,      TAPE_SIDE_B,   0u, TAPE_REC_OVERDUB,    0u },
    { "WP09-EMPTY-OD",       SC_EMPTY,      TAPE_SIDE_B, 128u, TAPE_REC_OVERDUB,    0u },
    { "WP09-EMPTY-OD-END",   SC_EMPTY,      TAPE_SIDE_B, 256u, TAPE_REC_OVERDUB,    0u },
    { "WP09-EMPTY-SP-START", SC_EMPTY,      TAPE_SIDE_B,   0u, TAPE_REC_SPLICE,     0u },
    { "WP09-EMPTY-SP",       SC_EMPTY,      TAPE_SIDE_B, 128u, TAPE_REC_SPLICE,     0u },
    { "WP09-EMPTY-SP-END",   SC_EMPTY,      TAPE_SIDE_B, 256u, TAPE_REC_SPLICE,     0u },

    { "WP09-ARMED-BUSY",     SC_ARMED_BUSY, TAPE_SIDE_B, 128u, TAPE_REC_OVERWRITE,  0u },
    { "WP09-RO-SIDE-A",      SC_ARM_REFUSE, TAPE_SIDE_A,   0u, TAPE_REC_OVERWRITE,  0u },
    { "WP09-SEQ-EXHAUSTED",  SC_ARM_REFUSE, TAPE_SIDE_B,   0u, TAPE_REC_OVERWRITE,  0u },
    { "WP09-INDEX-FULL",     SC_ARM_REFUSE, TAPE_SIDE_B,   0u, TAPE_REC_SPLICE,     0u },
    { "WP09-STAGE-REFUSE",   SC_ARM_REFUSE, TAPE_SIDE_B,   0u, TAPE_REC_OVERWRITE,  0u },
    { "WP09-CART-FULL",      SC_CART_FULL,  TAPE_SIDE_B,   0u, TAPE_REC_OVERWRITE, 64u },
    { "WP09-ABORT-DISARM",   SC_ABORT,      TAPE_SIDE_B, 128u, TAPE_REC_OVERWRITE,  0u },
};

static const char *mode_name(tape_rec_mode m)
{
    switch (m) {
    case TAPE_REC_OVERWRITE: return "overwrite";
    case TAPE_REC_OVERDUB:   return "overdub";
    case TAPE_REC_SPLICE:    return "splice";
    default:                 return "unknown";
    }
}

static const char *side_name(tape_side s)
{
    return (s == TAPE_SIDE_A) ? "A" : "B";
}

/* --- scripted steps --------------------------------------------------------- */

static tape_result step_mount(tape *t, const char *phase, tape_side side, int *failed)
{
    struct call_rec *c;
    tape_result r;
    g_phase = phase;
    r = tape_mount(t, side, 0u, NULL);
    c = push_call(phase, "tape_mount", r);
    if (c) c->side = side_name(side);
    if (r != TAPE_OK) *failed = 1;
    return r;
}

static tape_result step_seek(tape *t, const char *phase, uint64_t frame, int *failed,
                             tape_result expect)
{
    struct call_rec *c;
    tape_result r;
    g_phase = phase;
    r = tape_seek(t, frame);
    c = push_call(phase, "tape_seek", r);
    if (c) { c->has_frame = true; c->frame = frame; }
    if (r != expect) *failed = 1;
    return r;
}

static tape_result step_rate(tape *t, const char *phase, int32_t rate, int *failed,
                             tape_result expect)
{
    struct call_rec *c;
    tape_result r;
    g_phase = phase;
    r = tape_set_rate(t, rate);
    c = push_call(phase, "tape_set_rate", r);
    if (c) { c->has_rate = true; c->rate = rate; }
    if (r != expect) *failed = 1;
    return r;
}

static tape_result step_arm(tape *t, tape_rec_mode mode, int *failed, tape_result expect)
{
    struct call_rec *c;
    tape_result r;
    g_phase = "arm";
    r = tape_arm(t, mode);
    c = push_call("arm", "tape_arm", r);
    if (c) c->mode = mode_name(mode);
    if (r != expect) *failed = 1;
    return r;
}

static tape_result step_feed(tape *t, uint32_t frames, int *failed, tape_result expect,
                             uint32_t expect_accepted)
{
    struct call_rec *c;
    tape_result r;
    uint32_t accepted = 0u, i;
    size_t before;

    for (i = 0; i < frames; i++) {             /* deterministic; PCM is not an oracle */
        g_pcm[2u * i]      = (int16_t)(i * 7);
        g_pcm[2u * i + 1u] = (int16_t)(-(int)(i * 5));
    }
    g_phase = "feed";
    before = g_event_count;
    r = tape_feed(t, g_pcm, frames, &accepted);
    c = push_call("feed", "tape_feed", r);
    if (c) {
        c->has_requested = true; c->requested = frames;
        c->has_accepted  = true; c->accepted  = accepted;
        /* The contract is explicit that omitting this is NOT equivalent to
           zero, so it is always emitted and it is always a measurement. */
        c->has_evcount   = true; c->evcount   = (unsigned long)(g_event_count - before);
    }
    if (r != expect || accepted != expect_accepted) *failed = 1;
    return r;
}

static void step_service(tape *t, const char *phase, int *failed)
{
    bool more = true;
    uint32_t iter = 0u;
    while (more) {
        struct call_rec *c;
        tape_result r;
        if (iter >= SERVICE_GUARD) {
            fprintf(stderr, "finite service guard tripped after %u calls\n", iter);
            *failed = 1;
            return;
        }
        g_phase = phase;
        r = tape_service(t, SERVICE_BUDGET, &more);
        iter++;
        c = push_call(phase, "tape_service", r);
        if (c) { c->has_more_work = true; c->more_work = more; }
        if (r != TAPE_OK) { *failed = 1; return; }
    }
}

static void step_commit(tape *t, int *failed)
{
    tape_result r;
    g_phase = "commit";
    r = tape_commit(t);
    push_call("commit", "tape_commit", r);
    if (r != TAPE_OK) *failed = 1;
}

static void step_abort(tape *t, int *failed)
{
    tape_result r;
    g_phase = "abort";
    r = tape_abort(t);
    push_call("abort", "tape_abort", r);
    if (r != TAPE_OK) *failed = 1;
}

static void step_unmount(tape *t, int *failed)
{
    tape_result r;
    g_phase = "unmount";
    r = tape_unmount(t, NULL);
    push_call("unmount", "tape_unmount", r);
    if (r != TAPE_OK) *failed = 1;
}

/* The tail probe of the zero-accepted matrix: the pre-existing timeline must
   still be usable after the no-op. One frame, and the contract requires the
   exact callback count of that one render call. */
static void step_tail_render(tape *t, int *failed)
{
    struct call_rec *c;
    tape_result r;
    int16_t out[TAPE_CHANNELS];
    uint32_t rendered = 0u;
    size_t before;

    g_phase = "tail-render";
    before = g_event_count;
    r = tape_render(t, out, 1u, &rendered);
    c = push_call("tail-render", "tape_render", r);
    if (c) {
        c->has_requested = true; c->requested = 1u;
        c->has_rendered  = true; c->rendered  = rendered;
        c->has_evcount   = true; c->evcount   = (unsigned long)(g_event_count - before);
    }
    if (r != TAPE_OK || rendered != 1u) *failed = 1;
}

static void step_remount(int *failed)
{
    tape *t = NULL;
    tape_result r = open_instance(g_inst_b, sizeof g_inst_b, g_play_b, g_rec_b, &t);
    if (r != TAPE_OK) {
        fprintf(stderr, "tape_init(2): %s\n", result_name(r));
        *failed = 1;
        return;
    }
    (void)step_mount(t, "remount", TAPE_SIDE_B, failed);
}

/* --- case driver ------------------------------------------------------------ */

static int run_case(const struct case_row *row)
{
    tape *t = NULL;
    tape_result r;
    int failed = 0;

    r = open_instance(g_inst_a, sizeof g_inst_a, g_play_a, g_rec_a, &t);
    if (r != TAPE_OK) { fprintf(stderr, "tape_init: %s\n", result_name(r)); return 1; }

    if (step_mount(t, "mount", row->side, &failed) != TAPE_OK) { return 1; }

    switch (row->script) {
    case SC_HAPPY:
        (void)step_seek(t, "seek", row->seek, &failed, TAPE_OK);
        (void)step_arm(t, row->mode, &failed, TAPE_OK);
        (void)step_feed(t, row->feed, &failed, TAPE_OK, row->feed);
        step_service(t, "service", &failed);
        step_commit(t, &failed);
        step_unmount(t, &failed);
        step_remount(&failed);
        break;

    case SC_EMPTY: {
        uint64_t probe;
        (void)step_seek(t, "seek", row->seek, &failed, TAPE_OK);
        (void)step_arm(t, row->mode, &failed, TAPE_OK);
        step_commit(t, &failed);
        probe = (row->seek < 255u) ? row->seek : 255u;
        (void)step_seek(t, "tail-seek", probe, &failed, TAPE_OK);
        (void)step_rate(t, "tail-rate", 65536, &failed, TAPE_OK);
        step_service(t, "tail-service", &failed);
        step_tail_render(t, &failed);
        (void)step_rate(t, "tail-stop", 0, &failed, TAPE_OK);
        step_unmount(t, &failed);
        step_remount(&failed);
        break;
    }

    case SC_ARMED_BUSY:
        (void)step_seek(t, "seek", row->seek, &failed, TAPE_OK);
        (void)step_arm(t, row->mode, &failed, TAPE_OK);
        /* §10 forbids both while armed; each is probed exactly once. */
        (void)step_seek(t, "armed", 0u, &failed, TAPE_ERR_BUSY);
        (void)step_rate(t, "armed", 65536, &failed, TAPE_ERR_BUSY);
        step_abort(t, &failed);
        step_unmount(t, &failed);
        break;

    case SC_ARM_REFUSE: {
        /* The named refusal is the expected result, so a TAPE_OK here is the
           failure. RO-SIDE-A has no scripted seek, matching the package. */
        tape_result expect = TAPE_ERR_READ_ONLY;
        if (strcmp(row->id, "WP09-SEQ-EXHAUSTED") == 0
         || strcmp(row->id, "WP09-STAGE-REFUSE") == 0) expect = TAPE_ERR_SEQUENCE_EXHAUSTED;
        else if (strcmp(row->id, "WP09-INDEX-FULL") == 0) expect = TAPE_ERR_INDEX_FULL;
        if (row->side != TAPE_SIDE_A) {
            (void)step_seek(t, "seek", row->seek, &failed, TAPE_OK);
        }
        (void)step_arm(t, row->mode, &failed, expect);
        step_unmount(t, &failed);
        break;
    }

    case SC_CART_FULL:
        (void)step_seek(t, "seek", row->seek, &failed, TAPE_OK);
        (void)step_arm(t, row->mode, &failed, TAPE_OK);
        (void)step_feed(t, row->feed, &failed, TAPE_ERR_CARTRIDGE_FULL, 0u);
        step_abort(t, &failed);
        step_unmount(t, &failed);
        break;

    case SC_ABORT:
        (void)step_seek(t, "seek", row->seek, &failed, TAPE_OK);
        (void)step_arm(t, row->mode, &failed, TAPE_OK);
        step_abort(t, &failed);
        step_unmount(t, &failed);
        break;
    }

    return failed;
}

int main(int argc, char **argv)
{
    const struct case_row *row = NULL;
    size_t i;
    int failed;

    if (argc != 4) {
        fprintf(stderr, "usage: %s CASE_ID INPUT.vo08 OUTPUT.vo08\n", argv[0]);
        return 2;
    }
    for (i = 0; i < sizeof g_cases / sizeof g_cases[0]; i++) {
        if (strcmp(argv[1], g_cases[i].id) == 0) { row = &g_cases[i]; break; }
    }
    if (row == NULL) { fprintf(stderr, "unknown case %s\n", argv[1]); return 2; }
    if (row->feed > MAX_FEED_FRAMES) { fprintf(stderr, "feed exceeds harness pcm buffer\n"); return 2; }

    if (media_load(argv[2]) != 0) return 2;
    dev_init();

    failed = run_case(row);

    if (media_store(argv[3]) != 0) failed = 1;
    emit_json();
    if (g_event_overflow) { fprintf(stderr, "event trace overflowed\n"); failed = 1; }
    if (g_call_count >= MAX_CALLS) { fprintf(stderr, "call trace overflowed\n"); failed = 1; }
    return failed ? 1 : 0;
}
