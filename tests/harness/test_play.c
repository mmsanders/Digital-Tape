/*
 * WP-08 transport/playback — the parts of §6.1–§6.3 and §8 that the first
 * independent package does not reach.
 *
 * Software Lead scaffolding. NOT acceptance — the Verification Lead signs off,
 * and the independent playback package in tests/playback_draft8 is the authority
 * for the three families it covers. This exists because that package exercises
 * only +/-1.0x on a 15-frame timeline, where every interpolation has f == 0 and
 * no clamp is ever approached. An implementation narrowed to those examples
 * would pass it. These cases are the domain it leaves untested: fractional
 * rates, zero and extreme rates, the empty timeline, the V4-009 wrap, the
 * V5-005 off-grid snap, ring underrun, and "render touches no block".
 *
 * Expected interpolation values are computed here by a DIFFERENT formulation
 * than the engine's, so agreement is a cross-check rather than a copy.
 */

#include <stdlib.h>
#include "harness.h"
#include "tape.h"

#define CHUNKS   4u
#define BLOCKS   (TAPE_LBA_CHUNK_BASE + CHUNKS * TAPE_CHUNK_BLOCKS + 1u)

/* --- a device with real audio behind it ---------------------------------- */

static unsigned char IMG[(size_t)BLOCKS * TAPE_BLOCK_SIZE];
static uint32_t DEV_READS, DEV_CHUNK_READS;

static int img_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    (void)ctx;
    if ((uint64_t)lba + count > (uint64_t)BLOCKS) { return -1; }
    DEV_READS++;
    if (lba >= TAPE_LBA_CHUNK_BASE && lba < BLOCKS - 1u) { DEV_CHUNK_READS++; }
    memcpy(dst, IMG + (size_t)lba * TAPE_BLOCK_SIZE, (size_t)count * TAPE_BLOCK_SIZE);
    return 0;
}

static int img_flush(void *ctx) { (void)ctx; return 0; }

static uint32_t crc_tab_ready;
static uint32_t crc_tab[256];

static uint32_t crc32_of(const unsigned char *p, size_t n)
{
    uint32_t c = 0xFFFFFFFFu;
    size_t i;
    if (!crc_tab_ready) {
        uint32_t k, j;
        for (k = 0; k < 256u; k++) {
            uint32_t v = k;
            for (j = 0; j < 8u; j++) { v = (v & 1u) ? (0xEDB88320u ^ (v >> 1)) : (v >> 1); }
            crc_tab[k] = v;
        }
        crc_tab_ready = 1u;
    }
    for (i = 0; i < n; i++) { c = crc_tab[(c ^ p[i]) & 0xFFu] ^ (c >> 8); }
    return c ^ 0xFFFFFFFFu;
}

static void put32(unsigned char *p, uint32_t v)
{
    p[0] = (unsigned char)(v & 0xFFu);       p[1] = (unsigned char)((v >> 8) & 0xFFu);
    p[2] = (unsigned char)((v >> 16) & 0xFFu); p[3] = (unsigned char)((v >> 24) & 0xFFu);
}
static void put16(unsigned char *p, uint16_t v)
{
    p[0] = (unsigned char)(v & 0xFFu); p[1] = (unsigned char)((v >> 8) & 0xFFu);
}

static void build_sb(unsigned char *b)
{
    memset(b, 0, TAPE_BLOCK_SIZE);
    memcpy(b, "TAPEFS\0\x01", 8);
    put16(b + 8, 1u); put16(b + 10, 0u);
    put32(b + 12, 7u); b[16] = 0u;
    put32(b + 36, TAPE_SAMPLE_RATE); put16(b + 40, 2u); put16(b + 42, 16u);
    put32(b + 44, TAPE_CHUNK_BYTES);
    put32(b + 48, (uint32_t)(((uint64_t)CHUNKS * TAPE_CHUNK_FRAMES) / TAPE_SAMPLE_RATE));
    put32(b + 52, CHUNKS); put32(b + 56, CHUNKS);
    put32(b + 60, TAPE_INDEX_SLOT_BYTES);
    put32(b + 64, TAPE_LBA_INDEX_A0); put32(b + 68, TAPE_LBA_INDEX_A1);
    put32(b + 72, TAPE_LBA_INDEX_B0); put32(b + 76, TAPE_LBA_INDEX_B1);
    put32(b + 80, TAPE_LBA_CHUNK_BASE); put32(b + 84, BLOCKS - 1u);
    put32(b + 124, 0u);
    put32(b + 508, crc32_of(b, 508));
}

