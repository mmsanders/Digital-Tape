/*
 * vt8_ops_probe.c — mechanical VT8-001 adapter.
 *
 * Contract: tests/ops_draft8/ADAPTER.md (Verification-owned, imported verbatim).
 * This file exists only to (a) drive the frozen PUBLIC API through the two
 * scripted case sequences and (b) expose harness-owned block-device observations
 * to the verifier runner. It is NOT a product API, it implements no engine
 * behaviour, and it observes no engine internals: the only engine symbols it
 * references are public functions declared in the real product tape.h.
 *
 * Usage: vt8_ops_probe CASE_ID INPUT.vo08 OUTPUT.vo08
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

/* --- VO08 envelope, per tests/ops_draft8/oracle.py Media --------------------- */

#define VO_BLOCK        512u
#define VO_SLOT_BYTES   65536u
#define VO_SLOT_BLOCKS  (VO_SLOT_BYTES / VO_BLOCK)   /* 128 */
#define VO_SLOTS        4u
#define VO_HEADER       8u
#define VO_SIZE         (VO_HEADER + 2u * VO_BLOCK + VO_SLOTS * VO_SLOT_BYTES)

/* Region LBAs are the frozen §3 constants; the envelope maps onto them. */
#define LBA_PRIMARY     0u
#define LBA_A0          8u
#define LBA_CHUNK_BASE  2048u

#define POISON_BYTE     0xA5u
#define MAX_CHUNKS      64u          /* harness bound; fixtures use 16 */
#define SERVICE_GUARD   4096u        /* finite service guard (ADAPTER.md step 5) */
#define SERVICE_BUDGET  8u           /* positive fixed block budget */
#define REC_FRAMES      128u

/* Harness-owned media image. Sparse at chunk granularity: an audio chunk is
   allocated on first write, so unmapped audio reads stay deterministic poison. */
struct media {
    uint32_t  blocks;
    unsigned char primary[VO_BLOCK];
    unsigned char mirror[VO_BLOCK];
    unsigned char slots[VO_SLOTS][VO_SLOT_BYTES];
    unsigned char *chunk[MAX_CHUNKS];   /* NULL until written */
};

static struct media g_media;

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

/* --- public-call result log (diagnostic; not an oracle input) --------------- */

struct call_rec { const char *name; int rc; unsigned long detail; bool has_detail; };
#define MAX_CALLS 64
static struct call_rec g_calls[MAX_CALLS];
static size_t g_call_count;

static int note(const char *name, int rc)
{
    if (g_call_count < MAX_CALLS) {
        g_calls[g_call_count].name = name;
        g_calls[g_call_count].rc = rc;
        g_calls[g_call_count].has_detail = false;
        g_call_count++;
    }
    return rc;
}

static int note_d(const char *name, int rc, unsigned long detail)
{
    int r = note(name, rc);
    if (g_call_count > 0) {
        g_calls[g_call_count - 1].detail = detail;
        g_calls[g_call_count - 1].has_detail = true;
    }
    return r;
}

/* --- block resolution ------------------------------------------------------- */

/* Returns a pointer to the 512-byte block backing `lba`, or NULL if unmapped.
   `alloc` requests lazy allocation of an audio chunk for a write. */
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

