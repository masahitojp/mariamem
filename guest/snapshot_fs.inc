/* Cold filesystem snapshots: copy only before open or after server shutdown.
 * /mariadb remains an unmounted memory FS in memory mode. Only the transfer
 * directories are host mounts. Never traverse symlinks or overwrite files.
 */
#include <dirent.h>
#include <time.h>
#include <stdint.h>

/* Bounded, restore-only experiment. No syscall/stdio buffering changes. */
enum { RP_META, RP_SRC_OPEN, RP_DST_OPEN, RP_READ, RP_WRITE,
       RP_SRC_CLOSE, RP_DST_CLOSE, RP_STAGES };
static const char *rp_names[]= {"metadata", "source_open", "destination_create",
  "read", "write", "source_close", "destination_close"};
typedef struct { uint64_t wall, process, thread; int valid; } rp_stamp;
typedef struct { uint64_t wall, process, thread, calls, bytes; int invalid, failed_clocks, regressed_clocks; rp_stamp first_begin, first_end; } rp_cost;
typedef struct {
  int enabled, count, dropped;
  uint64_t directories;
  rp_stamp begin, end;
  rp_cost stages[RP_STAGES];
  struct { char path[384]; uint64_t size, wall; rp_cost stages[RP_STAGES]; } files[256];
} rp_record;
static rp_record restore_probe, restore_prestage;
static rp_cost restore_verification;
static int restore_source_experiment, restore_identity_verified;

static rp_stamp rp_now(void)
{
  rp_stamp s= {0};
  int saved= errno;
  struct timespec t;
  s.valid= !clock_gettime(CLOCK_MONOTONIC, &t) ? 1 : 0;
  if (s.valid) s.wall= (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec;
  int ok= !clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t);
  if (ok) s.process= (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec;
  if (ok) s.valid |= 2;
  ok= !clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t);
  if (ok) s.thread= (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec;
  if (ok) s.valid |= 4;
  errno= saved;
  return s;
}
static void rp_add(rp_cost *cost, rp_stamp begin, rp_stamp end, uint64_t bytes)
{
  cost->calls++; cost->bytes+= bytes;
  int failed= 7 & ~(begin.valid & end.valid);
  int regressed= ((begin.valid & end.valid & 1) && end.wall<begin.wall ? 1 : 0) |
    ((begin.valid & end.valid & 2) && end.process<begin.process ? 2 : 0) |
    ((begin.valid & end.valid & 4) && end.thread<begin.thread ? 4 : 0);
  if (failed || regressed) {
    if (!cost->invalid) { cost->first_begin= begin; cost->first_end= end; }
    cost->invalid= 1; cost->failed_clocks |= failed; cost->regressed_clocks |= regressed;
    return;
  }
  cost->wall+= end.wall-begin.wall;
  cost->process+= end.process-begin.process;
  cost->thread+= end.thread-begin.thread;
}
static void rp_finish(int stage, int file, rp_stamp begin, uint64_t bytes)
{
  if (!restore_probe.enabled) return;
  rp_stamp end= rp_now();
  rp_add(&restore_probe.stages[stage], begin, end, bytes);
  if (file >= 0) rp_add(&restore_probe.files[file].stages[stage], begin, end, bytes);
}
#define RP_CALL(stage,file,result,call) do { \
  rp_stamp rp_start= {0}; \
  if (restore_probe.enabled) rp_start= rp_now(); \
  result= (call); rp_finish(stage,file,rp_start,0); \
} while (0)