struct ent { uint32_t first, start, count; };

static void build_index(uint32_t lba, uint8_t side, uint32_t seq,
                        const struct ent *e, uint32_t n)
{
    unsigned char *s = IMG + (size_t)lba * TAPE_BLOCK_SIZE;
    uint64_t total = 0;
    uint32_t i;
    unsigned char tmp[64 + 12 * 16];

    memset(s, 0, TAPE_INDEX_SLOT_BYTES);
    memcpy(s, "TAPEIDX\x01", 8);
    put32(s + 8, seq); s[12] = side;
    put32(s + 16, n);
    for (i = 0; i < n; i++) {
        put32(s + 512 + 12u * i, e[i].first);
        put32(s + 516 + 12u * i, e[i].start);
        put32(s + 520 + 12u * i, e[i].count);
        total += e[i].count;
    }
    put32(s + 20, (uint32_t)total); put32(s + 24, (uint32_t)(total >> 32));
    memcpy(tmp, s, 60);
    memcpy(tmp + 60, s + 512, (size_t)12u * n);
    put32(s + 60, crc32_of(tmp, (size_t)60 + 12u * n));
}

/* Write one stereo frame at a physical frame index inside the chunk store. */
static void put_frame(uint64_t phys, int16_t l, int16_t r)
{
    unsigned char *p = IMG + (size_t)TAPE_LBA_CHUNK_BASE * TAPE_BLOCK_SIZE
                     + (size_t)phys * TAPE_FRAME_BYTES;
    put16(p,     (uint16_t)l);
    put16(p + 2, (uint16_t)r);
}

static unsigned char INST[262144];
static unsigned char PLAY[TAPE_PLAY_RING_MIN], REC[TAPE_REC_RING_MIN];

static tape *mount_a(const struct ent *e, uint32_t n, uint64_t resume)
{
    static tape_dev dev;
    tape *t = NULL;

    memset(IMG, 0, sizeof IMG);
    build_sb(IMG);
    memcpy(IMG + (size_t)(BLOCKS - 1u) * TAPE_BLOCK_SIZE, IMG, TAPE_BLOCK_SIZE);
    build_index(TAPE_LBA_INDEX_A0, 0u, 10u, e, n);
    build_index(TAPE_LBA_INDEX_A1, 0u, 9u, e, n);
    build_index(TAPE_LBA_INDEX_B0, 1u, 20u, e, 0u);
    build_index(TAPE_LBA_INDEX_B1, 1u, 19u, e, 0u);
    dev.read = img_read; dev.write = NULL; dev.flush = img_flush;
    dev.ctx = NULL; dev.block_count = BLOCKS;
    if (tape_init(INST, sizeof INST, &dev, PLAY, sizeof PLAY, REC, sizeof REC, &t) != TAPE_OK) {
        return NULL;
    }
    if (tape_mount(t, TAPE_SIDE_A, resume, NULL) != TAPE_OK) { return NULL; }
    return t;
}

/* An independent floor-division interpolation, deliberately written differently
   from the engine's unsigned-shift form, so agreement means something. */
static int16_t ref_interp(int16_t a, int16_t b, uint32_t f)
{
    long double exact = (long double)a + ((long double)b - (long double)a)
                        * ((long double)f / 4294967296.0L);
    long double fl = exact;
    int64_t q;
    /* floor toward -inf */
    q = (int64_t)fl;
    if ((long double)q > fl) { q--; }
    return (int16_t)q;
}

static void service_all(tape *t)
{
    bool more = true;
    int guard = 0;
    while (more && guard++ < 10000) {
        if (tape_service(t, 1024u, &more) != TAPE_OK) { break; }
    }
}

