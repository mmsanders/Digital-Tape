/* Verifier-owned WP-06a public-API probe.
 * Product integration changes include/link flags only. Expectations live in Python.
 */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef TAPE_PUBLIC_HEADER
#include TAPE_PUBLIC_HEADER
#else
#include "candidate_api.h"
#endif

#define BLOCK 512u
#define SLOT_BYTES 65536u
#define IMAGE_BYTES (2u*BLOCK + 4u*SLOT_BYTES)
#define MAX_EVENTS 4096u

typedef struct {
  const char *op;
  uint32_t lba,count;
  int rc;
} event_t;

typedef struct {
  unsigned char image[IMAGE_BYTES];
  uint32_t blocks;
  event_t events[MAX_EVENTS];
  size_t nevents;
  int event_overflow;
} device_t;

static uint32_t u32le(const unsigned char *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
         ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}

static void event(device_t *d,const char *op,uint32_t lba,uint32_t count,int rc) {
  if(d->nevents<MAX_EVENTS) {
    d->events[d->nevents].op=op;
    d->events[d->nevents].lba=lba;
    d->events[d->nevents].count=count;
    d->events[d->nevents].rc=rc;
    d->nevents++;
  } else {
    d->event_overflow=1;
  }
}

static unsigned char *mapped_block(device_t *d,uint32_t lba) {
  if(lba==0) return d->image;
  if(d->blocks && lba==d->blocks-1) return d->image+BLOCK;
  if(lba>=8 && lba<520) return d->image+2u*BLOCK+(size_t)(lba-8u)*BLOCK;
  return NULL;
}

static int read_cb(void *ctx,uint32_t lba,uint32_t count,void *dst) {
  device_t *d=(device_t *)ctx;
  unsigned char *out=(unsigned char *)dst;
  uint32_t i;
  int rc=(count==0 || (uint64_t)lba+count>d->blocks);
  event(d,"read",lba,count,rc);
  if(rc) return rc;
  for(i=0;i<count;i++) {
    unsigned char *src=mapped_block(d,lba+i);
    if(src) memcpy(out+(size_t)i*BLOCK,src,BLOCK);
    else memset(out+(size_t)i*BLOCK,0,BLOCK);
  }
  return 0;
}

static int write_cb(void *ctx,uint32_t lba,uint32_t count,const void *src) {
  device_t *d=(device_t *)ctx;
  const unsigned char *in=(const unsigned char *)src;
  uint32_t i;
  int rc=(count==0 || (uint64_t)lba+count>d->blocks);
  event(d,"write",lba,count,rc);
  if(rc) return rc;
  for(i=0;i<count;i++) {
    unsigned char *dst=mapped_block(d,lba+i);
    if(dst) memcpy(dst,in+(size_t)i*BLOCK,BLOCK);
  }
  return 0;
}

static int flush_cb(void *ctx) {
  device_t *d=(device_t *)ctx;
  event(d,"flush",0,0,0);
  return 0;
}

