#include "crash_harness.h"

#include <stddef.h>
#include <string.h>

static void record_case(const crash_scenario *scenario,
                        crash_run_stats *stats,
                        crash_case_result *result)
{
    if (result->remount_result != 0) {
        ++result->invariant_failures;
    }
    result->invariant_failures += scenario->validate(scenario->ctx, result);
    ++stats->cases_run;
    if (result->invariant_failures == 0u && result->fault_fired) {
        ++stats->cases_passed;
    } else {
        ++stats->cases_failed;
    }
    if (scenario->report != NULL) {
        scenario->report(scenario->ctx, result);
    }
}

static int run_fault_case(const crash_scenario *scenario,
                          crash_run_stats *stats,
                          crash_case_kind kind,
                          uint64_t ordinal,
                          uint16_t landed_bytes)
{
    crash_case_result result;
    fault_plan plan;

    if (scenario->prepare(scenario->ctx) != 0) {
        return -1;
    }
    fault_dev_reset_trace(scenario->device);

    plan.target_ordinal = ordinal;
    plan.torn_bytes = landed_bytes;
    if (kind == CRASH_AT_FLUSH) {
        plan.kind = FAULT_FLUSH;
    } else if (landed_bytes == 0u) {
        plan.kind = FAULT_BEFORE_BLOCK;
    } else {
        plan.kind = FAULT_TORN_BLOCK;
    }
    fault_dev_arm(scenario->device, plan);

    memset(&result, 0, sizeof(result));
    result.kind = kind;
    result.target_ordinal = ordinal;
    result.landed_bytes = landed_bytes;
    result.operation_result = scenario->operate(scenario->ctx);
    result.fault_fired = scenario->device->fault_fired ? 1 : 0;
    fault_dev_power_cut(scenario->device);
    result.remount_result = scenario->remount(scenario->ctx);
    record_case(scenario, stats, &result);
    return result.fault_fired ? 0 : -1;
}

int crash_run_exhaustive(const crash_scenario *scenario,
                         crash_run_stats *stats)
{
    crash_case_result baseline;
    uint64_t block;
    uint64_t flush;
    uint16_t landed;

    if (scenario == NULL || stats == NULL || scenario->device == NULL ||
        scenario->prepare == NULL || scenario->operate == NULL ||
        scenario->remount == NULL || scenario->validate == NULL) {
        return -1;
    }
    memset(stats, 0, sizeof(*stats));

    if (scenario->prepare(scenario->ctx) != 0) {
        return -1;
    }
    fault_dev_disarm(scenario->device);
    fault_dev_reset_trace(scenario->device);
    memset(&baseline, 0, sizeof(baseline));
    baseline.kind = CRASH_BASELINE;
    baseline.operation_result = scenario->operate(scenario->ctx);
    if (baseline.operation_result != 0) {
        return -1;
    }
    stats->baseline_block_writes = scenario->device->block_writes_seen;
    stats->baseline_flushes = scenario->device->flushes_seen;
    baseline.fault_fired = 1;
    baseline.remount_result = scenario->remount(scenario->ctx);
    record_case(scenario, stats, &baseline);

    for (block = 0u; block < stats->baseline_block_writes; ++block) {
        if (run_fault_case(scenario, stats, CRASH_BEFORE_BLOCK,
                           block, 0u) != 0) {
            return -1;
        }
        for (landed = 1u; landed < FAULT_BLOCK_SIZE; ++landed) {
            if (run_fault_case(scenario, stats, CRASH_TORN_BLOCK,
                               block, landed) != 0) {
                return -1;
            }
        }
        if (run_fault_case(scenario, stats, CRASH_AFTER_FULL_BLOCK,
                           block, FAULT_BLOCK_SIZE) != 0) {
            return -1;
        }
    }
    for (flush = 0u; flush < stats->baseline_flushes; ++flush) {
        if (run_fault_case(scenario, stats, CRASH_AT_FLUSH,
                           flush, 0u) != 0) {
            return -1;
        }
    }
    return stats->cases_failed == 0u ? 0 : 1;
}
