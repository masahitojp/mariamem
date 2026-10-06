/* Bounded OS process counters for informational resource probes; not product code. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#ifdef __APPLE__
#include <libproc.h>
#include <mach/mach_time.h>
#include <sys/resource.h>
#include <mach/mach.h>
#endif
int main(int argc,char **argv) {
 printf("{");
 for(int i=1;i<argc;i++) {
  int pid=atoi(argv[i]); uint64_t rss=0,primary=0,filemaps=0;
#ifndef __APPLE__
 uint64_t priv=0;
#endif
 double cpu=0;int ok=1;
#ifdef __APPLE__
  struct rusage_info_v0 r;
  mach_timebase_info_data_t timebase;
  if(mach_timebase_info(&timebase)!=KERN_SUCCESS)return 2;
  if(proc_pid_rusage(pid,RUSAGE_INFO_V0,(rusage_info_t*)&r))ok=0;
  else {rss=r.ri_resident_size;primary=r.ri_phys_footprint;cpu=((double)r.ri_user_time+r.ri_system_time)*timebase.numer/timebase.denom/1e9;}
  uint64_t address=0;
  struct proc_regionwithpathinfo region;
  while(proc_pidinfo(pid,PROC_PIDREGIONPATHINFO,address,&region,sizeof(region))==sizeof(region)) {
   if(region.prp_vip.vip_vi.vi_stat.vst_ino)filemaps+=region.prp_prinfo.pri_size;
   uint64_t next=region.prp_prinfo.pri_address+region.prp_prinfo.pri_size;
   if(next<=address)break;
   address=next;
  }
#else
  char path[128],line[4096],key[128];unsigned long long kb;
  snprintf(path,sizeof(path),"/proc/%d/smaps_rollup",pid);FILE *f=fopen(path,"r");
  if(!f)ok=0;else {while(fgets(line,sizeof(line),f))if(sscanf(line,"%127s %llu",key,&kb)==2){
   if(!strcmp(key,"Rss:"))rss=kb*1024;
   if(!strcmp(key,"Pss:"))primary=kb*1024;
   if(!strcmp(key,"Private_Clean:")||!strcmp(key,"Private_Dirty:")||!strcmp(key,"Private_Hugetlb:"))priv+=kb*1024;
  }fclose(f);}
  snprintf(path,sizeof(path),"/proc/%d/stat",pid);f=fopen(path,"r");
  if(!f||!fgets(line,sizeof(line),f))ok=0;
  if(f)fclose(f);
  if(ok){char *p=strrchr(line,')');if(!p)ok=0;else{char *s=p+2;int field=3;unsigned long long ticks=0;
   for(char *t=strtok(s," ");t;t=strtok(NULL," "),field++)if(field==14||field==15)ticks+=strtoull(t,NULL,10);
   cpu=(double)ticks/sysconf(_SC_CLK_TCK);
  }}
  snprintf(path,sizeof(path),"/proc/%d/maps",pid);f=fopen(path,"r");
  if(f) {unsigned long long start,end,inode;char perms[8],offset[32],dev[32];
   while(fgets(line,sizeof(line),f))if(sscanf(line,"%llx-%llx %7s %31s %31s %llu",&start,&end,perms,offset,dev,&inode)==6&&inode)filemaps+=end-start;
   fclose(f);
  }
#endif
  printf("%s\"%d\":",i>1?",":"",pid);
  if(!ok)printf("{\"error\":\"process counters unavailable\"}");
  else {
#ifdef __APPLE__
 printf("{\"rss_bytes\":%llu,\"primary_bytes\":%llu,\"file_mapping_bytes\":%llu,\"private_bytes\":null,\"cpu_seconds\":%.9f,\"cpu_timebase_numer\":%u,\"cpu_timebase_denom\":%u}",(unsigned long long)rss,(unsigned long long)primary,(unsigned long long)filemaps,cpu,timebase.numer,timebase.denom);
#else
 printf("{\"rss_bytes\":%llu,\"primary_bytes\":%llu,\"file_mapping_bytes\":%llu,\"private_bytes\":%llu,\"cpu_seconds\":%.9f}",(unsigned long long)rss,(unsigned long long)primary,(unsigned long long)filemaps,(unsigned long long)priv,cpu);
#endif
 }
 }
 puts("}");return 0;
}
