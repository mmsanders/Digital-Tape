/*
 * raw_ops.c — DRAFT-8 raw cartridge operations: tape_format (§9.6) and the
 * incremental tape_dup (§9.5, engine-api §9.1).
 *
 * Both take a raw destination tape_dev, never a mount. Refusal preconditions
 * run first, in their normative order, with zero writes; raw superblock
 * classification is a plan (two reads, no writes); then the ordered
 * destructive transaction, ending with the identity-assignment commit
 * (sb_generation = 1, A0/B0 at sequence 1 and 2), mirror then primary.
 *
 * tape_dup is a long operation on its SOURCE instance: at most block_budget
 * block reads/writes per call, driven to completion by repeated calls with the
 * same fixed arguments. A destination failure ends it without faulting the
 * source (engine-api §7.2, §9.1), which stays in its transport state.
 *
 * Normative: spec/tapefs-v1.md §2.1, §4.5, §4.6, §5, §9.5, §9.6;
 * spec/engine-api.md §7.2, §9, §10.
 */

#include <string.h>

#include "tape_internal.h"
#include "tape_crc32.h"
#include "dev.h"

#define RAW_FRAMES_PER_BLOCK (TAPE_BLOCK_SIZE / TAPE_FRAME_BYTES)

static const unsigned char raw_sb_magic[8] = { 'T', 'A', 'P', 'E', 'F', 'S', 0x00u, 0x01u };
static const unsigned char raw_idx_magic[8] = { 'T', 'A', 'P', 'E', 'I', 'D', 'X', 0x01u };

/*
 * Sparse phase tags, for the same reason as promote.c: keep -Os from lowering
 * the state machine to a compiler jump table, which the indirect-call gate's
 * link-time backstop cannot tell from an authored dispatch table.
 */
#define DUP_PHASE_READ_PRIMARY   11u
#define DUP_PHASE_READ_MIRROR    29u
#define DUP_PHASE_STEP1_FIRST    47u
#define DUP_PHASE_STEP1_SECOND   71u
#define DUP_PHASE_ZERO_SLOTS     97u
#define DUP_PHASE_COPY          131u
#define DUP_PHASE_A0_ENTRIES    163u
#define DUP_PHASE_A0_HEADER     193u
#define DUP_PHASE_B0_ENTRIES    211u
#define DUP_PHASE_B0_HEADER     227u
#define DUP_PHASE_SB_MIRROR     241u
#define DUP_PHASE_SB_PRIMARY    253u

#define RAW_STEP1_SKIP     0u   /* neither copy structurally valid: blank */
#define RAW_STEP1_TEMPLATE 1u   /* v1 WIP barrier template, §9.5 item 5 */
#define RAW_STEP1_ZERO     2u   /* §4.5 generation-exhausted fallback */

struct raw_plan {
    uint8_t  kind;
    uint32_t first_lba;    /* partner / non-selectable copy: written first */
    uint32_t second_lba;   /* selected candidate: written last */
};

static void raw_wr64(unsigned char *p, uint64_t v)
{
    tape_wr32(p, (uint32_t)(v & 0xFFFFFFFFu));
    tape_wr32(p + 4, (uint32_t)(v >> 32));
}

static bool raw_sb_structural(const unsigned char *blk, uint32_t *generation)
{
    struct tape_sb sb;

    if (tape_sb_parse(blk, &sb) != TAPE_OK) { return false; }
    *generation = sb.sb_generation;
    return true;
}

/*
 * §9.5 item 5 / §9.6 classification, shared by format and duplicate. A plan
 * only: it reads nothing and writes nothing. On return `pri` holds the exact
 * step-1 bytes (template or 512 zeros); `mir` is not modified.
 *
 * §4.6 roles: exactly one valid -> it is the candidate; different generations
 * -> the higher; equal and byte-identical -> primary candidate, mirror partner.
 * Equal-generation-divergent has no §4.1 candidate: the healthy-pair tie-break
 * decides only the ORDER (mirror first), and the template's other fields are
 * zeroed because there is no selected candidate to copy them from.
 */
