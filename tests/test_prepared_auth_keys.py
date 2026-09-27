"""Public, deterministic key fixture and exclusive per-guest provisioning."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prepared_auth_keys import FIXTURE,key_material,write_header


def test_fixed_fixture_pair_valid_and_reproducible(tmp_path):
    openssl=shutil.which('openssl')
    if not openssl:pytest.skip('OpenSSL unavailable')
    keys=key_material()
    private=tmp_path/'private.pem';private.write_text(keys['private'])
    subprocess.run([openssl,'pkey','-in',str(private),'-check','-noout'],check=True)
    public=subprocess.check_output([openssl,'pkey','-in',str(private),'-pubout'],text=True)
    assert public==keys['public']
    assert '2048 bit' in subprocess.check_output([openssl,'pkey','-in',str(private),'-text','-noout'],text=True)
    source=tmp_path/'source';(source/'wasm').mkdir(parents=True)
    header=source/write_header(source);before=header.read_bytes();write_header(source)
    assert before==header.read_bytes() and b'PUBLIC NON-SECRET' in before
    bad=json.loads(FIXTURE.read_text());bad['private_der_sha256']='0'*64
    fixture=tmp_path/'bad.json';fixture.write_text(json.dumps(bad))
    with pytest.raises(ValueError,match='hash mismatch'):key_material(fixture)
    bad['test_only']=False;fixture.write_text(json.dumps(bad))
    with pytest.raises(ValueError,match='test-only'):key_material(fixture)


def test_provisioning_exclusive_and_missing_location(tmp_path):
    cc=shutil.which('cc')
    if not cc:pytest.skip('C compiler unavailable')
    source=tmp_path/'source';(source/'wasm').mkdir(parents=True);write_header(source)
    inc=(ROOT/'guest/prepared_auth_keys.inc').read_text().replace('"/mariamem-auth"','directory').replace('"/mariamem-auth/private.pem"','private_path').replace('"/mariamem-auth/public.pem"','public_path')
    (source/'wasm/provision.inc').write_text(inc)
    code=source/'test.c';code.write_text('''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#include <unistd.h>
static const char *directory,*private_path,*public_path;
#include "provision.inc"
int main(int argc,char **argv){directory=argv[1];private_path=argv[2];public_path=argv[3];return prepare_auth_keys() ? 1 : 0;}
''')
    binary=source/'test';subprocess.run([cc,'-I',str(source/'wasm'),str(code),'-o',str(binary)],check=True)
    target=tmp_path/'keys';args=[str(binary),str(target),str(target/'private.pem'),str(target/'public.pem')]
    subprocess.run(args,check=True)
    assert (target/'private.pem').read_text()==key_material()['private']
    assert (target/'public.pem').read_text()==key_material()['public']
    fail=subprocess.run(args,capture_output=True,text=True);assert fail.returncode==1 and 'matching native bundle' in fail.stderr
    missing=tmp_path/'missing'/'keys';assert subprocess.run([str(binary),str(missing),str(missing/'private.pem'),str(missing/'public.pem')],capture_output=True).returncode==1


def test_canonical_guest_options_preserve_auth_and_disable_generation():
    patch=(ROOT/'guest/source.patch').read_text()
    assert '--caching-sha2-password-auto-generate-rsa-keys=OFF' in patch
    assert '--caching-sha2-password-private-key-path=/mariamem-auth/private.pem' in patch
    resident=(ROOT/'guest/resident.inc').read_text()
    assert 'mariamem_auth_keys_ready()' in resident and 'mariamem_auth_key_self_test()' in resident
    # No restore-copy implementation or exploratory source staging is integrated.
    assert 'restore-source' not in resident and 'MARIAMEM_EXPERIMENT_AUTH' not in resident
