"""Bounded key validation and real authentication acceptance for pinned MariaDB.

The acceptance helper is invoked only by the dedicated guest acceptance command.
Normal embedded SQL keeps its existing grant bypass and connection behavior.
"""
from pathlib import Path


PLUGIN = 'plugin/auth_mysql_sha2/mysql_sha2.c'
SSL = 'plugin/auth_mysql_sha2/ssl_stuff.c'

INIT_OLD = '''    ssl_genkeys();
  ssl_loadkeys();
  return 0;
}'''
INIT_NEW = '''  {
    mariamem_auth_generated= 1;
    if (ssl_genkeys())
      return 1;
  }
  int result= ssl_loadkeys();
  mariamem_auth_loaded= result == 0;
  return result;
}'''

LOAD_OLD = '''  public_key[len]= 0;
  public_key_len= len;
  private_key= pkey;
  return 0;'''
LOAD_NEW = '''  bio= NULL;
  public_key[len]= 0;
  bio= BIO_new_mem_buf(public_key, (int)len);
  if (!bio)
    goto err;
  EVP_PKEY *public_pkey= PEM_read_bio_PUBKEY(bio, NULL, NULL, NULL);
  /* Pinned wolfSSL defaults to 0 for matching keys, unlike OpenSSL's 1.
   * Its optional OpenSSL error-code mode restores the OpenSSL convention. */
#if defined(LIBWOLFSSL_VERSION_HEX) && !defined(WOLFSSL_ERROR_CODE_OPENSSL)
  const int keys_match= 0;
#else
  const int keys_match= 1;
#endif
  int valid= public_pkey && EVP_PKEY_base_id(pkey) == EVP_PKEY_RSA &&
    EVP_PKEY_bits(pkey) == 2048 && EVP_PKEY_cmp(pkey, public_pkey) == keys_match;
  EVP_PKEY_free(public_pkey);
  if (!valid)
    SSL_ERROR("validate RSA-2048 pair", public_key_path);
  BIO_free(bio);
  public_key_len= len;
  private_key= pkey;
  return 0;'''

