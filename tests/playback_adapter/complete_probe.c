/*
 * complete_probe.c — mechanical adapter for the P1-R6 complete playback tranche.
 *
 * Contract: tests/playback_complete_draft8/ADAPTER.md (Verification-owned,
 * imported verbatim). Plumbing from the frozen public API to that package. No
 * engine behaviour, no engine internals, no invented API: the only engine
 * symbols referenced are public functions declared in the real product tape.h.
 *
 *   complete_probe --fixture-dir DIR --out-dir DIR
 *
 * DIR holds the package's fixture.json plus RAW .vo08 images. The package ships
 * them gzipped; decompression is done by the wrapper next to this file, and this
 * probe re-verifies every raw image against fixture.json's own raw_sha256 before
 * using it. That is deliberate: it means the wrapper cannot substitute fixture
 * bytes, so the only trusted producer of observations is this binary.
 *
 * Ten families, seven PCM outputs, schema
 * playback-complete-draft8-observation-v1.
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
#define ADAPTER_ID   "software-lead-complete-playback-public-api-probe-v1"
#define OBS_SCHEMA   "playback-complete-draft8-observation-v1"

#define VO_BLOCK 512u
#define MAX_ROWS 64u

/*
 * The caller owns all storage (§4), and TAPE_PLAY_RING_MIN is a MINIMUM. The
 * scrub rows render up to 22,050 frames after a single service sequence, and at
 * 12.0x that spans 264,600 timeline frames -- far past 372 ms of ring. A desktop
 * harness is free to hand the engine a larger ring, and does: 8 MiB covers the
 * widest row with room to spare. Firmware's smaller ring simply services more
 * often, which is the documented interleaving case and yields identical bytes.
 */
#define PLAY_RING_BYTES (8u * 1024u * 1024u)

