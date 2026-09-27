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
typedef struct { uint64_t wall, process, thread, calls, bytes; int invalid; } rp_cost;
static struct {
  int enabled, count, dropped;
  uint64_t directories;
  rp_stamp begin, end;
  rp_cost stages[RP_STAGES];
  struct { char path[384]; uint64_t size, wall; rp_cost stages[RP_STAGES]; } files[256];
} restore_probe;

static rp_stamp rp_now(void)
{
  rp_stamp s= {0};
  int saved= errno;
  struct timespec t;
  s.valid= !clock_gettime(CLOCK_MONOTONIC, &t);
  if (s.valid) s.wall= (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec;
  int ok= !clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t);
  if (ok) s.process= (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec;
  s.valid &= ok;
  ok= !clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t);
  if (ok) s.thread= (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec;
  s.valid &= ok;
  errno= saved;
  return s;
}
static void rp_add(rp_cost *cost, rp_stamp begin, rp_stamp end, uint64_t bytes)
{
  cost->calls++; cost->bytes+= bytes;
  if (!begin.valid || !end.valid || end.wall<begin.wall ||
      end.process<begin.process || end.thread<begin.thread) { cost->invalid= 1; return; }
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

static void rp_write_cost(FILE *f, rp_cost *c)
{
  fprintf(f,"{\"wall_ns\":%llu,\"process_cpu_ns\":%llu,\"thread_cpu_ns\":%llu,\"calls\":%llu,\"bytes\":%llu,\"invalid_clock\":%s}",
    (unsigned long long)c->wall,(unsigned long long)c->process,
    (unsigned long long)c->thread,(unsigned long long)c->calls,
    (unsigned long long)c->bytes,c->invalid ? "true" : "false");
}
static void restore_probe_write(FILE *f)
{
  if (!restore_probe.enabled) return;
  fprintf(f,",\"restore_copy\":{\"version\":1,\"clock\":\"guest_monotonic\",\"wall_ns\":%llu,\"process_cpu_ns\":%llu,\"thread_cpu_ns\":%llu,\"invalid_clock\":%s,\"directories\":%llu,\"file_count\":%d,\"dropped_files\":%d,\"stages\":{",
    (unsigned long long)(restore_probe.end.wall-restore_probe.begin.wall),
    (unsigned long long)(restore_probe.end.process-restore_probe.begin.process),
    (unsigned long long)(restore_probe.end.thread-restore_probe.begin.thread),
    restore_probe.begin.valid && restore_probe.end.valid ? "false" : "true",
    (unsigned long long)restore_probe.directories,restore_probe.count,restore_probe.dropped);
  for (int i=0;i<RP_STAGES;i++) { if(i) fputc(',',f); fprintf(f,"\"%s\":",rp_names[i]); rp_write_cost(f,&restore_probe.stages[i]); }
  fputs("},\"files\":[",f);
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

static int snapshot_copy(const char *src, const char *dst, unsigned int depth)
{
  if (!depth) {
    restore_probe.enabled= !strcmp(src,"/snapshot-in/data") && getenv("MARIAMEM_RESTORE_DIAGNOSTICS") != NULL;
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
