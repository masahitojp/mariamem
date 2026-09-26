/* Bounded diagnostics only. POSIX link wrappers observe successful calls from
 * guest objects, not libc-internal calls, host disk I/O, or memory-mapped I/O.
 * All real calls/errno remain intact. Disabled unless explicitly requested. */
#include <stdatomic.h>
#include <stdarg.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <string.h>
#ifdef __APPLE__
extern size_t malloc_size(const void *);
#define malloc_usable_size malloc_size
#else
#include <malloc.h>
#endif
#include <pthread.h>
#include <errno.h>

#define INIT_EVENTS 32
#define INIT_FILES 96
#define INIT_FDS 4096
static int init_enabled;
static _Thread_local int init_internal;
static pthread_mutex_t init_lock = PTHREAD_MUTEX_INITIALIZER;
static _Atomic int64_t init_alloc_balance, init_mmap_balance;
static _Atomic uint64_t init_alloc_requested, init_threads;
static struct init_file {
  char path[384];
  uint64_t read_bytes, write_bytes, read_calls, write_calls, io_ns, opens, truncates;
} init_files[INIT_FILES];
static int init_fd[INIT_FDS], init_file_count;
static uint64_t init_dropped, init_origin;
static struct init_event {
  const char *name;
  uint64_t wall, process_cpu, thread_cpu, memory, requested, threads, read_bytes, write_bytes, io_ns;
  int64_t alloc_balance;
  int64_t mmap_balance;
  int process_valid, thread_valid;
} init_events[INIT_EVENTS];
static int init_event_count;