/* --- SHA-256 (harness-local; not engine code) ---------------------------- */

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
    uint32_t w[64], a,b,cc,d,e,f,g,h,t1,t2; unsigned i;
    for (i = 0; i < 16u; i++)
        w[i] = ((uint32_t)p[4*i]<<24)|((uint32_t)p[4*i+1]<<16)|((uint32_t)p[4*i+2]<<8)|(uint32_t)p[4*i+3];
    for (i = 16u; i < 64u; i++) {
        uint32_t s0 = ror(w[i-15],7)^ror(w[i-15],18)^(w[i-15]>>3);
        uint32_t s1 = ror(w[i-2],17)^ror(w[i-2],19)^(w[i-2]>>10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    a=c->h[0];b=c->h[1];cc=c->h[2];d=c->h[3];e=c->h[4];f=c->h[5];g=c->h[6];h=c->h[7];
    for (i = 0; i < 64u; i++) {
        t1 = h + (ror(e,6)^ror(e,11)^ror(e,25)) + ((e&f)^(~e&g)) + K[i] + w[i];
        t2 = (ror(a,2)^ror(a,13)^ror(a,22)) + ((a&b)^(a&cc)^(b&cc));
        h=g;g=f;f=e;e=d+t1;d=cc;cc=b;b=a;a=t1+t2;
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
        size_t take = 64u - c->n; if (take > n) { take = n; }
        memcpy(c->buf + c->n, p, take); c->n += take; p += take; n -= take;
        if (c->n == 64u) { sha256_block(c, c->buf); c->n = 0; }
    }
}

static void sha256_hex(struct sha256 *c, char out[65])
{
    uint64_t bits = c->len * 8u; unsigned char pad = 0x80, zero = 0, be[8]; unsigned i;
    sha256_update(c, &pad, 1);
    while (c->n != 56u) { sha256_update(c, &zero, 1); }
    for (i = 0; i < 8u; i++) { be[i] = (unsigned char)(bits >> (56u - 8u*i)); }
    sha256_update(c, be, 8);
    for (i = 0; i < 8u; i++) { sprintf(out + 8u*i, "%08lx", (unsigned long)c->h[i]); }
    out[64] = '\0';
}

/* --- fixture.json: a targeted scanner, so the package file stays the source -- */

static char *slurp(const char *path, size_t *len)
{
    long n; char *buf; FILE *f = fopen(path, "rb");
    if (f == NULL) { return NULL; }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    n = ftell(f);
    if (n < 0 || fseek(f, 0, SEEK_SET) != 0) { fclose(f); return NULL; }
    buf = malloc((size_t)n + 1u);
    if (buf == NULL) { fclose(f); return NULL; }
    if (fread(buf, 1u, (size_t)n, f) != (size_t)n) { fclose(f); free(buf); return NULL; }
    fclose(f); buf[n] = '\0'; if (len != NULL) { *len = (size_t)n; }
    return buf;
}

/* Read the integers of the JSON array named `key` into out[]. Returns count. */
static uint32_t json_int_array(const char *json, const char *key, long *out, uint32_t max)
{
    const char *p = strstr(json, key);
    uint32_t n = 0;
    if (p == NULL) { return 0; }
    p = strchr(p, '[');
    if (p == NULL) { return 0; }
    p++;
    while (*p != '\0' && *p != ']' && n < max) {
        char *end = NULL;
        while (*p == ' ' || *p == '\n' || *p == '\r' || *p == '\t' || *p == ',') { p++; }
        if (*p == ']' || *p == '\0') { break; }
        out[n++] = strtol(p, &end, 10);
        if (end == NULL || end == p) { break; }   /* no digits consumed: stop */
        p = end;
    }
    return n;
}

/* Read the 64-hex string value of "name" inside the raw_sha256 object. */
static bool json_raw_sha(const char *json, const char *name, char out[65])
{
    const char *p = strstr(json, "raw_sha256");
    const char *q;
    if (p == NULL) { return false; }
    q = strstr(p, name);
    if (q == NULL) { return false; }
    q = strchr(q, ':');
    if (q == NULL) { return false; }
    q = strchr(q, '"');
    if (q == NULL) { return false; }
    q++;
    if (strlen(q) < 64u) { return false; }
    memcpy(out, q, 64u); out[64] = '\0';
    return true;
}

/* --- harness-owned media ------------------------------------------------- */

static unsigned char *g_payload;
static uint32_t g_blocks;
static uint32_t DEV_READS;

/* --- observation trace --------------------------------------------------- */

enum ck { K_MOUNT, K_RATE, K_SERVICE, K_RENDER, K_SEEK, K_TELL, K_STATUS, K_INFO,
          K_SETSIDE, K_UNMOUNT };

struct call_rec {
    enum ck kind; int result;
    int32_t rate; uint32_t budget; bool more_work;
    uint32_t requested, rendered; uint64_t frame;
    bool at_end, at_start; uint64_t total_frames; bool warm_used;
    const char *side;
};

struct cb_rec { int call_index; uint32_t lba, count; int rc; };

#define MAX_CALLS  8192
#define MAX_CBS    262144

struct family {
    const char *name;        /* family id in the observation */
    const char *fixture;     /* "long" | "one" | "empty" */
    const char *output;      /* PCM file name, or NULL when the family emits none */
    struct call_rec calls[MAX_CALLS]; size_t n_calls;
    struct cb_rec cbs[MAX_CBS];       size_t n_cbs;
    bool overflow;
};

static struct family *g_fam;
static int g_call_index = -1;

static struct call_rec *begin(enum ck k)
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

/* Every callback, unfiltered, with its real rc -- including out-of-range. */
static void record(uint32_t lba, uint32_t count, int rc)
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
    if (count == 0u || (uint64_t)lba + count > (uint64_t)g_blocks) { record(lba, count, -1); return -1; }
    memcpy(dst, g_payload + (size_t)lba * VO_BLOCK, (size_t)count * VO_BLOCK);
    DEV_READS++;
    record(lba, count, 0);
    return 0;
}

/* Playback is read-only. If the engine asks, that is evidence: record and refuse. */
static int dev_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    (void)ctx; (void)src;
    fprintf(stderr, "PROTOCOL: write during playback (lba=%lu count=%lu)\n",
            (unsigned long)lba, (unsigned long)count);
    record(lba, count, -1);
    return -1;
}

