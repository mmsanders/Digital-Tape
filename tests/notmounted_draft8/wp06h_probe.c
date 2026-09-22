/* Verifier-owned WP-06h public-API probe.
 * One process tests one ordinary call, preventing cross-call state contamination.
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
#define SENTINEL UINT64_C(0x1111111111111111)
#define NOMINAL_LENGTH_S 60u

typedef struct {
  unsigned char image[IMAGE_BYTES];
  uint32_t blocks;
  unsigned long callbacks,writes,flushes;
} device_t;

static uint32_t u32le(const unsigned char *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
         ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static unsigned char *mapped_block(device_t *d,uint32_t lba) {
  if(lba==0) return d->image;
  if(d->blocks && lba==d->blocks-1) return d->image+BLOCK;
  if(lba>=8 && lba<520) return d->image+2u*BLOCK+(size_t)(lba-8u)*BLOCK;
  return NULL;
}
static int read_cb(void *ctx,uint32_t lba,uint32_t count,void *dst) {
  device_t *d=(device_t *)ctx; unsigned char *out=(unsigned char *)dst; uint32_t i;
  d->callbacks++;
  if(count==0 || (uint64_t)lba+count>d->blocks) return 1;
  for(i=0;i<count;i++) {
    unsigned char *src=mapped_block(d,lba+i);
    if(src) memcpy(out+(size_t)i*BLOCK,src,BLOCK);
    else memset(out+(size_t)i*BLOCK,0,BLOCK);
  }
  return 0;
}
static int write_cb(void *ctx,uint32_t lba,uint32_t count,const void *src) {
  device_t *d=(device_t *)ctx; const unsigned char *in=(const unsigned char *)src; uint32_t i;
  d->callbacks++; d->writes++;
  if(count==0 || (uint64_t)lba+count>d->blocks) return 1;
  for(i=0;i<count;i++) {
    unsigned char *dst=mapped_block(d,lba+i);
    if(dst) memcpy(dst,in+(size_t)i*BLOCK,BLOCK);
  }
  return 0;
}
static int flush_cb(void *ctx) {
  device_t *d=(device_t *)ctx; d->callbacks++; d->flushes++; return 0;
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

typedef enum {
  TG_SEEK,TG_SET_RATE,TG_RENDER,TG_SERVICE,TG_STATUS,TG_INFO,TG_TELL,TG_ARM,
  TG_FEED,TG_COMMIT,TG_ABORT,TG_SET_SIDE,TG_RESET_B,TG_PROMOTE,TG_RESPOOL,
  TG_DUP,TG_UNMOUNT
} target_t;

static int parse_case(const char *id,int *after,target_t *target,const char **name) {
  const char *p;
  if(!strncmp(id,"NM-BEFORE-",10)) {*after=0;p=id+10;}
  else if(!strncmp(id,"NM-AFTER-",9)) {*after=1;p=id+9;}
  else return 0;
#define CASE(s,e,n) if(!strcmp(p,s)){*target=e;*name=n;return 1;}
  CASE("SEEK",TG_SEEK,"tape_seek")
  CASE("SET-RATE",TG_SET_RATE,"tape_set_rate")
  CASE("RENDER",TG_RENDER,"tape_render")
  CASE("SERVICE",TG_SERVICE,"tape_service")
  CASE("STATUS",TG_STATUS,"tape_status")
  CASE("INFO",TG_INFO,"tape_get_info")
  CASE("TELL",TG_TELL,"tape_tell")
  CASE("ARM",TG_ARM,"tape_arm")
  CASE("FEED",TG_FEED,"tape_feed")
  CASE("COMMIT",TG_COMMIT,"tape_commit")
  CASE("ABORT",TG_ABORT,"tape_abort")
  CASE("SET-SIDE",TG_SET_SIDE,"tape_set_side")
  CASE("RESET-B",TG_RESET_B,"tape_reset_side_b")
  CASE("PROMOTE",TG_PROMOTE,"tape_promote")
  CASE("RESPOOL",TG_RESPOOL,"tape_respool")
  CASE("DUP",TG_DUP,"tape_dup")
  CASE("UNMOUNT",TG_UNMOUNT,"tape_unmount")
#undef CASE
  return 0;
}

static tape_result call_target(target_t target,tape *t,const tape_dev *dst,
                               uint64_t *tell_before,uint64_t *tell_after) {
  int16_t pcm[2]={0,0};
  uint32_t count=0;
  bool more=false;
  tape_status_t status;
  tape_info info;
  uint64_t pos=0;
  uint8_t uuid[16]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
  tape_result r=TAPE_ERR_INVALID_ARG;
  memset(&status,0,sizeof(status)); memset(&info,0,sizeof(info));
  switch(target) {
    case TG_SEEK: r=tape_seek(t,0); break;
    case TG_SET_RATE: r=tape_set_rate(t,65536); break;
    case TG_RENDER: r=tape_render(t,pcm,1,&count); break;
    case TG_SERVICE: r=tape_service(t,1,&more); break;
    case TG_STATUS: r=tape_status(t,&status); break;
    case TG_INFO: r=tape_get_info(t,&info); break;
    case TG_TELL:
      pos=SENTINEL; *tell_before=pos; r=tape_tell(t,&pos); *tell_after=pos; break;
    case TG_ARM: r=tape_arm(t,TAPE_REC_OVERWRITE); break;
    case TG_FEED: r=tape_feed(t,pcm,1,&count); break;
    case TG_COMMIT: r=tape_commit(t); break;
    case TG_ABORT: r=tape_abort(t); break;
    case TG_SET_SIDE: r=tape_set_side(t,TAPE_SIDE_A); break;
    case TG_RESET_B: r=tape_reset_side_b(t); break;
    case TG_PROMOTE: r=tape_promote(t,1,&more,NULL,NULL); break;
    case TG_RESPOOL: r=tape_respool(t,1,&more); break;
    case TG_DUP: r=tape_dup(t,dst,uuid,1,NOMINAL_LENGTH_S,1,&more,NULL,NULL); break;
    case TG_UNMOUNT: r=tape_unmount(t,&pos); break;
  }
  return r;
}

int main(int argc,char **argv) {
  FILE *f,*g;
  unsigned char header[8];
  device_t *src,*dst;
  tape_dev src_dev,dst_dev;
  tape *t=NULL;
  void *mem=NULL,*play=NULL,*rec=NULL;
  size_t mem_size;
  int after=0,have_probe=0;
  target_t target;
  const char *target_name=NULL;
  tape_result init,mount=TAPE_ERR_NOT_MOUNTED,setup_unmount=TAPE_ERR_NOT_MOUNTED;
  tape_result probe=TAPE_ERR_NOT_MOUNTED;
  uint64_t setup_pos=0,tell_before=0,tell_after=0;
  unsigned long sb_cb,sw,db_cb,dw;

  if(argc!=4) {
    fprintf(stderr,"usage: wp06h_probe CASE_ID INPUT.vo08 OUTPUT.vo08\n");
    return 2;
  }
  if(!parse_case(argv[1],&after,&target,&target_name)) return 2;

  src=(device_t *)calloc(1,sizeof(*src));
  dst=(device_t *)calloc(1,sizeof(*dst));
  if(!src || !dst) return 2;
  f=fopen(argv[2],"rb");
  if(!f) return 2;
  if(fread(header,1,sizeof(header),f)!=sizeof(header) ||
     fread(src->image,1,IMAGE_BYTES,f)!=IMAGE_BYTES || fgetc(f)!=EOF ||
     memcmp(header,"VO08",4)!=0) {
    fclose(f); return 2;
  }
  fclose(f);
  src->blocks=u32le(header+4);
  dst->blocks=src->blocks;

  src_dev.read=read_cb; src_dev.write=write_cb; src_dev.flush=flush_cb;
  src_dev.ctx=src; src_dev.block_count=src->blocks;
  dst_dev.read=read_cb; dst_dev.write=write_cb; dst_dev.flush=flush_cb;
  dst_dev.ctx=dst; dst_dev.block_count=dst->blocks;

  mem_size=tape_instance_size();
  mem=malloc(mem_size); play=malloc(65536); rec=malloc(65536);
  if(!mem || !play || !rec) return 2;

  init=tape_init(mem,mem_size,&src_dev,play,65536,rec,65536,&t);
  if(init==TAPE_OK && after) {
    mount=tape_mount(t,TAPE_SIDE_A,0,NULL);
    if(mount==TAPE_OK)
      setup_unmount=tape_unmount(t,&setup_pos);
  }

  if(init==TAPE_OK) {
    sb_cb=src->callbacks; sw=src->writes; db_cb=dst->callbacks; dw=dst->writes;
    probe=call_target(target,t,&dst_dev,&tell_before,&tell_after);
    have_probe=1;
    sb_cb=src->callbacks-sb_cb;
    sw=src->writes-sw;
    db_cb=dst->callbacks-db_cb;
    dw=dst->writes-dw;
  } else {
    sb_cb=sw=db_cb=dw=0;
  }

  g=fopen(argv[3],"wb");
  if(!g) return 2;
  if(fwrite(header,1,sizeof(header),g)!=sizeof(header) ||
     fwrite(src->image,1,IMAGE_BYTES,g)!=IMAGE_BYTES) {
    fclose(g); return 2;
  }
  fclose(g);

  printf("{\"format\":\"WP06H-OBSERVATION-2\",\"adapter_kind\":\"product\",\"calls\":[");
  printf("{\"phase\":\"setup\",\"fn\":\"tape_init\",\"result\":\"%s\"}",rname(init));
  if(after) {
    printf(",{\"phase\":\"setup\",\"fn\":\"tape_mount\",\"result\":\"%s\",\"side\":\"A\"}",rname(mount));
    if(mount==TAPE_OK)
      printf(",{\"phase\":\"setup\",\"fn\":\"tape_unmount\",\"result\":\"%s\"}",rname(setup_unmount));
  }
  if(have_probe) {
    printf(",{\"phase\":\"probe\",\"fn\":\"%s\",\"result\":\"%s\","
           "\"src_callbacks\":%lu,\"src_writes\":%lu,"
           "\"dst_callbacks\":%lu,\"dst_writes\":%lu",
           target_name,rname(probe),sb_cb,sw,db_cb,dw);
    if(target==TG_TELL)
      printf(",\"out_frame_before\":%llu,\"out_frame_after\":%llu",
             (unsigned long long)tell_before,(unsigned long long)tell_after);
    printf("}");
  }
  printf("]}\n");

  free(mem);free(play);free(rec);free(src);free(dst);
  return 0;
}
