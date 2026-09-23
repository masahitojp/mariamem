/* Cold filesystem snapshots: copy only before open or after server shutdown.
 * /mariadb remains an unmounted memory FS in memory mode. Only the transfer
 * directories are host mounts. Never traverse symlinks or overwrite files.
 */
#include <dirent.h>

static int snapshot_copy(const char *src, const char *dst, unsigned int depth)
{
  struct stat st;
  if (depth > 64 || lstat(src, &st))
    return -1;
  if (S_ISDIR(st.st_mode))
  {
    if (mkdir(dst, 0700))
      return -1;
    DIR *dir= opendir(src);
    if (!dir)
      return -1;
    int rc= 0;
    struct dirent *entry;
    for (;;)
    {
      errno= 0;
      entry= readdir(dir);
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
    if (closedir(dir))
    {
      fprintf(stderr, "snapshot closedir %s: %s\n", src, strerror(errno));
      rc= -1;
    }
    return rc;
  }
  if (!S_ISREG(st.st_mode))
    return -1;
  FILE *in= fopen(src, "rb");
  if (!in) return -1;
  FILE *out= fopen(dst, "wbx");
  if (!out)
  {
    fclose(in);
    return -1;
  }
  unsigned char buffer[65536];
  size_t n;
  int rc= 0;
  while ((n= fread(buffer, 1, sizeof(buffer), in)))
    if (fwrite(buffer, 1, n, out) != n)
    {
      rc= -1;
      break;
    }
  if (ferror(in)) rc= -1;
  if (fclose(in)) rc= -1;
  if (fclose(out)) rc= -1;
  return rc;
}