# In the plugin translation unit these use the real static auth/password helpers,
# not a reimplementation. The mock provides only the client transport/response.
SELF_TEST = r'''

/* mariamem: bounded acceptance of the actual full-authentication callback.
 * These public test credentials never create a SQL account or alter grants. */
#include <openssl/pem.h>
#include <openssl/rsa.h>

int mariamem_auth_keys_ready(void)
{
  return mariamem_auth_loaded && !mariamem_auth_generated &&
         private_key != NULL && public_key_len > 0;
}

struct mariamem_auth_vio {
  MYSQL_PLUGIN_VIO vio; /* first member: VIO callbacks recover test state */
  unsigned int step;
  unsigned char scramble[SCRAMBLE_LENGTH];
  unsigned char packet[512];
  size_t encrypted_len;
  const char *password;
  int malformed;
  int failed;
};

static int mariamem_auth_write(MYSQL_PLUGIN_VIO *vio,
                              const unsigned char *packet, int length)
{
  struct mariamem_auth_vio *v= (struct mariamem_auth_vio *)vio;
  if (v->step == 0 && length == SCRAMBLE_LENGTH + 1 &&
      packet[SCRAMBLE_LENGTH] == 0)
  {
    memcpy(v->scramble, packet, SCRAMBLE_LENGTH);
    v->step= 1;
    return 0;
  }
  if (v->step == 2 && length == 1 && packet[0] == 4)
  {
    v->step= 3;
    return 0;
  }
  if (v->step == 4 && length == (int)public_key_len &&
      memcmp(packet, public_key, public_key_len) == 0)
  {
    BIO *bio= BIO_new_mem_buf(packet, length);
    EVP_PKEY *key= bio ? PEM_read_bio_PUBKEY(bio, NULL, NULL, NULL) : NULL;
    BIO_free(bio);
    EVP_PKEY_CTX *ctx= key ? EVP_PKEY_CTX_new(key, NULL) : NULL;
    unsigned char plain[128];
    size_t n= strlen(v->password) + 1;
    int ok= ctx != NULL && n <= sizeof(plain);
    if (ok)
    {
      for (size_t i= 0; i < n; i++)
        plain[i]= ((const unsigned char *)v->password)[i] ^
                  v->scramble[i % SCRAMBLE_LENGTH];
      v->encrypted_len= sizeof(v->packet);
      ok= EVP_PKEY_encrypt_init(ctx) > 0 &&
          EVP_PKEY_CTX_set_rsa_padding(ctx, RSA_PKCS1_OAEP_PADDING) > 0 &&
          EVP_PKEY_encrypt(ctx, v->packet, &v->encrypted_len, plain, n) > 0;
    }
    EVP_PKEY_CTX_free(ctx);
    EVP_PKEY_free(key);
    if (ok)
    {
      v->step= 5;
      return 0;
    }
  }
  v->failed= 1;
  return 1;
}

static int mariamem_auth_read(MYSQL_PLUGIN_VIO *vio, unsigned char **packet)
{
  struct mariamem_auth_vio *v= (struct mariamem_auth_vio *)vio;
  *packet= v->packet;
  if (v->step == 1)
  {
    /* This plugin always requests full auth; the fast response is ignored. */
    memset(v->packet, 0x5a, SHA256_DIGEST_LENGTH);
    v->step= 2;
    return SHA256_DIGEST_LENGTH;
  }
  if (v->step == 3)
  {
    v->packet[0]= 2; /* request the real server public key */
    v->step= 4;
    return 1;
  }
  if (v->step == 5)
  {
    v->step= 6;
    if (v->malformed)
    {
      memset(v->packet, 0, v->encrypted_len); /* invalid OAEP encoding */
    }
    return (int)v->encrypted_len;
  }
  v->failed= 1;
  return -1;
}

static void mariamem_auth_info(MYSQL_PLUGIN_VIO *vio,
                              MYSQL_PLUGIN_VIO_INFO *info)
{
  (void)vio;
  memset(info, 0, sizeof(*info));
  info->protocol= MYSQL_VIO_TCP;
  info->tls= 0; /* force RSA, never the secure-transport plaintext shortcut */
}

int mariamem_auth_key_self_test(void)
{
  const char *password= "mariamem-public-auth-acceptance";
  char hash[256];
  size_t hash_len= sizeof(hash);
  union {
    struct digest value;
    unsigned char bytes[sizeof(struct digest) + 1];
  } account;
  size_t account_len= sizeof(account);
  if (!mariamem_auth_keys_ready() ||
      password_hash(password, strlen(password), hash, &hash_len) ||
      digest_to_binary(hash, hash_len, account.bytes, &account_len))
    return 1;
  for (int test= 0; test < 3; test++)
  {
    struct mariamem_auth_vio v;
    MYSQL_SERVER_AUTH_INFO account_info;
    memset(&v, 0, sizeof(v));
    memset(&account_info, 0, sizeof(account_info));
    v.vio.read_packet= mariamem_auth_read;
    v.vio.write_packet= mariamem_auth_write;
    v.vio.info= mariamem_auth_info;
    v.password= test == 1 ? "mariamem-deliberately-wrong" : password;
    v.malformed= test == 2;
    account_info.user_name= "mariamem_acceptance";
    account_info.user_name_length= (unsigned int)strlen(account_info.user_name);
    account_info.auth_string= (const char *)account.bytes;
    account_info.auth_string_length= account_len;
    int result= auth(&v.vio, &account_info);
    int expected= test == 0 ? CR_OK :
                  test == 1 ? CR_AUTH_USER_CREDENTIALS : CR_ERROR;
    if (v.failed || v.step != 6 || result != expected ||
        account_info.password_used != PASSWORD_USED_YES)
      return test + 2;
  }
  return 0;
}
'''


def _replace(text, old, new, name):
    if text.count(old) != 1:
        raise ValueError(f'authentication source anchor changed: {name}')
    return text.replace(old, new)


def prepare(source: Path):
    """Apply to pristine pinned plugin sources; reject reapplication/drift."""
    plugin = (source / PLUGIN).read_text()
    ssl = (source / SSL).read_text()
    if 'mariamem_auth_key_self_test' in plugin:
        raise ValueError('authentication source anchor changed: already prepared')
    plugin = _replace(plugin, 'static int init_keys(void *p)',
                      'static int mariamem_auth_generated, mariamem_auth_loaded;\n\n'
                      'static int init_keys(void *p)', 'init state')
    plugin = _replace(plugin, INIT_OLD, INIT_NEW, 'init_keys') + SELF_TEST
    ssl = _replace(ssl, '  size_t len;', '  int len;', 'public length type')
    ssl = _replace(ssl, '  if (len == sizeof(public_key))',
                   '  if (len <= 0 || len >= (int)sizeof(public_key))',
                   'public length bounds')
    ssl = _replace(ssl, LOAD_OLD, LOAD_NEW, 'public PEM and key pair')
    # Check every anchor before writing either file.
    (source / PLUGIN).write_text(plugin)
    (source / SSL).write_text(ssl)
    return [PLUGIN, SSL]
