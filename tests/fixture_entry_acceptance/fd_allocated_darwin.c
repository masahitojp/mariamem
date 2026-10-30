/* Test-only owned-process observer; no mariamem host or product linkage. */
#include <errno.h>
#include <limits.h>
#include <libproc.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/proc_info.h>
#include <sys/stat.h>

#define FD_LIMIT 4096

static int unavailable(const char *operation) {
    fprintf(stderr, "UNVERIFIED %s errno=%d\n", operation, errno);
    return 1;
}

int main(int argc, char **argv) {
    char *end = NULL;
    if (argc != 2) return unavailable("expected one owned PID");
    errno = 0;
    long value = strtol(argv[1], &end, 10);
    if (errno || !end || *end || value <= 0 || value > INT_MAX)
        return unavailable("invalid PID");
    int pid = (int)value;
    struct proc_fdinfo fds[FD_LIMIT + 1];
    int bytes = proc_pidinfo(pid, PROC_PIDLISTFDS, 0, fds, sizeof(fds));
    if (bytes <= 0 || bytes >= (int)sizeof(fds) ||
        bytes % (int)sizeof(struct proc_fdinfo))
        return unavailable("descriptor census missing or beyond 4096");
    int count = bytes / (int)sizeof(struct proc_fdinfo);
    printf("{\"pid\":%d,\"fd_count\":%d,\"fds\":[", pid, count);
    for (int i = 0; i < count; i++) {
        if (i) printf(",");
        int fd = fds[i].proc_fd;
        if (fd < 0) return unavailable("negative FD");
        if (fds[i].proc_fdtype != PROX_FDTYPE_VNODE) {
            printf("{\"fd\":%d,\"regular\":false}", fd);
            continue;
        }
        struct vnode_fdinfo vnode;
        int got = proc_pidfdinfo(pid, fd, PROC_PIDFDVNODEINFO, &vnode, sizeof(vnode));
        if (got != (int)sizeof(vnode)) return unavailable("vnode observation");
        struct vinfo_stat *st = &vnode.pvi.vi_stat;
        if (!S_ISREG(st->vst_mode)) {
            printf("{\"fd\":%d,\"regular\":false}", fd);
            continue;
        }
        if (st->vst_blocks < 0 || st->vst_size < 0 || !st->vst_ino)
            return unavailable("invalid vnode counters");
        printf("{\"fd\":%d,\"regular\":true,\"device\":%llu,\"inode\":%llu,"
               "\"links\":%u,\"blocks\":%lld,\"logical_bytes\":%lld}",
               fd, (unsigned long long)st->vst_dev, (unsigned long long)st->vst_ino,
               (unsigned)st->vst_nlink, (long long)st->vst_blocks, (long long)st->vst_size);
    }
    printf("]}\n");
    return 0;
}
