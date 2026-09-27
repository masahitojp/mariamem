"""Fail-closed source preparation and actual pinned callback/crypto acceptance."""
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from guest_auth_hooks import INIT_OLD, LOAD_OLD, PLUGIN, SSL, prepare


def anchors(root):
    (root / PLUGIN).parent.mkdir(parents=True)
    (root / PLUGIN).write_text('static int init_keys(void *p)\n' + INIT_OLD)
    (root / SSL).write_text('  size_t len;\n  if (len == sizeof(public_key))\n' + LOAD_OLD)


def test_auth_hooks_fail_closed(tmp_path):
    anchors(tmp_path)
    assert prepare(tmp_path) == [PLUGIN, SSL]
    with pytest.raises(ValueError, match='already prepared'):
        prepare(tmp_path)


def test_auth_hooks_check_both_files_before_writing(tmp_path):
    anchors(tmp_path)
    before = (tmp_path / PLUGIN).read_text()
    (tmp_path / SSL).write_text('changed upstream')
    with pytest.raises(ValueError, match='anchor changed'):
        prepare(tmp_path)
    assert (tmp_path / PLUGIN).read_text() == before


@pytest.mark.parametrize('comparison_mode', ['openssl', 'wolfssl', 'wolfssl-openssl-codes'])
def test_native_pinned_authentication(tmp_path, comparison_mode):
    """Native crypto catches protocol/key regressions; WASIX CLI proves ABI/build.

    Requires prepared pinned input sources locally. We compile the unchanged
    actual password/hash/auth/load function bodies with minimal server-service
    adapters; no server instance, grants or network listener is introduced.
    """
    lock = json.loads((ROOT / 'release/inputs.lock.json').read_text())
    pinned = next(item for item in lock['inputs'] if item['name'] == 'lite4mariadb')
    archive = ROOT / 'build/downloads' / pinned['file']
    if not archive.exists():
        pytest.skip('pinned MariaDB source archive has not been fetched')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == pinned['sha256']
    cc = shutil.which('cc')
    openssl = shutil.which('openssl')
    if not cc or not openssl:
        pytest.skip('native compiler/OpenSSL unavailable')
    hash_source = 'plugin/auth_mysql_sha2/sha256crypt.c'
    with tarfile.open(archive) as tar:
        for name in (PLUGIN, SSL, hash_source):
            matches = [m for m in tar.getmembers() if m.isfile() and m.name.endswith('/' + name)]
            assert len(matches) == 1
            target = tmp_path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(matches[0]).read())
    prepare(tmp_path)
    plugin = (tmp_path / PLUGIN).read_text()
    # Keep actual plugin functions; replace only MariaDB registration boilerplate.
    functions = plugin[:plugin.index('static struct st_mysql_auth info=')]
    init = plugin[plugin.index('static int mariamem_auth_generated'):plugin.index('static int free_keys')]
    acceptance = plugin[plugin.index('/* mariamem: bounded acceptance'):]
    crypto = (tmp_path / SSL).read_text()
    crypt_hash = (tmp_path / hash_source).read_text()
    code = '\n'.join((functions, init, crypto, crypt_hash, acceptance))
    code = re.sub(r'^#include [<"](?:mysql_sha2.h|mysql/plugin_auth.h|mysqld_error.h|my_alloca.h)[>"]\n', '', code, flags=re.M)
    header = r'''
#include <assert.h>
#include <alloca.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <openssl/evp.h>
#include <openssl/sha.h>
#include <openssl/rand.h>
#include <openssl/rsa.h>
#include <openssl/pem.h>
#define SELF "caching_sha2_password"
#define SHA256CRYPT_LEN 43
#define SCRAMBLE_LENGTH 20
#define ME_ERROR_LOG_ONLY 0
#define ER_PASSWD_LENGTH 0
#define PASSWORD_USED_YES 1
#define CR_OK -1
#define CR_ERROR 0
#define CR_AUTH_USER_CREDENTIALS 1
#define CR_AUTH_PLUGIN_ERROR 3
typedef int my_bool;
typedef struct { int protocol, socket, tls; } MYSQL_PLUGIN_VIO_INFO;
enum { MYSQL_VIO_INVALID, MYSQL_VIO_TCP, MYSQL_VIO_SOCKET };
typedef struct st_plugin_vio {
 int (*read_packet)(struct st_plugin_vio*, unsigned char**);
 int (*write_packet)(struct st_plugin_vio*, const unsigned char*, int);
 void (*info)(struct st_plugin_vio*, MYSQL_PLUGIN_VIO_INFO*);
} MYSQL_PLUGIN_VIO;
typedef struct {
 const char *user_name;
 unsigned int user_name_length;
 const char *auth_string;
 unsigned long auth_string_length;
 int password_used;
} MYSQL_SERVER_AUTH_INFO;
static void my_printf_error(int n, const char *format, int flags, ...) {
 (void)n; (void)format; (void)flags;
}
#define my_snprintf snprintf
#define my_random_bytes(p,n) RAND_bytes((p),(n))
#define my_sha256_context_size() sizeof(SHA256_CTX)
#define my_sha256_init SHA256_Init
#define my_sha256_input SHA256_Update
static void my_sha256_result(SHA256_CTX *c, unsigned char *out) { SHA256_Final(out,c); }
static void my_sha256_multi(unsigned char *out, ...) {
 SHA256_CTX c; SHA256_Init(&c); va_list ap; va_start(ap,out);
 const unsigned char *p;
 while ((p=va_arg(ap,const unsigned char*))) {
  size_t n=va_arg(ap,size_t); SHA256_Update(&c,p,n);
 }
 va_end(ap); SHA256_Final(out,&c);
}
static struct { char *def_val; } defaults_private, defaults_public;
#define MYSQL_SYSVAR_NAME_private_key_path defaults_private
#define MYSQL_SYSVAR_NAME_public_key_path defaults_public
#define MYSQL_SYSVAR_NAME(n) MYSQL_SYSVAR_NAME_##n
int ssl_genkeys(void);
int ssl_loadkeys(void);
int ssl_decrypt(EVP_PKEY*,unsigned char*,size_t,unsigned char*,size_t*);
void sha256_crypt_r(const unsigned char*,size_t,const unsigned char*,size_t,unsigned char*,size_t);
'''
    # Exercise the guest backend's documented return convention as well as
    # OpenSSL. Keep real crypto and mismatched-pair rejection in every mode.
    if comparison_mode != 'openssl':
        header += '\n#define LIBWOLFSSL_VERSION_HEX 0x05009001\n'
        if comparison_mode == 'wolfssl-openssl-codes':
            header += '#define WOLFSSL_ERROR_CODE_OPENSSL\n'
        else:
            header += '''
static int guest_backend_key_cmp(const EVP_PKEY *a, const EVP_PKEY *b) {
  return EVP_PKEY_cmp(a, b) == 1 ? 0 : -1;
}
#define EVP_PKEY_cmp guest_backend_key_cmp
'''
    main = r'''
int main(int argc, char **argv) {
 if (argc != 3) return 90;
 private_key_path=argv[1]; public_key_path=argv[2];
 digest_rounds=5000;
 int result=init_keys(NULL);
 if (result || !mariamem_auth_keys_ready()) return 91;
 result=mariamem_auth_key_self_test();
 EVP_PKEY_free(private_key);
 return result;
}
'''
    source = tmp_path / 'auth.c'
    source.write_text(header + code + main)
    flags = []
    brew = Path('/opt/homebrew/opt/openssl@3')
    if brew.exists():
        flags = ['-I' + str(brew / 'include'), '-L' + str(brew / 'lib')]
    binary = tmp_path / 'auth'
    subprocess.run([cc, '-std=gnu11', '-Wno-deprecated-declarations', *flags,
                    str(source), '-lcrypto', '-o', str(binary)], check=True, capture_output=True)
    fixture = json.loads((ROOT / 'guest/test-auth-keypair.json').read_text())
    for kind in ('private', 'public'):
        der = tmp_path / (kind + '.der')
        der.write_bytes(base64.b64decode(fixture[kind + '_der_base64']))
        args = [openssl, 'pkey', '-inform', 'DER', '-in', str(der)]
        if kind == 'public':
            args += ['-pubin', '-pubout']
        subprocess.run([*args, '-out', str(tmp_path / (kind + '.pem'))], check=True, capture_output=True)
    private, public = tmp_path / 'private.pem', tmp_path / 'public.pem'
    def run():
        return subprocess.run([str(binary), str(private), str(public)], capture_output=True).returncode
    assert run() == 0  # correct, wrong-password and malformed-ciphertext paths
    private_contents, public_contents = private.read_bytes(), public.read_bytes()
    private.unlink()
    assert run() == 91
    private.write_text('corrupt private')
    assert run() == 91
    private.write_bytes(private_contents)
    public.write_text('corrupt public')
    assert run() == 91
    public.write_bytes(b'')
    assert run() == 91
    public.unlink()
    assert run() == 91
    public.write_bytes(b'x' * 1024)
    assert run() == 91
    public.write_bytes(public_contents)
    # A valid public key of another pair must not count as a successful load.
    other = tmp_path / 'other.pem'
    subprocess.run([openssl, 'genpkey', '-algorithm', 'RSA', '-pkeyopt',
                    'rsa_keygen_bits:2048', '-out', str(other)], check=True, capture_output=True)
    subprocess.run([openssl, 'pkey', '-in', str(other), '-pubout', '-out', str(public)],
                   check=True, capture_output=True)
    assert run() == 91