static void raw_classify(unsigned char *pri, const unsigned char *mir,
                         uint32_t mirror_lba, struct raw_plan *plan)
{
    uint32_t pg = 0u, mg = 0u, g;
    bool pv = raw_sb_structural(pri, &pg);
    bool mv = raw_sb_structural(mir, &mg);
    int cand; /* 0 none, 1 primary, 2 mirror */

    if (!pv && !mv) {
        plan->kind = RAW_STEP1_SKIP;
        plan->first_lba = 0u;
        plan->second_lba = 0u;
        return;
    }

    if (pv && !mv) {
        cand = 1;
    } else if (!pv) {
        cand = 2;
    } else if (pg != mg) {
        cand = (pg > mg) ? 1 : 2;
    } else if (memcmp(pri, mir, TAPE_BLOCK_SIZE) == 0) {
        cand = 1;
    } else {
        cand = 0;
    }

    if (cand == 2) {
        plan->first_lba = TAPE_LBA_SUPERBLOCK;
        plan->second_lba = mirror_lba;
    } else {
        plan->first_lba = mirror_lba;
        plan->second_lba = TAPE_LBA_SUPERBLOCK;
    }

    g = 0u;
    if (pv) { g = pg; }
    if (mv && mg > g) { g = mg; }
    if (g < 1u) { g = 1u; }

    if (!tape_headroom_ok(g, 1u)) {
        /* §4.5: sb_generation >= 0xFFFFFFFD. Zero both, non-selectable first. */
        plan->kind = RAW_STEP1_ZERO;
        memset(pri, 0, TAPE_BLOCK_SIZE);
        return;
    }

    plan->kind = RAW_STEP1_TEMPLATE;
    if (cand == 2) {
        memcpy(pri, mir, TAPE_BLOCK_SIZE);
    } else if (cand == 0) {
        memset(pri, 0, TAPE_BLOCK_SIZE);
        memcpy(pri, raw_sb_magic, sizeof raw_sb_magic);
    }
    pri[8] = 1u; pri[9] = 0u;     /* version_major = 1 */
    pri[10] = 0u; pri[11] = 0u;   /* version_minor = 0 */
    tape_wr32(pri + 12, g + 1u);  /* max(existing, 1) + 1 */
    pri[16] = TAPE_STATE_WRITE_IN_PROGRESS;
    tape_wr32(pri + 124, TAPE_PROMOTE_STAGE_NONE);
    tape_wr32(pri + 128, 0u);
    tape_wr32(pri + 508, tape_crc32(pri, 508u));
}

/* The identity-assignment commit's inputs. A descriptor rather than eight
   parameters: arguments past the sixth go on the stack on x86-64, which
   -fstack-usage reports as a dynamic frame and the stack gate rejects. */
struct raw_identity {
    const uint8_t *uuid;
    const unsigned char *label32;    /* NULL: zero label */
    uint32_t epoch;
    uint32_t nominal_length_s;
    uint32_t total_chunks;
    uint32_t a_high_water;
    uint32_t block_count;
};

/* §4 superblock for the identity-assignment commit (§9.5 step 4, §9.6 4–5). */
static void raw_sb_final(unsigned char *b, const struct raw_identity *id)
{
    memset(b, 0, TAPE_BLOCK_SIZE);
    memcpy(b, raw_sb_magic, sizeof raw_sb_magic);
    b[8] = 1u;                                   /* version_major */
    tape_wr32(b + 12, 1u);                       /* sb_generation */
    b[16] = TAPE_STATE_VALID;
    memcpy(b + 20, id->uuid, 16u);
    tape_wr32(b + 36, TAPE_SAMPLE_RATE);
    b[40] = (unsigned char)TAPE_CHANNELS;
    b[42] = 16u;                                 /* bits_per_sample */
    tape_wr32(b + 44, TAPE_CHUNK_BYTES);
    tape_wr32(b + 48, id->nominal_length_s);
    tape_wr32(b + 52, id->total_chunks);
    tape_wr32(b + 56, id->a_high_water);
    tape_wr32(b + 60, TAPE_INDEX_SLOT_BYTES);
    tape_wr32(b + 64, TAPE_LBA_INDEX_A0);
    tape_wr32(b + 68, TAPE_LBA_INDEX_A1);
    tape_wr32(b + 72, TAPE_LBA_INDEX_B0);
    tape_wr32(b + 76, TAPE_LBA_INDEX_B1);
    tape_wr32(b + 80, TAPE_LBA_CHUNK_BASE);
    tape_wr32(b + 84, id->block_count - 1u);
    if (id->label32 != NULL) { memcpy(b + 88, id->label32, 32u); }
    tape_wr32(b + 120, id->epoch);
    /* promote_stage and promote_staging_chunk stay zero. */
    tape_wr32(b + 508, tape_crc32(b, 508u));
}

