/* PUBLIC test keys embedded by preparation. No runtime generation or persistent
 * host files. /mariamem-auth lives outside snapshot-exported /mariadb. */
#include "mariamem_test_auth_keypair.h"

static int prepared_auth_write(const char *path, const char *data)
{
  FILE *f= fopen(path, "wbx");
  if (!f) return -1;
  size_t size= strlen(data);
  int rc= fwrite(data, 1, size, f) == size ? 0 : -1;
  if (fclose(f)) rc= -1;
  if (rc) unlink(path);
  return rc;
}
static int prepare_auth_keys(void)
{
  if (mkdir("/mariamem-auth", 0700) ||
      prepared_auth_write("/mariamem-auth/private.pem", mariamem_test_private_pem) ||
      prepared_auth_write("/mariamem-auth/public.pem", mariamem_test_public_pem)) {
    fprintf(stderr, "mariamem: prepared test authentication keys could not be created in guest memory filesystem; use the complete matching native bundle and inspect guest startup stderr (errno=%d)\n", errno);
    return -1;
  }
  return 0;
}