/* Out-of-range rejection uses widened arithmetic before any copy. */
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
    unsigned char buf[VO_SIZE];
    size_t got;
    FILE *f = fopen(path, "rb");
    if (f == NULL) { fprintf(stderr, "cannot open input %s\n", path); return -1; }
    got = fread(buf, 1u, sizeof buf, f);
    if (got != sizeof buf || fgetc(f) != EOF) {
        fprintf(stderr, "input is not a %u-byte VO08 envelope (%zu bytes)\n", VO_SIZE, got);
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
    unsigned char buf[VO_SIZE];
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
    printf("{\"events\":[");
    for (i = 0; i < g_event_count; i++) {
        const struct event *e = &g_events[i];
        if (i != 0) printf(",");
        if (e->has_extent)
            printf("{\"phase\":\"%s\",\"op\":\"%s\",\"lba\":%lu,\"count\":%lu,\"rc\":%d}",
                   e->phase, e->op, (unsigned long)e->lba, (unsigned long)e->count, e->rc);
        else
            printf("{\"phase\":\"%s\",\"op\":\"%s\",\"rc\":%d}", e->phase, e->op, e->rc);
    }
    printf("],\"calls\":[");
    for (i = 0; i < g_call_count; i++) {
        if (i != 0) printf(",");
        printf("{\"call\":\"%s\",\"rc\":%d", g_calls[i].name, g_calls[i].rc);
        if (g_calls[i].has_detail) printf(",\"detail\":%lu", g_calls[i].detail);
        printf("}");
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
    int failed = 0;

    g_phase = "mount";
    r = (tape_result)note("tape_init", (int)open_instance(g_inst_a, sizeof g_inst_a, g_play_a, g_rec_a, &t));
    if (r != TAPE_OK) return 1;
    r = (tape_result)note("tape_mount(A,0,NULL)", (int)tape_mount(t, TAPE_SIDE_A, 0u, NULL));
    if (r != TAPE_OK) return 1;
    r = (tape_result)note("tape_get_info", (int)tape_get_info(t, &info));
    if (r != TAPE_OK) return 1;
    note_d("info.side_b_valid", 0, info.side_b_valid ? 1uL : 0uL);
    note_d("info.writable", 0, info.writable ? 1uL : 0uL);
    if (info.side_b_valid) {
        fprintf(stderr, "fixture precondition: expected degraded-B, info.side_b_valid true\n");
        failed = 1;
    }

    g_phase = "reset_b";
    r = (tape_result)note("tape_reset_side_b", (int)tape_reset_side_b(t));
    if (r != TAPE_OK) failed = 1;

    g_phase = "unmount";
    r = (tape_result)note("tape_unmount", (int)tape_unmount(t, NULL));
    if (r != TAPE_OK) failed = 1;

    g_phase = "remount";
    t = NULL;
    r = (tape_result)note("tape_init(2)", (int)open_instance(g_inst_b, sizeof g_inst_b, g_play_b, g_rec_b, &t));
    if (r != TAPE_OK) return 1;
    r = (tape_result)note("tape_mount(B,0,NULL)", (int)tape_mount(t, TAPE_SIDE_B, 0u, NULL));
    if (r != TAPE_OK) failed = 1;
    else {
        r = (tape_result)note("tape_get_info(2)", (int)tape_get_info(t, &info));
        if (r == TAPE_OK) note_d("remount.total_frames", 0, (unsigned long)info.total_frames);
    }
    note("tape_unmount(2)", (int)tape_unmount(t, NULL));
    return failed;
}

static int case_rec_allocseq(void)
{
    tape *t = NULL;
    tape_info info;
    tape_result r;
    int failed = 0;
    static int16_t pcm[REC_FRAMES * 2];
    uint32_t i, accepted = 0u;
    uint64_t pos = 0u;

    for (i = 0; i < REC_FRAMES; i++) {          /* deterministic, not an oracle */
        pcm[2u * i]      = (int16_t)(i * 7);
        pcm[2u * i + 1u] = (int16_t)(-(int)(i * 5));
    }

    g_phase = "mount";
    r = (tape_result)note("tape_init", (int)open_instance(g_inst_a, sizeof g_inst_a, g_play_a, g_rec_a, &t));
    if (r != TAPE_OK) return 1;
    r = (tape_result)note("tape_mount(B,0,NULL)", (int)tape_mount(t, TAPE_SIDE_B, 0u, NULL));
    if (r != TAPE_OK) return 1;
    r = (tape_result)note("tape_get_info", (int)tape_get_info(t, &info));
    if (r == TAPE_OK) {
        note_d("info.total_frames", 0, (unsigned long)info.total_frames);
        note_d("info.free_chunks", 0, (unsigned long)info.free_chunks);
    }

    g_phase = "seek";
    r = (tape_result)note("tape_seek(128)", (int)tape_seek(t, (uint64_t)REC_FRAMES));
    if (r != TAPE_OK) failed = 1;
    r = (tape_result)note("tape_tell", (int)tape_tell(t, &pos));
    if (r == TAPE_OK) note_d("tell.frame", 0, (unsigned long)pos);

    g_phase = "arm";
    r = (tape_result)note("tape_arm(SPLICE)", (int)tape_arm(t, TAPE_REC_SPLICE));
    if (r != TAPE_OK) failed = 1;

    g_phase = "feed";
    r = (tape_result)note("tape_feed(128)", (int)tape_feed(t, pcm, REC_FRAMES, &accepted));
    note_d("feed.accepted", 0, (unsigned long)accepted);
    if (r != TAPE_OK || accepted != REC_FRAMES) failed = 1;

    g_phase = "service";
    {
        bool more = true;
        uint32_t iter = 0u;
        while (more) {
            if (iter >= SERVICE_GUARD) {
                fprintf(stderr, "finite service guard tripped after %u calls\n", iter);
                note_d("service.guard_tripped", 0, (unsigned long)iter);
                failed = 1;
                break;
            }
            r = tape_service(t, SERVICE_BUDGET, &more);
            iter++;
            if (r != TAPE_OK) { note_d("tape_service", (int)r, (unsigned long)iter); failed = 1; break; }
        }
        note_d("service.iterations", 0, (unsigned long)iter);
    }

    g_phase = "commit";
    r = (tape_result)note("tape_commit", (int)tape_commit(t));
    if (r != TAPE_OK) failed = 1;

    g_phase = "unmount";
    r = (tape_result)note("tape_unmount", (int)tape_unmount(t, NULL));
    if (r != TAPE_OK) failed = 1;

    g_phase = "remount";
    t = NULL;
    r = (tape_result)note("tape_init(2)", (int)open_instance(g_inst_b, sizeof g_inst_b, g_play_b, g_rec_b, &t));
    if (r != TAPE_OK) return 1;
    r = (tape_result)note("tape_mount(B,0,NULL)(2)", (int)tape_mount(t, TAPE_SIDE_B, 0u, NULL));
    if (r != TAPE_OK) failed = 1;
    else {
        r = (tape_result)note("tape_get_info(2)", (int)tape_get_info(t, &info));
        if (r == TAPE_OK) {
            note_d("remount.total_frames", 0, (unsigned long)info.total_frames);
            note_d("remount.free_chunks", 0, (unsigned long)info.free_chunks);
        }
    }
    note("tape_unmount(2)", (int)tape_unmount(t, NULL));
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
    return failed ? 1 : 0;
}