static int dev_flush(void *ctx)
{
    (void)ctx;
    fprintf(stderr, "PROTOCOL: flush during playback\n");
    record(0, 0, -1);
    return -1;
}

/* --- caller-owned storage ------------------------------------------------ */

static unsigned char g_inst[262144];
static unsigned char *g_play;                      /* PLAY_RING_BYTES, malloc'd */
static unsigned char g_rec[TAPE_REC_RING_MIN];
static tape_dev g_dev;

static tape_result open_instance(tape **out)
{
    size_t need = tape_instance_size();
    if (need > sizeof g_inst) {
        fprintf(stderr, "instance needs %zu bytes, reserved %zu\n", need, sizeof g_inst);
        return TAPE_ERR_INVALID_ARG;
    }
    g_dev.read = dev_read; g_dev.write = dev_write; g_dev.flush = dev_flush;
    g_dev.ctx = NULL; g_dev.block_count = g_blocks;
    return tape_init(g_inst, need, &g_dev, g_play, PLAY_RING_BYTES, g_rec, sizeof g_rec, out);
}

/* --- fixture loading ----------------------------------------------------- */

static char g_json_path[4096];
static char *g_json;

static int load_fixture(const char *dir, const char *kind)
{
    char path[4096], want[65], got[65];
    struct sha256 sh;
    unsigned char hdr[8];
    long size;
    FILE *f;

    if ((size_t)snprintf(path, sizeof path, "%s/%s.vo08", dir, kind) >= sizeof path) { return -1; }
    f = fopen(path, "rb");
    if (f == NULL) { fprintf(stderr, "cannot open raw fixture %s\n", path); return -1; }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return -1; }
    size = ftell(f);
    if (size < 8 || fseek(f, 0, SEEK_SET) != 0) { fclose(f); return -1; }
    if (fread(hdr, 1u, 8u, f) != 8u) { fclose(f); return -1; }
    if (memcmp(hdr, "VO08", 4) != 0) { fprintf(stderr, "bad VO08 magic in %s\n", path); fclose(f); return -1; }
    g_blocks = (uint32_t)hdr[4] | ((uint32_t)hdr[5]<<8) | ((uint32_t)hdr[6]<<16) | ((uint32_t)hdr[7]<<24);
    if ((uint64_t)size != 8u + (uint64_t)g_blocks * VO_BLOCK) {
        fprintf(stderr, "VO08 size/block_count mismatch in %s\n", path); fclose(f); return -1;
    }
    free(g_payload);
    g_payload = malloc((size_t)g_blocks * VO_BLOCK);
    if (g_payload == NULL) { fclose(f); return -1; }
    if (fread(g_payload, 1u, (size_t)g_blocks * VO_BLOCK, f) != (size_t)g_blocks * VO_BLOCK) {
        fclose(f); return -1;
    }
    fclose(f);

    /* Re-verify against the package's own declared raw hash. The wrapper that
       gunzipped this cannot substitute bytes without being caught here. */
    sha256_init(&sh);
    sha256_update(&sh, hdr, 8u);
    sha256_update(&sh, g_payload, (size_t)g_blocks * VO_BLOCK);
    sha256_hex(&sh, got);
    if (!json_raw_sha(g_json, kind, want)) {
        fprintf(stderr, "fixture.json has no raw_sha256 for %s\n", kind); return -1;
    }
    if (strcmp(got, want) != 0) {
        fprintf(stderr, "raw fixture %s hash mismatch: got %s want %s\n", kind, got, want);
        return -1;
    }
    return 0;
}

/* --- scripts ------------------------------------------------------------- */

static int16_t *g_pcm;            /* output accumulator for the active family */
static size_t   g_pcm_frames;

static int pcm_reset(size_t cap)
{
    free(g_pcm);
    g_pcm = malloc(cap * 2u * sizeof(int16_t));
    g_pcm_frames = 0;
    return (g_pcm == NULL) ? -1 : 0;
}

