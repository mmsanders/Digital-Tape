/*
 * count.c — Q-P2-1(b) input: device callbacks and blocks per C-60 operation.
 *
 * Plan §5 (docs/PHASE2-PLAN.md) and #385 Part C. PM rules in P2-R2 between
 * port-level batching and multi-block engine calls; this counts what the
 * engine asks the device for today. It makes no throughput or timing claim
 * and changes no engine code.
 *
 * Stack, outermost first:
 *
 *   engine -> dev_sim (engine/port, counts calls) -> tally (here: calls,
 *   blocks, run shape) -> dev_file (engine/port, a sparse image file)
 *
 * dev_sim is the counter the issue names. tally also counts blocks, the
 * per-call block-count histogram and how many calls continue the previous
 * read (or write) call's LBA run: the batching opportunity a port could
 * exploit, since a flush does not end the run on media. The two
 * layers' call counts are cross-checked and must agree.
 *
 * Call shape mirrors tapectl (docs/WP11-CLI-CONTRACT.md): 1024-frame feeds,
 * service until done before each feed, and a 1024-block budget for service,
 * promote, respool and dup.
 *
 * Usage: count WORKDIR    (needs ~1.3 GB of sparse image space)
 * Prints a Markdown table on stdout. Exit 0 only if every operation returned
 * TAPE_OK, the two counters agreed, and every expected postcondition held.
 */

#include "tape.h"
#include "dev_file.h"
#include "dev_sim.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SAMPLE_RATE  44100u
#define C60_S        3600u
#define TOTAL_CHUNKS 1212u                         /* tapefs §2, C-60 */
#define C60_BLOCKS   (2048u + TOTAL_CHUNKS * 1024u + 1u)   /* GEOMETRY_OK minimum */
#define FEED_FRAMES  1024u
#define BUDGET       1024u

#define FRAG_BASE_S  1500u                         /* 25 min on Side B */
#define FRAG_EDITS   64u                           /* 1 s overwrites */

static union { long double ld; uint64_t u; void *p; unsigned char b[256u * 1024u]; } g_mem;
static unsigned char g_play[TAPE_PLAY_RING_MIN];
static unsigned char g_rec[TAPE_REC_RING_MIN];
static int16_t g_pcm[FEED_FRAMES * 2u];

/* ------------------------------------------------------------ the tally layer */

#define HIST_MAX 8u   /* buckets: 1, 2, 3..4, 5..8, 9..16, 17..64, 65..1024, >1024 */

struct op_tally {
    unsigned long long calls, blocks, contiguous, hist[HIST_MAX];
    uint32_t max_count;
    uint32_t next_lba;      /* LBA just past this stream's previous call */
    int have_prev;
};

struct tally {
    const tape_dev *inner;
    struct op_tally rd, wr;
    unsigned long long flushes;
};

static unsigned bucket(uint32_t n)
{
    if (n <= 1u) { return 0; }
    if (n == 2u) { return 1; }
    if (n <= 4u) { return 2; }
    if (n <= 8u) { return 3; }
    if (n <= 16u) { return 4; }
    if (n <= 64u) { return 5; }
    if (n <= 1024u) { return 6; }
    return 7;
}

static void note(struct op_tally *o, uint32_t lba, uint32_t count)
{
    o->calls++;
    o->blocks += count;
    o->hist[bucket(count)]++;
    if (count > o->max_count) { o->max_count = count; }
    if (o->have_prev && lba == o->next_lba) { o->contiguous++; }
    o->next_lba = lba + count;
    o->have_prev = 1;
}

static int t_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    struct tally *t = (struct tally *)ctx;
    note(&t->rd, lba, count);
    return t->inner->read(t->inner->ctx, lba, count, dst);
}

static int t_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    struct tally *t = (struct tally *)ctx;
    note(&t->wr, lba, count);
    return t->inner->write(t->inner->ctx, lba, count, src);
}

static int t_flush(void *ctx)
{
    struct tally *t = (struct tally *)ctx;
    t->flushes++;
    return t->inner->flush(t->inner->ctx);
}

/* One counted device: file -> tally -> dev_sim. `dev` is what the engine sees. */
struct counted {
    struct tape_dev_file file;
    tape_dev file_dev, tally_dev, dev;
    struct tally tally;
    struct tape_dev_sim sim;
};

