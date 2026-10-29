/*
 * tseam.h — the TAPECTL_TEST observation and fault seam (ADR-164 §5; #392).
 *
 * COMPILED ONLY WITH -DTAPECTL_TEST, into build/host/tapectl-test. The shipped
 * build/host/tapectl contains none of it; host/test_seam.sh checks the symbols
 * and configuration strings are absent there and present in the test binary.
 *
 * Observation (TAPECTL_TEST_TRACE=FILE) records, in Verification's normalized
 * wp14-trace-1 shape, what the program actually does:
 *   open / write_open   every port open, with its mode and result
 *   read                port reads: absolute offset, bytes, OS result, the
 *                       phase (layout/mount/service/other) and, for service
 *                       reads, side, frame and whether a chunk was read.
 *                       Adjacent successful reads with the same context are
 *                       JOINED into one event (`calls` = how many reads); a
 *                       failed read is always its own event.
 *   write               every port write, never joined: absolute offset,
 *                       bytes, issued_before_return, coalesced:false, OS
 *                       result. Payload (data_hex) for every write of a
 *                       provision, or of any command with TAPECTL_TEST_PAYLOADS=1.
 *   flush               os_call, os_success, os_error, success (what the port
 *                       reported) and, for the macOS raw-device fallback,
 *                       fullfsync_unsupported (ENOTTY/ENOTSUP, as observed).
 *   engine_bind         every tape_dev handed to the engine: write_is_null
 *   engine_mount        each tape_mount: side, cold, the returned result
 *   engine_info         each tape_get_info after a mount: needs_repair,
 *                       side_b_valid
 *   unmount             each own-partition-1 unmount: OS call and result
 *   media_query         make only: a required media query that failed (the
 *                       probe's facts, or the geometry query of the device
 *                       open) and its OS error
 * plus target, target_kind, device facts and policy, refusal, engine_used,
 * exit and build identity. The engine is not instrumented: its calls are
 * observed at the existing public API call sites in tapectl.
 *
 * Faults (TAPECTL_TEST_FAULT=...), each making the test binary wrong in one
 * way. Where a control needs an OS failure, the OS call is really made on an
 * invalid handle and really fails:
 *   noop-flush             flush reports success and calls no OS barrier
 *   hidden-flush-error     the barrier fails in the OS; reported as success
 *   native-flush-error     the barrier fails in the OS; failure propagates
 *   nonnull-binding        read-only engine bindings get a write callback
 *   read-error:LBA         an engine read covering partition LBA fails (real
 *                          failed OS read); read-error:LBA@PHASE only during
 *                          that make phase (e.g. @verify)
 *   target-read-error:LBA  a port read covering absolute target LBA fails
 *                          (real failed OS read), e.g. 0 for LBA 0
 *   unmount-error          the own-partition-1 unmount is a real OS call on
 *                          an invalid target, and fails
 *   query-error:POINT      a required media query is really issued so that the
 *                          OS fails it (a zero-size result buffer on Windows; a
 *                          missing sysfs file or NULL result pointer on Linux):
 *                          POINT is disk-length (the probe's capacity query) or
 *                          open-geometry (the authorized open's own query)
 *   typed-error:NAME       TYPED, not OS-generated: the census extents answer of
 *                          a volume on the target (not-ready-target) or on another
 *                          device (not-ready-other) is replaced by ERROR_NOT_READY
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
void tseam_read(uint64_t offset, size_t bytes, int ok, const char *os_error, const char *fault);
void tseam_write(uint64_t offset, size_t bytes, const void *data, int ok);
void tseam_flush(const char *os_call, int os_success, const char *os_error, int success,
                 const char *fullfsync_unsupported, const char *fault);
void tseam_bind(uint64_t base_lba, uint32_t blocks, int write_is_null);
void tseam_unmount(const char *where, const char *os_call, int ok, const char *os_error, const char *fault);

/* make (APP-1 §3) only, so no other command's trace changes:
   make_safety_pass, make_phase (provision/load/commit/verify, with the
   current write binding), make_media_change (phase, the OS error that the
   port classified as removal/change, and stdout bytes written so far) and
   make_close. tseam_make_pause: with TAPECTL_TEST_PAUSE=PHASE:DIR, at the
   start of PHASE create DIR/ready and wait for DIR/go, so a CI fixture can
   remove or swap the device at an exact boundary. Real I/O then detects it. */
void tseam_make(const char *kind, const char *phase, const char *os_error, int write_is_null);
void tseam_make_pause(const char *phase);
void tseam_query(const char *point, const char *os_error);

/* Engine call sites in tapectl. */
void tseam_engine_used(void);
void tseam_phase(const char *phase, char side, int64_t frame);   /* side 0 = none, frame -1 = n/a */
void tseam_mount(char side, int cold, const char *result);
void tseam_info(char side, int needs_repair, int side_b_valid);
void tseam_set_view_base(uint64_t base_lba);                     /* for chunk classification */

int  tseam_fault_noop_flush(void);
int  tseam_fault_hidden_flush_error(void);
int  tseam_fault_native_flush_error(void);
int  tseam_fault_nonnull_binding(void);
int  tseam_fault_read(uint64_t partition_lba, uint32_t count);
int  tseam_fault_target_read(uint64_t offset, size_t bytes);
int  tseam_fault_unmount(void);
int  tseam_fault_query(const char *point);
int  tseam_fault_typed(const char *name);

/* hport.c: a real failed OS read at `off` (used by the read-error control). */
struct hport;
int  hport_read_failing(struct hport *p, uint64_t off, void *buf, size_t len);

#endif /* TAPECTL_TEST */
#endif /* HOST_TSEAM_H */
