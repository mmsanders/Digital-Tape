#include "fault_block_device.h"

#include <assert.h>
#include <string.h>

enum { TEST_BLOCKS = 3 };

static void fill(uint8_t *p, size_t n, uint8_t value)
{
    memset(p, value, n);
}

int main(void)
{
    uint8_t durable[TEST_BLOCKS * FAULT_BLOCK_SIZE];
    uint8_t working[TEST_BLOCKS * FAULT_BLOCK_SIZE];
    uint8_t input[2 * FAULT_BLOCK_SIZE];
    uint8_t output[FAULT_BLOCK_SIZE];
    fault_block_device dev;
    fault_plan plan;

    fill(durable, sizeof(durable), 0x11u);
    fill(input, sizeof(input), 0x22u);
    assert(fault_dev_init(&dev, durable, working, sizeof(durable), TEST_BLOCKS) == 0);

    assert(fault_dev_write(&dev, 0u, 1u, input) == 0);
    assert(fault_dev_read(&dev, 0u, 1u, output) == 0);
    assert(output[0] == 0x22u);
    fault_dev_power_cut(&dev);
    assert(fault_dev_read(&dev, 0u, 1u, output) == 0);
    assert(output[0] == 0x11u);

    fault_dev_set_write_through(&dev, true);
    assert(fault_dev_write(&dev, 0u, 1u, input) == 0);
    fault_dev_power_cut(&dev);
    assert(fault_dev_read(&dev, 0u, 1u, output) == 0);
    assert(output[0] == 0x22u);
    fault_dev_set_write_through(&dev, false);

    assert(fault_dev_write(&dev, 0u, 1u, input) == 0);
    assert(fault_dev_flush(&dev) == 0);
    fault_dev_power_cut(&dev);
    assert(fault_dev_read(&dev, 0u, 1u, output) == 0);
    assert(output[0] == 0x22u);

    fault_dev_disarm(&dev);
    plan.kind = FAULT_BEFORE_BLOCK;
    plan.target_ordinal = dev.block_writes_seen + 1u;
    plan.torn_bytes = 0u;
    fault_dev_arm(&dev, plan);
    assert(fault_dev_write(&dev, 1u, 2u, input) != 0);
    assert(dev.fault_fired);
    assert(working[FAULT_BLOCK_SIZE] == 0x22u);
    assert(working[2u * FAULT_BLOCK_SIZE] == 0x11u);

    fault_dev_power_cut(&dev);
    plan.kind = FAULT_TORN_BLOCK;
    plan.target_ordinal = dev.block_writes_seen;
    plan.torn_bytes = 17u;
    fault_dev_arm(&dev, plan);
    assert(fault_dev_write(&dev, 2u, 1u, input) != 0);
    fault_dev_power_cut(&dev);
    assert(durable[2u * FAULT_BLOCK_SIZE + 16u] == 0x22u);
    assert(durable[2u * FAULT_BLOCK_SIZE + 17u] == 0x11u);
    assert(working[2u * FAULT_BLOCK_SIZE + 16u] == 0x22u);
    assert(working[2u * FAULT_BLOCK_SIZE + 17u] == 0x11u);

    fault_dev_power_cut(&dev);
    fault_dev_reset_trace(&dev);
    plan.kind = FAULT_FLUSH;
    plan.target_ordinal = 1u;
    plan.torn_bytes = 0u;
    fault_dev_arm(&dev, plan);
    assert(fault_dev_flush(&dev) == 0);
    assert(fault_dev_flush(&dev) != 0);
    assert(dev.flushes_seen == 2u);

    return 0;
}
