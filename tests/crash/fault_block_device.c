#include "fault_block_device.h"

#include <string.h>

static int range_ok(const fault_block_device *dev, uint32_t lba, uint32_t count)
{
    return dev != NULL && count <= dev->block_count &&
           lba <= dev->block_count - count;
}

int fault_dev_init(fault_block_device *dev,
                   uint8_t *durable,
                   uint8_t *working,
                   size_t storage_len,
                   uint32_t block_count)
{
    size_t required;

    if (dev == NULL || durable == NULL || working == NULL ||
        durable == working || block_count == 0u ||
        block_count > storage_len / FAULT_BLOCK_SIZE) {
        return -1;
    }
    required = (size_t)block_count * FAULT_BLOCK_SIZE;
    if (storage_len < required) {
        return -1;
    }

    memset(dev, 0, sizeof(*dev));
    dev->durable = durable;
    dev->working = working;
    dev->storage_len = required;
    dev->block_count = block_count;
    memcpy(working, durable, required);
    return 0;
}

void fault_dev_arm(fault_block_device *dev, fault_plan plan)
{
    if (dev == NULL) {
        return;
    }
    dev->plan = plan;
    dev->fault_fired = false;
}

void fault_dev_disarm(fault_block_device *dev)
{
    fault_plan plan = { FAULT_NONE, 0u, 0u };
    fault_dev_arm(dev, plan);
}

void fault_dev_reset_trace(fault_block_device *dev)
{
    if (dev != NULL) {
        dev->block_writes_seen = 0u;
        dev->flushes_seen = 0u;
        dev->fault_fired = false;
    }
}

void fault_dev_set_write_through(fault_block_device *dev, bool enabled)
{
    if (dev != NULL) {
        dev->write_through = enabled;
    }
}

void fault_dev_power_cut(fault_block_device *dev)
{
    if (dev != NULL) {
        memcpy(dev->working, dev->durable, dev->storage_len);
    }
}

int fault_dev_read(void *ctx, uint32_t lba, uint32_t count, void *dst)
{
    fault_block_device *dev = (fault_block_device *)ctx;
    size_t offset;
    size_t length;

    if (dst == NULL || !range_ok(dev, lba, count)) {
        return -1;
    }
    offset = (size_t)lba * FAULT_BLOCK_SIZE;
    length = (size_t)count * FAULT_BLOCK_SIZE;
    memcpy(dst, dev->working + offset, length);
    return 0;
}

int fault_dev_write(void *ctx, uint32_t lba, uint32_t count, const void *src)
{
    fault_block_device *dev = (fault_block_device *)ctx;
    const uint8_t *input = (const uint8_t *)src;
    uint32_t i;

    if (src == NULL || !range_ok(dev, lba, count)) {
        return -1;
    }

    for (i = 0u; i < count; ++i) {
        size_t offset = (size_t)(lba + i) * FAULT_BLOCK_SIZE;
        const uint8_t *block = input + (size_t)i * FAULT_BLOCK_SIZE;
        uint64_t ordinal = dev->block_writes_seen++;

        if (!dev->fault_fired && ordinal == dev->plan.target_ordinal) {
            if (dev->plan.kind == FAULT_BEFORE_BLOCK) {
                dev->fault_fired = true;
                return -1;
            }
            if (dev->plan.kind == FAULT_TORN_BLOCK) {
                size_t landed = dev->plan.torn_bytes;
                if (landed > FAULT_BLOCK_SIZE) {
                    return -1;
                }
                memcpy(dev->working + offset, block, landed);
                memcpy(dev->durable + offset, block, landed);
                dev->fault_fired = true;
                return -1;
            }
        }
        memcpy(dev->working + offset, block, FAULT_BLOCK_SIZE);
        if (dev->write_through) {
            memcpy(dev->durable + offset, block, FAULT_BLOCK_SIZE);
        }
    }
    return 0;
}

int fault_dev_flush(void *ctx)
{
    fault_block_device *dev = (fault_block_device *)ctx;

    if (dev == NULL) {
        return -1;
    }
    if (!dev->fault_fired && dev->plan.kind == FAULT_FLUSH &&
        dev->flushes_seen == dev->plan.target_ordinal) {
        ++dev->flushes_seen;
        dev->fault_fired = true;
        return -1;
    }
    ++dev->flushes_seen;
    memcpy(dev->durable, dev->working, dev->storage_len);
    return 0;
}