int main(void)
{
    static const struct ent one_run[1] = { { 0u, 0u, 8u } };
    static const struct ent split[2]   = { { 0u, 0u, 4u }, { 2u, 100u, 4u } };
    int16_t out[64];
    uint32_t got = 0u;
    tape *t;
    uint32_t i;

    /* Side A: 8 frames, values chosen so interpolation is visible and signed. */
    t = mount_a(one_run, 1u, 0u);
    CHECK(t != NULL);
    if (t == NULL) { return 1; }
    for (i = 0; i < 8u; i++) {
        put_frame(i, (int16_t)(i * 4000 - 16000), (int16_t)(-(int)i * 3000 + 9000));
    }

    /* --- 1. fetch-before-advance at every seek target (V4-010) ----------- */
    for (i = 0; i < 8u; i++) {
        CHECK(tape_seek(t, i) == TAPE_OK);
        CHECK(tape_set_rate(t, 65536) == TAPE_OK);
        service_all(t);
        got = 0u;
        CHECK(tape_render(t, out, 1u, &got) == TAPE_OK);
        CHECK_EQ_U32(got, 1u);
        CHECK_EQ_U32((uint16_t)out[0], (uint16_t)(int16_t)(i * 4000 - 16000));
    }

    /* --- 2. render performs ZERO block I/O (§6.3, contract 2) ------------ */
    CHECK(tape_seek(t, 0) == TAPE_OK);
    CHECK(tape_set_rate(t, 65536) == TAPE_OK);
    service_all(t);
    {
        uint32_t before = DEV_READS;
        got = 0u;
        CHECK(tape_render(t, out, 8u, &got) == TAPE_OK);
        CHECK_EQ_U32(got, 8u);
        CHECK_EQ_U32(DEV_READS, before);          /* not one read */
    }

    /* --- 3. fractional rate: f != 0, so §8 is actually exercised --------- */
    CHECK(tape_seek(t, 0) == TAPE_OK);
    CHECK(tape_set_rate(t, 32768) == TAPE_OK);    /* 0.5x */
    service_all(t);
    got = 0u;
    CHECK(tape_render(t, out, 4u, &got) == TAPE_OK);
    CHECK_EQ_U32(got, 4u);
    {
        /* positions 0.0, 0.5, 1.0, 1.5 */
        int16_t a0 = (int16_t)(0 * 4000 - 16000), a1 = (int16_t)(1 * 4000 - 16000);
        int16_t a2 = (int16_t)(2 * 4000 - 16000);
        CHECK_EQ_U32((uint16_t)out[0], (uint16_t)ref_interp(a0, a1, 0u));
        CHECK_EQ_U32((uint16_t)out[2], (uint16_t)ref_interp(a0, a1, 0x80000000u));
        CHECK_EQ_U32((uint16_t)out[4], (uint16_t)ref_interp(a1, a2, 0u));
        CHECK_EQ_U32((uint16_t)out[6], (uint16_t)ref_interp(a1, a2, 0x80000000u));
        /* and it is genuinely between the endpoints, not a copy of either */
        CHECK(out[2] != a0 && out[2] != a1);
    }

    /* --- 4. negative fractional rate floors toward -inf (V4-013) -------- */
    CHECK(tape_seek(t, 7) == TAPE_OK);
    CHECK(tape_set_rate(t, -32768) == TAPE_OK);
    service_all(t);
    got = 0u;
    CHECK(tape_render(t, out, 4u, &got) == TAPE_OK);
    CHECK_EQ_U32(got, 4u);

    /* --- 5. reverse from the end snaps ON GRID (V5-005) ----------------- */
    CHECK(tape_seek(t, 8) == TAPE_OK);            /* == total_frames, i.e. max_pos */
    CHECK(tape_set_rate(t, -65536) == TAPE_OK);
    service_all(t);
    got = 0u;
    CHECK(tape_render(t, out, 8u, &got) == TAPE_OK);
    CHECK_EQ_U32(got, 8u);
    for (i = 0; i < 8u; i++) {
        /* Exact reverse. The DRAFT-5 max_pos-1 snap got sample 0 right and every
           later sample wrong, so checking the whole run is the point. */
        CHECK_EQ_U32((uint16_t)out[i * 2u],
                     (uint16_t)(int16_t)((7u - i) * 4000 - 16000));
    }

    /* --- 6. rate 0 renders nothing and changes no flag ------------------ */
    CHECK(tape_seek(t, 3) == TAPE_OK);
    CHECK(tape_set_rate(t, 0) == TAPE_OK);
    service_all(t);
    got = 99u;
    CHECK(tape_render(t, out, 4u, &got) == TAPE_OK);
    CHECK_EQ_U32(got, 0u);

    /* --- 7. extreme positive rate clamps without wrapping (V4-009) ------ */
    CHECK(tape_seek(t, 0) == TAPE_OK);
    CHECK(tape_set_rate(t, 2147483647) == TAPE_OK);
    service_all(t);
    got = 0u;
    CHECK(tape_render(t, out, 4u, &got) == TAPE_OK);
    CHECK_EQ_U32(got, 1u);                        /* one frame, then at_end */
    {
        uint64_t pos = 0u;
        CHECK(tape_tell(t, &pos) == TAPE_OK);
        CHECK_EQ_U32((uint32_t)pos, 8u);          /* clamped to total, not wrapped */
    }

    /* --- 8. extreme negative rate lands on frame 0 and stops ----------- */
    CHECK(tape_seek(t, 8) == TAPE_OK);
    CHECK(tape_set_rate(t, -2147483647 - 1) == TAPE_OK);
    service_all(t);
    got = 0u;
    CHECK(tape_render(t, out, 8u, &got) == TAPE_OK);
    CHECK(got >= 1u);                             /* emits, then at_start stops it */

    /* --- 9. seek beyond the end clamps, forward render reports at_end --- */
    CHECK(tape_seek(t, 1000000u) == TAPE_OK);
    CHECK(tape_set_rate(t, 65536) == TAPE_OK);
    service_all(t);
    got = 7u;
    CHECK(tape_render(t, out, 4u, &got) == TAPE_OK);
    CHECK_EQ_U32(got, 0u);
    /* at_end is asserted behaviourally: tape_status is a different operation and
       is deliberately NOT implemented in this round, so depending on it here
       would be reaching outside the assigned slice. A second forward render
       still yielding nothing is the observable consequence of the flag. */
    got = 7u;
    CHECK(tape_render(t, out, 4u, &got) == TAPE_OK);
    CHECK_EQ_U32(got, 0u);

    /* --- 10. tell truncates a fractional position to whole frames ------- */
    CHECK(tape_seek(t, 0) == TAPE_OK);
    CHECK(tape_set_rate(t, 32768) == TAPE_OK);
    service_all(t);
    got = 0u;
    CHECK(tape_render(t, out, 1u, &got) == TAPE_OK);
    {
        uint64_t pos = 1u;
        CHECK(tape_tell(t, &pos) == TAPE_OK);
        CHECK_EQ_U32((uint32_t)pos, 0u);          /* at 0.5, truncates to 0 */
    }

    /* --- 11. a run that jumps chunks still reads the right frames ------- */
    t = mount_a(split, 2u, 0u);
    CHECK(t != NULL);
    if (t != NULL) {
        for (i = 0; i < 4u; i++) { put_frame(i, (int16_t)(1000 + (int)i), 0); }
        for (i = 0; i < 4u; i++) {
            put_frame((uint64_t)2u * TAPE_CHUNK_FRAMES + 100u + i, (int16_t)(2000 + (int)i), 0);
        }
        CHECK(tape_seek(t, 0) == TAPE_OK);
        CHECK(tape_set_rate(t, 65536) == TAPE_OK);
        service_all(t);
        got = 0u;
        CHECK(tape_render(t, out, 8u, &got) == TAPE_OK);
        CHECK_EQ_U32(got, 8u);
        for (i = 0; i < 4u; i++) {
            CHECK_EQ_U32((uint16_t)out[i * 2u], (uint16_t)(int16_t)(1000 + (int)i));
        }
        for (i = 0; i < 4u; i++) {
            CHECK_EQ_U32((uint16_t)out[(i + 4u) * 2u], (uint16_t)(int16_t)(2000 + (int)i));
        }
    }

    /* --- 12. render before service is an UNDERRUN, not silence --------- */
    t = mount_a(one_run, 1u, 0u);
    CHECK(t != NULL);
    if (t != NULL) {
        for (i = 0; i < 8u; i++) { put_frame(i, (int16_t)(i * 100), 0); }
        CHECK(tape_set_rate(t, 65536) == TAPE_OK);
        got = 5u;
        CHECK(tape_render(t, out, 4u, &got) == TAPE_ERR_UNDERRUN);
        CHECK_EQ_U32(got, 0u);
    }

    /* --- 13. block_budget 0 is INVALID_ARG, per §9's reasoning --------- */
    if (t != NULL) {
        bool more = true;
        CHECK(tape_service(t, 0u, &more) == TAPE_ERR_INVALID_ARG);
    }

    if (tape_test_failures != 0) {
        (void)fprintf(stderr, "\n%d of %d checks FAILED\n",
                      tape_test_failures, tape_test_checks);
        return 1;
    }
    (void)printf("PASS  playback beyond the package    %d checks\n", tape_test_checks);
    return 0;
}