/* §5 slot 0 entry array: one entry {0, 0, frames} (§9.5 step 3). */
static void raw_index_entries(unsigned char *b, uint64_t frames)
{
    memset(b, 0, TAPE_BLOCK_SIZE);
    tape_wr32(b + 8, (uint32_t)frames);
}

/* §5 header. Zero frames is the valid zero-entry header (§9.6 step 3), CRC
   over the header alone; otherwise one entry {0, 0, frames}. */
static void raw_index_header(unsigned char *b, uint8_t side, uint32_t sequence,
                             uint64_t frames)
{
    unsigned char entry[TAPE_INDEX_ENTRY_BYTES];
    uint32_t crc;

    memset(b, 0, TAPE_BLOCK_SIZE);
    memcpy(b, raw_idx_magic, sizeof raw_idx_magic);
    tape_wr32(b + 8, sequence);
    b[12] = side;
    tape_wr32(b + 16, (frames != 0u) ? 1u : 0u);
    raw_wr64(b + 20, frames);

    crc = tape_crc32_update(tape_crc32_init(), b, 60u);
    if (frames != 0u) {
        memset(entry, 0, sizeof entry);
        tape_wr32(entry + 8, (uint32_t)frames);
        crc = tape_crc32_update(crc, entry, sizeof entry);
    }
    tape_wr32(b + 60, tape_crc32_final(crc));
}

static int raw_write_flush(const tape_dev *d, uint32_t lba, const unsigned char *blk)
{
    if (dev_write(d, lba, 1u, blk) != 0) { return -1; }
    return dev_flush(d);
}

/* ------------------------------------------------------------------------- */
/* §9.6 format                                                               */
/* ------------------------------------------------------------------------- */

