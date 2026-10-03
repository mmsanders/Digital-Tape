/* Independent C99 oracle: signed division + remainder, no signed shifts.
 * Candidate supplies only tape_test_interp from engine/test/tape_test_hooks.h. */
#include <stdint.h>
#include <stdio.h>
#include <inttypes.h>
#include "tape_test_hooks.h"
#define SEED UINT32_C(0x63d10a5e)
static const uint32_t fs[12]={0,1,2,UINT32_C(0x40000000),UINT32_C(0x7ffffffe),UINT32_C(0x7fffffff),UINT32_C(0x80000000),UINT32_C(0x80000001),UINT32_C(0xc0000000),UINT32_C(0xfffffffd),UINT32_C(0xfffffffe),UINT32_C(0xffffffff)};
static int16_t expected(int16_t a,int16_t b,uint32_t f) {
    int64_t product=((int64_t)b-(int64_t)a)*(int64_t)f;
    const int64_t denominator=INT64_C(4294967296);
    int64_t q=product/denominator;
    if(product<0 && product%denominator!=0) --q;
    return (int16_t)((int64_t)a+q);
}
static uint32_t next(uint32_t *s) {
    uint32_t x=*s; x^=x<<13; x^=x>>17; x^=x<<5; return *s=x;
}
static uint64_t count=0;
static int check(int16_t a,int16_t b,uint32_t f) {
    int16_t e=expected(a,b,f),got=tape_test_interp(a,b,f); ++count;
    if(e!=got) { fprintf(stderr,"FAIL pair=%" PRIu64 " a=%d b=%d f=%" PRIu32 " expected=%d actual=%d\n",count,(int)a,(int)b,f,(int)e,(int)got); return 1; }
    return 0;
}
int main(void) {
    int32_t d; unsigned j; uint32_t s=SEED,i;
    for(d=-65535;d<=65535;++d) {
        int16_t a=(d<0)?INT16_MAX:INT16_MIN;
        int16_t b=(int16_t)((int32_t)a+d);
        for(j=0;j<12;++j) if(check(a,b,fs[j]))return 1;
    }
    for(i=0;i<UINT32_C(10000000);++i) {
        /* Map unsigned words into representable signed samples without an
         * implementation-defined out-of-range unsigned-to-signed conversion. */
        int16_t a=(int16_t)((int32_t)(next(&s)&65535u)-32768);
        int16_t b=(int16_t)((int32_t)(next(&s)&65535u)-32768);
        uint32_t f=next(&s); if(check(a,b,f))return 1;
    }
    for(j=0;j<12;++j) {
        if(check(INT16_MIN,INT16_MAX,fs[j]) || check(INT16_MAX,INT16_MIN,fs[j]))return 1;
    }
    printf("PASS boundary=1572852 prng=10000000 extremes=24 total=%" PRIu64 " seed=0x%08" PRIx32 "\n",count,SEED);
    return 0;
}