static int service_to_idle(tape *t)
{
    bool more = true;
    uint32_t iter = 0u;
    while (more) {
        struct call_rec *c;
        tape_result r;
        if (iter >= 100000u) { fprintf(stderr, "service guard tripped\n"); return -1; }
        c = begin(K_SERVICE);
        r = tape_service(t, 1024u, &more);
        iter++;
        if (c != NULL) { c->result = (int)r; c->budget = 1024u; c->more_work = more; }
        if (r != TAPE_OK) { return -1; }
    }
    return 0;
}

/* Render `n` frames, appending to the PCM accumulator. Records the real result. */
static tape_result do_render(tape *t, uint32_t n)
{
    struct call_rec *c = begin(K_RENDER);
    uint32_t done = 0u;
    tape_result r = tape_render(t, g_pcm + g_pcm_frames * 2u, n, &done);
    if (c != NULL) { c->result = (int)r; c->requested = n; c->rendered = done; }
    g_pcm_frames += done;
    return r;
}

static tape_result do_tell(tape *t)
{
    struct call_rec *c = begin(K_TELL);
    uint64_t f = 0u;
    tape_result r = tape_tell(t, &f);
    if (c != NULL) { c->result = (int)r; c->frame = f; }
    return r;
}

static tape_result do_status(tape *t)
{
    struct call_rec *c = begin(K_STATUS);
    tape_status_t st;
    tape_result r;
    memset(&st, 0, sizeof st);
    r = tape_status(t, &st);
    if (c != NULL) { c->result = (int)r; c->at_end = st.at_end; c->at_start = st.at_start; }
    return r;
}

static tape_result do_info(tape *t)
{
    struct call_rec *c = begin(K_INFO);
    tape_info info;
    tape_result r;
    memset(&info, 0, sizeof info);
    r = tape_get_info(t, &info);
    if (c != NULL) { c->result = (int)r; c->total_frames = info.total_frames;
                     c->warm_used = info.warm_start_used; }
    return r;
}

static tape_result do_rate(tape *t, int32_t rate)
{
    struct call_rec *c = begin(K_RATE);
    tape_result r = tape_set_rate(t, rate);
    if (c != NULL) { c->result = (int)r; c->rate = rate; }
    return r;
}

static tape_result do_seek(tape *t, uint64_t frame)
{
    struct call_rec *c = begin(K_SEEK);
    tape_result r = tape_seek(t, frame);
    if (c != NULL) { c->result = (int)r; c->frame = frame; }
    return r;
}

static tape_result do_mount(tape *t)
{
    struct call_rec *c = begin(K_MOUNT);
    tape_result r = tape_mount(t, TAPE_SIDE_A, 0u, NULL);
    if (c != NULL) { c->result = (int)r; c->side = "A"; }
    return r;
}

static tape_result do_unmount(tape *t)
{
    struct call_rec *c = begin(K_UNMOUNT);
    tape_result r = tape_unmount(t, NULL);
    if (c != NULL) { c->result = (int)r; }
    return r;
}

/* tape_set_side records the rate it RETAINS, which is what the oracle checks. */
static tape_result do_set_side(tape *t, tape_side side, int32_t retained)
{
    struct call_rec *c = begin(K_SETSIDE);
    tape_result r = tape_set_side(t, side);
    if (c != NULL) { c->result = (int)r; c->side = (side == TAPE_SIDE_B) ? "B" : "A";
                     c->rate = retained; }
    return r;
}

/* empty_zero / empty_nonzero / nonempty_zero */
static int script_basic(struct family *fam, const char *dir, int32_t rate, bool seek1234)
{
    tape *t = NULL;
    g_fam = fam;
    if (load_fixture(dir, fam->fixture) != 0) { return -1; }
    if (pcm_reset(16u) != 0) { return -1; }
    if (open_instance(&t) != TAPE_OK) { return -1; }
    if (do_mount(t) != TAPE_OK) { return -1; }
    if (seek1234 && do_seek(t, 1234u) != TAPE_OK) { return -1; }
    if (do_rate(t, rate) != TAPE_OK) { return -1; }
    (void)do_render(t, 4u);                  /* expected: 0 frames, TAPE_OK */
    if (do_tell(t) != TAPE_OK)   { return -1; }
    if (do_status(t) != TAPE_OK) { return -1; }
    if (do_unmount(t) != TAPE_OK) { return -1; }
    return 0;
}

