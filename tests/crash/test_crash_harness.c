#include "crash_harness.h"

#include <assert.h>
#include <string.h>

enum { BLOCKS = 2 };

typedef struct {
    fault_block_device dev;
    uint8_t durable[BLOCKS * FAULT_BLOCK_SIZE];
    uint8_t working[BLOCKS * FAULT_BLOCK_SIZE];
    uint8_t input[BLOCKS * FAULT_BLOCK_SIZE];
    uint64_t prepares;
    uint64_t remounts;
    uint64_t reports;
} fixture;

static int prepare(void *opaque)
{
    fixture *f = (fixture *)opaque;
    memset(f->durable, 0x11, sizeof(f->durable));
    memset(f->working, 0x11, sizeof(f->working));
    ++f->prepares;
    return 0;
}

static int operate(void *opaque)
{
    fixture *f = (fixture *)opaque;
    int rc;

    rc = fault_dev_write(&f->dev, 0u, BLOCKS, f->input);
    if (rc != 0) {
        return rc;
    }
    rc = fault_dev_flush(&f->dev);
    if (rc != 0) {
        return rc;
    }
    return fault_dev_flush(&f->dev);
}

static int remount(void *opaque)
{
    fixture *f = (fixture *)opaque;
    ++f->remounts;
    return 0;
}

static uint32_t validate(void *opaque, const crash_case_result *result)
{
    fixture *f = (fixture *)opaque;
    (void)f;
    return result->kind == CRASH_BASELINE && result->operation_result != 0;
}

static void report(void *opaque, const crash_case_result *result)
{
    fixture *f = (fixture *)opaque;
    (void)result;
    ++f->reports;
}

int main(void)
{
    fixture f;
    crash_scenario scenario;
    crash_run_stats stats;

    memset(&f, 0, sizeof(f));
    memset(f.durable, 0x11, sizeof(f.durable));
    memset(f.input, 0x22, sizeof(f.input));
    assert(fault_dev_init(&f.dev, f.durable, f.working,
                          sizeof(f.durable), BLOCKS) == 0);

    scenario.device = &f.dev;
    scenario.ctx = &f;
    scenario.prepare = prepare;
    scenario.operate = operate;
    scenario.remount = remount;
    scenario.validate = validate;
    scenario.report = report;

    assert(crash_run_exhaustive(&scenario, &stats) == 0);
    assert(stats.baseline_block_writes == 2u);
    assert(stats.baseline_flushes == 2u);
    assert(stats.cases_run == 1029u); /* baseline + 2*513 + 2 */
    assert(stats.cases_passed == stats.cases_run);
    assert(stats.cases_failed == 0u);
    assert(f.prepares == stats.cases_run);
    assert(f.remounts == stats.cases_run);
    assert(f.reports == stats.cases_run);
    return 0;
}
