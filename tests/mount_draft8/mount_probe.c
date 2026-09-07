/* Host-only probe: calls public API; records actual callback traffic.
 * No expected values, private layout inspection, or substitute mount logic.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <inttypes.h>
#ifdef TAPE_PUBLIC_HEADER
#include TAPE_PUBLIC_HEADER
#else
#include "candidate_api.h"
#endif
#define IMAGE_BYTES (2u*512u+4u*65536u)
typedef struct {
 unsigned char image[IMAGE_BYTES];
 uint32_t blocks,fail_write,fail_flush;
 unsigned long reads,writes,flushes,oob,chunk_reads;
 int comma;
} device;
static uint32_t u32(const unsigned char *p) {
 return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static void event(device *d,const char *op,uint32_t lba,uint32_t count,int rc) {
 printf("%s{\"op\":\"%s\",\"lba\":%"PRIu32",\"count\":%"PRIu32",\"rc\":%d}",
        d->comma?",":"",op,lba,count,rc); d->comma=1;
}
static unsigned char *block(device *d,uint32_t lba) {
 if(lba==0) return d->image;
 if(d->blocks>0 && lba==d->blocks-1) return d->image+512;
 if(lba>=8 && lba<520) return d->image+1024+(lba-8)*512;
 return NULL;
}
static int read_cb(void *ctx,uint32_t lba,uint32_t count,void *dst) {
 device *d=ctx; uint32_t i; int rc=0; unsigned char *out=dst;
 d->reads++;
 if((uint64_t)lba+count>d->blocks || count==0) { d->oob++; rc=1; }
 event(d,"read",lba,count,rc); if(rc) return rc;
 for(i=0;i<count;i++) {
  unsigned char *src=block(d,lba+i);
  if(lba+i>=2048 && lba+i!=d->blocks-1) d->chunk_reads++;
  if(src) memcpy(out+(size_t)i*512,src,512);
  else memset(out+(size_t)i*512,0xA5,512); /* undefined audio/padding poison */
 }
 return 0;
}
static int write_cb(void *ctx,uint32_t lba,uint32_t count,const void *src) {
 device *d=ctx; uint32_t i; const unsigned char *in=src; int rc=0;
 d->writes++;
 if((uint64_t)lba+count>d->blocks || count==0) {d->oob++; rc=1;}
 if(d->fail_write && d->writes==d->fail_write) rc=1;
 event(d,"write",lba,count,rc);
 /* Trace attempted bytes even on failure. Failed write is fail-before-write. */
 printf(", {\"op\":\"write_bytes\",\"hex\":\"");
 for(i=0;i<count && i<2;i++) {
  size_t j; for(j=0;j<512;j++) printf("%02x",in[(size_t)i*512+j]);
 }
 printf("\"}");
 if(rc) return rc;
 for(i=0;i<count;i++) {unsigned char *dst=block(d,lba+i); if(dst) memcpy(dst,in+(size_t)i*512,512);}
 return 0;
}
static int flush_cb(void *ctx) {
 device *d=ctx; int rc; d->flushes++;
 rc=d->fail_flush && d->flushes==d->fail_flush;
 event(d,"flush",0,0,rc); return rc;
}
int main(int argc,char **argv) {
 unsigned char header[32]; FILE *f; device *d; tape_dev dev; tape *t=NULL;
 void *mem,*play,*rec; size_t size; tape_result init,result,ir=TAPE_ERR_NOT_MOUNTED,tr=TAPE_ERR_NOT_MOUNTED;
 tape_info info; uint64_t pos=UINT64_MAX,resume; uint32_t side;
 if(argc!=2) {fprintf(stderr,"usage: mount_probe fixture.bin\n");return 2;}
 d=calloc(1,sizeof(*d)); if(!d) return 2;
 f=fopen(argv[1],"rb"); if(!f) return 2;
 if(fread(header,1,32,f)!=32 || fread(d->image,1,IMAGE_BYTES,f)!=IMAGE_BYTES || fgetc(f)!=EOF) return 2;
 fclose(f);
 if(memcmp(header,"VM08",4)) return 2;
 d->blocks=u32(header+4);side=u32(header+8);
 resume=u32(header+12)|((uint64_t)u32(header+16)<<32);
 d->fail_write=u32(header+24);d->fail_flush=u32(header+28);
 dev.read=read_cb;dev.write=u32(header+20)?write_cb:NULL;dev.flush=flush_cb;
 dev.ctx=d;dev.block_count=d->blocks;
 size=tape_instance_size(); mem=malloc(size);play=malloc(65536);rec=malloc(65536);
 if(!mem||!play||!rec) return 2;
 memset(mem,0xCC,size);memset(play,0xCD,65536);memset(rec,0xCE,65536);memset(&info,0,sizeof(info));
 printf("{\"events\":[");
 init=tape_init(mem,size,&dev,play,65536,rec,65536,&t);
 result=init==TAPE_OK?tape_mount(t,(tape_side)side,resume,NULL):init;
 if(result==TAPE_OK) {ir=tape_get_info(t,&info);tr=tape_tell(t,&pos);}
 printf("],\"init\":%d,\"result\":%d,\"info_result\":%d,\"tell_result\":%d,\"position\":%"PRIu64,
        (int)init,(int)result,(int)ir,(int)tr,pos);
 printf(",\"reads\":%lu,\"writes\":%lu,\"flushes\":%lu,\"oob\":%lu,\"chunk_reads\":%lu",
        d->reads,d->writes,d->flushes,d->oob,d->chunk_reads);
 printf(",\"info\":{\"total_frames\":%"PRIu64",\"entry_count\":%"PRIu32",\"entries_free\":%"PRIu32
        ",\"total_chunks\":%"PRIu32",\"free_chunks\":%"PRIu32",\"nominal_length_s\":%"PRIu32
        ",\"version_minor\":%u,\"writable\":%d,\"side_b_valid\":%d,\"needs_repair\":%d,\"warm_start_used\":%d,\"uuid\":\"",
        info.total_frames,info.entry_count,info.entries_free,info.total_chunks,info.free_chunks,info.nominal_length_s,
        (unsigned)info.version_minor,info.writable,info.side_b_valid,info.needs_repair,info.warm_start_used);
 {size_t j;for(j=0;j<16;j++) printf("%02x",info.uuid[j]);}
 printf("\"},\"superblocks\":[\"");
 {size_t j;for(j=0;j<1024;j++) {if(j==512) printf("\",\"");printf("%02x",d->image[j]);}}
 printf("\"]}\n");
 free(mem);free(play);free(rec);free(d);return 0;
}
