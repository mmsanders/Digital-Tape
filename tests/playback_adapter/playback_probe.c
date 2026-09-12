/*
 * playback_probe.c — mechanical DRAFT-8 playback adapter (product).
 *
 * Contract: tests/playback_draft8/ADAPTER.md (Verification-owned, imported
 * verbatim). This is plumbing from the frozen public API to the independent
 * package. It implements no engine behaviour, observes no engine internals, and
 * references only public functions declared in the real product tape.h.
 *
 *   playback_probe --fixture RAW.vo08 --out-dir DIR
 *
 * Emits observation.json plus forward-1x.pcm, seek-boundaries.pcm and
 * reverse-neg1x.pcm (interleaved stereo s16le, 44.1 kHz). Every public call and
 * every block callback is recorded in order, unfiltered, with its real result.
 *
 * SHA-256 is implemented here rather than delegated to a script wrapper so that
 * one binary performs the engine calls AND binds the fixture hash: there is no
 * intermediate process that could synthesise an observation the engine did not
 * produce.
 *
 * Mechanical header/library selection:
 *   -DTAPE_PUBLIC_HEADER='"tape.h"' -I<engine>/include
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
#define ADAPTER_ID   "software-lead-playback-public-api-probe-v1"
#define OBS_SCHEMA   "playback-draft8-observation-v1"

#define VO_BLOCK      512u
#define RATE_ONE       65536
#define RATE_NEG_ONE  (-65536)
#define FWD_FRAMES    15u
#define REV_FRAMES    15u
#define SERVICE_BUDGET 1024u          /* the oracle requires exactly this */
#define SERVICE_GUARD  4096u          /* finite bound; nontermination fails */

static const uint64_t SEEK_TARGETS[] = {0, 1, 4, 5, 6, 8, 9, 10};
#define N_SEEK (sizeof SEEK_TARGETS / sizeof SEEK_TARGETS[0])

/* ---------------- SHA-256 (harness-local; not engine code) ---------------- */

struct sha256 { uint32_t h[8]; uint64_t len; unsigned char buf[64]; size_t n; };

static uint32_t ror(uint32_t x, unsigned s) { return (x >> s) | (x << (32u - s)); }

