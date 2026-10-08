/* Independent counting backend, used directly as the engine's callbacks.
 * Test-only host infrastructure. No engine/port cache, skipped requests or
 * synthesized verdicts. Trace records are five LE u32: op,lba,count,rc,completed.
 * 1=read,2=write,3=flush. Every callback request, including errors, is recorded.
 */
#include "counting_device.h"
#include <stdlib.h>
#include <string.h>
#include <limits.h>
static void le32(uint8_t *p,uint32_t v) {
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);
}
static void event(read1_device *d,uint32_t op,uint32_t lba,uint32_t n,int rc) {
    uint8_t b[20];le32(b,op);le32(b+4,lba);le32(b+8,n);
    le32(b+12,(uint32_t)rc);le32(b+16,rc?0:n);
    if(fwrite(b,1,sizeof b,d->trace)!=sizeof b || fflush(d->trace)) abort();
}
static int seek_block(FILE *f,uint32_t lba) {
    uint64_t off=(uint64_t)lba*512u;
    /* All issued fixtures are below 2 GiB, including C60. */
    if(off>(uint64_t)LONG_MAX) return 1;
    return fseek(f,(long)off,SEEK_SET)!=0;
}
int read1_open(read1_device *d,const char *image,const char *trace,uint32_t n,uint32_t seed,int ro) {
    memset(d,0,sizeof *d);d->blocks=n;d->seed=seed;d->read_only=ro;
    d->image=fopen(image,ro?"rb":"r+b");d->trace=fopen(trace,"ab");
    d->dirty=(uint8_t *)calloc(n,1);
    if(!d->image||!d->trace||!d->dirty){read1_close(d);return 1;}return 0;
}
void read1_close(read1_device *d) {
    if(d->image)fclose(d->image);
    if(d->trace)fclose(d->trace);
    free(d->dirty);memset(d,0,sizeof *d);
}
static int one_block(read1_device *d,uint32_t lba,uint8_t *p) {
    if(lba>=2048 && lba<d->blocks-1 && !d->dirty[lba]) {
        uint32_t first=(lba-2048u)*128u;
        for(uint32_t i=0;i<128u;i++)le32(p+4u*i,(first+i)*UINT32_C(2654435761)+UINT32_C(0x5a17c3e1)+d->seed);
        return 0;
    }
    return seek_block(d->image,lba)||fread(p,1,512,d->image)!=512;
}
int read1_read(void *ctx,uint32_t lba,uint32_t n,void *out) {
    read1_device *d=ctx;int rc=0;uint8_t *p=out;
    if(!n || (uint64_t)lba+n>d->blocks)rc=1;
    else if(d->fail_read) {
        d->fail_read=0;memset(p,0xcd,(size_t)n*512u);
        for(uint32_t i=0;i<n && i<d->fail_read_prefix;i++) {
            if(one_block(d,lba+i,p+(size_t)i*512u))break;
        }
        d->fail_read_prefix=0;rc=1;
    } else {
        for(uint32_t i=0;i<n;i++)if(one_block(d,lba+i,p+(size_t)i*512u)){rc=1;break;}
    }
    event(d,1,lba,n,rc);return rc;
}
int read1_write(void *ctx,uint32_t lba,uint32_t n,const void *in) {
    read1_device *d=ctx;int rc=0;
    if(d->read_only || !n || (uint64_t)lba+n>d->blocks)rc=1;
    else if(d->fail_write){d->fail_write=0;rc=1;}
    else if(seek_block(d->image,lba)||fwrite(in,512,n,d->image)!=n)rc=1;
    else memset(d->dirty+lba,1,n);
    event(d,2,lba,n,rc);return rc;
}
int read1_flush(void *ctx) {
    read1_device *d=ctx;int rc=0;
    if(d->fail_flush){d->fail_flush=0;rc=1;}
    else rc=fflush(d->image)!=0;
    event(d,3,0,0,rc);return rc;
}
