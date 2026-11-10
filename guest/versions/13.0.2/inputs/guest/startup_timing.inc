/* Opt-in startup diagnostics only. Independent guest monotonic clock scope;
 * no new protocol messages, SQL, or runtime behavior. Never fail startup on I/O. */
#include <time.h>
#include <stdint.h>
#include "init_diagnostics.inc"

static struct {
  int enabled, count;
  uint64_t origin;
  const char *names[12];
  uint64_t offsets[12];
} startup_timing;

static void startup_mark(const char *name)
{
  if (!startup_timing.enabled || startup_timing.count == 12) return;
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts)) { startup_timing.enabled= 0; return; }
  uint64_t now= (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
  if (!startup_timing.count) startup_timing.origin= now;
  int i= startup_timing.count++;
  startup_timing.names[i]= name;
  startup_timing.offsets[i]= now - startup_timing.origin;
}

static void startup_write(void)
{
  if (!startup_timing.enabled) return;
  FILE *f= fopen("/snapshot-out/startup-timing.json", "w");
  if (!f) return;
  fputs("{\"version\":1,\"clock\":\"guest_monotonic\",\"events\":[", f);
  for (int i= 0; i < startup_timing.count; i++)
    fprintf(f, "%s{\"name\":\"%s\",\"offset_ns\":%llu}", i ? "," : "",
            startup_timing.names[i], (unsigned long long)startup_timing.offsets[i]);
  fputs("]", f);
  init_write(f);
  fputs("}\n", f);
  fclose(f);
}