tape_result tape_format(const tape_dev *dev, const uint8_t uuid[16], uint32_t epoch,
                        const char *label, uint32_t nominal_length_s)
{
    /* No instance exists here, so the two blocks are necessarily on the stack
       (1 KiB of the 8 KiB budget). */
    unsigned char pri[TAPE_BLOCK_SIZE];
    unsigned char mir[TAPE_BLOCK_SIZE];
    unsigned char label32[32];
    struct raw_plan plan;
    struct raw_identity id;
    uint32_t total_chunks, mirror_lba;
    size_t n;
    tape_result rc;

    if (dev == NULL) { return TAPE_ERR_INVALID_ARG; }

    /* §9.6 precondition order is normative; both write nothing, and geometry
       (with DEVICE_ADDRESSABLE) is evaluated before any superblock read. */
    if (dev->write == NULL) { return TAPE_ERR_READ_ONLY; }
    rc = tape_geometry_ok(nominal_length_s, dev->block_count, &total_chunks);
    if (rc != TAPE_OK) { return rc; }

    /* Caller-argument validity, still before any callback. The label field is
       32 bytes NUL-padded; a longer label is refused rather than truncated. */
    if (uuid == NULL || label == NULL) { return TAPE_ERR_INVALID_ARG; }
    if (dev->read == NULL || dev->flush == NULL) { return TAPE_ERR_INVALID_ARG; }
    memset(label32, 0, sizeof label32);
    for (n = 0u; label[n] != '\0'; n++) {
        if (n >= sizeof label32) { return TAPE_ERR_INVALID_ARG; }
        label32[n] = (unsigned char)label[n];
    }

    mirror_lba = dev->block_count - 1u;

    /* Raw superblock classification: two reads, a plan, no writes. */
    if (dev_read(dev, TAPE_LBA_SUPERBLOCK, 1u, pri) != 0) { return TAPE_ERR_IO; }
    if (dev_read(dev, mirror_lba, 1u, mir) != 0) { return TAPE_ERR_IO; }
    raw_classify(pri, mir, mirror_lba, &plan);

    /* 1. WIP barrier template or generation-exhausted zeros, partner first,
          selected candidate last, a flush behind each. Skipped on blank media. */
    if (plan.kind != RAW_STEP1_SKIP) {
        if (raw_write_flush(dev, plan.first_lba, pri) != 0) { return TAPE_ERR_IO; }
        if (raw_write_flush(dev, plan.second_lba, pri) != 0) { return TAPE_ERR_IO; }
    }

    /* 2. A1 and B1 block 0 zeroed; flush. */
    memset(mir, 0, sizeof mir);
    if (dev_write(dev, TAPE_LBA_INDEX_A1, 1u, mir) != 0) { return TAPE_ERR_IO; }
    if (dev_write(dev, TAPE_LBA_INDEX_B1, 1u, mir) != 0) { return TAPE_ERR_IO; }
    if (dev_flush(dev) != 0) { return TAPE_ERR_IO; }

    /* 3. A0 and B0 valid empty headers at sequence 1 and 2; flush. */
    raw_index_header(pri, (uint8_t)TAPE_SIDE_A, 1u, 0u);
    if (dev_write(dev, TAPE_LBA_INDEX_A0, 1u, pri) != 0) { return TAPE_ERR_IO; }
    raw_index_header(pri, (uint8_t)TAPE_SIDE_B, 2u, 0u);
    if (dev_write(dev, TAPE_LBA_INDEX_B0, 1u, pri) != 0) { return TAPE_ERR_IO; }
    if (dev_flush(dev) != 0) { return TAPE_ERR_IO; }

    /* 4–5. Identity assignment: mirror, flush, primary, flush. The primary is
            the commit. §4.6 does not apply (V8C-002). */
    id.uuid = uuid;
    id.label32 = label32;
    id.epoch = epoch;
    id.nominal_length_s = nominal_length_s;
    id.total_chunks = total_chunks;
    id.a_high_water = 0u;
    id.block_count = dev->block_count;
    raw_sb_final(pri, &id);
    if (raw_write_flush(dev, mirror_lba, pri) != 0) { return TAPE_ERR_IO; }
    if (raw_write_flush(dev, TAPE_LBA_SUPERBLOCK, pri) != 0) { return TAPE_ERR_IO; }
    return TAPE_OK;
}

/* ------------------------------------------------------------------------- */
/* §9.5 duplicate                                                            */
/* ------------------------------------------------------------------------- */

/* Interior cut points x in (0, len) where (base + x) is a multiple of 128. */
static uint64_t dup_block_cuts(uint64_t base, uint64_t len)
{
    uint64_t first = (RAW_FRAMES_PER_BLOCK - base % RAW_FRAMES_PER_BLOCK)
                   % RAW_FRAMES_PER_BLOCK;

    if (first == 0u) { first = RAW_FRAMES_PER_BLOCK; }
    if (first >= len) { return 0u; }
    return (len - 1u - first) / RAW_FRAMES_PER_BLOCK + 1u;
}

/*
 * Source reads the compacting copy will issue. Within one entry a piece ends
 * at the entry end, at a source block boundary and at a destination block
 * boundary; the last two coincide when the entry's physical and timeline
 * offsets agree modulo a block. Arithmetic over the index only — no I/O — so
 * blocks_total is known at initiation without walking the timeline.
 */
