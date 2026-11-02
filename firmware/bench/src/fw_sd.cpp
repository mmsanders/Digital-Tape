/*
 * fw_sd.cpp — the Teensy 4.1 built-in microSD slot as a whole-card tape_dev.
 * See fw_sd.h. Raw sectors through SdFat's SdioCard; no filesystem is mounted.
 */

#include <Arduino.h>
#include <SdFat.h>

#include "fw_sd.h"

/* How long flush waits for the card to leave busy before it reports failure.
   The engine has no clock (guardrail 09); the caller owns this policy, and a
   failed flush puts the engine in its §7.2 quarantine, which is the safe side. */
#define FW_SD_BUSY_LIMIT_MS 2000u

static SdioCard g_card;

static int sd_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    (void)ctx;
    return g_card.readSectors(lba, static_cast<uint8_t *>(dst), count) ? 0 : 1;
}

/* fw_part issues one block per call; a larger count is still honoured one
   sector at a time, so this device never batches either. */
static int sd_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    const uint8_t *b = static_cast<const uint8_t *>(src);
    (void)ctx;
    for (uint32_t i = 0; i < count; i++) {
        if (!g_card.writeSector(lba + i, b + i * TAPE_BLOCK_SIZE)) { return 1; }
    }
    return 0;
}

/* engine-api §3: success only once the card has left the busy state, not when
   it has merely accepted the blocks. In FIFO mode SdioCard::isBusy() tracks
   only the host transfer, so this asks the card itself: CMD13 until it reports
   the `tran` state (no programming in progress) with READY_FOR_DATA set
   (SD Physical Layer spec, card status bits 12:9 and 8). */
#define FW_SD_STATE(s)       (((s) >> 9) & 0xFu)
#define FW_SD_STATE_TRAN     4u
#define FW_SD_READY_FOR_DATA (1u << 8)

static int sd_flush(void *ctx)
{
    (void)ctx;
    if (!g_card.syncDevice()) { return 1; }
    uint32_t t0 = millis();
    for (;;) {
        uint32_t s = g_card.status();       /* 0: the card did not answer */
        if (s == 0) { return 1; }
        if (FW_SD_STATE(s) == FW_SD_STATE_TRAN && (s & FW_SD_READY_FOR_DATA)) { return 0; }
        if (millis() - t0 > FW_SD_BUSY_LIMIT_MS) { return 1; }
        yield();
    }
}

extern "C" int fw_sd_begin(tape_dev *card)
{
    if (!g_card.begin(SdioConfig(FIFO_SDIO))) { return -1; }
    card->read = sd_read;
    card->write = sd_write;
    card->flush = sd_flush;
    card->ctx = nullptr;
    card->block_count = g_card.sectorCount();
    return card->block_count == 0 ? -1 : 0;
}

extern "C" int fw_sd_present(void)
{
    /* CMD13. SdioCard::status() returns 0 when the card does not answer. */
    return g_card.status() != 0;
}
