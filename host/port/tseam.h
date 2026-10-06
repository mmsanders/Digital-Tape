/*
 * tseam.h — the TAPECTL_TEST observation and fault seam (ADR-164, §5).
 *
 * COMPILED ONLY WITH -DTAPECTL_TEST, into build/host/tapectl-test. The shipped
 * build/host/tapectl contains none of it; host/test_seam.sh checks the symbols
 * and configuration strings are absent there and present in the test binary.
 *
 * Observation (TAPECTL_TEST_TRACE=FILE): the host port records what it actually
 * does, from inside the port, in Verification's normalized trace shape:
 *   open / write_open      every hport open, with its mode
 *   write                  every hport write: 64-bit byte offset and length,
 *                          issued before return, never coalesced
 *   flush                  every flush: the OS barrier called, its result, and
 *                          what the port reported
 *   engine_bind            every partition view handed to the engine, and
 *                          whether its write callback is NULL
 *   read_fault             an injected read failure, where it hit
 * plus the device facts and policy verdict, the command, exit status and
 * build identity. The engine itself is not instrumented (engine/ is unchanged).
 *
 * Faults (TAPECTL_TEST_FAULT=...), the controls Verification asked for. Each
 * makes this binary wrong in one way, so a test that cannot see it is shown
 * to be blind:
 *   noop-flush            flush reports success and calls no OS barrier
 *   hidden-flush-error    flush calls the barrier, treats it as failed, and
 *                         reports success anyway
 *   nonnull-binding       verify's engine binding gets a write callback
 *   read-error:LBA        an engine read covering partition-relative LBA fails
 */

#ifndef HOST_TSEAM_H
#define HOST_TSEAM_H

#ifdef TAPECTL_TEST

#include <stddef.h>
#include <stdint.h>

struct device_facts;

void tseam_begin(int argc, char **argv);
int  tseam_finish(int exit_code);                 /* returns exit_code */

void tseam_target(const char *path, int is_device, uint64_t bytes);
void tseam_facts(const struct device_facts *f, const char *verdict, int from_seam);
void tseam_refusal(const char *id);

void tseam_open(const char *path, int is_device, int writable, int ok);
void tseam_write(uint64_t offset, size_t bytes, int ok);
void tseam_flush(const char *os_call, int os_success, int success);
void tseam_bind(uint64_t base_lba, uint32_t blocks, int write_is_null);
void tseam_read_fault(uint64_t lba, uint32_t count);

int  tseam_fault_noop_flush(void);
int  tseam_fault_hidden_flush_error(void);
int  tseam_fault_nonnull_binding(void);
int  tseam_fault_read(uint64_t partition_lba, uint32_t count);

#endif /* TAPECTL_TEST */
#endif /* HOST_TSEAM_H */