static uint64_t dup_copy_reads(const struct tape_index *idx)
{
    uint64_t reads = 0u, timeline = 0u;
    uint32_t i;

    for (i = 0u; i < idx->entry_count; i++) {
        const struct tape_entry *e = &idx->entries[i];
        uint64_t phys = (uint64_t)e->first_chunk_id * TAPE_CHUNK_FRAMES + e->start_frame;
        uint64_t len = e->frame_count;

        reads += 1u + dup_block_cuts(timeline, len);
        if ((phys - timeline) % RAW_FRAMES_PER_BLOCK != 0u) {
            reads += dup_block_cuts(phys, len);
        }
        timeline += len;
    }
    return reads;
}

static void dup_end(tape *t)
{
    t->dup_in_progress = false;
    t->dup_phase = 0u;
    t->dup_zero_next = 0u;
    t->dup_copy_block = 0u;
    t->dup_copy_frame = 0u;
}

static void dup_begin(tape *t, const tape_dev *dst, const uint8_t uuid[16],
                      uint32_t epoch, uint32_t nominal, uint32_t total_chunks)
{
    uint64_t frames = t->idx[TAPE_SIDE_A].total_frames;
    uint64_t blocks = (frames + RAW_FRAMES_PER_BLOCK - 1u) / RAW_FRAMES_PER_BLOCK;
    uint64_t total;

    t->dup_dev = *dst;
    memcpy(t->dup_uuid, uuid, 16u);
    t->dup_epoch = epoch;
    t->dup_nominal = nominal;
    t->dup_total_chunks = total_chunks;
    t->dup_copy_blocks = (uint32_t)blocks;
    t->dup_copy_block = 0u;
    t->dup_copy_frame = 0u;
    t->dup_zero_next = 0u;
    t->dup_done = 0u;

    /* 2 classification reads + 2 step-1 writes + 4 slot zeros + the copy +
       entries/header per slot (header only when empty) + 2 superblocks. A
       blank destination later drops the two step-1 writes. */
    total = 2u + 2u + 4u + 2u;
    if (frames != 0u) {
        total += dup_copy_reads(&t->idx[TAPE_SIDE_A]) + blocks + 4u;
    } else {
        total += 2u;
    }
    t->dup_total = (total > 0xFFFFFFFFu) ? 0xFFFFFFFFu : (uint32_t)total;

    t->dup_phase = DUP_PHASE_READ_PRIMARY;
    t->dup_in_progress = true;
}

/*
 * §9.5 step 3's compacting copy, one budget unit per source read and per
 * destination write (flushes are barriers, not blocks — the promote.c
 * convention). mix_block carries a partially assembled destination block
 * across calls so a small budget never repeats a read or a write.
 */
static tape_result dup_copy(tape *t, uint32_t budget, uint32_t *used, bool *done)
{
    const struct tape_index *src = &t->idx[TAPE_SIDE_A];

    *done = false;
    while (t->dup_copy_block < t->dup_copy_blocks) {
        uint64_t f = (uint64_t)t->dup_copy_block * RAW_FRAMES_PER_BLOCK
                   + t->dup_copy_frame;

        if (t->dup_copy_frame == 0u) {
            memset(t->mix_block, 0, TAPE_BLOCK_SIZE);
        }

        if (t->dup_copy_frame < RAW_FRAMES_PER_BLOCK && f < src->total_frames) {
            uint64_t physical, source_lba;
            uint32_t run, offset, take;

            if (*used >= budget) { return TAPE_OK; }
            if (!tape_timeline_physical(src, f, &physical)) {
                return TAPE_ERR_INCONSISTENT;
            }
            run = tape_timeline_run(src, f);
            if (run == 0u) { return TAPE_ERR_INCONSISTENT; }

            offset = (uint32_t)(physical % RAW_FRAMES_PER_BLOCK);
            take = RAW_FRAMES_PER_BLOCK - t->dup_copy_frame;
            if (take > RAW_FRAMES_PER_BLOCK - offset) { take = RAW_FRAMES_PER_BLOCK - offset; }
            if (take > run) { take = run; }
            if ((uint64_t)take > src->total_frames - f) {
                take = (uint32_t)(src->total_frames - f);
            }

            source_lba = (uint64_t)t->sb.lba_chunk_base + physical / RAW_FRAMES_PER_BLOCK;
            if (source_lba >= (uint64_t)t->dev.block_count) { return TAPE_ERR_GEOMETRY; }
            /* A source READ failure is not an indeterminate write: the source
               is not faulted, the duplicate simply ends. */
            if (dev_read(&t->dev, (uint32_t)source_lba, 1u, t->block) != 0) {
                return TAPE_ERR_IO;
            }
            (*used)++;
            t->dup_done++;
            memcpy(t->mix_block + (size_t)t->dup_copy_frame * TAPE_FRAME_BYTES,
                   t->block + (size_t)offset * TAPE_FRAME_BYTES,
                   (size_t)take * TAPE_FRAME_BYTES);
            t->dup_copy_frame += take;
            continue;
        }

        /* Block complete (the last one's tail was zeroed when it began). */
        t->dup_copy_frame = RAW_FRAMES_PER_BLOCK;
        if (*used >= budget) { return TAPE_OK; }
        if (dev_write(&t->dup_dev, TAPE_LBA_CHUNK_BASE + t->dup_copy_block, 1u,
                      t->mix_block) != 0) {
            return TAPE_ERR_IO;
        }
        (*used)++;
        t->dup_done++;
        t->dup_copy_block++;
        t->dup_copy_frame = 0u;
    }

    if (dev_flush(&t->dup_dev) != 0) { return TAPE_ERR_IO; }
    *done = true;
    return TAPE_OK;
}

