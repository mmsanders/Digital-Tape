/*
 * wp_transport_probe.c — mechanical product adapter for transport_draft8.
 *
 * Drives only public tape.h APIs and records public results plus harness-owned
 * block callback observations. Verifier assertions/fixtures remain in the
 * imported tests/transport_draft8 package and are not reproduced here.
 *
 * Usage: wp_transport_probe CASE_ID INPUT.vo08 OUTPUT.vo08
 */
#ifndef TAPE_PUBLIC_HEADER
#define TAPE_PUBLIC_HEADER "tape.h"
#endif
#include TAPE_PUBLIC_HEADER

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define OBS_FORMAT "WP-TRANSPORT-OBSERVATION-1"
#define VO_BLOCK 512u
#define VO_SLOT_BYTES 65536u
#define VO_SLOT_BLOCKS (VO_SLOT_BYTES / VO_BLOCK)
#define VO_SLOTS 4u
#define VO_HEADER 8u
#define VO_SIZE (VO_HEADER + 2u * VO_BLOCK + VO_SLOTS * VO_SLOT_BYTES)
#define LBA_A0 8u
#define LBA_CHUNK_BASE 2048u
#define INSTANCE_BYTES 262144u
#define MAX_EVENTS 4096u
#define MAX_CALLS 128u
#define SERVICE_BUDGET 1024u
#define SERVICE_GUARD 64u

enum case_kind {
    K_PLAYING, K_IDLE, K_SAME, K_DEGRADED, K_DEGRADED_SAME, K_ARMED, K_WARM
};

struct warm_row {
    bool present;
    bool data_present;
    uint32_t data_bytes;
    uint32_t valid_frames;
    uint32_t start_frame;
    uint64_t resume_frame;
    bool bad_uuid;
    tape_side side;
};

struct case_row {
    const char *id;
    enum case_kind kind;
    tape_side mount_side;
    struct warm_row warm;
};

static const struct case_row g_cases[] = {
    {"SS-PLAYING-A-TO-B", K_PLAYING, TAPE_SIDE_A, {false,false,0u,0u,0u,0u,false,TAPE_SIDE_A}},
    {"SS-IDLE-A-TO-B", K_IDLE, TAPE_SIDE_A, {false,false,0u,0u,0u,0u,false,TAPE_SIDE_A}},
    {"SS-SAME-A", K_SAME, TAPE_SIDE_A, {false,false,0u,0u,0u,0u,false,TAPE_SIDE_A}},
    {"SS-DEGRADED-B", K_DEGRADED, TAPE_SIDE_A, {false,false,0u,0u,0u,0u,false,TAPE_SIDE_A}},
    {"SS-DEGRADED-SAME-A", K_DEGRADED_SAME, TAPE_SIDE_A, {false,false,0u,0u,0u,0u,false,TAPE_SIDE_A}},
    {"SS-ARMED-BUSY", K_ARMED, TAPE_SIDE_B, {false,false,0u,0u,0u,0u,false,TAPE_SIDE_A}},
    {"WARM-NULL", K_WARM, TAPE_SIDE_A, {false,false,0u,0u,0u,40u,false,TAPE_SIDE_A}},
    {"WARM-DATA-NULL", K_WARM, TAPE_SIDE_A, {true,false,64u,16u,32u,40u,false,TAPE_SIDE_A}},
    {"WARM-ZERO-FRAMES", K_WARM, TAPE_SIDE_A, {true,true,64u,0u,32u,32u,false,TAPE_SIDE_A}},
    {"WARM-SHORT-BUF", K_WARM, TAPE_SIDE_A, {true,true,63u,16u,32u,40u,false,TAPE_SIDE_A}},
    {"WARM-PAST-END", K_WARM, TAPE_SIDE_A, {true,true,64u,16u,250u,250u,false,TAPE_SIDE_A}},
    {"WARM-U32-OVERFLOW", K_WARM, TAPE_SIDE_A, {true,true,64u,16u,0xFFFFFFF8u,250u,false,TAPE_SIDE_A}},
    {"WARM-RESUME-OUT", K_WARM, TAPE_SIDE_A, {true,true,64u,16u,32u,48u,false,TAPE_SIDE_A}},
    {"WARM-UUID", K_WARM, TAPE_SIDE_A, {true,true,64u,16u,32u,40u,true,TAPE_SIDE_A}},
    {"WARM-SIDE", K_WARM, TAPE_SIDE_A, {true,true,64u,16u,32u,40u,false,TAPE_SIDE_B}},
    {"WARM-VALID-METADATA", K_WARM, TAPE_SIDE_A, {true,true,64u,16u,32u,40u,false,TAPE_SIDE_A}}
};

