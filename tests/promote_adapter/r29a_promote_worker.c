/*
 * r29a_promote_worker.c — Software-owned mechanical binding for the imported
 * R29-A promote verifier package (tests/promote_draft8, tree 2eb707d7).
 *
 * Drives the real engine against an in-memory fault device with separate
 * WORKING and DURABLE images (ADAPTER.md "Fault device / durability") and
 * reports raw facts only: public results, device callback traces, raw bytes,
 * numeric counters. Every verdict is Verification's; nothing here decides
 * whether a case passed.
 *
 * Protocol: adapter.py writes tab-separated commands on stdin; every command
 * except M and D answers with one JSON line on stdout.
 *
 *   M name total_chunks nblocks     then nblocks lines "lba<TAB>hex"
 *   B media                         clean baseline promote write trace
 *   BZ media                        closure baseline (first superblock write)
 *   C idx media mode kind ordinal landed      ordinary crash case
 *   Z idx media mode kind landed               closure crash case
 *   K idx family param media...                contract case
 *   D                                          done
 */
#define _POSIX_C_SOURCE 200809L
#include "tape.h"
#include "tape_crc32.h"
/* Read-only white-box access for raw facts no public call exposes (rate,
   ring window, owed frames, counters, fault flag). Nothing here writes engine
   state. */
#include "tape_internal.h"

#include <openssl/sha.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BLOCK 512u
#define LBA_CHUNK_BASE 2048u
#define CHUNK_BLOCKS 1024u
#define IMG_CAP 192u
#define MAX_MEDIA 96u
#define MAX_EVENTS 16384u
#define BIG_BUDGET 0x100000u

static const uint32_t k_slot_base[4] = {8u, 136u, 264u, 392u};
static const char *const k_slot_name[4] = {"a0", "a1", "b0", "b1"};

/* ------------------------------------------------------------------------ */
/* sparse block images                                                      */
/* ------------------------------------------------------------------------ */

struct img {
    uint32_t n;
    uint32_t lba[IMG_CAP];
    unsigned char data[IMG_CAP][BLOCK];
};

static void img_copy(struct img *dst, const struct img *src)
{
    uint32_t i;
    dst->n = src->n;
    for (i = 0u; i < src->n; ++i) {
        dst->lba[i] = src->lba[i];
        memcpy(dst->data[i], src->data[i], BLOCK);
    }
}

static int img_find(const struct img *im, uint32_t lba)
{
    uint32_t i;
    for (i = 0u; i < im->n; ++i) if (im->lba[i] == lba) return (int)i;
    return -1;
}

static void img_get(const struct img *im, uint32_t lba, unsigned char *out)
{
    int i = img_find(im, lba);
    if (i < 0) memset(out, 0, BLOCK);
    else memcpy(out, im->data[i], BLOCK);
}

static void img_put(struct img *im, uint32_t lba, const unsigned char *src, uint32_t len)
{
    int i = img_find(im, lba);
    if (i < 0) {
        uint32_t k;
        /* An absent block reads as zero, so writing zeros over it changes
           nothing observable and needs no slot. */
        for (k = 0u; k < len && src[k] == 0u; ++k) {}
        if (k == len) return;
        if (im->n >= IMG_CAP) { fprintf(stderr, "image capacity\n"); exit(3); }
        i = (int)im->n++;
        im->lba[i] = lba;
        memset(im->data[i], 0, BLOCK);
    }
    memcpy(im->data[i], src, len);
}

struct media {
    char name[64];
    uint32_t total_chunks;
    struct img im;
};

static struct media g_media[MAX_MEDIA];
static unsigned g_media_n;

static const struct media *media_get(const char *name)
{
    unsigned i;
    for (i = 0u; i < g_media_n; ++i) if (strcmp(g_media[i].name, name) == 0) return &g_media[i];
    fprintf(stderr, "unknown media %s\n", name);
    exit(3);
}

static uint32_t block_count_for(uint32_t total_chunks)
{
    return LBA_CHUNK_BASE + total_chunks * CHUNK_BLOCKS + 1u;
}

/* ------------------------------------------------------------------------ */
/* fault device                                                             */
/* ------------------------------------------------------------------------ */

enum inj {
    INJ_NONE = 0, INJ_BEFORE, INJ_TORN, INJ_AFTER, INJ_AT_FLUSH
};

struct dev_ctx {
    const char *name;
    struct img working, durable, pre;
    uint32_t total_chunks, block_count;
    bool write_through;
    bool dead;               /* power lost: every later callback fails */
    bool fired;
    /* ordinary crash: target the Nth write in promote scope, or the Nth flush */
    enum inj inj;
    int target_write;
    int target_flush;
    unsigned landed;
    /* closure crash: target the first superblock write in promote scope */
    bool closure;
    bool closure_seen;
    bool fail_next_flush;
    bool pre_captured;
    /* repair refusal: writes issued while tape_mount runs return rc 5 */
    bool refuse_mount_writes;
    /* contract: fail the own-device write with this absolute ordinal */
    long fail_write_at;
    unsigned writes_total;
    unsigned scope_writes, scope_flushes;
};

struct event {
    const char *dev;
    char op;
    uint32_t lba, count;
    int rc;
    bool in_promote;
    bool in_mount;
    unsigned char sha[SHA256_DIGEST_LENGTH];
    bool has_data;
    uint32_t word8, word12, word0;   /* raw little-endian words of the written block */
};

static struct event g_ev[MAX_EVENTS];
static unsigned g_evn;
static int g_promote_depth;
static bool g_in_mount;

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void log_ev(const struct dev_ctx *c, char op, uint32_t lba, uint32_t count, int rc,
                   const unsigned char *data)
{
    struct event *e;
    if (g_evn >= MAX_EVENTS) { fprintf(stderr, "event log full\n"); exit(3); }
    e = &g_ev[g_evn++];
    memset(e, 0, sizeof *e);
    e->dev = c->name;
    e->op = op;
    e->lba = lba;
    e->count = count;
    e->rc = rc;
    e->in_promote = g_promote_depth > 0;
    e->in_mount = g_in_mount;
    if (data != NULL) {
        e->has_data = true;
        (void)SHA256(data, (size_t)count * BLOCK, e->sha);
        e->word0 = rd32(data);
        e->word8 = rd32(data + 8);
        e->word12 = rd32(data + 12);
    }
}

static bool is_sb_lba(const struct dev_ctx *c, uint32_t lba)
{
    return lba == 0u || lba == c->block_count - 1u;
}

static bool is_chunk_lba(const struct dev_ctx *c, uint32_t lba)
{
    return lba >= LBA_CHUNK_BASE && lba < LBA_CHUNK_BASE + c->total_chunks * CHUNK_BLOCKS;
}

static int cb_read(void *v, uint32_t lba, uint32_t count, void *dst)
{
    struct dev_ctx *c = (struct dev_ctx *)v;
    uint32_t i;
    if (c->dead || dst == NULL || count == 0u || (uint64_t)lba + count > c->block_count) {
        log_ev(c, 'r', lba, count, -1, NULL);
        return -1;
    }
    for (i = 0u; i < count; ++i) img_get(&c->working, lba + i, (unsigned char *)dst + (size_t)i * BLOCK);
    log_ev(c, 'r', lba, count, 0, NULL);
    return 0;
}

static void full_write(struct dev_ctx *c, uint32_t lba, uint32_t count, const unsigned char *src)
{
    uint32_t i;
    for (i = 0u; i < count; ++i) {
        img_put(&c->working, lba + i, src + (size_t)i * BLOCK, BLOCK);
        if (c->write_through) img_put(&c->durable, lba + i, src + (size_t)i * BLOCK, BLOCK);
    }
}

/* Apply a targeted injection to write `src` at `lba`. Returns the callback's
   raw return code. */