static const char *rname(tape_result r) {
  switch(r) {
    case TAPE_OK:return "TAPE_OK";
    case TAPE_ERR_IO:return "TAPE_ERR_IO";
    case TAPE_ERR_BAD_MAGIC:return "TAPE_ERR_BAD_MAGIC";
    case TAPE_ERR_CRC:return "TAPE_ERR_CRC";
    case TAPE_ERR_VERSION:return "TAPE_ERR_VERSION";
    case TAPE_ERR_UNSUPPORTED_STATE:return "TAPE_ERR_UNSUPPORTED_STATE";
    case TAPE_ERR_GEOMETRY:return "TAPE_ERR_GEOMETRY";
    case TAPE_ERR_INCOMPLETE:return "TAPE_ERR_INCOMPLETE";
    case TAPE_ERR_INCONSISTENT:return "TAPE_ERR_INCONSISTENT";
    case TAPE_ERR_NO_VALID_INDEX:return "TAPE_ERR_NO_VALID_INDEX";
    case TAPE_ERR_READ_ONLY:return "TAPE_ERR_READ_ONLY";
    case TAPE_ERR_CARTRIDGE_FULL:return "TAPE_ERR_CARTRIDGE_FULL";
    case TAPE_ERR_INDEX_FULL:return "TAPE_ERR_INDEX_FULL";
    case TAPE_ERR_DEST_TOO_SMALL:return "TAPE_ERR_DEST_TOO_SMALL";
    case TAPE_ERR_SEQUENCE_EXHAUSTED:return "TAPE_ERR_SEQUENCE_EXHAUSTED";
    case TAPE_ERR_FAULTED:return "TAPE_ERR_FAULTED";
    case TAPE_ERR_NOT_MOUNTED:return "TAPE_ERR_NOT_MOUNTED";
    case TAPE_ERR_BUSY:return "TAPE_ERR_BUSY";
    case TAPE_ERR_UNDERRUN:return "TAPE_ERR_UNDERRUN";
    case TAPE_ERR_INVALID_ARG:return "TAPE_ERR_INVALID_ARG";
    default:return "TAPE_RESULT_UNKNOWN";
  }
}

typedef enum {TG_NONE,TG_ARM,TG_RESET,TG_PROMOTE,TG_RESPOOL,TG_FEED,TG_COMMIT} target_t;

static int classify(const char *id,tape_side *side,target_t *target) {
  *target=TG_NONE;
  if(!strcmp(id,"W06A-ARM")) {*side=TAPE_SIDE_B;*target=TG_ARM;}
  else if(!strcmp(id,"W06A-RESET-B")) {*side=TAPE_SIDE_A;*target=TG_RESET;}
  else if(!strcmp(id,"W06A-PROMOTE")) {*side=TAPE_SIDE_A;*target=TG_PROMOTE;}
  else if(!strcmp(id,"W06A-RESPOOL")) {*side=TAPE_SIDE_B;*target=TG_RESPOOL;}
  else if(!strcmp(id,"W06A-FEED")) {*side=TAPE_SIDE_B;*target=TG_FEED;}
  else if(!strcmp(id,"W06A-COMMIT")) {*side=TAPE_SIDE_B;*target=TG_COMMIT;}
  else if(!strcmp(id,"W06A-REPAIR-INVALID") || !strcmp(id,"W06A-REPAIR-STALE"))
    {*side=TAPE_SIDE_A;*target=TG_NONE;}
  else return 0;
  return 1;
}

static void print_events(const device_t *d) {
  size_t i;
  printf("[");
  for(i=0;i<d->nevents;i++) {
    if(i) printf(",");
    printf("{\"op\":\"%s\",\"lba\":%u,\"count\":%u,\"rc\":%d}",
           d->events[i].op,d->events[i].lba,d->events[i].count,d->events[i].rc);
  }
  printf("]");
}