static void counted_bind(struct counted *c)
{
    memset(&c->tally, 0, sizeof c->tally);
    c->tally.inner = &c->file_dev;
    c->tally_dev.read = t_read;
    c->tally_dev.write = (c->file_dev.write != NULL) ? t_write : NULL;
    c->tally_dev.flush = t_flush;
    c->tally_dev.ctx = &c->tally;
    c->tally_dev.block_count = c->file_dev.block_count;
    tape_dev_sim_bind(&c->sim, &c->dev, &c->tally_dev);
}

static void counted_reset(struct counted *c)
{
    const tape_dev *inner = c->tally.inner;
    memset(&c->tally, 0, sizeof c->tally);
    c->tally.inner = inner;
    tape_dev_sim_reset(&c->sim);
}

static int make_device(struct counted *c, const char *path)
{
    memset(c, 0, sizeof *c);
    if (tape_dev_file_create(&c->file, &c->file_dev, path, C60_BLOCKS) != TAPE_DEV_OK) {
        fprintf(stderr, "count: cannot create %s\n", path);
        return 1;
    }
    counted_bind(c);
    return 0;
}

/* --------------------------------------------------------------- reporting */

static int g_bad;

#define CHECK(expr) do { tape_result r_ = (expr); if (r_ != TAPE_OK) { \
    fprintf(stderr, "count: %s -> %d (line %d)\n", #expr, (int)r_, __LINE__); \
    exit(1); } } while (0)

static void expect(int cond, const char *what)
{
    if (!cond) { fprintf(stderr, "count: FAILED %s\n", what); g_bad = 1; }
}

static void row(const char *op, const char *dev, const struct counted *c)
{
    const struct tally *t = &c->tally;
    unsigned long long calls = t->rd.calls + t->wr.calls + t->flushes;
    expect(c->sim.reads_seen == t->rd.calls && c->sim.writes_seen == t->wr.calls
           && c->sim.flushes_seen == t->flushes, "dev_sim and tally call counts agree");
    printf("| %s | %s | %llu | %llu | %llu | %llu | %llu | %llu | %u / %u | %llu / %llu |\n",
           op, dev, (unsigned long long)c->sim.reads_seen, (unsigned long long)c->sim.writes_seen,
           (unsigned long long)c->sim.flushes_seen, calls, t->rd.blocks, t->wr.blocks,
           t->rd.max_count, t->wr.max_count, t->rd.contiguous, t->wr.contiguous);
}

static void hist(const char *op, const struct counted *c)
{
    static const char *const names[HIST_MAX] = {"1", "2", "3-4", "5-8", "9-16", "17-64", "65-1024", ">1024"};
    unsigned i;
    printf("| %s |", op);
    for (i = 0; i < HIST_MAX; i++) {
        printf(" %llu / %llu |", c->tally.rd.hist[i], c->tally.wr.hist[i]);
    }
    printf("\n");
    (void)names;
}

/* ------------------------------------------------------------- engine steps */

static tape *g_t;

static void mount(const tape_dev *dev, tape_side side)
{
    CHECK(tape_init(g_mem.b, tape_instance_size(), dev, g_play, sizeof g_play, g_rec, sizeof g_rec, &g_t));
    CHECK(tape_mount(g_t, side, 0u, NULL));
}

static void unmount(void)
{
    uint64_t pos;
    CHECK(tape_unmount(g_t, &pos));
    g_t = NULL;
}

static void service(void)
{
    bool more = true;
    while (more) { CHECK(tape_service(g_t, BUDGET, &more)); }
}

/* Deterministic, non-silent stereo; content does not affect call shape. */
static void fill(uint64_t first, uint32_t n)
{
    uint32_t i;
    for (i = 0; i < n; i++) {
        uint64_t f = first + i;
        g_pcm[2u * i] = (int16_t)(uint16_t)((f * 2654435761u) >> 7);
        g_pcm[2u * i + 1u] = (int16_t)(uint16_t)(f * 37u);
    }
}

