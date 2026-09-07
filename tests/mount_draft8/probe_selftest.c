/* Exercise the probe's own callback instrumentation without an engine. */
#define main unused_probe_main
#include "mount_probe.c"
#undef main
#include <assert.h>
int main(void) {
 device *d=calloc(1,sizeof(*d));unsigned char data[1024];
 assert(d);d->blocks=30000;memset(d->image,0x37,sizeof(d->image));
 printf("{\"events\":[");
 assert(read_cb(d,8,2,data)==0);assert(data[0]==0x37 && data[1023]==0x37);
 assert(d->reads==1 && d->chunk_reads==0);
 assert(read_cb(d,d->blocks-1,1,data)==0);assert(d->chunk_reads==0);
 assert(read_cb(d,2048,1,data)==0);assert(data[0]==0xA5 && d->chunk_reads==1);
 assert(read_cb(d,d->blocks-1,2,data)!=0);assert(d->oob==1);
 memset(data,0x62,sizeof(data));
 assert(write_cb(d,0,1,data)==0);assert(d->image[0]==0x62);
 d->fail_write=2;memset(data,0x71,sizeof(data));
 assert(write_cb(d,0,1,data)!=0);assert(d->image[0]==0x62);
 assert(flush_cb(d)==0);d->fail_flush=2;assert(flush_cb(d)!=0);
 assert(d->writes==2 && d->flushes==2);
 printf("],\"probe_selftest\":\"PASS\"}\n");free(d);return 0;
}
