/*
 * harness.h — minimal test scaffolding.
 *
 * SCOPE, and it matters: this is scaffolding, owned by the Software Lead. It is
 * the thing tests run *in*, not tests. `tests/golden/`, `tests/crash/` and
 * `tests/fuzz/` belong to the Verification Lead and are the acceptance
 * authority; nothing here signs anything off.
 *
 * The self-tests under tests/harness/ verify the scaffolding and the ports —
 * the Software Lead's own infrastructure. They are not acceptance tests and
 * must never be cited as one.
 *
 * No framework dependency, on purpose. Test source arriving from the
 * Verification Lead should compile against engine/include/ and this file and
 * nothing else.
 */

#ifndef TAPE_TEST_HARNESS_H
#define TAPE_TEST_HARNESS_H

#include <stdio.h>
#include <string.h>

static int tape_test_failures;
static int tape_test_checks;

#define CHECK(cond)                                                          \
    do {                                                                     \
        tape_test_checks++;                                                  \
        if (!(cond)) {                                                       \
            tape_test_failures++;                                            \
            (void)fprintf(stderr, "  FAIL %s:%d  %s\n",                      \
                          __FILE__, __LINE__, #cond);                        \
        }                                                                    \
    } while (0)

#define CHECK_EQ_U32(got, want)                                              \
    do {                                                                     \
        unsigned long g_ = (unsigned long)(got);                             \
        unsigned long w_ = (unsigned long)(want);                            \
        tape_test_checks++;                                                  \
        if (g_ != w_) {                                                      \
            tape_test_failures++;                                            \
            (void)fprintf(stderr,                                            \
                "  FAIL %s:%d  %s\n        got  0x%08lX (%lu)\n"             \
                "        want 0x%08lX (%lu)\n",                              \
                __FILE__, __LINE__, #got, g_, g_, w_, w_);                   \
        }                                                                    \
    } while (0)

#define CHECK_EQ_INT(got, want)                                              \
    do {                                                                     \
        long g_ = (long)(got);                                               \
        long w_ = (long)(want);                                              \
        tape_test_checks++;                                                  \
        if (g_ != w_) {                                                      \
            tape_test_failures++;                                            \
            (void)fprintf(stderr, "  FAIL %s:%d  %s\n        got %ld want %ld\n", \
                          __FILE__, __LINE__, #got, g_, w_);                 \
        }                                                                    \
    } while (0)

#define CHECK_MEM_EQ(got, want, n)                                           \
    do {                                                                     \
        tape_test_checks++;                                                  \
        if (memcmp((got), (want), (n)) != 0) {                               \
            tape_test_failures++;                                            \
            (void)fprintf(stderr, "  FAIL %s:%d  %s != %s (%u bytes)\n",     \
                          __FILE__, __LINE__, #got, #want, (unsigned)(n));   \
        }                                                                    \
    } while (0)

#define TAPE_TEST_REPORT(name)                                               \
    (tape_test_failures == 0                                                 \
        ? ((void)printf("PASS  %-22s %d checks\n", (name), tape_test_checks), 0) \
        : ((void)printf("FAIL  %-22s %d of %d checks failed\n",              \
                        (name), tape_test_failures, tape_test_checks), 1))

#endif /* TAPE_TEST_HARNESS_H */
