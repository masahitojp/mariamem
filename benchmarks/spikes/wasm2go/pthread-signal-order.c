// Isolated source-ordering reduction; no MariaDB/runtime configuration changes.
// A predicate read before its mutex is deliberately stale, like buf0flu.cc.
#include <pthread.h>
#include <stdatomic.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static pthread_mutex_t work = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t control = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t condition = PTHREAD_COND_INITIALIZER;
static pthread_cond_t progress = PTHREAD_COND_INITIALIZER;
static atomic_int target;
static int read_done, entering, finished, observed, live, rc;
static double elapsed_ms;
static void check(int error) { if (error) abort(); }
static double seconds(struct timespec t) { return t.tv_sec + t.tv_nsec / 1e9; }
static void *worker(void *unused) {
    (void)unused;
    observed = atomic_load(&target);
    check(pthread_mutex_lock(&control));
    read_done = 1;
    check(pthread_cond_broadcast(&progress));
    check(pthread_mutex_unlock(&control));
    check(pthread_mutex_lock(&work));
    live = atomic_load(&target);
    check(pthread_mutex_lock(&control));
    entering = 1;
    check(pthread_cond_broadcast(&progress));
    check(pthread_mutex_unlock(&control));
    struct timespec start, end, deadline;
    check(clock_gettime(CLOCK_MONOTONIC, &start));
    check(clock_gettime(CLOCK_REALTIME, &deadline));
    deadline.tv_sec++;
    rc = pthread_cond_timedwait(&condition, &work, &deadline);
    check(clock_gettime(CLOCK_MONOTONIC, &end));
    elapsed_ms = 1000 * (seconds(end) - seconds(start));
    check(pthread_mutex_unlock(&work));
    check(pthread_mutex_lock(&control));
    finished = 1;
    check(pthread_cond_broadcast(&progress));
    check(pthread_mutex_unlock(&control));
    return NULL;
}
static void await(int *flag) {
    check(pthread_mutex_lock(&control));
    while (!*flag) check(pthread_cond_wait(&progress, &control));
    check(pthread_mutex_unlock(&control));
}
int main(void) {
    for (int early = 1; early >= 0; early--) {
        read_done = entering = finished = 0;
        atomic_store(&target, 0);
        if (early) check(pthread_mutex_lock(&work));
        pthread_t thread;
        check(pthread_create(&thread, NULL, worker, NULL));
        await(early ? &read_done : &entering);
        // In the fast case, taking work proves pthread_cond_timedwait has
        // atomically registered its waiter and released the application mutex.
        if (!early) check(pthread_mutex_lock(&work));
        atomic_store(&target, 12288);
        check(pthread_cond_signal(&condition));
        check(pthread_mutex_unlock(&work));
        await(&finished);
        check(pthread_join(thread, NULL));
        int valid = observed == 0 && atomic_load(&target) == 12288 &&
            (early ? (live == 12288 && rc == ETIMEDOUT && elapsed_ms >= 900)
                   : (rc == 0 && elapsed_ms < 500));
        printf("{\"early_signal\":%s,\"observed\":%d,\"live_before_wait\":%d,"
               "\"timeout\":%s,\"elapsed_ms\":%.3f,\"valid\":%s}\n",
               early ? "true" : "false", observed, live,
               rc == ETIMEDOUT ? "true" : "false", elapsed_ms,
               valid ? "true" : "false");
        if (!valid) return 1;
    }
    return 0;
}