int main(int argc,char **argv) {
  FILE *f,*g;
  unsigned char header[8];
  device_t *d;
  tape_dev dev;
  tape *t=NULL;
  void *mem=NULL,*play=NULL,*rec=NULL;
  size_t mem_size;
  tape_side side;
  target_t target;
  tape_result init,mount=TAPE_ERR_NOT_MOUNTED,info_r=TAPE_ERR_NOT_MOUNTED;
  tape_result target_r=TAPE_ERR_NOT_MOUNTED,unmount_r=TAPE_ERR_NOT_MOUNTED;
  tape_info info;
  uint64_t pos=0;
  bool more=false;
  uint32_t accepted=0;
  int16_t frame[2]={0,0};
  int have_mount=0,have_info=0,have_target=0,have_unmount=0;
  const char *target_name=NULL;

  if(argc!=4) {
    fprintf(stderr,"usage: wp06a_probe CASE_ID INPUT.vo08 OUTPUT.vo08\n");
    return 2;
  }
  if(!classify(argv[1],&side,&target)) return 2;

  d=(device_t *)calloc(1,sizeof(*d));
  if(!d) return 2;
  f=fopen(argv[2],"rb");
  if(!f) return 2;
  if(fread(header,1,sizeof(header),f)!=sizeof(header) ||
     fread(d->image,1,IMAGE_BYTES,f)!=IMAGE_BYTES || fgetc(f)!=EOF ||
     memcmp(header,"VO08",4)!=0) {
    fclose(f); return 2;
  }
  fclose(f);
  d->blocks=u32le(header+4);

  dev.read=read_cb;
  dev.write=write_cb; /* WP-06a premise: physically writable device */
  dev.flush=flush_cb;
  dev.ctx=d;
  dev.block_count=d->blocks;

  mem_size=tape_instance_size();
  mem=malloc(mem_size);
  play=malloc(65536);
  rec=malloc(65536);
  if(!mem || !play || !rec) return 2;
  memset(&info,0,sizeof(info));

  init=tape_init(mem,mem_size,&dev,play,65536,rec,65536,&t);
  if(init==TAPE_OK) {
    mount=tape_mount(t,side,0,NULL);
    have_mount=1;
    if(mount==TAPE_OK) {
      info_r=tape_get_info(t,&info);
      have_info=1;
      switch(target) {
        case TG_ARM:
          target_name="tape_arm";
          target_r=tape_arm(t,TAPE_REC_OVERWRITE);
          have_target=1;
          break;
        case TG_RESET:
          target_name="tape_reset_side_b";
          target_r=tape_reset_side_b(t);
          have_target=1;
          break;
        case TG_PROMOTE:
          target_name="tape_promote";
          more=true;
          target_r=tape_promote(t,64,&more,NULL,NULL);
          have_target=1;
          break;
        case TG_RESPOOL:
          target_name="tape_respool";
          more=true;
          target_r=tape_respool(t,64,&more);
          have_target=1;
          break;
        case TG_FEED:
          target_name="tape_feed";
          accepted=0;
          target_r=tape_feed(t,frame,1,&accepted);
          have_target=1;
          break;
        case TG_COMMIT:
          target_name="tape_commit";
          target_r=tape_commit(t);
          have_target=1;
          break;
        case TG_NONE:
          break;
      }
      unmount_r=tape_unmount(t,&pos);
      have_unmount=1;
    }
  }

  g=fopen(argv[3],"wb");
  if(!g) return 2;
  if(fwrite(header,1,sizeof(header),g)!=sizeof(header) ||
     fwrite(d->image,1,IMAGE_BYTES,g)!=IMAGE_BYTES) {
    fclose(g); return 2;
  }
  fclose(g);

  printf("{\"format\":\"WP06A-OBSERVATION-2\",\"adapter_kind\":\"product\","
         "\"device_write_nonnull\":true,\"event_overflow\":%s,\"calls\":[",
         d->event_overflow?"true":"false");
  printf("{\"fn\":\"tape_init\",\"result\":\"%s\"}",rname(init));
  if(have_mount) {
    printf(",{\"fn\":\"tape_mount\",\"result\":\"%s\",\"side\":\"%s\"}",
           rname(mount),side==TAPE_SIDE_A?"A":"B");
  }
  if(have_info) {
    printf(",{\"fn\":\"tape_get_info\",\"result\":\"%s\","
           "\"writable\":%s,\"version_minor\":%u,\"needs_repair\":%s}",
           rname(info_r),info.writable?"true":"false",(unsigned)info.version_minor,
           info.needs_repair?"true":"false");
  }
  if(have_target) {
    printf(",{\"fn\":\"%s\",\"result\":\"%s\"",
           target_name,rname(target_r));
    if(target==TG_PROMOTE || target==TG_RESPOOL)
      printf(",\"more_work\":%s",more?"true":"false");
    if(target==TG_FEED)
      printf(",\"accepted\":%u",accepted);
    printf("}");
  }
  if(have_unmount)
    printf(",{\"fn\":\"tape_unmount\",\"result\":\"%s\"}",rname(unmount_r));
  printf("],\"events\":");
  print_events(d);
  printf("}\n");

  free(mem);free(play);free(rec);free(d);
  return 0;
}