struct media {
    uint32_t blocks;
    unsigned char primary[VO_BLOCK];
    unsigned char mirror[VO_BLOCK];
    unsigned char slots[VO_SLOTS][VO_SLOT_BYTES];
};
static struct media g_media;

struct event {
    const char *phase;
    const char *op;
    uint32_t lba;
    uint32_t count;
    int rc;
    bool extent;
};
static struct event g_events[MAX_EVENTS];
static size_t g_event_count;
static bool g_event_overflow;
static const char *g_phase = "init";

struct call_rec {
    const char *phase;
    const char *fn;
    const char *result;
    const char *side;
    const char *mode;
    bool has_frame; uint64_t frame;
    bool has_requested; uint32_t requested;
    bool has_rendered; uint32_t rendered;
    bool has_rate; int32_t rate;
    bool has_more; bool more;
    bool has_evcount; unsigned long evcount;
    bool has_status; bool at_end; bool at_start;
    bool has_info; uint64_t total_frames; uint32_t entry_count; uint32_t entries_free;
    bool side_b_valid; bool warm_used;
    bool has_resume; uint64_t resume_frame;
    bool warm_present;
    bool warm_fields;
    bool warm_data_present;
    uint32_t warm_data_bytes;
    uint32_t warm_valid_frames;
    uint32_t warm_start_frame;
    unsigned char warm_uuid[16];
    tape_side warm_side;
    bool has_warm_used;
};
static struct call_rec g_calls[MAX_CALLS];
static size_t g_call_count;

static unsigned char g_inst[INSTANCE_BYTES];
static unsigned char g_play[TAPE_PLAY_RING_MIN];
static unsigned char g_rec[TAPE_REC_RING_MIN];
static int16_t g_pcm[256u * TAPE_CHANNELS];
static int16_t g_warm_pcm[16u * TAPE_CHANNELS];
static tape_dev g_dev;

static const char *result_name(tape_result r)
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

static const char *side_name(tape_side side)
{
    return side == TAPE_SIDE_B ? "B" : "A";
}

static void event_push(const char *op, uint32_t lba, uint32_t count, int rc, bool extent)
{
    struct event *e;
    if (g_event_count >= MAX_EVENTS) { g_event_overflow = true; return; }
    e = &g_events[g_event_count++];
    e->phase = g_phase; e->op = op; e->lba = lba; e->count = count; e->rc = rc; e->extent = extent;
}

static struct call_rec *call_push(const char *phase, const char *fn, tape_result r)
{
    struct call_rec *c;
    if (g_call_count >= MAX_CALLS) return NULL;
    c = &g_calls[g_call_count++];
    memset(c, 0, sizeof *c);
    c->phase = phase; c->fn = fn; c->result = result_name(r);
    return c;
}

static bool range_ok(uint32_t lba, uint32_t count)
{
    return count != 0u && (uint64_t)lba + (uint64_t)count <= (uint64_t)g_media.blocks;
}

static const unsigned char *media_block(uint32_t lba)
{
    if (lba == 0u) return g_media.primary;
    if (lba == g_media.blocks - 1u) return g_media.mirror;
    if (lba >= LBA_A0 && lba < LBA_A0 + VO_SLOTS * VO_SLOT_BLOCKS) {
        uint32_t off = lba - LBA_A0;
        return g_media.slots[off / VO_SLOT_BLOCKS] + (size_t)(off % VO_SLOT_BLOCKS) * VO_BLOCK;
    }
    return NULL;
}

static int dev_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    unsigned char *out = dst;
    uint32_t i;
    (void)ctx;
    if (!range_ok(lba, count)) { event_push("read", lba, count, -1, true); return -1; }
    for (i = 0u; i < count; i++) {
        const unsigned char *src = media_block(lba + i);
        if (src != NULL) memcpy(out + (size_t)i * VO_BLOCK, src, VO_BLOCK);
        else memset(out + (size_t)i * VO_BLOCK, 0, VO_BLOCK);
    }
    event_push("read", lba, count, 0, true);
    return 0;
}

static int dev_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    (void)ctx; (void)src;
    event_push("write", lba, count, -1, true);
    return -1;
}

static int dev_flush(void *ctx)
{
    (void)ctx;
    event_push("flush", 0u, 0u, -1, false);
    return -1;
}