/* tapectl's record: set side B, seek, arm, feed, drain, commit. */
static void record_at(uint64_t at, uint64_t frames, tape_rec_mode mode)
{
    uint64_t done = 0;
    tape_status_t st;
    CHECK(tape_set_side(g_t, TAPE_SIDE_B));
    CHECK(tape_seek(g_t, at));
    CHECK(tape_arm(g_t, mode));
    while (done < frames) {
        uint32_t n = (frames - done) > FEED_FRAMES ? FEED_FRAMES : (uint32_t)(frames - done), fed = 0;
        fill(at + done, n);
        while (fed < n) {
            uint32_t acc = 0;
            service();
            CHECK(tape_feed(g_t, g_pcm + (size_t)fed * 2u, n - fed, &acc));
            fed += acc;
        }
        done += n;
    }
    do {
        bool more = true;
        CHECK(tape_service(g_t, BUDGET, &more));
        CHECK(tape_status(g_t, &st));
    } while (st.frames_owed);
    CHECK(tape_commit(g_t));
}

static void run_long(int promote)
{
    bool more = true;
    while (more) {
        if (promote) { CHECK(tape_promote(g_t, BUDGET, &more, NULL, NULL)); }
        else         { CHECK(tape_respool(g_t, BUDGET, &more)); }
    }
}

static const uint8_t UUID_A[16] = {0xa0,0xa1,0xa2,0xa3,0xa4,0xa5,0xa6,0xa7,0xa8,0xa9,0xaa,0xab,0xac,0xad,0xae,0xaf};
static const uint8_t UUID_B[16] = {0xb0,0xb1,0xb2,0xb3,0xb4,0xb5,0xb6,0xb7,0xb8,0xb9,0xba,0xbb,0xbc,0xbd,0xbe,0xbf};
static const uint8_t UUID_C[16] = {0xc0,0xc1,0xc2,0xc3,0xc4,0xc5,0xc6,0xc7,0xc8,0xc9,0xca,0xcb,0xcc,0xcd,0xce,0xcf};