/* one_intmax / reverse_zero / intmin */
static int script_boundary(struct family *fam, const char *dir, int32_t rate, bool seek, uint64_t at)
{
    tape *t = NULL;
    g_fam = fam;
    if (load_fixture(dir, fam->fixture) != 0) { return -1; }
    if (pcm_reset(16u) != 0) { return -1; }
    if (open_instance(&t) != TAPE_OK) { return -1; }
    if (do_mount(t) != TAPE_OK) { return -1; }
    if (seek && do_seek(t, at) != TAPE_OK) { return -1; }
    if (do_rate(t, rate) != TAPE_OK) { return -1; }
    if (service_to_idle(t) != 0) { return -1; }
    (void)do_render(t, 2u);                  /* expected: exactly 1 frame */
    if (do_tell(t) != TAPE_OK)   { return -1; }
    if (do_status(t) != TAPE_OK) { return -1; }
    if (do_unmount(t) != TAPE_OK) { return -1; }
    return 0;
}

/* scrub_forward / scrub_reverse over every authenticated WP-08 row */
static int script_scrub(struct family *fam, const char *dir, bool reverse,
                        const long *rates, const long *counts, uint32_t rows,
                        uint64_t long_n, size_t total_frames)
{
    tape *t = NULL;
    uint32_t k;
    g_fam = fam;
    if (load_fixture(dir, fam->fixture) != 0) { return -1; }
    if (pcm_reset(total_frames + 16u) != 0) { return -1; }
    if (open_instance(&t) != TAPE_OK) { return -1; }
    if (do_mount(t) != TAPE_OK) { return -1; }
    if (reverse && do_seek(t, long_n) != TAPE_OK) { return -1; }
    for (k = 0; k < rows; k++) {
        long remaining = counts[k];
        int32_t rate = (int32_t)(reverse ? -rates[k] : rates[k]);
        if (do_rate(t, rate) != TAPE_OK) { return -1; }
        if (service_to_idle(t) != 0) { return -1; }
        while (remaining > 0) {
            uint32_t n = (remaining > 128) ? 128u : (uint32_t)remaining;
            if (do_render(t, n) != TAPE_OK) { return -1; }
            remaining -= (long)n;
        }
    }
    if (do_unmount(t) != TAPE_OK) { return -1; }
    return 0;
}

/* side_playing / side_idle */
static int script_side(struct family *fam, const char *dir, bool playing, uint64_t long_n)
{
    tape *t = NULL;
    g_fam = fam;
    if (load_fixture(dir, fam->fixture) != 0) { return -1; }
    if (pcm_reset(16u) != 0) { return -1; }
    if (open_instance(&t) != TAPE_OK) { return -1; }
    if (do_mount(t) != TAPE_OK) { return -1; }
    if (playing) {
        if (do_seek(t, long_n - 1u) != TAPE_OK) { return -1; }
        if (do_rate(t, 65536) != TAPE_OK) { return -1; }
        if (service_to_idle(t) != 0) { return -1; }
        (void)do_render(t, 2u);
        if (do_status(t) != TAPE_OK) { return -1; }
    } else {
        if (do_rate(t, 0) != TAPE_OK) { return -1; }
    }
    if (do_set_side(t, TAPE_SIDE_B, playing ? 65536 : 0) != TAPE_OK) { return -1; }
    if (do_tell(t) != TAPE_OK)   { return -1; }
    if (do_status(t) != TAPE_OK) { return -1; }
    if (do_info(t) != TAPE_OK)   { return -1; }
    if (!playing && do_rate(t, 65536) != TAPE_OK) { return -1; }
    /* The pre-service render must retain UNDERRUN and zero frames: the ring was
       invalidated by the switch and no Side-B frame has been loaded yet. */
    (void)do_render(t, 1u);
    if (service_to_idle(t) != 0) { return -1; }
    if (do_render(t, 1u) != TAPE_OK) { return -1; }
    if (do_unmount(t) != TAPE_OK) { return -1; }
    return 0;
}