static int media_load(const char *path)
{
    static unsigned char buf[VO_SIZE];
    size_t got, p;
    unsigned i;
    FILE *f = fopen(path, "rb");
    if (f == NULL) return -1;
    got = fread(buf, 1u, sizeof buf, f);
    if (got != sizeof buf || fgetc(f) != EOF) { fclose(f); return -1; }
    fclose(f);
    if (memcmp(buf, "VO08", 4u) != 0) return -1;
    memset(&g_media, 0, sizeof g_media);
    g_media.blocks = (uint32_t)buf[4] | ((uint32_t)buf[5] << 8)
                   | ((uint32_t)buf[6] << 16) | ((uint32_t)buf[7] << 24);
    p = VO_HEADER;
    memcpy(g_media.primary, buf + p, VO_BLOCK); p += VO_BLOCK;
    memcpy(g_media.mirror, buf + p, VO_BLOCK); p += VO_BLOCK;
    for (i = 0u; i < VO_SLOTS; i++) {
        memcpy(g_media.slots[i], buf + p, VO_SLOT_BYTES);
        p += VO_SLOT_BYTES;
    }
    return 0;
}

static int media_store(const char *path)
{
    static unsigned char buf[VO_SIZE];
    size_t p = VO_HEADER;
    unsigned i;
    FILE *f;
    memcpy(buf, "VO08", 4u);
    buf[4] = (unsigned char)(g_media.blocks & 0xFFu);
    buf[5] = (unsigned char)((g_media.blocks >> 8) & 0xFFu);
    buf[6] = (unsigned char)((g_media.blocks >> 16) & 0xFFu);
    buf[7] = (unsigned char)((g_media.blocks >> 24) & 0xFFu);
    memcpy(buf + p, g_media.primary, VO_BLOCK); p += VO_BLOCK;
    memcpy(buf + p, g_media.mirror, VO_BLOCK); p += VO_BLOCK;
    for (i = 0u; i < VO_SLOTS; i++) {
        memcpy(buf + p, g_media.slots[i], VO_SLOT_BYTES);
        p += VO_SLOT_BYTES;
    }
    f = fopen(path, "wb");
    if (f == NULL) return -1;
    if (fwrite(buf, 1u, sizeof buf, f) != sizeof buf) { fclose(f); return -1; }
    return fclose(f) == 0 ? 0 : -1;
}

static tape_result open_instance(tape **out)
{
    size_t need = tape_instance_size();
    if (need > sizeof g_inst) return TAPE_ERR_INVALID_ARG;
    memset(g_inst, 0, sizeof g_inst);
    memset(g_play, 0, sizeof g_play);
    memset(g_rec, 0, sizeof g_rec);
    g_dev.read = dev_read; g_dev.write = dev_write; g_dev.flush = dev_flush;
    g_dev.ctx = NULL; g_dev.block_count = g_media.blocks;
    return tape_init(g_inst, need, &g_dev, g_play, sizeof g_play, g_rec, sizeof g_rec, out);
}

static void fill_uuid(unsigned char out[16], bool bad)
{
    unsigned i;
    for (i = 0u; i < 16u; i++) out[i] = bad ? 0xFFu : (unsigned char)i;
}

static struct call_rec *step_mount(tape *t, const struct case_row *row, tape_result *out_r)
{
    tape_warm_start w;
    const tape_warm_start *wp = NULL;
    struct call_rec *c;
    unsigned i;
    memset(&w, 0, sizeof w);
    if (row->kind == K_WARM && row->warm.present) {
        w.data = row->warm.data_present ? (const void *)g_warm_pcm : NULL;
        w.data_bytes = row->warm.data_bytes;
        w.valid_frames = row->warm.valid_frames;
        w.start_frame = row->warm.start_frame;
        fill_uuid(w.uuid, row->warm.bad_uuid);
        w.side = row->warm.side;
        wp = &w;
    }
    g_phase = "mount";
    *out_r = tape_mount(t, row->mount_side,
                        row->kind == K_WARM ? row->warm.resume_frame : 0u, wp);
    c = call_push("mount", "tape_mount", *out_r);
    if (c != NULL) {
        c->side = side_name(row->mount_side);
        c->has_resume = true;
        c->resume_frame = row->kind == K_WARM ? row->warm.resume_frame : 0u;
        c->warm_present = (wp != NULL);
        if (wp != NULL) {
            c->warm_fields = true;
            c->warm_data_present = (wp->data != NULL);
            c->warm_data_bytes = wp->data_bytes;
            c->warm_valid_frames = wp->valid_frames;
            c->warm_start_frame = wp->start_frame;
            for (i = 0u; i < 16u; i++) c->warm_uuid[i] = wp->uuid[i];
            c->warm_side = wp->side;
        }
    }
    return c;
}

