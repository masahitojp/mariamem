/* Resident guest: one persistent WASIX worker per reusable slot.
 * Request: u32le length, u8 opcode, u32le request id, u32le slot, SQL bytes.
 * 1=open, 2=query, 3=close; zero-length frame shuts down all sessions.
 * Responses may be reordered and carry request_id + connection_id.
 */
#define MULTI_LIMIT 16
typedef struct {
  pthread_t thread;
  pthread_mutex_t mutex;
  pthread_cond_t condition;
  int started, live, busy, stop, op;
  uint32_t request, slot;
  char *sql;
  size_t length;
} multi_slot;
static multi_slot multi_slots[MULTI_LIMIT];
static pthread_mutex_t multi_output= PTHREAD_MUTEX_INITIALIZER;

static uint32_t multi_u32(const unsigned char *p)
{
  return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static void multi_reply(uint32_t request, uint32_t slot, const char *json)
{
  buf_t b= {0};
  char prefix[128];
  snprintf(prefix, sizeof(prefix), "{\"request_id\":%u,\"connection_id\":%u,\"result\":", request, slot);
  if (!json || buf_puts(&b, prefix) || buf_puts(&b, json) || buf_putc(&b, '}'))
    _Exit(20);
  uint32_t n= (uint32_t)b.n;
  unsigned char h[4]= {n & 255, n >> 8 & 255, n >> 16 & 255, n >> 24 & 255};
  pthread_mutex_lock(&multi_output);
  int rc= fwrite(h, 1, 4, stdout) != 4 || fwrite(b.p, 1, b.n, stdout) != b.n || fflush(stdout);
  pthread_mutex_unlock(&multi_output);
  free(b.p);
  if (rc) _Exit(21);
}

static void multi_error(uint32_t request, uint32_t slot, unsigned int code, const char *message)
{
  char *json= wire_error(code, message, "HY000");
  multi_reply(request, slot, json);
  free(json);
}

static void *multi_worker(void *arg)
{
  multi_slot *s= arg;
  if (mysql_thread_init()) _Exit(22);
  for (;;)
  {
    pthread_mutex_lock(&s->mutex);
    while (!s->op && !s->stop)
      pthread_cond_wait(&s->condition, &s->mutex);
    int op= s->op, stop= s->stop;
    uint32_t request= s->request;
    char *sql= s->sql;
    size_t length= s->length;
    s->op= 0;
    s->sql= NULL;
    pthread_mutex_unlock(&s->mutex);
    if (stop)
    {
      free(sql);
      if (multi_mysql) mysql_close(multi_mysql);
      multi_mysql= NULL;
      mysql_thread_end();
      return NULL;
    }
    char *reply= NULL;
    if (op == 1)
    {
      multi_mysql= mysql_init(NULL);
      if (!multi_mysql || !mysql_real_connect(multi_mysql, NULL, "root", "", "test", 0, NULL, 0) ||
          mysql_query(multi_mysql, "SET NAMES utf8mb4"))
      {
        reply= wire_error(multi_mysql ? mysql_errno(multi_mysql) : 2000,
                          multi_mysql ? mysql_error(multi_mysql) : "mysql_init failed", "HY000");
        if (multi_mysql) mysql_close(multi_mysql);
        multi_mysql= NULL;
      }
      else
        reply= strdup("{\"ok\":true,\"api_version\":2,\"server_status\":2}");
    }
    else if (op == 3)
    {
      mysql_close(multi_mysql);
      multi_mysql= NULL;
      reply= strdup("{\"ok\":true,\"closed\":true}");
    }
    else
      reply= l4m_query_v2(sql, (unsigned long)length);
    free(sql);
    pthread_mutex_lock(&s->mutex);
    s->live= multi_mysql != NULL;
    s->busy= 0;
    pthread_mutex_unlock(&s->mutex);
    multi_reply(request, s->slot, reply);
    free(reply);
  }
}

#include "snapshot_fs.inc"

int main(int argc, char **argv)
{
  if (argc > 2 || (argc == 2 && strcmp(argv[1], "--restore-snapshot"))) return 16;
  if (argc == 2 && snapshot_copy("/snapshot-in/data", "/mariadb", 0)) return 17;
  if (l4m_open()) return 11;
  /* Bootstrap connection creates test; engine remains alive after closing it. */
  mysql_close(g_mysql);
  g_mysql= NULL;
  for (unsigned int i= 0; i < MULTI_LIMIT; i++)
  {
    pthread_mutex_init(&multi_slots[i].mutex, NULL);
    pthread_cond_init(&multi_slots[i].condition, NULL);
    multi_slots[i].slot= i;
  }
  multi_reply(0, 0, "{\"ready\":true,\"api_version\":2,\"max_sessions\":16,\"snapshot_version\":1}");
  int rc= 0, export_snapshot= 0;
  for (;;)
  {
    unsigned char h[4];
    size_t got= fread(h, 1, 4, stdin);
    if (!got && feof(stdin)) break;
    if (got != 4) { rc= 13; break; }
    uint32_t n= multi_u32(h);
    if (!n) break;
    if (n == 0xfffffffe) { export_snapshot= 1; break; }
    if (n < 9 || n > 1048585) { rc= 14; break; }
    unsigned char *packet= malloc(n + 1);
    if (!packet) { rc= 10; break; }
    if (fread(packet, 1, n, stdin) != n) { free(packet); rc= 13; break; }
    packet[n]= 0;
    unsigned int op= packet[0];
    uint32_t request= multi_u32(packet + 1), slot= multi_u32(packet + 5);
    if (slot >= MULTI_LIMIT || op < 1 || op > 3)
      multi_error(request, slot, 1235, "unsupported request/slot");
    else
    {
      multi_slot *s= &multi_slots[slot];
      pthread_mutex_lock(&s->mutex);
      if (op == 1 && !s->live && !s->busy)
      {
        s->live= s->busy= 1;
        s->stop= 0;
        s->op= 1;
        s->request= request;
        if (!s->started)
        {
          int error= pthread_create(&s->thread, NULL, multi_worker, s);
          s->started= !error;
          if (error) { s->live= s->busy= 0; multi_error(request, slot, 2000, "pthread_create failed"); }
        }
        else
          pthread_cond_signal(&s->condition);
      }
      else if (op == 1 || !s->live || s->busy)
        multi_error(request, slot, 1235, "session exists, closed, or busy");
      else
      {
        s->request= request;
        s->length= n - 9;
        s->sql= malloc(s->length + 1);
        if (!s->sql) _Exit(20);
        memcpy(s->sql, packet + 9, s->length + 1);
        s->op= op;
        s->busy= 1;
        pthread_cond_signal(&s->condition);
      }
      pthread_mutex_unlock(&s->mutex);
    }
    free(packet);
  }
  for (unsigned int i= 0; i < MULTI_LIMIT; i++)
  {
    multi_slot *s= &multi_slots[i];
    pthread_mutex_lock(&s->mutex);
    s->stop= 1;
    pthread_cond_signal(&s->condition);
    pthread_mutex_unlock(&s->mutex);
  }
  for (unsigned int i= 0; i < MULTI_LIMIT; i++)
    if (multi_slots[i].started) pthread_join(multi_slots[i].thread, NULL);
  l4m_close();
  if (!rc && export_snapshot)
  {
    if (snapshot_copy("/mariadb", "/snapshot-out/data", 0)) return 17;
    multi_reply(0, 0, "{\"snapshot\":true,\"snapshot_version\":1}");
  }
  return rc;
}