/* Bit masks: 1=monotonic wall, 2=process CPU, 4=current-thread CPU. */
static void rp_write_clock_error(FILE *f, rp_cost *c)
{
  if (!c->invalid) return;
  fprintf(f,",\"clock_error\":{\"failed_mask\":%d,\"regressed_mask\":%d,\"first_begin\":[%llu,%llu,%llu],\"first_end\":[%llu,%llu,%llu]}",
    c->failed_clocks,c->regressed_clocks,
    (unsigned long long)c->first_begin.wall,(unsigned long long)c->first_begin.process,(unsigned long long)c->first_begin.thread,
    (unsigned long long)c->first_end.wall,(unsigned long long)c->first_end.process,(unsigned long long)c->first_end.thread);
}
static void rp_write_cost(FILE *f, rp_cost *c)
{
  fprintf(f,"{\"wall_ns\":%llu,\"process_cpu_ns\":%llu,\"thread_cpu_ns\":%llu,\"calls\":%llu,\"bytes\":%llu,\"invalid_clock\":%s",
    (unsigned long long)c->wall,(unsigned long long)c->process,
    (unsigned long long)c->thread,(unsigned long long)c->calls,
    (unsigned long long)c->bytes,c->invalid ? "true" : "false");
  rp_write_clock_error(f,c); fputc('}',f);
}
static void rp_write_record(FILE *f, const char *name)
{
  if (!restore_probe.enabled) return;
  rp_cost total= {0};
  rp_add(&total,restore_probe.begin,restore_probe.end,0);
  fprintf(f,",\"%s\":{\"version\":1,\"clock\":\"guest_monotonic\",\"wall_ns\":%llu,\"process_cpu_ns\":%llu,\"thread_cpu_ns\":%llu,\"invalid_clock\":%s,\"directories\":%llu,\"file_count\":%d,\"dropped_files\":%d,\"stages\":{",
    name, (unsigned long long)total.wall,
    (unsigned long long)total.process,
    (unsigned long long)total.thread,
    total.invalid ? "true" : "false",
    (unsigned long long)restore_probe.directories,restore_probe.count,restore_probe.dropped);
  for (int i=0;i<RP_STAGES;i++) { if(i) fputc(',',f); fprintf(f,"\"%s\":",rp_names[i]); rp_write_cost(f,&restore_probe.stages[i]); }
  fputs("}",f); rp_write_clock_error(f,&total);
  fputs(",\"files\":[",f);
  for(int i=0;i<restore_probe.count;i++) {
    if(i) fputc(',',f);
    fputs("{\"path\":",f); init_quote(f,restore_probe.files[i].path);
    fprintf(f,",\"size_bytes\":%llu,\"wall_ns\":%llu,\"stages\":{",
      (unsigned long long)restore_probe.files[i].size,(unsigned long long)restore_probe.files[i].wall);
    for(int j=0;j<RP_STAGES;j++) { if(j) fputc(',',f); fprintf(f,"\"%s\":",rp_names[j]); rp_write_cost(f,&restore_probe.files[i].stages[j]); }
    fputs("}}",f);
  }
  fputs("]}",f);
}

static void restore_probe_write(FILE *f)
{
  rp_write_record(f,"restore_copy");
  if (restore_source_experiment) {
    rp_record saved=restore_probe;
    restore_probe=restore_prestage; rp_write_record(f,"restore_prestage"); restore_probe=saved;
    fputs(",\"restore_verification\":",f); rp_write_cost(f,&restore_verification);
    fprintf(f,",\"restore_source\":\"%s\",\"restore_identity_verified\":%s",
      getenv("MARIAMEM_GUEST_RESTORE_SOURCE") ? "guest" : "host", restore_identity_verified ? "true" : "false");
  }
}

static int snapshot_copy(const char *src, const char *dst, unsigned int depth)
{
  if (!depth) {
    memset(&restore_probe,0,sizeof(restore_probe));
    restore_probe.enabled= (!strcmp(src,"/snapshot-in/data") || (restore_source_experiment && !strcmp(src,"/restore-source"))) && getenv("MARIAMEM_RESTORE_DIAGNOSTICS") != NULL;
    if (restore_probe.enabled) restore_probe.begin= rp_now();
  }
  struct stat st;
  int status;
  if (depth > 64) return -1;
  RP_CALL(RP_META,-1,status,lstat(src, &st));
  if (status)
    return -1;
  if (S_ISDIR(st.st_mode))
  {
    RP_CALL(RP_META,-1,status,mkdir(dst, 0700));
    if (status)
      return -1;
    DIR *dir;
    RP_CALL(RP_META,-1,dir,opendir(src));
    if (!dir)
      return -1;
    int rc= 0;
    if (restore_probe.enabled) restore_probe.directories++;
    struct dirent *entry;
    for (;;)
    {
      errno= 0;
      RP_CALL(RP_META,-1,entry,readdir(dir));
      if (!entry)
      {
        if (errno)
        {
          fprintf(stderr, "snapshot readdir %s: %s\n", src, strerror(errno));
          rc= -1;
        }
        break;
      }
      if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, ".."))
        continue;
      char from[4096], to[4096];
      if (snprintf(from, sizeof(from), "%s/%s", src, entry->d_name) >= (int)sizeof(from) ||
          snprintf(to, sizeof(to), "%s/%s", dst, entry->d_name) >= (int)sizeof(to) ||
          snapshot_copy(from, to, depth + 1))
      {
        fprintf(stderr, "snapshot copy %s -> %s: %s\n", from, to, strerror(errno));
        rc= -1;
        break;
      }
    }
    RP_CALL(RP_META,-1,status,closedir(dir));
    if (status)
    {
      fprintf(stderr, "snapshot closedir %s: %s\n", src, strerror(errno));
      rc= -1;
    }
    if (!depth && restore_probe.enabled) restore_probe.end= rp_now();
    return rc;
  }
  if (!S_ISREG(st.st_mode))
    return -1;
  int file= -1;
  rp_stamp file_begin= {0};
  if (restore_probe.enabled) {
    file_begin= rp_now();
    if (restore_probe.count < 256) {
      file= restore_probe.count++;
      if (snprintf(restore_probe.files[file].path,384,"%s",src) >= 384) restore_probe.dropped++;
      restore_probe.files[file].size= st.st_size;
    } else restore_probe.dropped++;
  }
  FILE *in;
  RP_CALL(RP_SRC_OPEN,file,in,fopen(src, "rb"));
  if (!in) return -1;
  FILE *out;
  RP_CALL(RP_DST_OPEN,file,out,fopen(dst, "wbx"));
  if (!out)
  {
    RP_CALL(RP_SRC_CLOSE,file,status,fclose(in));
    return -1;
  }
  unsigned char buffer[65536];
  size_t n;
  int rc= 0;
  for (;;)
  {
    rp_stamp begin= {0};
    if (restore_probe.enabled) begin= rp_now();
    n= fread(buffer, 1, sizeof(buffer), in);
    rp_finish(RP_READ,file,begin,n);
    if (!n) break;
    if (restore_probe.enabled) begin= rp_now();
    size_t written= fwrite(buffer, 1, n, out);
    rp_finish(RP_WRITE,file,begin,written);
    if (written != n)
    {
      rc= -1;
      break;
    }
  }
  if (ferror(in)) rc= -1;
  RP_CALL(RP_SRC_CLOSE,file,status,fclose(in));
  if (status) rc= -1;
  RP_CALL(RP_DST_CLOSE,file,status,fclose(out));
  if (status) rc= -1;
  if (file >= 0) restore_probe.files[file].wall= rp_now().wall-file_begin.wall;
  return rc;
}