/* One destination block write + flush, counted as one budget unit. */
static tape_result dup_put(tape *t, uint32_t lba, const unsigned char *blk, uint32_t *used)
{
    if (raw_write_flush(&t->dup_dev, lba, blk) != 0) { return TAPE_ERR_IO; }
    (*used)++;
    t->dup_done++;
    return TAPE_OK;
}

/*
 * Advance the duplicate by at most `budget` blocks. Every phase is at most one
 * block, or the copy (which splits at single blocks), so any budget >= 1 makes
 * progress and the loop terminates (engine-api §9.1, V5-011).
 *
 * No destination failure touches t->faulted: the source's media is determinate
 * (§7.2's second exclusion). An if/else chain, not a switch, for the
 * indirect-call gate's link-time backstop.
 */
static tape_result dup_run(tape *t, uint32_t budget, uint32_t *used)
{
    const tape_dev *d = &t->dup_dev;
    uint32_t mirror_lba = d->block_count - 1u;
    uint64_t frames = t->idx[TAPE_SIDE_A].total_frames;
    tape_result rc;

    while (t->dup_in_progress && *used < budget) {
        uint8_t ph = t->dup_phase;

        if (ph == DUP_PHASE_READ_PRIMARY) {
            if (dev_read(d, TAPE_LBA_SUPERBLOCK, 1u, t->dup_sb) != 0) { return TAPE_ERR_IO; }
            (*used)++;
            t->dup_done++;
            t->dup_phase = DUP_PHASE_READ_MIRROR;
        } else if (ph == DUP_PHASE_READ_MIRROR) {
            struct raw_plan plan;

            if (dev_read(d, mirror_lba, 1u, t->block) != 0) { return TAPE_ERR_IO; }
            (*used)++;
            t->dup_done++;
            raw_classify(t->dup_sb, t->block, mirror_lba, &plan);
            t->dup_first_lba = plan.first_lba;
            t->dup_second_lba = plan.second_lba;
            if (plan.kind == RAW_STEP1_SKIP) {
                t->dup_total -= 2u;
                t->dup_phase = DUP_PHASE_ZERO_SLOTS;
            } else {
                t->dup_phase = DUP_PHASE_STEP1_FIRST;
            }
        } else if (ph == DUP_PHASE_STEP1_FIRST) {
            rc = dup_put(t, t->dup_first_lba, t->dup_sb, used);
            if (rc != TAPE_OK) { return rc; }
            t->dup_phase = DUP_PHASE_STEP1_SECOND;
        } else if (ph == DUP_PHASE_STEP1_SECOND) {
            rc = dup_put(t, t->dup_second_lba, t->dup_sb, used);
            if (rc != TAPE_OK) { return rc; }
            t->dup_phase = DUP_PHASE_ZERO_SLOTS;
        } else if (ph == DUP_PHASE_ZERO_SLOTS) {
            /* Step 2: A0, A1, B0, B1 block 0 zeroed; one flush after all four. */
            uint32_t lba;

            if (t->dup_zero_next == 0u)      { lba = TAPE_LBA_INDEX_A0; }
            else if (t->dup_zero_next == 1u) { lba = TAPE_LBA_INDEX_A1; }
            else if (t->dup_zero_next == 2u) { lba = TAPE_LBA_INDEX_B0; }
            else                             { lba = TAPE_LBA_INDEX_B1; }
            memset(t->block, 0, TAPE_BLOCK_SIZE);
            if (dev_write(d, lba, 1u, t->block) != 0) { return TAPE_ERR_IO; }
            (*used)++;
            t->dup_done++;
            t->dup_zero_next++;
            if (t->dup_zero_next == 4u) {
                if (dev_flush(d) != 0) { return TAPE_ERR_IO; }
                t->dup_phase = (frames != 0u) ? DUP_PHASE_COPY : DUP_PHASE_A0_HEADER;
            }
        } else if (ph == DUP_PHASE_COPY) {
            bool done = false;

            rc = dup_copy(t, budget, used, &done);
            if (rc != TAPE_OK) { return rc; }
            if (done) { t->dup_phase = DUP_PHASE_A0_ENTRIES; }
        } else if (ph == DUP_PHASE_A0_ENTRIES) {
            raw_index_entries(t->block, frames);
            rc = dup_put(t, TAPE_LBA_INDEX_A0 + 1u, t->block, used);
            if (rc != TAPE_OK) { return rc; }
            t->dup_phase = DUP_PHASE_A0_HEADER;
        } else if (ph == DUP_PHASE_A0_HEADER) {
            raw_index_header(t->block, (uint8_t)TAPE_SIDE_A, 1u, frames);
            rc = dup_put(t, TAPE_LBA_INDEX_A0, t->block, used);
            if (rc != TAPE_OK) { return rc; }
            t->dup_phase = (frames != 0u) ? DUP_PHASE_B0_ENTRIES : DUP_PHASE_B0_HEADER;
        } else if (ph == DUP_PHASE_B0_ENTRIES) {
            raw_index_entries(t->block, frames);
            rc = dup_put(t, TAPE_LBA_INDEX_B0 + 1u, t->block, used);
            if (rc != TAPE_OK) { return rc; }
            t->dup_phase = DUP_PHASE_B0_HEADER;
        } else if (ph == DUP_PHASE_B0_HEADER) {
            raw_index_header(t->block, (uint8_t)TAPE_SIDE_B, 2u, frames);
            rc = dup_put(t, TAPE_LBA_INDEX_B0, t->block, used);
            if (rc != TAPE_OK) { return rc; }
            t->dup_phase = DUP_PHASE_SB_MIRROR;
        } else if (ph == DUP_PHASE_SB_MIRROR || ph == DUP_PHASE_SB_PRIMARY) {
            /* Step 4: identity assignment, mirror then primary. The label is a
               byte copy of the source superblock's (V7-004); geometry is the
               destination's own; a_high_water is len_A. */
            struct raw_identity id;

            id.uuid = t->dup_uuid;
            id.label32 = t->sb_block + 88;
            id.epoch = t->dup_epoch;
            id.nominal_length_s = t->dup_nominal;
            id.total_chunks = t->dup_total_chunks;
            id.a_high_water = tape_chunks_for_frames(frames);
            id.block_count = d->block_count;
            raw_sb_final(t->block, &id);
            rc = dup_put(t, (ph == DUP_PHASE_SB_MIRROR) ? mirror_lba : TAPE_LBA_SUPERBLOCK,
                         t->block, used);
            if (rc != TAPE_OK) { return rc; }
            if (ph == DUP_PHASE_SB_MIRROR) {
                t->dup_phase = DUP_PHASE_SB_PRIMARY;
            } else {
                dup_end(t);
            }
        } else {
            return TAPE_ERR_INCONSISTENT;
        }
    }
    return TAPE_OK;
}