static uint64_t init_clock(clockid_t id, int *valid)
{
  struct timespec ts;
  *valid = !clock_gettime(id, &ts);
  return *valid ? (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec : 0;
}
static uint64_t init_now(void) { int valid; return init_clock(CLOCK_MONOTONIC, &valid); }
static void init_enable(void)
{
  init_enabled = getenv("MARIAMEM_INIT_DIAGNOSTICS") != NULL;
  if (init_enabled) {
    for (int i=0; i<INIT_FDS; i++) init_fd[i] = -1;
    init_origin = init_now();
  }
}
void mariamem_init_mark(const char *name)
{
  if (!init_enabled) return;
  int saved = errno;
  pthread_mutex_lock(&init_lock);
  if (init_event_count < INIT_EVENTS) {
    struct init_event *e = &init_events[init_event_count++];
    e->name=name; e->wall=init_now()-init_origin;
    e->process_cpu=init_clock(CLOCK_PROCESS_CPUTIME_ID, &e->process_valid);
    e->thread_cpu=init_clock(CLOCK_THREAD_CPUTIME_ID, &e->thread_valid);
#ifdef __wasm__
    e->memory=(uint64_t)__builtin_wasm_memory_size(0)*65536;
#endif
    e->alloc_balance=atomic_load(&init_alloc_balance);
    e->mmap_balance=atomic_load(&init_mmap_balance);
    e->requested=atomic_load(&init_alloc_requested);
    e->threads=atomic_load(&init_threads);
    for (int i=0; i<init_file_count; i++) {
      e->read_bytes+=init_files[i].read_bytes; e->write_bytes+=init_files[i].write_bytes;
      e->io_ns+=init_files[i].io_ns;
    }
  } else init_dropped++;
  pthread_mutex_unlock(&init_lock);
  errno=saved;
}
static void init_quote(FILE *f, const char *s)
{
  fputc('"', f);
  for (; *s; s++) {
    unsigned char c=(unsigned char)*s;
    if (c=='"' || c=='\\') fprintf(f, "\\%c", c);
    else if (c<32) fprintf(f, "\\u%04x", c);
    else fputc(c, f);
  }
  fputc('"', f);
}
static void init_write(FILE *f)
{
  if (!init_enabled) return;
  init_internal=1;
  pthread_mutex_lock(&init_lock);
  fputs(",\"initialization\":{\"version\":1,\"clock\":\"guest_monotonic\",\"events\":[", f);
  for (int i=0; i<init_event_count; i++) {
    struct init_event *e=&init_events[i];
    if (i) fputc(',',f);
    fputs("{\"name\":", f); init_quote(f,e->name);
    fprintf(f,",\"offset_ns\":%llu,\"process_cpu_ns\":",(unsigned long long)e->wall);
    if (e->process_valid) fprintf(f,"%llu",(unsigned long long)e->process_cpu); else fputs("null",f);
    fputs(",\"thread_cpu_ns\":",f);
    if (e->thread_valid) fprintf(f,"%llu",(unsigned long long)e->thread_cpu); else fputs("null",f);
    fprintf(f,",\"linear_memory_bytes\":%llu,\"wrapped_alloc_balance_bytes\":%lld,\"wrapped_mmap_balance_bytes\":%lld,\"wrapped_alloc_requested_bytes\":%llu,\"pthread_creates\":%llu,\"read_bytes\":%llu,\"write_bytes\":%llu,\"io_call_ns\":%llu}",
      (unsigned long long)e->memory,(long long)e->alloc_balance,(long long)e->mmap_balance,(unsigned long long)e->requested,
      (unsigned long long)e->threads,(unsigned long long)e->read_bytes,(unsigned long long)e->write_bytes,(unsigned long long)e->io_ns);
  }
  fputs("],\"files\":[",f);
  for (int i=0; i<init_file_count; i++) {
    struct init_file *v=&init_files[i]; if (i) fputc(',',f);
    fputs("{\"path\":",f); init_quote(f,v->path);
    fprintf(f,",\"read_bytes\":%llu,\"write_bytes\":%llu,\"read_calls\":%llu,\"write_calls\":%llu,\"io_call_ns\":%llu,\"opens\":%llu,\"truncates\":%llu}",
      (unsigned long long)v->read_bytes,(unsigned long long)v->write_bytes,(unsigned long long)v->read_calls,(unsigned long long)v->write_calls,
      (unsigned long long)v->io_ns,(unsigned long long)v->opens,(unsigned long long)v->truncates);
  }
  fprintf(f,"],\"dropped_records\":%llu}",(unsigned long long)init_dropped);
  pthread_mutex_unlock(&init_lock);
  init_internal=0;
}

#ifdef MARIAMEM_DIAGNOSTIC_TEST
#define __real_open open
#define __real_close close
#define __real_read read
#define __real_write write
#define __real_pread pread
#define __real_pwrite pwrite
#define __real_ftruncate ftruncate
#define __real_malloc malloc
#define __real_calloc calloc
#define __real_realloc realloc
#define __real_free free
#define __real_posix_memalign posix_memalign
#define __real_mmap mmap
#define __real_munmap munmap
#define __real_pthread_create pthread_create
#endif
extern int __real_open(const char *, int, ...);
extern int __real_close(int);
extern ssize_t __real_read(int, void *, size_t);
extern ssize_t __real_write(int, const void *, size_t);
extern ssize_t __real_pread(int, void *, size_t, off_t);
extern ssize_t __real_pwrite(int, const void *, size_t, off_t);
extern int __real_ftruncate(int, off_t);
extern void *__real_malloc(size_t);
extern void *__real_calloc(size_t,size_t);
extern void *__real_realloc(void *,size_t);
extern void __real_free(void *);
extern int __real_posix_memalign(void **,size_t,size_t);
extern void *__real_mmap(void *,size_t,int,int,int,off_t);
extern int __real_munmap(void *,size_t);
extern int __real_pthread_create(pthread_t *,const pthread_attr_t *,void *(*)(void *),void *);

static void init_opened(int fd,const char *path,int flags)
{
  if (!init_enabled || init_internal || fd<0) return;
  int saved=errno;
  char full[384];
  if(path[0]!='/') {
    char cwd[384];
    if(!getcwd(cwd,sizeof(cwd)) || snprintf(full,sizeof(full),"%s/%s",cwd,path)>=(int)sizeof(full)) { errno=saved; return; }
    path=full;
  }
  if(strncmp(path,"/mariadb/",9)) { errno=saved; return; }
  pthread_mutex_lock(&init_lock);
  if (fd<INIT_FDS && strlen(path)<sizeof(init_files[0].path)) {
    int i; for(i=0;i<init_file_count;i++) if(!strcmp(path,init_files[i].path)) break;
    if(i==init_file_count && i<INIT_FILES) { strcpy(init_files[i].path,path); init_file_count++; }
    if(i<INIT_FILES) { init_fd[fd]=i; init_files[i].opens++; if(flags&O_TRUNC) init_files[i].truncates++; }
    else init_dropped++;
  } else init_dropped++;
  pthread_mutex_unlock(&init_lock); errno=saved;
}
int __wrap_open(const char *path,int flags,...)
{
  mode_t mode=0; if(flags&O_CREAT) { va_list ap; va_start(ap,flags); mode=va_arg(ap,int); va_end(ap); }
  int fd=__real_open(path,flags,mode); init_opened(fd,path,flags); return fd;
}
int __wrap_open64(const char *path,int flags,...)
{
  mode_t mode=0; if(flags&O_CREAT) { va_list ap; va_start(ap,flags); mode=va_arg(ap,int); va_end(ap); }
  int fd=__real_open(path,flags,mode); init_opened(fd,path,flags); return fd;
}
static void init_io(int fd,ssize_t n,int write_op,uint64_t begin)
{
  if (!init_enabled || init_internal || n<0) return;
  int saved=errno; uint64_t elapsed=init_now()-begin;
  pthread_mutex_lock(&init_lock);
  if(fd>=0 && fd<INIT_FDS && init_fd[fd]>=0) {
    struct init_file *v=&init_files[init_fd[fd]];
    if(write_op) { v->write_bytes+=n; v->write_calls++; } else { v->read_bytes+=n; v->read_calls++; }
    v->io_ns+=elapsed;
  }
  pthread_mutex_unlock(&init_lock); errno=saved;
}
ssize_t __wrap_read(int fd,void *p,size_t n) { uint64_t t=init_enabled?init_now():0; ssize_t r=__real_read(fd,p,n); init_io(fd,r,0,t); return r; }
ssize_t __wrap_write(int fd,const void *p,size_t n) { uint64_t t=init_enabled?init_now():0; ssize_t r=__real_write(fd,p,n); init_io(fd,r,1,t); return r; }
ssize_t __wrap_pread(int fd,void *p,size_t n,off_t o) { uint64_t t=init_enabled?init_now():0; ssize_t r=__real_pread(fd,p,n,o); init_io(fd,r,0,t); return r; }
ssize_t __wrap_pwrite(int fd,const void *p,size_t n,off_t o) { uint64_t t=init_enabled?init_now():0; ssize_t r=__real_pwrite(fd,p,n,o); init_io(fd,r,1,t); return r; }
ssize_t __wrap_pread64(int fd,void *p,size_t n,off_t o) { return __wrap_pread(fd,p,n,o); }
ssize_t __wrap_pwrite64(int fd,const void *p,size_t n,off_t o) { return __wrap_pwrite(fd,p,n,o); }
int __wrap_close(int fd)
{
  int r=__real_close(fd),saved=errno;
  if(init_enabled && r==0 && fd>=0 && fd<INIT_FDS) { pthread_mutex_lock(&init_lock); init_fd[fd]=-1; pthread_mutex_unlock(&init_lock); }
  errno=saved; return r;
}
int __wrap_ftruncate(int fd,off_t n)
{
  int r=__real_ftruncate(fd,n),saved=errno;
  if(init_enabled && r==0) { pthread_mutex_lock(&init_lock); if(fd>=0 && fd<INIT_FDS && init_fd[fd]>=0) init_files[init_fd[fd]].truncates++; pthread_mutex_unlock(&init_lock); }
  errno=saved; return r;
}
int __wrap_ftruncate64(int fd,off_t n) { return __wrap_ftruncate(fd,n); }
void *__wrap_malloc(size_t n) { void *p=__real_malloc(n); if(init_enabled && p) { atomic_fetch_add(&init_alloc_balance,malloc_usable_size(p)); atomic_fetch_add(&init_alloc_requested,n); } return p; }
void *__wrap_calloc(size_t n,size_t size) { void *p=__real_calloc(n,size); if(init_enabled && p) { atomic_fetch_add(&init_alloc_balance,malloc_usable_size(p)); atomic_fetch_add(&init_alloc_requested,(uint64_t)n*size); } return p; }
void __wrap_free(void *p) { if(init_enabled && p) atomic_fetch_sub(&init_alloc_balance,malloc_usable_size(p)); __real_free(p); }
int __wrap_posix_memalign(void **p,size_t align,size_t n)
{
  int r=__real_posix_memalign(p,align,n);
  if(init_enabled && !r) { atomic_fetch_add(&init_alloc_balance,malloc_usable_size(*p)); atomic_fetch_add(&init_alloc_requested,n); }
  return r;
}
void *__wrap_mmap(void *p,size_t n,int prot,int flags,int fd,off_t off)
{
  void *r=__real_mmap(p,n,prot,flags,fd,off);
  if(init_enabled && r!=MAP_FAILED) atomic_fetch_add(&init_mmap_balance,n);
  return r;
}
void *__wrap_mmap64(void *p,size_t n,int prot,int flags,int fd,off_t off) { return __wrap_mmap(p,n,prot,flags,fd,off); }
int __wrap_munmap(void *p,size_t n)
{
  int r=__real_munmap(p,n); if(init_enabled && !r) atomic_fetch_sub(&init_mmap_balance,n); return r;
}
void *__wrap_realloc(void *p,size_t n)
{
  size_t old=init_enabled && p?malloc_usable_size(p):0;
  void *q=__real_realloc(p,n);
  if(init_enabled && (q || !n)) { atomic_fetch_add(&init_alloc_balance,(int64_t)(q?malloc_usable_size(q):0)-(int64_t)old); if(q) atomic_fetch_add(&init_alloc_requested,n); }
  return q;
}
int __wrap_pthread_create(pthread_t *t,const pthread_attr_t *a,void *(*fn)(void *),void *arg)
{
  int r=__real_pthread_create(t,a,fn,arg); if(init_enabled && !r) atomic_fetch_add(&init_threads,1); return r;
}