/* --- emission ------------------------------------------------------------ */

static int write_pcm(const char *dir, const char *name)
{
    char path[4096]; FILE *f; size_t i;
    if (name == NULL) { return 0; }
    if ((size_t)snprintf(path, sizeof path, "%s/%s", dir, name) >= sizeof path) { return -1; }
    f = fopen(path, "wb");
    if (f == NULL) { fprintf(stderr, "cannot write %s\n", path); return -1; }
    for (i = 0; i < g_pcm_frames * 2u; i++) {
        unsigned char le[2];
        le[0] = (unsigned char)((uint16_t)g_pcm[i] & 0xFFu);
        le[1] = (unsigned char)(((uint16_t)g_pcm[i] >> 8) & 0xFFu);
        if (fwrite(le, 1u, 2u, f) != 2u) { fclose(f); return -1; }
    }
    if (fclose(f) != 0) { return -1; }
    return 0;
}

static void emit_calls(FILE *f, const struct family *fam)
{
    size_t i;
    for (i = 0; i < fam->n_calls; i++) {
        const struct call_rec *c = &fam->calls[i];
        if (i != 0) { fputs(",\n", f); }
        switch (c->kind) {
        case K_MOUNT:
            fprintf(f, "        {\"call\": \"tape_mount\", \"result\": %d, \"side\": \"A\","
                       " \"resume_frame\": 0, \"warm\": null}", c->result); break;
        case K_RATE:
            fprintf(f, "        {\"call\": \"tape_set_rate\", \"result\": %d, \"rate_q16_16\": %ld}",
                    c->result, (long)c->rate); break;
        case K_SERVICE:
            fprintf(f, "        {\"call\": \"tape_service\", \"result\": %d, \"block_budget\": %lu,"
                       " \"more_work\": %s}", c->result, (unsigned long)c->budget,
                    c->more_work ? "true" : "false"); break;
        case K_RENDER:
            fprintf(f, "        {\"call\": \"tape_render\", \"result\": %d, \"requested\": %lu,"
                       " \"rendered\": %lu}", c->result, (unsigned long)c->requested,
                    (unsigned long)c->rendered); break;
        case K_SEEK:
            fprintf(f, "        {\"call\": \"tape_seek\", \"result\": %d, \"frame\": %llu}",
                    c->result, (unsigned long long)c->frame); break;
        case K_TELL:
            fprintf(f, "        {\"call\": \"tape_tell\", \"result\": %d, \"frame\": %llu}",
                    c->result, (unsigned long long)c->frame); break;
        case K_STATUS:
            fprintf(f, "        {\"call\": \"tape_status\", \"result\": %d, \"at_end\": %s,"
                       " \"at_start\": %s}", c->result, c->at_end ? "true" : "false",
                    c->at_start ? "true" : "false"); break;
        case K_INFO:
            fprintf(f, "        {\"call\": \"tape_get_info\", \"result\": %d, \"total_frames\": %llu,"
                       " \"warm_start_used\": %s}", c->result,
                    (unsigned long long)c->total_frames, c->warm_used ? "true" : "false"); break;
        case K_SETSIDE:
            fprintf(f, "        {\"call\": \"tape_set_side\", \"result\": %d, \"side\": \"%s\","
                       " \"rate_q16_16\": %ld}", c->result, c->side, (long)c->rate); break;
        case K_UNMOUNT:
            fprintf(f, "        {\"call\": \"tape_unmount\", \"result\": %d}", c->result); break;
        }
    }
}

