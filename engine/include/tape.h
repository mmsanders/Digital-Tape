/*
 * tape.h — Digital Tape engine, public API.
 *
 * STATUS: stub. The API is defined by spec/engine-api.md (WP-03), which is not yet
 * written. Nothing is declared here on purpose — a speculative API would be implemented
 * against before the spec froze, which is exactly the failure mode the Phase 0 gate exists
 * to prevent.
 *
 * Standing constraints on everything that will go in this file:
 *
 *   - C99. No dependency beyond libc.
 *   - No allocation after init. No malloc, no recursion, no libc file I/O.
 *     Applies to the desktop build too. Static budget under 200 KB, asserted in CI.
 *   - No function returns a heap pointer.
 *   - No #ifdef naming a board, chip or peripheral. The engine knows nothing about
 *     hardware; two function pointers for block read and write are the entire coupling.
 *   - The source slot is constructed with a NULL write pointer. A write attempt is a
 *     crash in test, not a corruption in the field. Not a permission check. Not an if.
 *   - Side A immutability is structural: allocation below a high-water mark, never a flag.
 *
 * See CLAUDE.md §1 for the full guardrail set and why each one breaks when "improved".
 */

#ifndef TAPE_H
#define TAPE_H

/* Intentionally empty. Fills in at WP-03/WP-06. */

#endif /* TAPE_H */
