#ifndef CRASH_HARNESS_H
#define CRASH_HARNESS_H

#include "fault_block_device.h"

#include <stdint.h>

typedef enum {
    CRASH_BASELINE = 0,
    CRASH_BEFORE_BLOCK,
    CRASH_TORN_BLOCK,
    CRASH_AFTER_FULL_BLOCK,
    CRASH_AT_FLUSH
} crash_case_kind;

typedef struct {
    crash_case_kind kind;
    uint64_t target_ordinal;
    uint16_t landed_bytes;
    int operation_result;
    int remount_result;
    uint32_t invariant_failures;
    int fault_fired;
} crash_case_result;

typedef struct {
    uint64_t baseline_block_writes;
    uint64_t baseline_flushes;
    uint64_t cases_run;
    uint64_t cases_passed;
    uint64_t cases_failed;
} crash_run_stats;

typedef int (*crash_prepare_fn)(void *ctx);
typedef int (*crash_operation_fn)(void *ctx);
typedef int (*crash_remount_fn)(void *ctx);
typedef uint32_t (*crash_validate_fn)(void *ctx,
                                      const crash_case_result *result);
typedef void (*crash_report_fn)(void *ctx,
                                const crash_case_result *result);

typedef struct {
    fault_block_device *device;
    void *ctx;
    crash_prepare_fn prepare;
    crash_operation_fn operate;
    crash_remount_fn remount;
    crash_validate_fn validate;
    crash_report_fn report;
} crash_scenario;

/*
 * Runs a clean baseline, then every block-write outcome (0..512 landed
 * bytes) and every flush failure observed in that baseline. No allocation.
 * Returns 0 when infrastructure and all invariants pass, 1 when one or more
 * cases violate invariants/remount, and -1 for invalid setup/nonrepeatable I/O.
 */
int crash_run_exhaustive(const crash_scenario *scenario,
                         crash_run_stats *stats);

#endif