static tape_result step_info(tape *t, const char *phase, struct call_rec *mount_rec)
{
    tape_info info;
    struct call_rec *c;
    tape_result r;
    memset(&info, 0, sizeof info);
    g_phase = phase;
    r = tape_get_info(t, &info);
    c = call_push(phase, "tape_get_info", r);
    if (c != NULL && r == TAPE_OK) {
        c->has_info = true;
        c->total_frames = info.total_frames;
        c->entry_count = info.entry_count;
        c->entries_free = info.entries_free;
        c->side_b_valid = info.side_b_valid;
        c->warm_used = info.warm_start_used;
    }
    if (mount_rec != NULL && r == TAPE_OK) {
        mount_rec->has_warm_used = true;
        mount_rec->warm_used = info.warm_start_used;
    }
    return r;
}

static tape_result step_tell(tape *t, const char *phase)
{
    uint64_t f = 0u;
    struct call_rec *c;
    tape_result r;
    g_phase = phase;
    r = tape_tell(t, &f);
    c = call_push(phase, "tape_tell", r);
    if (c != NULL && r == TAPE_OK) { c->has_frame = true; c->frame = f; }
    return r;
}

static tape_result step_status(tape *t, const char *phase)
{
    tape_status_t st;
    struct call_rec *c;
    tape_result r;
    memset(&st, 0, sizeof st);
    g_phase = phase;
    r = tape_status(t, &st);
    c = call_push(phase, "tape_status", r);
    if (c != NULL && r == TAPE_OK) {
        c->has_status = true; c->at_end = st.at_end; c->at_start = st.at_start;
    }
    return r;
}

static tape_result step_seek(tape *t, const char *phase, uint64_t frame)
{
    struct call_rec *c;
    tape_result r;
    g_phase = phase;
    r = tape_seek(t, frame);
    c = call_push(phase, "tape_seek", r);
    if (c != NULL) { c->has_frame = true; c->frame = frame; }
    return r;
}

static tape_result step_rate(tape *t, const char *phase, int32_t rate)
{
    struct call_rec *c;
    tape_result r;
    g_phase = phase;
    r = tape_set_rate(t, rate);
    c = call_push(phase, "tape_set_rate", r);
    if (c != NULL) { c->has_rate = true; c->rate = rate; }
    return r;
}

static tape_result step_set_side(tape *t, tape_side side)
{
    struct call_rec *c;
    tape_result r;
    g_phase = "set-side";
    r = tape_set_side(t, side);
    c = call_push("set-side", "tape_set_side", r);
    if (c != NULL) c->side = side_name(side);
    return r;
}

static tape_result step_render(tape *t, const char *phase, uint32_t requested)
{
    uint32_t rendered = 0u;
    size_t before = g_event_count;
    struct call_rec *c;
    tape_result r;
    memset(g_pcm, 0, sizeof g_pcm);
    g_phase = phase;
    r = tape_render(t, g_pcm, requested, &rendered);
    c = call_push(phase, "tape_render", r);
    if (c != NULL) {
        c->has_requested = true; c->requested = requested;
        c->has_rendered = true; c->rendered = rendered;
        c->has_evcount = true; c->evcount = (unsigned long)(g_event_count - before);
    }
    return r;
}

static tape_result step_service(tape *t, const char *phase)
{
    bool more = true;
    uint32_t n = 0u;
    tape_result r = TAPE_OK;
    while (more) {
        struct call_rec *c;
        if (n++ >= SERVICE_GUARD) return TAPE_ERR_IO;
        g_phase = phase;
        r = tape_service(t, SERVICE_BUDGET, &more);
        c = call_push(phase, "tape_service", r);
        if (c != NULL) { c->has_more = true; c->more = more; }
        if (r != TAPE_OK) break;
    }
    return r;
}

static tape_result step_arm(tape *t)
{
    struct call_rec *c;
    tape_result r;
    g_phase = "arm";
    r = tape_arm(t, TAPE_REC_OVERWRITE);
    c = call_push("arm", "tape_arm", r);
    if (c != NULL) c->mode = "overwrite";
    return r;
}

static tape_result step_abort(tape *t)
{
    tape_result r;
    g_phase = "abort";
    r = tape_abort(t);
    (void)call_push("abort", "tape_abort", r);
    return r;
}

