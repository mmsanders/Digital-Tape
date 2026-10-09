/*
 * entropy.c — the caller-owned entropy and clock for provision (§3).
 *
 * docs/WP14-CLI-CONTRACT.md §3: with --uuid/--epoch omitted, tapectl is the
 * caller that owns entropy: the UUID comes from the OS CSPRNG and the epoch
 * from the wall clock. This is the only place WP-14 uses either.
 */

#include "entropy.h"

#include <time.h>

#if defined(_WIN32)
#include <windows.h>
#include <bcrypt.h>
int entropy_uuid(uint8_t out[16])
{
    return BCryptGenRandom(NULL, out, 16, BCRYPT_USE_SYSTEM_PREFERRED_RNG) == 0 ? 0 : -1;
}
#elif defined(__APPLE__)
#include <Security/SecRandom.h>
int entropy_uuid(uint8_t out[16])
{
    return SecRandomCopyBytes(kSecRandomDefault, 16, out) == errSecSuccess ? 0 : -1;
}
#else
#include <sys/random.h>
int entropy_uuid(uint8_t out[16])
{
    size_t got = 0;
    while (got < 16u) {
        ssize_t n = getrandom(out + got, 16u - got, 0);
        if (n <= 0) { return -1; }
        got += (size_t)n;
    }
    return 0;
}
#endif

int entropy_epoch(uint32_t *out)
{
    time_t now = time(NULL);
    if (now == (time_t)-1 || now < 0) { return -1; }
    *out = (uint32_t)now;
    return 0;
}
