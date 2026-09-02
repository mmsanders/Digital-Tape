/*
 * CRC-32/ISO-HDLC vectors.
 *
 * The commit protocol's integrity check. Three streams and two toolchains have
 * to agree on this bit for bit, so it is pinned against published vectors
 * rather than against whatever this implementation happens to produce.
 */

#include "harness.h"
#include "tape_crc32.h"

int main(void);

int main(void)
{
    /* The canonical check value for this parameterisation. */
    CHECK_EQ_U32(tape_crc32("123456789", 9), 0xCBF43926u);

    /* Published vectors. */
    CHECK_EQ_U32(tape_crc32("", 0),          0x00000000u);
    CHECK_EQ_U32(tape_crc32("a", 1),         0xE8B7BE43u);
    CHECK_EQ_U32(tape_crc32("abc", 3),       0x352441C2u);
    CHECK_EQ_U32(tape_crc32("message digest", 14), 0x20159D7Fu);
    CHECK_EQ_U32(tape_crc32("abcdefghijklmnopqrstuvwxyz", 26), 0x4C2750BDu);

    {
        static const unsigned char zeros[32] = { 0 };
        CHECK_EQ_U32(tape_crc32(zeros, 32), 0x190A55ADu);
    }

    /* Streaming must equal one-shot, split anywhere. The commit CRC spans a
       header and an entry array that are not adjacent in memory. */
    {
        const char *s = "123456789";
        size_t cut;
        for (cut = 0; cut <= 9; cut++) {
            uint32_t c = tape_crc32_init();
            c = tape_crc32_update(c, s, cut);
            c = tape_crc32_update(c, s + cut, 9 - cut);
            CHECK_EQ_U32(tape_crc32_final(c), 0xCBF43926u);
        }
    }

    /* Residue: appending a message's own CRC little-endian and re-running gives
       the same value for every message. That is the property a reader uses to
       verify a block without extracting the CRC out of it first — which is what
       mount does on every index slot. Asserted as "constant across messages"
       rather than against a literal, so it does not depend on whose convention
       the literal came from. */
    {
        static const char *const msgs[] = { "123456789", "", "abc", "the tape" };
        uint32_t residue = 0;
        size_t k;
        for (k = 0; k < sizeof msgs / sizeof msgs[0]; k++) {
            unsigned char buf[64];
            size_t n = strlen(msgs[k]);
            uint32_t crc = tape_crc32(msgs[k], n);
            uint32_t r;
            memcpy(buf, msgs[k], n);
            buf[n + 0] = (unsigned char)(crc & 0xFFu);
            buf[n + 1] = (unsigned char)((crc >> 8) & 0xFFu);
            buf[n + 2] = (unsigned char)((crc >> 16) & 0xFFu);
            buf[n + 3] = (unsigned char)((crc >> 24) & 0xFFu);
            r = tape_crc32(buf, n + 4);
            if (k == 0) {
                residue = r;
            } else {
                CHECK_EQ_U32(r, residue);
            }
        }
    }

    /* A single flipped bit must change the CRC. */
    {
        unsigned char a[16], b[16];
        memset(a, 0x5A, sizeof a);
        memcpy(b, a, sizeof b);
        b[7] ^= 0x01u;
        CHECK(tape_crc32(a, sizeof a) != tape_crc32(b, sizeof b));
    }

    return TAPE_TEST_REPORT("crc32");
}