int main(int argc, char **argv)
{
    char path[1024];
    static struct counted src, dst, frag;
    tape_info info;
    uint64_t c60_frames = (uint64_t)C60_S * SAMPLE_RATE;
    unsigned k;

    if (argc != 2) { fprintf(stderr, "usage: count WORKDIR\n"); return 2; }
    if (tape_instance_size() > sizeof g_mem.b) { fprintf(stderr, "count: instance too large\n"); return 1; }

    /* 1. Full C-60 load = record 3600 s onto Side B, then promote B -> A. */
    snprintf(path, sizeof path, "%s/src.img", argv[1]);
    if (make_device(&src, path)) { return 1; }
    CHECK(tape_format(&src.dev, UUID_A, 0u, "qp21 load", C60_S));
    mount(&src.dev, TAPE_SIDE_A);
    counted_reset(&src);
    record_at(0u, c60_frames, TAPE_REC_OVERWRITE);
    struct counted rec = src;                 /* snapshot of the record phase */
    counted_reset(&src);
    run_long(1);
    struct counted pro = src;
    CHECK(tape_get_info(g_t, &info));
    expect(info.total_frames == c60_frames, "load: Side A holds the whole C-60");
    expect(info.total_chunks == TOTAL_CHUNKS, "load: C-60 geometry");

    /* 2. tape_dup of that full C-60 onto a blank C-60 device. */
    snprintf(path, sizeof path, "%s/dst.img", argv[1]);
    if (make_device(&dst, path)) { return 1; }
    counted_reset(&src);
    {
        bool more = true;
        while (more) { CHECK(tape_dup(g_t, &dst.dev, UUID_B, 1u, C60_S, BUDGET, &more, NULL, NULL)); }
    }
    struct counted dup_src = src, dup_dst = dst;
    unmount();
    mount(&dst.dev, TAPE_SIDE_A);
    CHECK(tape_get_info(g_t, &info));
    expect(info.total_frames == c60_frames, "dup: destination Side A holds the whole C-60");
    unmount();

    /* 3. Re-spool of a fragmented C-60: 25 min recorded on Side B of a fresh
          C-60 (Side A empty, so both passes have room), then 64 one-second
          overdubs spread across it, each a separate commit. Overdub keeps the
          timeline length (an overwrite truncates after the playhead) and
          allocates fresh chunks for the span, so each one splits a run. */
    snprintf(path, sizeof path, "%s/frag.img", argv[1]);
    if (make_device(&frag, path)) { return 1; }
    CHECK(tape_format(&frag.dev, UUID_C, 0u, "qp21 frag", C60_S));
    mount(&frag.dev, TAPE_SIDE_A);
    record_at(0u, (uint64_t)FRAG_BASE_S * SAMPLE_RATE, TAPE_REC_OVERWRITE);
    for (k = 0; k < FRAG_EDITS; k++) {
        uint64_t at = ((uint64_t)FRAG_BASE_S * SAMPLE_RATE / FRAG_EDITS) * k + 12345u * k % SAMPLE_RATE;
        record_at(at, SAMPLE_RATE, TAPE_REC_OVERDUB);
    }
    CHECK(tape_set_side(g_t, TAPE_SIDE_B));
    CHECK(tape_get_info(g_t, &info));
    uint32_t entries_before = info.entry_count;
    expect(entries_before > FRAG_EDITS, "respool: Side B is fragmented");
    counted_reset(&frag);
    run_long(0);
    CHECK(tape_get_info(g_t, &info));
    expect(info.entry_count == 1u, "respool: Side B is one contiguous run");
    expect(info.total_frames == (uint64_t)FRAG_BASE_S * SAMPLE_RATE, "respool: timeline length kept");
    unmount();

    printf("Engine call shape as tapectl: %u-frame feeds, block budget %u. C-60 = %u s, %u chunks, "
           "%u-block device.\n\n", FEED_FRAMES, BUDGET, C60_S, TOTAL_CHUNKS, C60_BLOCKS);
    printf("| Operation | Device | read calls | write calls | flush calls | total calls | blocks read "
           "| blocks written | max blocks/call (r / w) | calls continuing that stream's LBA run (r / w) |\n");
    printf("|---|---|---|---|---|---|---|---|---|---|\n");
    row("load: record 3600 s", "card", &rec);
    row("load: promote", "card", &pro);
    {
        struct counted sum = rec;
        sum.sim.reads_seen += pro.sim.reads_seen;
        sum.sim.writes_seen += pro.sim.writes_seen;
        sum.sim.flushes_seen += pro.sim.flushes_seen;
        sum.tally.rd.calls += pro.tally.rd.calls; sum.tally.wr.calls += pro.tally.wr.calls;
        sum.tally.flushes += pro.tally.flushes;
        sum.tally.rd.blocks += pro.tally.rd.blocks; sum.tally.wr.blocks += pro.tally.wr.blocks;
        sum.tally.rd.contiguous += pro.tally.rd.contiguous; sum.tally.wr.contiguous += pro.tally.wr.contiguous;
        if (pro.tally.rd.max_count > sum.tally.rd.max_count) { sum.tally.rd.max_count = pro.tally.rd.max_count; }
        if (pro.tally.wr.max_count > sum.tally.wr.max_count) { sum.tally.wr.max_count = pro.tally.wr.max_count; }
        row("**load total**", "card", &sum);
    }
    row("tape_dup", "source", &dup_src);
    row("tape_dup", "destination", &dup_dst);
    {
        char op[96];
        snprintf(op, sizeof op, "respool (%u s, %u entries)", FRAG_BASE_S, (unsigned)entries_before);
        row(op, "card", &frag);
    }
    printf("\nBlocks per call, read / write calls in each bucket:\n\n");
    printf("| Operation | 1 | 2 | 3-4 | 5-8 | 9-16 | 17-64 | 65-1024 | >1024 |\n");
    printf("|---|---|---|---|---|---|---|---|---|\n");
    hist("load: record", &rec);
    hist("load: promote", &pro);
    hist("tape_dup source", &dup_src);
    hist("tape_dup destination", &dup_dst);
    hist("respool", &frag);

    tape_dev_file_close(&src.file);
    tape_dev_file_close(&dst.file);
    tape_dev_file_close(&frag.file);
    if (g_bad) { fprintf(stderr, "count: FAIL\n"); return 1; }
    fprintf(stderr, "count: PASS\n");
    return 0;
}