static int emit_observation(const char *dir, struct family *fams, size_t n, const char *wp08)
{
    char path[4096]; FILE *f; size_t k, i;
    if ((size_t)snprintf(path, sizeof path, "%s/observation.json", dir) >= sizeof path) { return -1; }
    f = fopen(path, "wb");
    if (f == NULL) { return -1; }
    fprintf(f, "{\n  \"schema\": \"%s\",\n  \"wp08_sha256\": \"%s\",\n", OBS_SCHEMA, wp08);
    fprintf(f, "  \"adapter\": {\"kind\": \"%s\", \"id\": \"%s\"},\n", ADAPTER_KIND, ADAPTER_ID);
    fputs("  \"cases\": {\n", f);
    for (k = 0; k < n; k++) {
        fprintf(f, "    \"%s\": {\n      \"fixture\": \"%s\",\n      \"calls\": [\n",
                fams[k].name, fams[k].fixture);
        emit_calls(f, &fams[k]);
        fputs("\n      ],\n      \"callbacks\": [\n", f);
        for (i = 0; i < fams[k].n_cbs; i++) {
            const struct cb_rec *e = &fams[k].cbs[i];
            fprintf(f, "%s        {\"call_index\": %d, \"op\": \"read\", \"lba\": %lu,"
                       " \"count\": %lu, \"rc\": %d}", i ? ",\n" : "", e->call_index,
                    (unsigned long)e->lba, (unsigned long)e->count, e->rc);
        }
        fprintf(f, "\n      ]\n    }%s\n", k + 1u < n ? "," : "");
    }
    fputs("  }\n}\n", f);
    if (fclose(f) != 0) { return -1; }
    return 0;
}

/* --- main ---------------------------------------------------------------- */

static struct family FAMS[10];

