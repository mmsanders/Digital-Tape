/*
 * dev.h — the ONLY sanctioned indirect call sites in the engine.
 *
 * Guardrail 09 says the engine knows nothing about hardware and that two
 * function pointers are the entire coupling. The invariant that actually
 * expresses that is:
 *
 *     every indirect call in the engine targets a tape_dev callback
 *
 * That is not decidable by inspecting disassembly — an optimiser can turn a
 * callback into a jump, and a jump table into something that looks like one.
 * So it is made decidable by construction instead: every indirect call goes
 * through one of the three wrappers below, and a source-level gate
 * (tools/ci/audit-indirect.sh) asserts that nothing else in the engine
 * dereferences a tape_dev member.
 *
 * If you find yourself wanting to call d->read directly, that is the gate
 * doing its job. Add a wrapper here or escalate; do not reach past it.
 */

#ifndef TAPE_SRC_DEV_H
#define TAPE_SRC_DEV_H

#include "tape_dev.h"

/*
 * Guardrail 06: a write reaching a read-only device must be a loud crash, not
 * a quiet error code. In debug builds we trap deliberately so a test dies at
 * the offending call. In release we do nothing and the NULL dereference below
 * kills the process just as loudly.
 *
 * __builtin_trap rather than assert(): assert writes to stderr through libc,
 * and guardrail 08 forbids libc file I/O in the engine. This costs no
 * dependency at all.
 */
#ifndef NDEBUG
#  define TAPE_TRAP_IF(cond) do { if (cond) { __builtin_trap(); } } while (0)
#else
#  define TAPE_TRAP_IF(cond) ((void)0)
#endif

static inline int dev_read(const struct tape_dev *d,
                           uint32_t lba, uint32_t count, void *buf)
{
    return d->read(d->ctx, lba, count, buf);
}

static inline int dev_write(const struct tape_dev *d,
                            uint32_t lba, uint32_t count, const void *buf)
{
    /* Debug: trap at the call. Release: dereference NULL and die. Never an
       error return — an error return here would let a caller carry on. */
    TAPE_TRAP_IF(d->write == NULL);
    return d->write(d->ctx, lba, count, buf);
}

static inline int dev_flush(const struct tape_dev *d)
{
    return d->flush(d->ctx);
}

#endif /* TAPE_SRC_DEV_H */