static tape_result step_unmount(tape *t)
{
    tape_result r;
    g_phase = "unmount";
    r = tape_unmount(t, NULL);
    (void)call_push("unmount", "tape_unmount", r);
    return r;
}

static int run_case(const struct case_row *row)
{
    tape *t = NULL;
    tape_result r;
    struct call_rec *mount_rec;
    int failed = 0;

    if (open_instance(&t) != TAPE_OK) return 1;
    mount_rec = step_mount(t, row, &r);
    if (r != TAPE_OK) return 1;

    switch (row->kind) {
    case K_PLAYING:
        if (step_rate(t, "pre-rate", 65536) != TAPE_OK) failed = 1;
        if (step_service(t, "pre-service") != TAPE_OK) failed = 1;
        if (step_render(t, "pre-render-to-end", 256u) != TAPE_OK) failed = 1;
        if (step_status(t, "pre-status") != TAPE_OK) failed = 1;
        if (step_set_side(t, TAPE_SIDE_B) != TAPE_OK) failed = 1;
        if (step_tell(t, "post-switch-tell") != TAPE_OK) failed = 1;
        if (step_status(t, "post-switch-status") != TAPE_OK) failed = 1;
        if (step_info(t, "post-switch-info", NULL) != TAPE_OK) failed = 1;
        if (step_render(t, "pre-service-render", 1u) != TAPE_ERR_UNDERRUN) failed = 1;
        if (step_service(t, "post-switch-service") != TAPE_OK) failed = 1;
        if (step_render(t, "post-service-render", 1u) != TAPE_OK) failed = 1;
        if (step_tell(t, "post-service-tell") != TAPE_OK) failed = 1;
        break;
    case K_IDLE:
        if (step_seek(t, "pre-seek", 10u) != TAPE_OK) failed = 1;
        if (step_set_side(t, TAPE_SIDE_B) != TAPE_OK) failed = 1;
        if (step_tell(t, "post-switch-tell") != TAPE_OK) failed = 1;
        if (step_status(t, "post-switch-status") != TAPE_OK) failed = 1;
        if (step_info(t, "post-switch-info", NULL) != TAPE_OK) failed = 1;
        if (step_rate(t, "post-switch-rate", 65536) != TAPE_OK) failed = 1;
        if (step_render(t, "pre-service-render", 1u) != TAPE_ERR_UNDERRUN) failed = 1;
        if (step_service(t, "post-switch-service") != TAPE_OK) failed = 1;
        if (step_render(t, "post-service-render", 1u) != TAPE_OK) failed = 1;
        if (step_tell(t, "post-service-tell") != TAPE_OK) failed = 1;
        break;
    case K_SAME:
    case K_DEGRADED_SAME:
        if (step_seek(t, "pre-seek", 10u) != TAPE_OK) failed = 1;
        if (step_set_side(t, TAPE_SIDE_A) != TAPE_OK) failed = 1;
        if (step_tell(t, "post-switch-tell") != TAPE_OK) failed = 1;
        if (step_info(t, "post-switch-info", NULL) != TAPE_OK) failed = 1;
        break;
    case K_DEGRADED:
        if (step_seek(t, "pre-seek", 10u) != TAPE_OK) failed = 1;
        if (step_info(t, "pre-info", NULL) != TAPE_OK) failed = 1;
        if (step_set_side(t, TAPE_SIDE_B) != TAPE_ERR_NO_VALID_INDEX) failed = 1;
        if (step_tell(t, "post-refusal-tell") != TAPE_OK) failed = 1;
        if (step_info(t, "post-refusal-info", NULL) != TAPE_OK) failed = 1;
        break;
    case K_ARMED:
        if (step_seek(t, "pre-seek", 10u) != TAPE_OK) failed = 1;
        if (step_arm(t) != TAPE_OK) failed = 1;
        if (step_set_side(t, TAPE_SIDE_A) != TAPE_ERR_BUSY) failed = 1;
        if (step_tell(t, "post-refusal-tell") != TAPE_OK) failed = 1;
        if (step_info(t, "post-refusal-info", NULL) != TAPE_OK) failed = 1;
        if (step_abort(t) != TAPE_OK) failed = 1;
        break;
    case K_WARM:
        if (step_info(t, "info", mount_rec) != TAPE_OK) failed = 1;
        if (step_tell(t, "tell") != TAPE_OK) failed = 1;
        break;
    }

    if (step_unmount(t) != TAPE_OK) failed = 1;
    return failed;
}