static int inject(struct dev_ctx *c, uint32_t lba, uint32_t count, const unsigned char *src)
{
    c->fired = true;
    if (c->inj == INJ_BEFORE) {
        c->dead = true;
        return -1;
    }
    if (c->inj == INJ_TORN) {
        img_put(&c->working, lba, src, c->landed);
        img_put(&c->durable, lba, src, c->landed);
        c->dead = true;
        return -1;
    }
    full_write(c, lba, count, src);
    if (c->inj == INJ_AFTER) {
        c->dead = true;        /* power lost before the following flush */
    } else {
        c->fail_next_flush = true;
    }
    return 0;
}

static int cb_write(void *v, uint32_t lba, uint32_t count, const void *srcv)
{
    struct dev_ctx *c = (struct dev_ctx *)v;
    const unsigned char *src = (const unsigned char *)srcv;
    unsigned ord;
    int rc;

    if (c->dead || src == NULL || count == 0u || (uint64_t)lba + count > c->block_count) {
        log_ev(c, 'w', lba, count, -1, src);
        return -1;
    }
    ord = c->writes_total++;
    if (c->fail_write_at >= 0 && (long)ord == c->fail_write_at) {
        log_ev(c, 'w', lba, count, 5, src);
        return 5;
    }
    if (g_in_mount && c->refuse_mount_writes) {
        log_ev(c, 'w', lba, count, 5, src);
        return 5;
    }
    rc = 0;
    if (g_promote_depth > 0) {
        unsigned sord = c->scope_writes++;
        if (c->closure && !c->closure_seen && count == 1u && is_sb_lba(c, lba)) {
            c->closure_seen = true;
            img_copy(&c->pre, &c->durable);
            c->pre_captured = true;
            if (c->inj != INJ_NONE) {
                rc = inject(c, lba, count, src);
                log_ev(c, 'w', lba, count, rc, src);
                return rc;
            }
        } else if (!c->closure && c->inj != INJ_NONE && c->inj != INJ_AT_FLUSH
                   && (int)sord == c->target_write) {
            rc = inject(c, lba, count, src);
            log_ev(c, 'w', lba, count, rc, src);
            return rc;
        }
    }
    full_write(c, lba, count, src);
    log_ev(c, 'w', lba, count, 0, src);
    return 0;
}

static int cb_flush(void *v)
{
    struct dev_ctx *c = (struct dev_ctx *)v;
    if (c->dead) { log_ev(c, 'f', 0u, 0u, -1, NULL); return -1; }
    if (c->fail_next_flush) {
        c->fail_next_flush = false;
        c->dead = true;
        log_ev(c, 'f', 0u, 0u, -1, NULL);
        return -1;
    }
    if (g_promote_depth > 0) {
        unsigned ford = c->scope_flushes++;
        if (!c->closure && c->inj == INJ_AT_FLUSH && (int)ford == c->target_flush) {
            c->fired = true;
            c->dead = true;
            log_ev(c, 'f', 0u, 0u, -1, NULL);
            return -1;
        }
    }
    img_copy(&c->durable, &c->working);
    log_ev(c, 'f', 0u, 0u, 0, NULL);
    return 0;
}

static void dev_load(struct dev_ctx *c, const char *name, const struct media *m, bool write_through)
{
    memset(c, 0, sizeof *c);
    c->name = name;
    c->total_chunks = m->total_chunks;
    c->block_count = block_count_for(m->total_chunks);
    c->write_through = write_through;
    c->fail_write_at = -1;
    c->target_write = -1;
    c->target_flush = -1;
    img_copy(&c->working, &m->im);
    img_copy(&c->durable, &m->im);
}

static tape_dev dev_of(struct dev_ctx *c)
{
    tape_dev d;
    d.read = cb_read;
    d.write = cb_write;
    d.flush = cb_flush;
    d.ctx = c;
    d.block_count = c->block_count;
    return d;
}

/* ------------------------------------------------------------------------ */
/* engine instances (caller-owned storage, reused)                          */
/* ------------------------------------------------------------------------ */

struct inst {
    unsigned char *mem;
    unsigned char *play;
    unsigned char *rec;
    size_t mem_len;
    tape_dev dev;
    tape *t;
};

static struct inst g_main_inst, g_aux_inst;

static void inst_alloc(struct inst *in)
{
    in->mem_len = tape_instance_size();
    in->mem = calloc(1u, in->mem_len);
    in->play = calloc(1u, TAPE_PLAY_RING_MIN);
    in->rec = calloc(1u, TAPE_REC_RING_MIN);
    if (in->mem == NULL || in->play == NULL || in->rec == NULL) { fprintf(stderr, "oom\n"); exit(3); }
}

static tape_result inst_mount(struct inst *in, struct dev_ctx *c, tape_side side)
{
    tape_result r;
    memset(in->mem, 0, in->mem_len);
    in->dev = dev_of(c);
    in->t = NULL;
    r = tape_init(in->mem, in->mem_len, &in->dev, in->play, TAPE_PLAY_RING_MIN,
                  in->rec, TAPE_REC_RING_MIN, &in->t);
    if (r != TAPE_OK) return r;
    g_in_mount = true;
    r = tape_mount(in->t, side, 0u, NULL);
    g_in_mount = false;
    return r;
}

static tape_result promote_call(tape *t, uint32_t budget, bool *more, tape_progress_fn cb, void *user)
{
    tape_result r;
    g_promote_depth++;
    r = tape_promote(t, budget, more, cb, user);
    g_promote_depth--;
    return r;
}

/* ------------------------------------------------------------------------ */
/* JSON                                                                      */
/* ------------------------------------------------------------------------ */

struct jb { char *p; size_t n, cap; };
static char g_out_mem[1u << 23];
static char g_nested_mem[1u << 20];

static void jb_init(struct jb *b, char *mem, size_t cap) { b->p = mem; b->n = 0u; b->cap = cap; b->p[0] = '\0'; }

static void jb_printf(struct jb *b, const char *fmt, ...)
{
    va_list ap;
    int k;
    va_start(ap, fmt);
    k = vsnprintf(b->p + b->n, b->cap - b->n, fmt, ap);
    va_end(ap);
    if (k < 0 || (size_t)k >= b->cap - b->n) { fprintf(stderr, "json overflow\n"); exit(3); }
    b->n += (size_t)k;
}

