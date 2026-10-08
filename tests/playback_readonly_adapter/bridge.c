#include "read1_observe.h"
#ifdef TAPE_READ1_OBSERVE
struct tape_read1_work tape_read1_work;
const char *tape_read1_control;
void tape_read1_seam_work(uint64_t refill, uint64_t warm, uint64_t move, uint64_t visits, uint64_t loops);
void tape_read1_seam_work(uint64_t refill, uint64_t warm, uint64_t move, uint64_t visits, uint64_t loops)
{
    unsigned char src[1024]={1}, dst[1024]={0};
    uint32_t entries[16]={1};
    volatile uint32_t tape_read1_sink=0;
    uint64_t j;
    if (refill>1024 || warm>1024 || move>1024 || visits>16 || loops>16) { return; }
    TAPE_READ1_COPY(dst,src,(size_t)refill,refill);
    TAPE_READ1_ADOPT(dst,src,(size_t)warm);
    TAPE_READ1_COPY(src,dst,(size_t)move,move);
    for (j=0;j<visits;++j) { tape_read1_sink+=entries[j]; TAPE_READ1_VISIT(); }
    for (j=0;j<loops;++j) { tape_read1_sink+=dst[j]; TAPE_READ1_LOOP(); }
    tape_read1_sink+=src[0]; (void)tape_read1_sink;
}
#endif