/* Exact recursive inventory and byte comparison, outside timed copy. */
static int restore_equal(const char *a, const char *b, unsigned depth)
{
  struct stat sa,sb;
  if(depth>64 || lstat(a,&sa) || lstat(b,&sb)) return -1;
  if(S_ISDIR(sa.st_mode) && S_ISDIR(sb.st_mode)) {
    DIR *da=opendir(a),*db=opendir(b); int rc=0,na=0,nb=0;
    if(!da || !db) { if(da)closedir(da); if(db)closedir(db); return -1; }
    struct dirent *e;
    for(;;) {
      errno=0; e=readdir(da); if(!e) { if(errno)rc=-1; break; }
      if(!strcmp(e->d_name,".") || !strcmp(e->d_name,".."))continue;
      na++; char pa[4096],pb[4096];
      if(snprintf(pa,sizeof(pa),"%s/%s",a,e->d_name)>=(int)sizeof(pa) ||
         snprintf(pb,sizeof(pb),"%s/%s",b,e->d_name)>=(int)sizeof(pb) || restore_equal(pa,pb,depth+1)) {rc=-1;break;}
    }
    for(;;) {errno=0;e=readdir(db);if(!e){if(errno)rc=-1;break;}if(strcmp(e->d_name,".")&&strcmp(e->d_name,".."))nb++;}
    if(closedir(da))rc=-1; if(closedir(db))rc=-1;
    return rc || na!=nb ? -1 : 0;
  }
  if(!S_ISREG(sa.st_mode)||!S_ISREG(sb.st_mode)||sa.st_size!=sb.st_size)return -1;
  FILE *fa=fopen(a,"rb"),*fb=fopen(b,"rb");int rc=0;
  if(!fa||!fb){if(fa)fclose(fa);if(fb)fclose(fb);return -1;}
  unsigned char ba[65536],bb[65536];size_t n,m;
  do {n=fread(ba,1,sizeof(ba),fa);m=fread(bb,1,sizeof(bb),fb);if(n!=m||memcmp(ba,bb,n)){rc=-1;break;}}while(n);
  if(ferror(fa)||ferror(fb))rc=-1;
  if(fclose(fa))rc=-1;if(fclose(fb))rc=-1;return rc;
}
static int snapshot_restore(void)
{
  const char *original="/snapshot-in/data",*source=original;
  restore_source_experiment=getenv("MARIAMEM_SOURCE_BOUNDARY_PROBE")!=NULL;
  if(restore_source_experiment && !getenv("MARIAMEM_RESTORE_DIAGNOSTICS"))return -1;
  if(restore_source_experiment && getenv("MARIAMEM_GUEST_RESTORE_SOURCE")) {
    if(snapshot_copy(original,"/restore-source",0))return -1;
    restore_prestage=restore_probe;
    rp_stamp begin=rp_now();int rc=restore_equal(original,"/restore-source",0);
    rp_add(&restore_verification,begin,rp_now(),0);if(rc)return -1;
    source="/restore-source";
  }
  if(snapshot_copy(source,"/mariadb",0))return -1;
  if(restore_source_experiment) {
    rp_stamp begin=rp_now();int rc=restore_equal(original,"/mariadb",0);
    rp_add(&restore_verification,begin,rp_now(),0);if(rc)return -1;
    restore_identity_verified=1;
  }
  return 0;
}