int main(int argc, char **argv)
{
    const char *fdir = NULL, *odir = NULL;
    long rates[MAX_ROWS], counts[MAX_ROWS];
    uint32_t rows, nrows2;
    uint64_t long_n = 0;
    size_t scrub_total = 0;
    char wp08[65] = {0};
    int i, failed = 0;
    uint32_t k;

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--fixture-dir") == 0 && i + 1 < argc)   { fdir = argv[++i]; }
        else if (strcmp(argv[i], "--out-dir") == 0 && i + 1 < argc)  { odir = argv[++i]; }
        else { fprintf(stderr, "usage: %s --fixture-dir DIR --out-dir DIR\n", argv[0]); return 2; }
    }
    if (fdir == NULL || odir == NULL) {
        fprintf(stderr, "usage: %s --fixture-dir DIR --out-dir DIR\n", argv[0]); return 2;
    }
    if ((size_t)snprintf(g_json_path, sizeof g_json_path, "%s/fixture.json", fdir) >= sizeof g_json_path) {
        return 2;
    }
    g_json = slurp(g_json_path, NULL);
    if (g_json == NULL) { fprintf(stderr, "cannot read %s\n", g_json_path); return 2; }

    rows   = json_int_array(g_json, "rates_q16_16", rates, MAX_ROWS);
    nrows2 = json_int_array(g_json, "row_render_frames", counts, MAX_ROWS);
    if (rows == 0u || rows != nrows2) {
        fprintf(stderr, "fixture.json rate/row arrays disagree (%lu vs %lu)\n",
                (unsigned long)rows, (unsigned long)nrows2);
        return 2;
    }
    { long v[1];
      if (json_int_array(g_json, "long_side_a_frames", v, 1u) == 1u) { long_n = (uint64_t)v[0]; } }
    if (long_n == 0u) { fprintf(stderr, "fixture.json long_side_a_frames missing\n"); return 2; }
    for (k = 0; k < rows; k++) { scrub_total += (size_t)counts[k]; }

    /*
     * The observation binds the WP-08 identity. It is COMPUTED from the
     * package's own input/WP-08.md rather than hard-coded here: the runner
     * passes <package>/fixtures as --fixture-dir, so the table sits next door.
     * Hashing it means a changed table is caught by the oracle instead of being
     * papered over by a constant baked into my adapter.
     */
    {
        char wpath[4096]; size_t wlen = 0; char *wdata;
        struct sha256 wsh;
        if ((size_t)snprintf(wpath, sizeof wpath, "%s/../input/WP-08.md", fdir) >= sizeof wpath) {
            return 2;
        }
        wdata = slurp(wpath, &wlen);
        if (wdata == NULL) { fprintf(stderr, "cannot read %s\n", wpath); return 2; }
        sha256_init(&wsh);
        sha256_update(&wsh, (const unsigned char *)wdata, wlen);
        sha256_hex(&wsh, wp08);
        free(wdata);
    }

    g_play = malloc(PLAY_RING_BYTES);
    if (g_play == NULL) { fprintf(stderr, "cannot allocate play ring\n"); return 2; }

    FAMS[0].name="empty_zero";     FAMS[0].fixture="empty"; FAMS[0].output=NULL;
    FAMS[1].name="empty_nonzero";  FAMS[1].fixture="empty"; FAMS[1].output=NULL;
    FAMS[2].name="nonempty_zero";  FAMS[2].fixture="long";  FAMS[2].output=NULL;
    FAMS[3].name="one_intmax";     FAMS[3].fixture="one";   FAMS[3].output="one-intmax.pcm";
    FAMS[4].name="reverse_zero";   FAMS[4].fixture="long";  FAMS[4].output="reverse-zero.pcm";
    FAMS[5].name="intmin";         FAMS[5].fixture="long";  FAMS[5].output="intmin.pcm";
    FAMS[6].name="scrub_forward";  FAMS[6].fixture="long";  FAMS[6].output="scrub-forward.pcm";
    FAMS[7].name="scrub_reverse";  FAMS[7].fixture="long";  FAMS[7].output="scrub-reverse.pcm";
    FAMS[8].name="side_playing";   FAMS[8].fixture="long";  FAMS[8].output="side-playing.pcm";
    FAMS[9].name="side_idle";      FAMS[9].fixture="long";  FAMS[9].output="side-idle.pcm";

    if (script_basic(&FAMS[0], fdir, 0, false) != 0)              { failed = 1; }
    if (write_pcm(odir, FAMS[0].output) != 0)                     { failed = 1; }
    if (script_basic(&FAMS[1], fdir, 65536, false) != 0)          { failed = 1; }
    if (write_pcm(odir, FAMS[1].output) != 0)                     { failed = 1; }
    if (script_basic(&FAMS[2], fdir, 0, true) != 0)               { failed = 1; }
    if (write_pcm(odir, FAMS[2].output) != 0)                     { failed = 1; }
    if (script_boundary(&FAMS[3], fdir, 2147483647, false, 0) != 0) { failed = 1; }
    if (write_pcm(odir, FAMS[3].output) != 0)                     { failed = 1; }
    if (script_boundary(&FAMS[4], fdir, -65536, false, 0) != 0)   { failed = 1; }
    if (write_pcm(odir, FAMS[4].output) != 0)                     { failed = 1; }
    if (script_boundary(&FAMS[5], fdir, -2147483647 - 1, true, 1u) != 0) { failed = 1; }
    if (write_pcm(odir, FAMS[5].output) != 0)                     { failed = 1; }
    if (script_scrub(&FAMS[6], fdir, false, rates, counts, rows, long_n, scrub_total) != 0) { failed = 1; }
    if (write_pcm(odir, FAMS[6].output) != 0)                     { failed = 1; }
    if (script_scrub(&FAMS[7], fdir, true, rates, counts, rows, long_n, scrub_total) != 0) { failed = 1; }
    if (write_pcm(odir, FAMS[7].output) != 0)                     { failed = 1; }
    if (script_side(&FAMS[8], fdir, true, long_n) != 0)           { failed = 1; }
    if (write_pcm(odir, FAMS[8].output) != 0)                     { failed = 1; }
    if (script_side(&FAMS[9], fdir, false, long_n) != 0)          { failed = 1; }
    if (write_pcm(odir, FAMS[9].output) != 0)                     { failed = 1; }

    if (emit_observation(odir, FAMS, 10u, wp08) != 0) { failed = 1; }
    for (k = 0; k < 10u; k++) {
        if (FAMS[k].overflow) { fprintf(stderr, "trace overflow in %s\n", FAMS[k].name); failed = 1; }
    }
    return failed ? 1 : 0;
}