static void jb_hex(struct jb *b, const unsigned char *p, size_t n)
{
    static const char d[] = "0123456789abcdef";
    size_t i;
    if (b->n + 2u * n + 1u >= b->cap) { fprintf(stderr, "json overflow\n"); exit(3); }
    for (i = 0u; i < n; ++i) {
        b->p[b->n++] = d[(p[i] >> 4) & 15u];
        b->p[b->n++] = d[p[i] & 15u];
    }
    b->p[b->n] = '\0';
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

static const char *tf(bool v) { return v ? "true" : "false"; }

static void jb_snapshot(struct jb *b, const struct img *im, uint32_t total_chunks)
{
    unsigned char blk[BLOCK];
    uint32_t bc = block_count_for(total_chunks);
    unsigned i;
    jb_printf(b, "{\"format\":\"PROMOTE-RAW-SNAPSHOT-1\",\"total_chunks\":%u,\"block_count\":%u,\"primary_hex\":\"",
              total_chunks, bc);
    img_get(im, 0u, blk); jb_hex(b, blk, BLOCK);
    jb_printf(b, "\",\"mirror_hex\":\"");
    img_get(im, bc - 1u, blk); jb_hex(b, blk, BLOCK);
    jb_printf(b, "\"");
    for (i = 0u; i < 4u; ++i) {
        jb_printf(b, ",\"%s_header_hex\":\"", k_slot_name[i]);
        img_get(im, k_slot_base[i], blk); jb_hex(b, blk, BLOCK);
        jb_printf(b, "\",\"%s_entries_hex\":\"", k_slot_name[i]);
        img_get(im, k_slot_base[i] + 1u, blk); jb_hex(b, blk, BLOCK);
        jb_printf(b, "\"");
    }
    jb_printf(b, ",\"chunk0_hex\":{");
    for (i = 0u; i < total_chunks; ++i) {
        jb_printf(b, "%s\"%u\":\"", i ? "," : "", i);
        img_get(im, LBA_CHUNK_BASE + i * CHUNK_BLOCKS, blk); jb_hex(b, blk, BLOCK);
        jb_printf(b, "\"");
    }
    jb_printf(b, "}}");
}

static const char *ev_kind(const struct dev_ctx *c, const struct event *e)
{
    unsigned i;
    if (e->op != 'w' && e->op != 'r') return NULL;
    if (is_sb_lba(c, e->lba)) return "superblock";
    for (i = 0u; i < 4u; ++i) {
        if (e->lba == k_slot_base[i]) return "index_header";
        if (e->lba > k_slot_base[i] && e->lba < k_slot_base[i] + 128u) return "index_entries";
    }
    if (is_chunk_lba(c, e->lba)) return "chunk";
    return "other";
}

/* Chronological callback trace for events [from, to) on device `c`. */
static void jb_events(struct jb *b, const struct dev_ctx *c, unsigned from, unsigned to)
{
    unsigned i;
    bool first = true;
    jb_printf(b, "[");
    for (i = from; i < to; ++i) {
        const struct event *e = &g_ev[i];
        if (strcmp(e->dev, c->name) != 0) continue;
        jb_printf(b, "%s{\"device\":\"%s\",\"op\":\"%s\"", first ? "" : ",", e->dev,
                  e->op == 'r' ? "read" : e->op == 'w' ? "write" : "flush");
        first = false;
        if (e->op != 'f') {
            jb_printf(b, ",\"lba\":%u,\"count\":%u,\"kind\":\"%s\"", e->lba, e->count, ev_kind(c, e));
        }
        jb_printf(b, ",\"rc\":%d}", e->rc);
    }
    jb_printf(b, "]");
}

/* ------------------------------------------------------------------------ */
/* remount and render (raw facts after a crash)                              */
/* ------------------------------------------------------------------------ */

static int16_t g_pcm[2u * 70000u];
static struct dev_ctx g_aux_dev;

static tape_result remount_render(const struct img *im, uint32_t total_chunks, tape_side side,
                                  unsigned char digest[SHA256_DIGEST_LENGTH])
{
    struct media tmp;
    tape_info info;
    tape_result r;
    SHA256_CTX sh;
    uint64_t want, got = 0u;
    unsigned guard = 0u;

    tmp.total_chunks = total_chunks;
    img_copy(&tmp.im, im);
    dev_load(&g_aux_dev, "remount", &tmp, true);
    r = inst_mount(&g_aux_inst, &g_aux_dev, side);
    if (r != TAPE_OK) return r;
    SHA256_Init(&sh);
    want = (tape_get_info(g_aux_inst.t, &info) == TAPE_OK) ? info.total_frames : 0u;
    if (want > 0u && tape_set_rate(g_aux_inst.t, 0x10000) != TAPE_OK) want = 0u;
    while (got < want && guard++ < 100000u) {
        bool more = false;
        uint32_t rendered = 0u;
        uint32_t ask = (uint32_t)((want - got) > 4096u ? 4096u : (want - got));
        tape_result rr;
        (void)tape_service(g_aux_inst.t, 256u, &more);
        rr = tape_render(g_aux_inst.t, g_pcm, ask, &rendered);
        if (rr != TAPE_OK && rr != TAPE_ERR_UNDERRUN) break;
        SHA256_Update(&sh, g_pcm, (size_t)rendered * 4u);
        got += rendered;
    }
    SHA256_Final(digest, &sh);
    return r;
}

static void jb_remounts(struct jb *b, const struct img *im, uint32_t total_chunks)
{
    unsigned char dg[SHA256_DIGEST_LENGTH];
    tape_result ra, rb;
    unsigned char da[SHA256_DIGEST_LENGTH];
    unsigned mark = g_evn;
    ra = remount_render(im, total_chunks, TAPE_SIDE_A, da);
    jb_printf(b, ",\"actual_mount_A\":\"%s\"", rname(ra));
    if (ra == TAPE_OK) { jb_printf(b, ",\"actual_audio_A_sha256\":\""); jb_hex(b, da, sizeof da); jb_printf(b, "\""); }
    rb = remount_render(im, total_chunks, TAPE_SIDE_B, dg);
    jb_printf(b, ",\"actual_mount_B\":\"%s\"", rname(rb));
    if (rb == TAPE_OK) { jb_printf(b, ",\"actual_audio_B_sha256\":\""); jb_hex(b, dg, sizeof dg); jb_printf(b, "\""); }
    g_evn = mark;   /* remount traces are not part of any case trace */
}

/* ------------------------------------------------------------------------ */
/* crash cases                                                               */
/* ------------------------------------------------------------------------ */

static struct dev_ctx g_dev;
static struct dev_ctx g_dst;

static enum inj parse_inj(const char *s)
{
    if (strcmp(s, "before_write") == 0 || strcmp(s, "before_partner") == 0) return INJ_BEFORE;
    if (strcmp(s, "torn_write") == 0 || strcmp(s, "torn_partner") == 0) return INJ_TORN;
    if (strcmp(s, "after_write") == 0 || strcmp(s, "after_partner") == 0) return INJ_AFTER;
    if (strcmp(s, "at_flush") == 0 || strcmp(s, "at_partner_flush") == 0) return INJ_AT_FLUSH;
    fprintf(stderr, "unknown injection %s\n", s);
    exit(3);
}

/* Run promote to completion (or until the device dies). */
static tape_result run_promote(tape *t, unsigned *calls)
{
    tape_result r;
    bool more = false;
    unsigned guard = 0u;
    do {
        more = false;
        r = promote_call(t, BIG_BUDGET, &more, NULL, NULL);
        guard++;
    } while (r == TAPE_OK && more && guard < 64u);
    if (calls != NULL) *calls = guard;
    return r;
}

static void cmd_baseline(const char *mname, bool closure)
{
    const struct media *m = media_get(mname);
    struct jb b;
    tape_result mr, r = TAPE_OK;
    unsigned mark, i, writes = 0u, flushes = 0u;
    bool first = true;

    g_evn = 0u;
    dev_load(&g_dev, "own", m, false);
    g_dev.refuse_mount_writes = closure;
    mr = inst_mount(&g_main_inst, &g_dev, TAPE_SIDE_A);
    mark = g_evn;
    if (mr == TAPE_OK) r = run_promote(g_main_inst.t, NULL);
    jb_init(&b, g_out_mem, sizeof g_out_mem);
    jb_printf(&b, "{\"mount_result\":\"%s\",\"promote_result\":\"%s\",\"writes\":[", rname(mr), rname(r));
    for (i = mark; i < g_evn; ++i) {
        const struct event *e = &g_ev[i];
        if (e->op == 'f') { flushes++; continue; }
        if (e->op != 'w') continue;
        jb_printf(&b, "%s{\"write_ordinal\":%u,\"flushes_before\":%u,\"lba\":%u,\"count\":%u,\"kind\":\"%s\",\"sha256\":\"",
                  first ? "" : ",", writes, flushes, e->lba, e->count, ev_kind(&g_dev, e));
        jb_hex(&b, e->sha, sizeof e->sha);
        /* The ordinal of the next flush this write is followed by. */
        {
            unsigned j, f = flushes;
            int nf = -1;
            for (j = i + 1u; j < g_evn; ++j) {
                if (g_ev[j].op == 'f') { nf = (int)f; break; }
                if (g_ev[j].op == 'w') break;
            }
            jb_printf(&b, "\",\"following_flush_ordinal\":%d}", nf);
        }
        first = false;
        writes++;
    }
    jb_printf(&b, "],\"setup_events\":");
    jb_events(&b, &g_dev, 0u, mark);
    jb_printf(&b, "}\n");
    fputs(b.p, stdout);
    fflush(stdout);
}

static void cmd_crash(unsigned idx, const char *mname, const char *mode, const char *kind,
                      int ordinal, unsigned landed, bool closure)
{
    const struct media *m = media_get(mname);
    struct jb b;
    tape_result mr, r = TAPE_OK;
    unsigned mark;

    g_evn = 0u;
    dev_load(&g_dev, "own", m, strcmp(mode, "write_through") == 0);
    g_dev.inj = parse_inj(kind);
    g_dev.landed = landed;
    g_dev.closure = closure;
    g_dev.refuse_mount_writes = closure;
    if (!closure) {
        if (g_dev.inj == INJ_AT_FLUSH) g_dev.target_flush = ordinal;
        else g_dev.target_write = ordinal;
    }
    mr = inst_mount(&g_main_inst, &g_dev, TAPE_SIDE_A);
    mark = g_evn;
    if (mr == TAPE_OK) r = run_promote(g_main_inst.t, NULL);

    jb_init(&b, g_out_mem, sizeof g_out_mem);
    jb_printf(&b, "{\"case_index\":%u,\"injection_fired\":%s,\"setup_mount_result\":\"%s\",\"promote_result\":\"%s\",\"pre_snapshot\":",
              idx, tf(g_dev.fired), rname(mr), rname(r));
    if (closure) {
        /* The durable image immediately before the targeted partner write. */
        if (g_dev.pre_captured) jb_snapshot(&b, &g_dev.pre, m->total_chunks);
        else jb_printf(&b, "null");
        jb_printf(&b, ",\"run_start_snapshot\":");
    }
    jb_snapshot(&b, &m->im, m->total_chunks);
    jb_printf(&b, ",\"post_snapshot\":");
    jb_snapshot(&b, &g_dev.durable, m->total_chunks);
    jb_printf(&b, ",\"setup_events\":");
    jb_events(&b, &g_dev, 0u, mark);
    jb_remounts(&b, &g_dev.durable, m->total_chunks);
    jb_printf(&b, "}\n");
    fputs(b.p, stdout);
    fflush(stdout);
}

/* ------------------------------------------------------------------------ */
/* contract cases                                                            */
/* ------------------------------------------------------------------------ */

struct cbs {
    uint32_t last_done, last_total;
    unsigned entries, depth, max_depth;
    const char *nested_column;     /* non-NULL: perform this call from inside */
    struct jb *nested_out;
    struct jb *before_out, *after_out;
    bool nested_done;
};

static struct cbs g_cbs;
static uint32_t g_progress;       /* last blocks_done delivered to any callback */
static bool g_last_more;          /* *more_work of the last setup promote call */

static void jb_opstate(struct jb *b, const char *token);
static void probe_column(struct jb *b, tape *t, const char *col);

static void progress_cb(void *user, uint32_t done, uint32_t total)
{
    struct cbs *s = (struct cbs *)user;
    s->entries++;
    s->depth++;
    if (s->depth > s->max_depth) s->max_depth = s->depth;
    s->last_done = done;
    s->last_total = total;
    g_progress = done;
    if (s->nested_column != NULL && !s->nested_done) {
        s->nested_done = true;
        jb_printf(s->before_out, "{\"operation\":");
        jb_opstate(s->before_out, "promote-op-1");
        jb_printf(s->before_out, ",\"callback_entry_count\":%u,\"callback_max_depth\":%u}", s->entries, s->max_depth);
        probe_column(s->nested_out, g_main_inst.t, s->nested_column);
        jb_printf(s->after_out, "{\"operation\":");
        jb_opstate(s->after_out, "promote-op-1");
        jb_printf(s->after_out, ",\"callback_entry_count\":%u,\"callback_max_depth\":%u}", s->entries, s->max_depth);
    }
    s->depth--;
}

/* A second, distinct callback for the allowed-mutables case. */
static void progress_cb_b(void *user, uint32_t done, uint32_t total)
{
    progress_cb(user, done, total);
}

static void cbs_reset(void)
{
    memset(&g_cbs, 0, sizeof g_cbs);
    g_progress = 0u;
}

static unsigned promote_event_count(void)
{
    unsigned i, n = 0u;
    for (i = 0u; i < g_evn; ++i) if (g_ev[i].in_promote && strcmp(g_ev[i].dev, g_dev.name) == 0) n++;
    return n;
}

static void jb_chunk_writes(struct jb *b)
{
    unsigned i;
    bool first = true;
    jb_printf(b, "[");
    for (i = 0u; i < g_evn; ++i) {
        const struct event *e = &g_ev[i];
        if (!e->in_promote || strcmp(e->dev, g_dev.name) != 0 || e->op != 'w' || e->rc != 0) continue;
        if (!is_chunk_lba(&g_dev, e->lba)) continue;
        jb_printf(b, "%s%u", first ? "" : ",", e->lba);
        first = false;
    }
    jb_printf(b, "]");
}

/* ADAPTER.md "Promote WP-12a row": the operation snapshot is exactly an
   optional non-causal label, numeric progress, the cumulative own-device event
   count of tape_promote calls, and their cumulative chunk-region write LBAs. */
static void jb_opstate(struct jb *b, const char *token)
{
    if (token == NULL) jb_printf(b, "{\"operation_token\":null");
    else jb_printf(b, "{\"operation_token\":\"%s\"", token);
    jb_printf(b, ",\"progress_blocks\":%u,\"own_device_event_count\":%u,\"chunk_write_lbas\":",
              g_progress, promote_event_count());
    jb_chunk_writes(b);
    jb_printf(b, "}");
}

static const int16_t k_feed_pcm[2u * 300u];

static void jb_render(struct jb *b, tape *t, uint32_t frames)
{
    uint32_t rendered = 0u;
    tape_result r;
    unsigned mark = g_evn;
    memset(g_pcm, 0, sizeof g_pcm);
    r = tape_render(t, g_pcm, frames, &rendered);
    jb_printf(b, "{\"fn\":\"tape_render\",\"rate_q16_16\":%d,\"result\":\"%s\",\"rendered\":%u,\"output_hex\":\"",
              (int)t->rate_q16_16, rname(r), rendered);
    jb_hex(b, (const unsigned char *)g_pcm, (size_t)rendered * 4u);
    jb_printf(b, "\",\"block_events\":");
    jb_events(b, &g_dev, mark, g_evn);
    jb_printf(b, "}");
}

static void jb_status(struct jb *b, tape *t)
{
    tape_status_t st;
    tape_info info;
    uint64_t pos = 0u;
    tape_result r1, r2, r3;
    unsigned mark = g_evn;
    r1 = tape_status(t, &st);
    r2 = tape_get_info(t, &info);
    r3 = tape_tell(t, &pos);
    jb_printf(b, "{\"calls\":[{\"fn\":\"tape_status\",\"result\":\"%s\"},{\"fn\":\"tape_get_info\",\"result\":\"%s\"},"
                 "{\"fn\":\"tape_tell\",\"result\":\"%s\",\"position\":%llu}],\"block_events\":",
              rname(r1), rname(r2), rname(r3), (unsigned long long)pos);
    jb_events(b, &g_dev, mark, g_evn);
    jb_printf(b, "}");
}

static const uint8_t k_dup_uuid[16] = {0xd0,0xd1,0xd2,0xd3,0xd4,0xd5,0xd6,0xd7,0xd8,0xd9,0xda,0xdb,0xdc,0xdd,0xde,0xdf};

/* One matrix column, exactly one public call (three for status/info/tell). */
static void probe_column(struct jb *b, tape *t, const char *col)
{
    tape_result r;
    bool more = false;
    unsigned mark;

    if (strcmp(col, "render") == 0) { jb_render(b, t, 16u); return; }
    if (strcmp(col, "status_info_tell") == 0) { jb_status(b, t); return; }

    mark = g_evn;
    if (strcmp(col, "seek") == 0) r = tape_seek(t, 0u);
    else if (strcmp(col, "set_rate") == 0) r = tape_set_rate(t, 0x10000);
    else if (strcmp(col, "service") == 0) r = tape_service(t, 16u, &more);
    else if (strcmp(col, "arm") == 0) r = tape_arm(t, TAPE_REC_OVERWRITE);
    else if (strcmp(col, "feed") == 0) { uint32_t acc = 0u; r = tape_feed(t, k_feed_pcm, 4u, &acc); }
    else if (strcmp(col, "commit") == 0) r = tape_commit(t);
    else if (strcmp(col, "abort") == 0) r = tape_abort(t);
    else if (strcmp(col, "set_side") == 0) r = tape_set_side(t, TAPE_SIDE_B);
    else if (strcmp(col, "reset_b") == 0) r = tape_reset_side_b(t);
    else if (strcmp(col, "promote") == 0) r = promote_call(t, 1u, &more, progress_cb, &g_cbs);
    else if (strcmp(col, "respool") == 0) r = tape_respool(t, 1u, &more);
    else if (strcmp(col, "dup") == 0) {
        tape_dev dd = dev_of(&g_dst);
        r = tape_dup(t, &dd, k_dup_uuid, 0u, 9u, 1u, &more, NULL, NULL);
    }
    else if (strcmp(col, "unmount") == 0) { uint64_t pos = 0u; r = tape_unmount(t, &pos); }
    else { fprintf(stderr, "unknown column %s\n", col); exit(3); }

    jb_printf(b, "{\"fn\":\"%s\",\"result\":\"%s\"", strcmp(col, "promote") == 0 ? "tape_promote" : col, rname(r));
    if (strcmp(col, "promote") == 0 || strcmp(col, "service") == 0) jb_printf(b, ",\"more_work\":%s", tf(more));
    jb_printf(b, ",\"block_events\":");
    jb_events(b, &g_dev, mark, g_evn);
    jb_printf(b, "}");
}

static tape *open_main(const char *mname, bool write_through, tape_side side, tape_result *mr)
{
    const struct media *m = media_get(mname);
    g_evn = 0u;
    dev_load(&g_dev, "own", m, write_through);
    *mr = inst_mount(&g_main_inst, &g_dev, side);
    return g_main_inst.t;
}

static void open_dst(void)
{
    static struct media blank;
    blank.total_chunks = 4u;
    blank.im.n = 0u;
    dev_load(&g_dst, "destination", &blank, true);
}

/* Start the fresh allocating promote and advance it by `calls` budget-1 calls. */
static tape *start_in_progress(const char *mname, unsigned calls)
{
    tape_result mr;
    tape *t;
    unsigned i;
    bool more = false;
    cbs_reset();
    open_dst();
    t = open_main(mname, false, TAPE_SIDE_A, &mr);
    if (mr != TAPE_OK) { fprintf(stderr, "setup mount %s\n", rname(mr)); exit(3); }
    for (i = 0u; i < calls; ++i) (void)promote_call(t, 1u, &more, progress_cb, &g_cbs);
    g_last_more = more;
    return t;
}

static void jb_continuation(struct jb *b, tape *t)
{
    bool more = false;
    tape_result r;
    jb_printf(b, "{\"before\":");
    jb_opstate(b, "promote-op-1");
    r = promote_call(t, 1u, &more, progress_cb, &g_cbs);
    jb_printf(b, ",\"call\":{\"fn\":\"tape_promote\",\"block_budget\":1,\"result\":\"%s\",\"more_work\":%s},\"after\":",
              rname(r), tf(more));
    jb_opstate(b, "promote-op-1");
    jb_printf(b, "}");
}

static bool is_busy_column(const char *c)
{
    return strcmp(c, "render") != 0 && strcmp(c, "service") != 0
        && strcmp(c, "status_info_tell") != 0 && strcmp(c, "promote") != 0;
}

static void k_promote_row(struct jb *b, const char *col, const char *mname)
{
    tape *t = start_in_progress(mname, 2u);
    jb_printf(b, ",\"column\":\"%s\",\"state_before\":{\"promote_in_progress\":%s,\"rate_q16_16\":%d,\"faulted\":%s}",
              col, tf(t->promote_in_progress), (int)t->rate_q16_16, tf(t->faulted));
    jb_printf(b, ",\"before\":");
    jb_opstate(b, "promote-op-1");
    jb_printf(b, ",\"probe\":");
    probe_column(b, t, col);
    jb_printf(b, ",\"after_probe\":");
    jb_opstate(b, "promote-op-1");
    if (is_busy_column(col)) {
        jb_printf(b, ",\"next_continuation\":");
        jb_continuation(b, t);
    }
}

static void k_reentry(struct jb *b, const char *col, const char *mname)
{
    struct jb nested, before, after;
    static char bmem[1u << 16], amem[1u << 16];
    tape *t = start_in_progress(mname, 2u);
    bool more = false;
    tape_result r;

    jb_init(&nested, g_nested_mem, sizeof g_nested_mem);
    jb_init(&before, bmem, sizeof bmem);
    jb_init(&after, amem, sizeof amem);
    g_cbs.entries = 0u;
    g_cbs.max_depth = 0u;
    g_cbs.nested_column = col;
    g_cbs.nested_out = &nested;
    g_cbs.before_out = &before;
    g_cbs.after_out = &after;
    g_cbs.nested_done = false;
    r = promote_call(t, 1u, &more, progress_cb, &g_cbs);
    g_cbs.nested_column = NULL;
    jb_printf(b, ",\"column\":\"%s\",\"outer_call\":{\"fn\":\"tape_promote\",\"block_budget\":1,\"result\":\"%s\",\"more_work\":%s}",
              col, rname(r), tf(more));
    jb_printf(b, ",\"callback_before\":%s,\"nested_call\":%s,\"callback_after\":%s",
              before.n ? before.p : "null", nested.n ? nested.p : "null", after.n ? after.p : "null");
    jb_printf(b, ",\"next_continuation\":");
    jb_continuation(b, t);
}

static void k_zero_budget(struct jb *b, const char *variant, const char *mname)
{
    tape *t = start_in_progress(mname, strcmp(variant, "initiate") == 0 ? 0u : 2u);
    bool more = false;
    tape_result r;
    unsigned mark;
    const char *tok = strcmp(variant, "initiate") == 0 ? NULL : "promote-op-1";
    jb_printf(b, ",\"variant\":\"%s\",\"before\":", variant);
    jb_opstate(b, tok);
    mark = g_evn;
    r = promote_call(t, 0u, &more, progress_cb, &g_cbs);
    jb_printf(b, ",\"call\":{\"fn\":\"tape_promote\",\"block_budget\":0,\"result\":\"%s\",\"more_work\":%s,\"block_events\":",
              rname(r), tf(more));
    jb_events(b, &g_dev, mark, g_evn);
    jb_printf(b, "},\"after\":");
    jb_opstate(b, tok);
}

static void k_allowed_mutables(struct jb *b, const char *mname)
{
    static bool mw_a, mw_b;
    static struct cbs user_b;
    tape_result mr, r;
    tape *t;
    cbs_reset();
    memset(&user_b, 0, sizeof user_b);
    open_dst();
    t = open_main(mname, false, TAPE_SIDE_A, &mr);
    (void)promote_call(t, 1u, &mw_a, progress_cb, &g_cbs);
    jb_printf(b, ",\"initial_args\":{\"block_budget\":1,\"more_work_ptr\":\"mw-a\",\"cb\":\"cb-a\",\"user\":\"u-a\"}");
    jb_printf(b, ",\"initial_result\":{\"more_work\":%s}", tf(mw_a));
    jb_printf(b, ",\"call_args\":{\"block_budget\":2,\"more_work_ptr\":\"mw-b\",\"cb\":\"cb-b\",\"user\":\"u-b\"}");
    jb_printf(b, ",\"before\":");
    jb_opstate(b, "promote-op-1");
    r = promote_call(t, 2u, &mw_b, progress_cb_b, &user_b);
    jb_printf(b, ",\"call\":{\"fn\":\"tape_promote\",\"result\":\"%s\",\"more_work\":%s},\"cb_b_entries\":%u,\"cb_a_entries\":%u,\"after\":",
              rname(r), tf(mw_b), user_b.entries, g_cbs.entries);
    jb_opstate(b, "promote-op-1");
}

static const char *transport_label(const tape *t, bool more)
{
    if (t->faulted) return "FAULTED";
    if (t->promote_in_progress && more) return "Promote in progress";
    if (t->rec_armed) return "Armed";
    if (t->rate_q16_16 != 0) return "Playing";
    return "Mounted, idle";
}

/* Own-device failure from Promote in progress: the third budget-1 call is the
   phase-1 data write, which the device fails with a raw rc of 5. */
static tape *fault_from_promote(struct jb *b, const char *mname, bool emit)
{
    tape *t = start_in_progress(mname, 2u);
    bool more = true;
    tape_result r;
    unsigned mark;
    if (emit) {
        jb_printf(b, ",\"state_before\":\"%s\",\"operation_before\":", transport_label(t, g_last_more));
        jb_opstate(b, "promote-op-1");
    }
    g_dev.fail_write_at = (long)g_dev.writes_total;
    mark = g_evn;
    r = promote_call(t, 1u, &more, progress_cb, &g_cbs);
    g_dev.fail_write_at = -1;
    if (emit) {
        jb_printf(b, ",\"call\":{\"fn\":\"tape_promote\",\"block_budget\":1,\"result\":\"%s\",\"more_work\":%s}",
                  rname(r), tf(more));
        jb_printf(b, ",\"own_device_events\":");
        jb_events(b, &g_dev, mark, g_evn);
        jb_printf(b, ",\"transport_after\":\"%s\"", transport_label(t, more));
    }
    return t;
}

/* Frames of the retained play window at or after the playhead. */
static uint32_t ring_window_frames(const tape *t)
{
    uint64_t pos = t->position_frame >> 32;
    uint64_t end = (uint64_t)t->play_base + t->play_frames;
    if (!t->play_ring_valid || end <= pos) return 0u;
    return (uint32_t)(end - pos);
}

/* Frames tape_render can still emit from that window: §6.3 interpolates frame
   i with i+1, so when the window stops short of the timeline end its last
   frame is not renderable until i+1 is loaded. */
static uint32_t ring_frames(const tape *t)
{
    uint32_t w = ring_window_frames(t);
    uint64_t end = (uint64_t)t->play_base + t->play_frames;
    if (w > 0u && end < TAPE_LIVE(t).total_frames) w--;
    return w;
}

static void k_faulted_row(struct jb *b, const char *col, const char *mname, const char *play_media)
{
    jb_printf(b, ",\"column\":\"%s\"", col);
    if (strcmp(col, "render") == 0) {
        /* A separate Playing fixture: Side B playing, ring filled, then an
           own-device write fails (tape_arm's §8 stage-clearing write). */
        tape_result mr, ra;
        tape *t;
        bool more = false;
        unsigned guard = 0u, mark;
        cbs_reset();
        t = open_main(play_media, false, TAPE_SIDE_B, &mr);
        (void)tape_set_rate(t, 0x10000);
        while (guard++ < 1000u) {
            more = false;
            if (tape_service(t, 256u, &more) != TAPE_OK || !more) break;
        }
        jb_printf(b, ",\"probe\":{\"fixture_mount_result\":\"%s\",\"fixture_state_before_fault\":\"%s\",\"ring_frames_at_fault\":%u",
                  rname(mr), transport_label(t, false), ring_frames(t));
        g_dev.fail_write_at = (long)g_dev.writes_total;
        mark = g_evn;
        ra = tape_arm(t, TAPE_REC_OVERWRITE);
        g_dev.fail_write_at = -1;
        jb_printf(b, ",\"fault_call\":{\"fn\":\"tape_arm\",\"result\":\"%s\",\"block_events\":", rname(ra));
        jb_events(b, &g_dev, mark, g_evn);
        jb_printf(b, "},\"state_after_fault\":\"%s\",\"calls\":[", transport_label(t, false));
        mark = g_evn;
        guard = 0u;
        while (guard++ < 64u) {
            uint32_t before = ring_frames(t), rendered = 0u, ask;
            tape_result r;
            ask = before > 8192u ? 8192u : (before == 0u ? 64u : before);
            r = tape_render(t, g_pcm, ask, &rendered);
            jb_printf(b, "%s{\"result\":\"%s\",\"ring_frames_before\":%u,\"ring_frames_after\":%u,\"ring_window_frames_after\":%u,\"rendered\":%u,\"output_hex\":\"",
                      guard > 1u ? "," : "", rname(r), before, ring_frames(t), ring_window_frames(t), rendered);
            jb_hex(b, (const unsigned char *)g_pcm, (size_t)rendered * 4u);
            jb_printf(b, "\"}");
            if (r != TAPE_OK || before == 0u) break;
        }
        jb_printf(b, "],\"block_events\":");
        jb_events(b, &g_dev, mark, g_evn);
        jb_printf(b, "}");
        return;
    }
    if (strcmp(col, "abort") == 0) {
        /* Armed with frames owed, then the owed chunk write fails in service. */
        tape_result mr, ra, rf, rs, rab;
        tape *t;
        uint32_t acc = 0u;
        bool more = false;
        unsigned mark;
        uint64_t owed_before, owed_after;
        bool armed_before;
        static int16_t pcm[2u * 300u];
        unsigned i;
        for (i = 0u; i < 600u; ++i) pcm[i] = (int16_t)(i + 1u);
        cbs_reset();
        t = open_main(mname, false, TAPE_SIDE_B, &mr);
        ra = tape_arm(t, TAPE_REC_OVERWRITE);
        rf = tape_feed(t, pcm, 300u, &acc);
        g_dev.fail_write_at = (long)g_dev.writes_total;
        mark = g_evn;
        rs = tape_service(t, 16u, &more);
        g_dev.fail_write_at = -1;
        jb_printf(b, ",\"setup\":{\"mount\":\"%s\",\"arm\":\"%s\",\"feed\":\"%s\",\"accepted\":%u,\"service\":\"%s\",\"service_events\":",
                  rname(mr), rname(ra), rname(rf), acc, rname(rs));
        jb_events(b, &g_dev, mark, g_evn);
        jb_printf(b, ",\"state_after_fault\":\"%s\"}", transport_label(t, false));
        owed_before = t->rec_frames - t->rec_written;
        armed_before = t->rec_armed;
        mark = g_evn;
        rab = tape_abort(t);
        owed_after = t->rec_frames - t->rec_written;
        jb_printf(b, ",\"probe\":{\"fn\":\"tape_abort\",\"result\":\"%s\",\"frames_owed_before\":%llu,\"frames_owed_after\":%llu,\"armed_before\":%s,\"armed_after\":%s,\"block_events\":",
                  rname(rab), (unsigned long long)owed_before, (unsigned long long)owed_after,
                  tf(armed_before), tf(t->rec_armed));
        jb_events(b, &g_dev, mark, g_evn);
        jb_printf(b, "}");
        return;
    }
    {
        tape *t = fault_from_promote(b, mname, false);
        jb_printf(b, ",\"state_before_probe\":\"%s\",\"probe\":", transport_label(t, false));
        open_dst();
        probe_column(b, t, col);
    }
}

static void k_small_budget(struct jb *b, const char *mname)
{
    tape_result mr, r;
    tape *t;
    bool more = true;
    unsigned guard = 0u;
    bool first = true;
    cbs_reset();
    t = open_main(mname, false, TAPE_SIDE_A, &mr);
    jb_printf(b, ",\"call_sequence\":[");
    while (more && guard++ < 10000u) {
        uint32_t pb = g_progress;
        jb_printf(b, "%s{\"fn\":\"tape_promote\",\"budget\":1,\"operation_token\":\"promote-op-1\",\"progress_before\":%u,\"chunk_write_lbas_before\":",
                  first ? "" : ",", pb);
        jb_chunk_writes(b);
        more = false;
        r = promote_call(t, 1u, &more, progress_cb, &g_cbs);
        jb_printf(b, ",\"result\":\"%s\",\"more_work\":%s,\"progress_after\":%u,\"progress_total\":%u,\"chunk_write_lbas_after\":",
                  rname(r), tf(more), g_progress, g_cbs.last_total);
        jb_chunk_writes(b);
        jb_printf(b, "}");
        first = false;
        if (r != TAPE_OK) break;
    }
    jb_printf(b, "],\"terminal_snapshot\":");
    jb_snapshot(b, &g_dev.durable, g_dev.total_chunks);
}

/* A single promote driven to terminal with a large budget; emits the call
   result and the complete callback trace. */
static tape_result drive(struct jb *b, tape *t, unsigned *calls_out)
{
    unsigned mark = g_evn;
    tape_result r = run_promote(t, calls_out);
    jb_printf(b, ",\"call_result\":\"%s\",\"block_events\":", rname(r));
    jb_events(b, &g_dev, mark, g_evn);
    return r;
}

static void jb_written(struct jb *b, bool headers)
{
    unsigned i;
    bool first = true;
    uint32_t last_gen = 0u;
    jb_printf(b, "[");
    for (i = 0u; i < g_evn; ++i) {
        const struct event *e = &g_ev[i];
        unsigned s;
        bool hdr = false;
        if (!e->in_promote || e->op != 'w' || e->rc != 0 || strcmp(e->dev, g_dev.name) != 0) continue;
        for (s = 0u; s < 4u; ++s) if (e->lba == k_slot_base[s]) hdr = true;
        if (headers && hdr) {
            jb_printf(b, "%s%u", first ? "" : ",", e->word8);
            first = false;
        } else if (!headers && is_sb_lba(&g_dev, e->lba)) {
            if (first || e->word12 != last_gen) {
                jb_printf(b, "%s%u", first ? "" : ",", e->word12);
                first = false;
                last_gen = e->word12;
            }
        }
    }
    jb_printf(b, "]");
}

static void jb_counters(struct jb *b, const tape *t)
{
    jb_printf(b, "{\"sequence\":%u,\"sb_generation\":%u}", t->cartridge_sequence, t->sb.sb_generation);
}

static bool slot_structural(const unsigned char *hdr, const unsigned char *ent, uint32_t *seq)
{
    uint32_t count = rd32(hdr + 16);
    uint32_t c;
    if (memcmp(hdr, "TAPEIDX\x01", 8) != 0 || count > 4096u) return false;
    if ((size_t)count * 12u > BLOCK) return false;   /* fixtures carry one entry block */
    c = tape_crc32_init();
    c = tape_crc32_update(c, hdr, 60u);
    c = tape_crc32_update(c, ent, (size_t)count * 12u);
    if (tape_crc32_final(c) != rd32(hdr + 60)) return false;
    *seq = rd32(hdr + 8);
    return true;
}

static void k_contract(unsigned idx, const char *fam, const char *param, char **media, unsigned nmedia)
{
    struct jb b;
    tape_result mr;
    tape *t;
    unsigned mark;

    jb_init(&b, g_out_mem, sizeof g_out_mem);
    jb_printf(&b, "{\"case_index\":%u", idx);

    if (strcmp(fam, "stage_oracle") == 0) {
        const struct media *m = media_get(media[0]);
        jb_printf(&b, ",\"variant\":\"%s\",\"snapshot\":", param);
        jb_snapshot(&b, &m->im, m->total_chunks);
        t = open_main(media[0], true, TAPE_SIDE_A, &mr);
        jb_printf(&b, ",\"actual_mount_result\":\"%s\",\"mount_events\":", rname(mr));
        jb_events(&b, &g_dev, 0u, g_evn);
    } else if (strcmp(fam, "rerun_row") == 0 || strcmp(fam, "rerun_special") == 0) {
        const struct media *m = media_get(media[0]);
        if (strcmp(fam, "rerun_row") == 0) jb_printf(&b, ",\"row\":%s", param);
        else jb_printf(&b, ",\"variant\":\"%s\"", param);
        if (strcmp(param, "repeated_between3_4") == 0) {
            /* Three attempts cut by power loss before the step-4 partner write
               (flush-required), each remounted from the durable result, then
               one uninterrupted attempt. Raw per-attempt facts only. */
            static struct media cur;
            unsigned a;
            cur = *m;
            jb_printf(&b, ",\"seed_snapshot\":");
            jb_snapshot(&b, &m->im, m->total_chunks);
            jb_printf(&b, ",\"attempts\":[");
            for (a = 0u; a < 4u; ++a) {
                unsigned i;
                tape_result r;
                int staging = -1;
                g_evn = 0u;
                dev_load(&g_dev, "own", &cur, false);
                if (a < 3u) { g_dev.closure = true; g_dev.inj = INJ_BEFORE; }
                mr = inst_mount(&g_main_inst, &g_dev, TAPE_SIDE_A);
                jb_printf(&b, "%s{\"attempt\":%u,\"mount_result\":\"%s\",\"free_next_before\":%u",
                          a ? "," : "", a, rname(mr), g_main_inst.t->free_next);
                mark = g_evn;
                r = run_promote(g_main_inst.t, NULL);
                for (i = mark; i < g_evn; ++i) {
                    const struct event *e = &g_ev[i];
                    if (e->op == 'w' && e->rc == 0 && (e->lba == 9u || e->lba == 137u)) { staging = (int)e->word0; break; }
                }
                jb_printf(&b, ",\"power_cut_before_first_superblock_write\":%s,\"call_result\":\"%s\",\"staging_start\":%d,\"chunk_write_lbas\":",
                          tf(a < 3u), rname(r), staging);
                jb_chunk_writes(&b);
                jb_printf(&b, ",\"block_events\":");
                jb_events(&b, &g_dev, mark, g_evn);
                jb_printf(&b, "}");
                img_copy(&cur.im, &g_dev.durable);
            }
            jb_printf(&b, "],\"terminal_snapshot\":");
            jb_snapshot(&b, &cur.im, cur.total_chunks);
        } else {
            jb_printf(&b, ",\"seed_snapshot\":");
            jb_snapshot(&b, &m->im, m->total_chunks);
            t = open_main(media[0], true, TAPE_SIDE_A, &mr);
            jb_printf(&b, ",\"setup_mount_result\":\"%s\",\"block_count\":%u", rname(mr), g_dev.block_count);
            if (mr == TAPE_OK) (void)drive(&b, t, NULL);
            jb_printf(&b, ",\"terminal_snapshot\":");
            jb_snapshot(&b, &g_dev.durable, m->total_chunks);
        }
    } else if (strcmp(fam, "stored_position") == 0) {
        bool more = true, first = true, cleared = false;
        unsigned guard = 0u;
        cbs_reset();
        t = open_main(media[0], true, TAPE_SIDE_A, &mr);
        jb_printf(&b, ",\"variant\":\"%s\",\"setup_mount_result\":\"%s\",\"position_table_owner\":\"caller-model\","
                      "\"position_table_before\":{\"A\":111,\"B\":222},\"calls\":[", param, rname(mr));
        while (more && guard++ < 1000u) {
            tape_result r;
            more = false;
            r = promote_call(t, 1u, &more, progress_cb, &g_cbs);
            /* The caller's model: it clears (uuid, A) and (uuid, B) only on an
               observed terminal TAPE_OK / more_work == false. */
            jb_printf(&b, "%s{\"result\":\"%s\",\"more_work\":%s,\"caller_table_before\":", first ? "" : ",", rname(r), tf(more));
            if (cleared) jb_printf(&b, "{\"A\":null,\"B\":null}"); else jb_printf(&b, "{\"A\":111,\"B\":222}");
            if (r == TAPE_OK && !more) cleared = true;
            jb_printf(&b, ",\"caller_table_after\":");
            if (cleared) jb_printf(&b, "{\"A\":null,\"B\":null}"); else jb_printf(&b, "{\"A\":111,\"B\":222}");
            jb_printf(&b, "}");
            first = false;
            if (r != TAPE_OK) break;
        }
        jb_printf(&b, "]");
    } else if (strcmp(fam, "headroom_exact") == 0 || strcmp(fam, "headroom_short") == 0
               || strcmp(fam, "headroom_special") == 0 || strcmp(fam, "zero_needed_reserved") == 0
               || strcmp(fam, "entry_refusal") == 0 || strcmp(fam, "shared_sequence") == 0) {
        t = open_main(media[0], true, TAPE_SIDE_A, &mr);
        jb_printf(&b, ",\"setup_media\":\"%s\",\"setup_mount_result\":\"%s\",\"counter_values\":", media[0], rname(mr));
        jb_counters(&b, t);
        if (strcmp(fam, "shared_sequence") == 0) {
            unsigned s;
            bool first = true;
            jb_printf(&b, ",\"structural_sequences_before\":{");
            for (s = 0u; s < 4u; ++s) {
                unsigned char hdr[BLOCK], ent[BLOCK];
                uint32_t seq;
                img_get(&media_get(media[0])->im, k_slot_base[s], hdr);
                img_get(&media_get(media[0])->im, k_slot_base[s] + 1u, ent);
                if (slot_structural(hdr, ent, &seq)) {
                    jb_printf(&b, "%s\"%c%c\":%u", first ? "" : ",", k_slot_name[s][0] - 32, k_slot_name[s][1], seq);
                    first = false;
                }
            }
            jb_printf(&b, "}");
        }
        if (mr == TAPE_OK) (void)drive(&b, t, NULL);
        jb_printf(&b, ",\"index_commit_sequences\":");
        jb_written(&b, true);
        jb_printf(&b, ",\"superblock_generations\":");
        jb_written(&b, false);
    } else if (strcmp(fam, "counter_domains") == 0) {
        bool more = true, first = true;
        unsigned guard = 0u;
        cbs_reset();
        t = open_main(media[0], true, TAPE_SIDE_A, &mr);
        jb_printf(&b, ",\"setup_media\":\"%s\",\"calls\":[", media[0]);
        while (more && guard++ < 1000u) {
            uint32_t s0 = t->cartridge_sequence, g0 = t->sb.sb_generation;
            tape_result r;
            mark = g_evn;
            more = false;
            r = promote_call(t, 1u, &more, progress_cb, &g_cbs);
            jb_printf(&b, "%s{\"result\":\"%s\",\"more_work\":%s,\"sequence_before\":%u,\"sequence_after\":%u,"
                          "\"sb_generation_before\":%u,\"sb_generation_after\":%u,\"block_events\":",
                      first ? "" : ",", rname(r), tf(more), s0, t->cartridge_sequence, g0, t->sb.sb_generation);
            jb_events(&b, &g_dev, mark, g_evn);
            jb_printf(&b, "}");
            first = false;
            if (r != TAPE_OK) break;
        }
        jb_printf(&b, "]");
    } else if (strcmp(fam, "promote_in_progress_row") == 0) {
        k_promote_row(&b, param, media[0]);
    } else if (strcmp(fam, "callback_reentry") == 0) {
        k_reentry(&b, param, media[0]);
    } else if (strcmp(fam, "zero_budget") == 0) {
        k_zero_budget(&b, param, media[0]);
    } else if (strcmp(fam, "allowed_mutables") == 0) {
        k_allowed_mutables(&b, media[0]);
    } else if (strcmp(fam, "own_device_failure") == 0) {
        (void)fault_from_promote(&b, media[0], true);
    } else if (strcmp(fam, "faulted_row") == 0) {
        k_faulted_row(&b, param, media[0], nmedia > 1u ? media[1] : media[0]);
    } else if (strcmp(fam, "small_budget_completion") == 0) {
        k_small_budget(&b, media[0]);
    } else {
        fprintf(stderr, "unknown family %s\n", fam);
        exit(3);
    }
    jb_printf(&b, "}\n");
    fputs(b.p, stdout);
    fflush(stdout);
}

/* ------------------------------------------------------------------------ */
/* main loop                                                                 */
/* ------------------------------------------------------------------------ */

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

static char g_line[1u << 16];

static unsigned split(char *s, char **f, unsigned max)
{
    unsigned n = 0u;
    char *p = s;
    while (n < max) {
        char *tab = strchr(p, '\t');
        f[n++] = p;
        if (tab == NULL) break;
        *tab = '\0';
        p = tab + 1;
    }
    return n;
}

static void chomp(char *s)
{
    size_t n = strlen(s);
    while (n > 0u && (s[n - 1u] == '\n' || s[n - 1u] == '\r')) s[--n] = '\0';
}

static void cmd_media(char **f, unsigned nf)
{
    struct media *m;
    unsigned long nb, i;
    if (nf < 4u || g_media_n >= MAX_MEDIA) { fprintf(stderr, "bad M\n"); exit(3); }
    m = &g_media[g_media_n++];
    memset(m, 0, sizeof *m);
    snprintf(m->name, sizeof m->name, "%s", f[1]);
    m->total_chunks = (uint32_t)strtoul(f[2], NULL, 10);
    nb = strtoul(f[3], NULL, 10);
    for (i = 0u; i < nb; ++i) {
        char *g[2];
        unsigned char blk[BLOCK];
        unsigned k;
        if (fgets(g_line, sizeof g_line, stdin) == NULL) { fprintf(stderr, "short M\n"); exit(3); }
        chomp(g_line);
        if (split(g_line, g, 2u) != 2u || strlen(g[1]) != 2u * BLOCK) { fprintf(stderr, "bad block\n"); exit(3); }
        for (k = 0u; k < BLOCK; ++k) {
            int hi = hexval(g[1][2u * k]), lo = hexval(g[1][2u * k + 1u]);
            if (hi < 0 || lo < 0) { fprintf(stderr, "bad hex\n"); exit(3); }
            blk[k] = (unsigned char)(hi * 16 + lo);
        }
        img_put(&m->im, (uint32_t)strtoul(g[0], NULL, 10), blk, BLOCK);
    }
}

int main(void)
{
    inst_alloc(&g_main_inst);
    inst_alloc(&g_aux_inst);
    while (fgets(g_line, sizeof g_line, stdin) != NULL) {
        char *f[16];
        unsigned nf;
        chomp(g_line);
        nf = split(g_line, f, 16u);
        if (strcmp(f[0], "D") == 0) return 0;
        if (strcmp(f[0], "M") == 0) { cmd_media(f, nf); continue; }
        if (strcmp(f[0], "B") == 0 && nf == 2u) { cmd_baseline(f[1], false); continue; }
        if (strcmp(f[0], "BZ") == 0 && nf == 2u) { cmd_baseline(f[1], true); continue; }
        if (strcmp(f[0], "C") == 0 && nf == 7u) {
            cmd_crash((unsigned)strtoul(f[1], NULL, 10), f[2], f[3], f[4],
                      (int)strtol(f[5], NULL, 10), (unsigned)strtoul(f[6], NULL, 10), false);
            continue;
        }
        if (strcmp(f[0], "Z") == 0 && nf == 6u) {
            cmd_crash((unsigned)strtoul(f[1], NULL, 10), f[2], f[3], f[4], 0,
                      (unsigned)strtoul(f[5], NULL, 10), true);
            continue;
        }
        if (strcmp(f[0], "K") == 0 && nf >= 5u) {
            k_contract((unsigned)strtoul(f[1], NULL, 10), f[2], f[3], f + 4, nf - 4u);
            continue;
        }
        fprintf(stderr, "bad command %s\n", f[0]);
        return 3;
    }
    return 3;
}