tape_result tape_dup(tape *src, const tape_dev *dst_dev,
                     const uint8_t new_uuid[16], uint32_t epoch,
                     uint32_t dst_nominal_length_s,
                     uint32_t block_budget, bool *more_work,
                     tape_progress_fn cb, void *user)
{
    uint32_t used = 0u;
    tape_result rc;

    if (src == NULL || dst_dev == NULL || more_work == NULL) {
        return TAPE_ERR_INVALID_ARG;
    }
    /* engine-api §9.1: re-entry from a progress callback is BUSY with no state
       change, and never ends the operation. */
    if (src->in_callback) {
        *more_work = src->dup_in_progress;
        return TAPE_ERR_BUSY;
    }
    *more_work = false;

    /* §10 source row. A duplicate in progress is the ✓ continuation cell. */
    if (!src->mounted) { return TAPE_ERR_NOT_MOUNTED; }
    if (src->faulted) { return TAPE_ERR_FAULTED; }
    if (src->rec_armed || src->promote_in_progress) { return TAPE_ERR_BUSY; }

    /* §9.1: zero budget after the state matrix, no state change. */
    if (block_budget == 0u) {
        *more_work = src->dup_in_progress;
        return TAPE_ERR_INVALID_ARG;
    }

    if (src->dup_in_progress) {
        /* §9.1 argument stability: dst_dev (by ctx), new_uuid, epoch and
           dst_nominal_length_s are fixed; budget, more_work, cb, user are not.
           A mismatch does no work and leaves the operation in progress. */
        if (!dev_same_context(&src->dup_dev, dst_dev) || new_uuid == NULL
            || memcmp(src->dup_uuid, new_uuid, 16u) != 0
            || src->dup_epoch != epoch
            || src->dup_nominal != dst_nominal_length_s) {
            *more_work = true;
            return TAPE_ERR_INVALID_ARG;
        }
    } else {
        uint32_t dst_total_chunks;
        uint32_t need_chunks;
        uint64_t source_frames;

        /* §9.5 refusal preconditions 1..4 — exact normative order, all before
           any destination superblock read and all with zero writes. */

        /* 1. Aliasing. tape_dev exposes ctx as the available device identity. */
        if (dev_same_context(&src->dev, dst_dev)) { return TAPE_ERR_INVALID_ARG; }

        /* 2. Destination writability. */
        if (dst_dev->write == NULL) { return TAPE_ERR_READ_ONLY; }

        /* 3. Destination geometry, including DEVICE_ADDRESSABLE. */
        rc = tape_geometry_ok(dst_nominal_length_s, dst_dev->block_count,
                              &dst_total_chunks);
        if (rc != TAPE_OK) { return rc; }

        /* 4. Side-A capacity. Mount has already validated the source timeline. */
        source_frames = src->idx[TAPE_SIDE_A].total_frames;
        need_chunks = tape_chunks_for_frames(source_frames);
        if (source_frames > (uint64_t)TAPE_MAX_TOTAL_FRAMES
            || need_chunks > dst_total_chunks) {
            return TAPE_ERR_DEST_TOO_SMALL;
        }

        /* Caller-argument validity, still before any destination callback. */
        if (new_uuid == NULL || dst_dev->read == NULL || dst_dev->flush == NULL) {
            return TAPE_ERR_INVALID_ARG;
        }

        dup_begin(src, dst_dev, new_uuid, epoch, dst_nominal_length_s,
                  dst_total_chunks);
    }

    rc = dup_run(src, block_budget, &used);
    if (rc != TAPE_OK) {
        /* §9.1 termination; the source stays in its transport state (V6-006). */
        dup_end(src);
        *more_work = false;
        return rc;
    }

    *more_work = src->dup_in_progress;
    if (cb != NULL) {
        src->in_callback = true;
        dev_progress(cb, user, src->dup_done, src->dup_total);
        src->in_callback = false;
    }
    return TAPE_OK;
}
