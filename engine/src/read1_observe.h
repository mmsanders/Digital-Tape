/* Test-only observations. No definitions, references or storage in shipping. */
#ifdef TAPE_READ1_OBSERVE
#ifndef TAPE_READ1_HEADER
#define TAPE_READ1_HEADER
#include <stdint.h>
#include <stddef.h>
#include <string.h>
struct tape_read1_work { uint64_t refill, warm, move, visits, loops; };
extern struct tape_read1_work tape_read1_work;
extern const char *tape_read1_control;
#define TAPE_READ1_CONTROL(s) (tape_read1_control != NULL && strcmp(tape_read1_control, (s)) == 0)
#define TAPE_READ1_LOOP() (++tape_read1_work.loops)
#define TAPE_READ1_VISIT() (++tape_read1_work.visits)
#define TAPE_READ1_ADOPT(dst,src,n) do { memmove((dst),(src),(n)); tape_read1_work.warm += (uint64_t)(n); } while (0)
#define TAPE_READ1_COPY(dst,src,n,kind) do { memcpy((dst),(src),(n)); tape_read1_work.kind += (uint64_t)(n); } while (0)
#endif
#endif