static void json_bool(bool v)
{
    fputs(v ? "true" : "false", stdout);
}

static void emit_uuid(const unsigned char uuid[16])
{
    unsigned i;
    for (i = 0u; i < 16u; i++) printf("%02x", (unsigned)uuid[i]);
}

static void emit_json(void)
{
    size_t i;
    printf("{\"format\":\"%s\",\"adapter_kind\":\"product\",\"calls\":[", OBS_FORMAT);
    for (i = 0u; i < g_call_count; i++) {
        const struct call_rec *c = &g_calls[i];
        if (i != 0u) putchar(',');
        printf("{\"phase\":\"%s\",\"fn\":\"%s\",\"result\":\"%s\"", c->phase, c->fn, c->result);
        if (c->side != NULL) printf(",\"side\":\"%s\"", c->side);
        if (c->mode != NULL) printf(",\"mode\":\"%s\"", c->mode);
        if (c->has_frame) printf(",\"frame\":%llu", (unsigned long long)c->frame);
        if (c->has_requested) printf(",\"requested\":%lu", (unsigned long)c->requested);
        if (c->has_rendered) printf(",\"rendered\":%lu", (unsigned long)c->rendered);
        if (c->has_rate) printf(",\"rate_q16_16\":%ld", (long)c->rate);
        if (c->has_more) { fputs(",\"more_work\":", stdout); json_bool(c->more); }
        if (c->has_evcount) printf(",\"events_from_call\":%lu", c->evcount);
        if (c->has_status) {
            fputs(",\"at_end\":", stdout); json_bool(c->at_end);
            fputs(",\"at_start\":", stdout); json_bool(c->at_start);
        }
        if (c->has_info) {
            printf(",\"total_frames\":%llu,\"entry_count\":%lu,\"entries_free\":%lu",
                   (unsigned long long)c->total_frames,
                   (unsigned long)c->entry_count, (unsigned long)c->entries_free);
            fputs(",\"side_b_valid\":", stdout); json_bool(c->side_b_valid);
            fputs(",\"warm_start_used\":", stdout); json_bool(c->warm_used);
        }
        if (c->has_resume) printf(",\"resume_frame\":%llu", (unsigned long long)c->resume_frame);
        fputs(",\"warm_present\":", stdout); json_bool(c->warm_present);
        if (c->warm_fields) {
            fputs(",\"warm_data_present\":", stdout); json_bool(c->warm_data_present);
            printf(",\"warm_data_bytes\":%lu,\"warm_valid_frames\":%lu,\"warm_start_frame\":%lu,\"warm_uuid_hex\":\"",
                   (unsigned long)c->warm_data_bytes,
                   (unsigned long)c->warm_valid_frames,
                   (unsigned long)c->warm_start_frame);
            emit_uuid(c->warm_uuid);
            printf("\",\"warm_side\":\"%s\"", side_name(c->warm_side));
        }
        if (c->has_warm_used) {
            fputs(",\"warm_start_used\":", stdout); json_bool(c->warm_used);
        }
        putchar('}');
    }
    fputs("],\"events\":[", stdout);
    for (i = 0u; i < g_event_count; i++) {
        const struct event *e = &g_events[i];
        if (i != 0u) putchar(',');
        if (e->extent) {
            printf("{\"phase\":\"%s\",\"op\":\"%s\",\"lba\":%lu,\"count\":%lu,\"rc\":%d}",
                   e->phase, e->op, (unsigned long)e->lba, (unsigned long)e->count, e->rc);
        } else {
            printf("{\"phase\":\"%s\",\"op\":\"%s\",\"rc\":%d}", e->phase, e->op, e->rc);
        }
    }
    fputs("],\"event_overflow\":", stdout); json_bool(g_event_overflow);
    puts("}");
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
    for (i = 0u; i < sizeof g_cases / sizeof g_cases[0]; i++) {
        if (strcmp(argv[1], g_cases[i].id) == 0) { row = &g_cases[i]; break; }
    }
    if (row == NULL) { fprintf(stderr, "unknown case %s\n", argv[1]); return 2; }
    if (media_load(argv[2]) != 0) { fprintf(stderr, "failed to load input\n"); return 2; }

    memset(g_warm_pcm, 0, sizeof g_warm_pcm);
    failed = run_case(row);
    if (media_store(argv[3]) != 0) failed = 1;
    emit_json();
    if (g_event_overflow || g_call_count >= MAX_CALLS) failed = 1;
    return failed ? 1 : 0;
}