static void sha256_block(struct sha256 *c, const unsigned char *p)
{
    static const uint32_t K[64] = {
        0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
        0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
        0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
        0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
        0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
        0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
        0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
        0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u };
    uint32_t w[64], a, b, cc, d, e, f, g, h, t1, t2;
    unsigned i;
    for (i = 0; i < 16; i++)
        w[i] = ((uint32_t)p[4*i] << 24) | ((uint32_t)p[4*i+1] << 16)
             | ((uint32_t)p[4*i+2] << 8) | (uint32_t)p[4*i+3];
    for (i = 16; i < 64; i++) {
        uint32_t s0 = ror(w[i-15],7) ^ ror(w[i-15],18) ^ (w[i-15] >> 3);
        uint32_t s1 = ror(w[i-2],17) ^ ror(w[i-2],19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    a=c->h[0];b=c->h[1];cc=c->h[2];d=c->h[3];e=c->h[4];f=c->h[5];g=c->h[6];h=c->h[7];
    for (i = 0; i < 64; i++) {
        t1 = h + (ror(e,6)^ror(e,11)^ror(e,25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
        t2 = (ror(a,2)^ror(a,13)^ror(a,22)) + ((a & b) ^ (a & cc) ^ (b & cc));
        h=g; g=f; f=e; e=d+t1; d=cc; cc=b; b=a; a=t1+t2;
    }
    c->h[0]+=a;c->h[1]+=b;c->h[2]+=cc;c->h[3]+=d;c->h[4]+=e;c->h[5]+=f;c->h[6]+=g;c->h[7]+=h;
}

static void sha256_init(struct sha256 *c)
{
    static const uint32_t iv[8] = {0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,
                                   0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u};
    memcpy(c->h, iv, sizeof iv); c->len = 0; c->n = 0;
}

static void sha256_update(struct sha256 *c, const unsigned char *p, size_t n)
{
    c->len += (uint64_t)n;
    while (n > 0) {
        size_t take = 64u - c->n; if (take > n) take = n;
        memcpy(c->buf + c->n, p, take); c->n += take; p += take; n -= take;
        if (c->n == 64u) { sha256_block(c, c->buf); c->n = 0; }
    }
}

static void sha256_hex(struct sha256 *c, char out[65])
{
    uint64_t bits = c->len * 8u;
    unsigned char pad = 0x80, zero = 0, len_be[8];
    unsigned i;
    sha256_update(c, &pad, 1);
    while (c->n != 56u) sha256_update(c, &zero, 1);
    for (i = 0; i < 8; i++) len_be[i] = (unsigned char)(bits >> (56u - 8u*i));
    sha256_update(c, len_be, 8);
    for (i = 0; i < 8; i++)
        sprintf(out + 8*i, "%08lx", (unsigned long)c->h[i]);
    out[64] = '\0';
}

/* ------------------------- harness-owned media --------------------------- */

static unsigned char *g_payload;      /* blocks * 512, dense partition image */
static uint32_t g_blocks;
static char g_fixture_sha[65];

/* --------------------------- observation trace --------------------------- */

enum call_kind { C_MOUNT, C_RATE, C_SERVICE, C_RENDER, C_SEEK, C_UNMOUNT };

struct call_rec {
    enum call_kind kind;
    int      result;
    int32_t  rate;
    uint32_t budget;
    bool     more_work;
    uint32_t requested, rendered;
    uint64_t frame;
};

struct cb_rec { int call_index; uint32_t lba, count; int rc; };

#define MAX_CALLS 512
#define MAX_CBS   65536

struct family {
    const char *name;
    const char *output;
    struct call_rec calls[MAX_CALLS];
    size_t n_calls;
    struct cb_rec cbs[MAX_CBS];
    size_t n_cbs;
    bool overflow;
};

static struct family *g_fam;          /* family currently being driven */
static int g_call_index = -1;         /* index of the in-flight public call */

static struct call_rec *begin_call(enum call_kind k)
{
    struct call_rec *c;
    if (g_fam->n_calls >= MAX_CALLS) { g_fam->overflow = true; return NULL; }
    c = &g_fam->calls[g_fam->n_calls];
    memset(c, 0, sizeof *c);
    c->kind = k;
    g_call_index = (int)g_fam->n_calls;
    g_fam->n_calls++;
    return c;
}

/* Record EVERY callback, unfiltered, including out-of-range and failures. */
static void record_cb(uint32_t lba, uint32_t count, int rc)
{
    if (g_fam->n_cbs >= MAX_CBS) { g_fam->overflow = true; return; }
    g_fam->cbs[g_fam->n_cbs].call_index = g_call_index;
    g_fam->cbs[g_fam->n_cbs].lba = lba;
    g_fam->cbs[g_fam->n_cbs].count = count;
    g_fam->cbs[g_fam->n_cbs].rc = rc;
    g_fam->n_cbs++;
}

static int dev_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    (void)ctx;
    if (count == 0u || (uint64_t)lba + count > (uint64_t)g_blocks) {   /* widened */
        record_cb(lba, count, -1);
        return -1;
    }
    memcpy(dst, g_payload + (size_t)lba * VO_BLOCK, (size_t)count * VO_BLOCK);
    record_cb(lba, count, 0);
    return 0;
}

/* Playback is read-only. A write or flush must never happen; if the engine asks,
   that is evidence and it is recorded and refused rather than hidden. */
static int dev_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    (void)ctx; (void)src;
    fprintf(stderr, "PROTOCOL: engine attempted a write during playback (lba=%lu count=%lu)\n",
            (unsigned long)lba, (unsigned long)count);
    record_cb(lba, count, -1);
    return -1;
}

static int dev_flush(void *ctx)
{
    (void)ctx;
    fprintf(stderr, "PROTOCOL: engine attempted a flush during playback\n");
    record_cb(0, 0, -1);
    return -1;
}

/* ----------------------------- fixture I/O ------------------------------- */

static int load_fixture(const char *path)
{
    long size;
    unsigned char hdr[8];
    struct sha256 sh;
    FILE *f = fopen(path, "rb");
    if (f == NULL) { fprintf(stderr, "cannot open fixture %s\n", path); return -1; }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return -1; }
    size = ftell(f);
    if (size < 8 || fseek(f, 0, SEEK_SET) != 0) { fclose(f); return -1; }
    if (fread(hdr, 1, 8, f) != 8) { fclose(f); return -1; }
    if (memcmp(hdr, "VO08", 4) != 0) { fprintf(stderr, "bad VO08 magic\n"); fclose(f); return -1; }
    g_blocks = (uint32_t)hdr[4] | ((uint32_t)hdr[5] << 8)
             | ((uint32_t)hdr[6] << 16) | ((uint32_t)hdr[7] << 24);
    if ((uint64_t)size != 8u + (uint64_t)g_blocks * VO_BLOCK) {
        fprintf(stderr, "VO08 size/block_count mismatch (%ld bytes, %lu blocks)\n",
                size, (unsigned long)g_blocks);
        fclose(f); return -1;
    }
    g_payload = malloc((size_t)g_blocks * VO_BLOCK);
    if (g_payload == NULL) { fclose(f); return -1; }
    if (fread(g_payload, 1, (size_t)g_blocks * VO_BLOCK, f) != (size_t)g_blocks * VO_BLOCK) {
        fclose(f); return -1;
    }
    fclose(f);
    sha256_init(&sh);
    sha256_update(&sh, hdr, 8);
    sha256_update(&sh, g_payload, (size_t)g_blocks * VO_BLOCK);
    sha256_hex(&sh, g_fixture_sha);
    return 0;
}

static int write_pcm(const char *dir, const char *name, const int16_t *s, size_t frames)
{
    char path[4096];
    FILE *f;
    size_t i;
    if ((size_t)snprintf(path, sizeof path, "%s/%s", dir, name) >= sizeof path) return -1;
    f = fopen(path, "wb");
    if (f == NULL) { fprintf(stderr, "cannot write %s\n", path); return -1; }
    for (i = 0; i < frames * 2u; i++) {
        unsigned char le[2];
        le[0] = (unsigned char)((uint16_t)s[i] & 0xFFu);
        le[1] = (unsigned char)(((uint16_t)s[i] >> 8) & 0xFFu);
        if (fwrite(le, 1, 2, f) != 2) { fclose(f); return -1; }
    }
    if (fclose(f) != 0) return -1;
    return 0;
}

/* ----------------------------- caller storage ---------------------------- */

static unsigned char g_inst[262144];
static unsigned char g_play[TAPE_PLAY_RING_MIN];
static unsigned char g_rec[TAPE_REC_RING_MIN];
static tape_dev g_dev;

static tape_result open_instance(tape **out)
{
    size_t need = tape_instance_size();
    if (need > sizeof g_inst) {
        fprintf(stderr, "instance needs %zu bytes, harness reserved %zu\n", need, sizeof g_inst);
        return TAPE_ERR_INVALID_ARG;
    }
    g_dev.read = dev_read; g_dev.write = dev_write; g_dev.flush = dev_flush;
    g_dev.ctx = NULL; g_dev.block_count = g_blocks;
    return tape_init(g_inst, need, &g_dev, g_play, TAPE_PLAY_RING_MIN, g_rec, TAPE_REC_RING_MIN, out);
}

/* Drive tape_service to completion at the oracle's required budget. */
static int service_to_idle(tape *t)
{
    bool more = true;
    uint32_t iter = 0;
    while (more) {
        struct call_rec *c;
        tape_result r;
        if (iter >= SERVICE_GUARD) {
            fprintf(stderr, "service guard tripped after %u calls\n", iter);
            return -1;
        }
        c = begin_call(C_SERVICE);
        r = tape_service(t, SERVICE_BUDGET, &more);
        iter++;
        if (c != NULL) { c->result = (int)r; c->budget = SERVICE_BUDGET; c->more_work = more; }
        if (r != TAPE_OK) return -1;
    }
    return 0;
}

/* -------------------------------- scripts -------------------------------- */

static int script_forward(struct family *fam, const char *dir)
{
    static int16_t pcm[FWD_FRAMES * 2];
    tape *t = NULL; tape_result r; struct call_rec *c;
    uint32_t rendered = 0;
    g_fam = fam;
    if ((r = open_instance(&t)) != TAPE_OK) { fprintf(stderr, "tape_init: %d\n", (int)r); return -1; }
    c = begin_call(C_MOUNT);
    r = tape_mount(t, TAPE_SIDE_A, 0u, NULL);
    if (c != NULL) { c->result = (int)r; }
    if (r != TAPE_OK) { return -1; }
    c = begin_call(C_RATE);
    r = tape_set_rate(t, RATE_ONE);
    if (c != NULL) { c->result = (int)r; c->rate = RATE_ONE; }
    if (r != TAPE_OK) { return -1; }
    if (service_to_idle(t) != 0) { return -1; }
    c = begin_call(C_RENDER);
    r = tape_render(t, pcm, FWD_FRAMES, &rendered);
    if (c != NULL) { c->result = (int)r; c->requested = FWD_FRAMES; c->rendered = rendered; }
    if (r != TAPE_OK || rendered != FWD_FRAMES) { return -1; }
    c = begin_call(C_UNMOUNT);
    r = tape_unmount(t, NULL);
    if (c != NULL) { c->result = (int)r; }
    if (r != TAPE_OK) { return -1; }
    return write_pcm(dir, fam->output, pcm, FWD_FRAMES);
}

static int script_seek(struct family *fam, const char *dir)
{
    static int16_t pcm[N_SEEK * 2];
    tape *t = NULL; tape_result r; struct call_rec *c;
    size_t i;
    g_fam = fam;
    if ((r = open_instance(&t)) != TAPE_OK) { fprintf(stderr, "tape_init: %d\n", (int)r); return -1; }
    c = begin_call(C_MOUNT);
    r = tape_mount(t, TAPE_SIDE_A, 0u, NULL);
    if (c != NULL) { c->result = (int)r; }
    if (r != TAPE_OK) { return -1; }
    c = begin_call(C_RATE);
    r = tape_set_rate(t, RATE_ONE);
    if (c != NULL) { c->result = (int)r; c->rate = RATE_ONE; }
    if (r != TAPE_OK) { return -1; }
    for (i = 0; i < N_SEEK; i++) {
        uint32_t rendered = 0;
        c = begin_call(C_SEEK);
        r = tape_seek(t, SEEK_TARGETS[i]);
        if (c != NULL) { c->result = (int)r; c->frame = SEEK_TARGETS[i]; }
        if (r != TAPE_OK) { return -1; }
        if (service_to_idle(t) != 0) { return -1; }
        c = begin_call(C_RENDER);
        r = tape_render(t, &pcm[i * 2u], 1u, &rendered);
        if (c != NULL) { c->result = (int)r; c->requested = 1u; c->rendered = rendered; }
        if (r != TAPE_OK || rendered != 1u) { return -1; }
    }
    c = begin_call(C_UNMOUNT);
    r = tape_unmount(t, NULL);
    if (c != NULL) { c->result = (int)r; }
    if (r != TAPE_OK) { return -1; }
    return write_pcm(dir, fam->output, pcm, N_SEEK);
}

static int script_reverse(struct family *fam, const char *dir)
{
    static int16_t pcm[REV_FRAMES * 2];
    tape *t = NULL; tape_result r; struct call_rec *c;
    uint32_t rendered = 0;
    g_fam = fam;
    if ((r = open_instance(&t)) != TAPE_OK) { fprintf(stderr, "tape_init: %d\n", (int)r); return -1; }
    c = begin_call(C_MOUNT);
    r = tape_mount(t, TAPE_SIDE_A, 0u, NULL);
    if (c != NULL) { c->result = (int)r; }
    if (r != TAPE_OK) { return -1; }
    c = begin_call(C_SEEK);
    r = tape_seek(t, 15u);
    if (c != NULL) { c->result = (int)r; c->frame = 15u; }
    if (r != TAPE_OK) { return -1; }
    c = begin_call(C_RATE);
    r = tape_set_rate(t, RATE_NEG_ONE);
    if (c != NULL) { c->result = (int)r; c->rate = RATE_NEG_ONE; }
    if (r != TAPE_OK) { return -1; }
    if (service_to_idle(t) != 0) { return -1; }
    c = begin_call(C_RENDER);
    r = tape_render(t, pcm, REV_FRAMES, &rendered);
    if (c != NULL) { c->result = (int)r; c->requested = REV_FRAMES; c->rendered = rendered; }
    if (r != TAPE_OK || rendered != REV_FRAMES) { return -1; }
    c = begin_call(C_UNMOUNT);
    r = tape_unmount(t, NULL);
    if (c != NULL) { c->result = (int)r; }
    if (r != TAPE_OK) { return -1; }
    return write_pcm(dir, fam->output, pcm, REV_FRAMES);
}

/* ------------------------------ observation ------------------------------ */

static void emit_calls(FILE *f, const struct family *fam)
{
    size_t i;
    for (i = 0; i < fam->n_calls; i++) {
        const struct call_rec *c = &fam->calls[i];
        if (i) fputs(",\n", f);
        switch (c->kind) {
        case C_MOUNT:
            fprintf(f, "        {\"call\": \"tape_mount\", \"side\": \"A\", \"resume_frame\": 0,"
                       " \"warm\": null, \"result\": %d}", c->result); break;
        case C_RATE:
            fprintf(f, "        {\"call\": \"tape_set_rate\", \"rate_q16_16\": %ld, \"result\": %d}",
                    (long)c->rate, c->result); break;
        case C_SERVICE:
            fprintf(f, "        {\"call\": \"tape_service\", \"block_budget\": %lu,"
                       " \"more_work\": %s, \"result\": %d}",
                    (unsigned long)c->budget, c->more_work ? "true" : "false", c->result); break;
        case C_RENDER:
            fprintf(f, "        {\"call\": \"tape_render\", \"requested\": %lu,"
                       " \"rendered\": %lu, \"result\": %d}",
                    (unsigned long)c->requested, (unsigned long)c->rendered, c->result); break;
        case C_SEEK:
            fprintf(f, "        {\"call\": \"tape_seek\", \"frame\": %llu, \"result\": %d}",
                    (unsigned long long)c->frame, c->result); break;
        case C_UNMOUNT:
            fprintf(f, "        {\"call\": \"tape_unmount\", \"result\": %d}", c->result); break;
        }
    }
}

static int emit_observation(const char *dir, struct family *fams, size_t n)
{
    char path[4096];
    FILE *f;
    size_t k, i;
    if ((size_t)snprintf(path, sizeof path, "%s/observation.json", dir) >= sizeof path) return -1;
    f = fopen(path, "wb");
    if (f == NULL) { fprintf(stderr, "cannot write %s\n", path); return -1; }
    fprintf(f, "{\n  \"schema\": \"%s\",\n  \"fixture_sha256\": \"%s\",\n", OBS_SCHEMA, g_fixture_sha);
    fprintf(f, "  \"adapter\": {\"kind\": \"%s\", \"id\": \"%s\"},\n", ADAPTER_KIND, ADAPTER_ID);
    fputs("  \"cases\": {\n", f);
    for (k = 0; k < n; k++) {
        fprintf(f, "    \"%s\": {\n      \"output\": \"%s\",\n      \"calls\": [\n",
                fams[k].name, fams[k].output);
        emit_calls(f, &fams[k]);
        fputs("\n      ],\n      \"callbacks\": [\n", f);
        for (i = 0; i < fams[k].n_cbs; i++) {
            const struct cb_rec *e = &fams[k].cbs[i];
            fprintf(f, "%s        {\"call_index\": %d, \"op\": \"read\", \"lba\": %lu,"
                       " \"count\": %lu, \"rc\": %d}",
                    i ? ",\n" : "", e->call_index, (unsigned long)e->lba,
                    (unsigned long)e->count, e->rc);
        }
        fprintf(f, "\n      ]\n    }%s\n", k + 1u < n ? "," : "");
    }
    fputs("  }\n}\n", f);
    if (fclose(f) != 0) return -1;
    return 0;
}

int main(int argc, char **argv)
{
    const char *fixture = NULL, *out_dir = NULL;
    static struct family fams[3];
    int i, failed = 0;

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--fixture") == 0 && i + 1 < argc)      fixture = argv[++i];
        else if (strcmp(argv[i], "--out-dir") == 0 && i + 1 < argc) out_dir = argv[++i];
        else { fprintf(stderr, "usage: %s --fixture RAW.vo08 --out-dir DIR\n", argv[0]); return 2; }
    }
    if (fixture == NULL || out_dir == NULL) {
        fprintf(stderr, "usage: %s --fixture RAW.vo08 --out-dir DIR\n", argv[0]); return 2;
    }
    if (load_fixture(fixture) != 0) return 2;

    fams[0].name = "forward_1x";      fams[0].output = "forward-1x.pcm";
    fams[1].name = "seek_boundaries"; fams[1].output = "seek-boundaries.pcm";
    fams[2].name = "reverse_neg1x";   fams[2].output = "reverse-neg1x.pcm";

    if (script_forward(&fams[0], out_dir) != 0) failed = 1;
    if (script_seek(&fams[1], out_dir)    != 0) failed = 1;
    if (script_reverse(&fams[2], out_dir) != 0) failed = 1;

    if (emit_observation(out_dir, fams, 3) != 0) failed = 1;
    for (i = 0; i < 3; i++)
        if (fams[i].overflow) { fprintf(stderr, "trace overflow in %s\n", fams[i].name); failed = 1; }
    return failed ? 1 : 0;
}
