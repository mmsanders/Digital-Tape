#ifndef FAULT_BLOCK_DEVICE_H
#define FAULT_BLOCK_DEVICE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define FAULT_BLOCK_SIZE 512u

typedef enum {
    FAULT_NONE = 0,
    FAULT_BEFORE_BLOCK,
    FAULT_TORN_BLOCK,
    FAULT_FLUSH
} fault_kind;

typedef struct {
    fault_kind kind;
    uint64_t target_ordinal;
    uint16_t torn_bytes;
} fault_plan;

typedef struct {
    uint8_t *durable;
    uint8_t *working;
    size_t storage_len;
    uint32_t block_count;
    uint64_t block_writes_seen;
    uint64_t flushes_seen;
    fault_plan plan;
    bool fault_fired;
    bool write_through;
} fault_block_device;

int fault_dev_init(fault_block_device *dev,
                   uint8_t *durable,
                   uint8_t *working,
                   size_t storage_len,
                   uint32_t block_count);
void fault_dev_arm(fault_block_device *dev, fault_plan plan);
void fault_dev_disarm(fault_block_device *dev);
void fault_dev_reset_trace(fault_block_device *dev);
void fault_dev_set_write_through(fault_block_device *dev, bool enabled);
void fault_dev_power_cut(fault_block_device *dev);

int fault_dev_read(void *ctx, uint32_t lba, uint32_t count, void *dst);
int fault_dev_write(void *ctx, uint32_t lba, uint32_t count, const void *src);
int fault_dev_flush(void *ctx);

#endif
